"""Bounded CSV staging. Vendor values never confer access, approval or a reviewer decision."""
import csv,io,json,re
from pathlib import PurePosixPath
from fastapi import HTTPException
from sqlalchemy import select
from kestrel.models import VdrMappingProfile,VdrImportBatch,VdrImportRow,DocumentSource,SourceVersion,Matter
from kestrel.services import workflow as w
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest

# All Review Log columns are traced, including governed inputs not yet applied.
FIELDS={
 'doc_id':'Doc ID','vdr_index':'VDR Index #','folder_path':'VDR Folder Path','title':'Document Title',
 'doc_type':'Doc Type','workstream':'Workstream','counterparty':'Counterparty','doc_date':'Doc Date',
 'vdr_added_at':'Date Added to VDR','assigned_reviewer':'Assigned Reviewer','assigned_at':'Date Assigned',
 'review_status':'Review Status','reviewed_at':'Date Reviewed','days_open':'Days Open',
 'change_of_control':'Change of Control','anti_assignment':'Anti-Assignment','consent_notice':"Consent / Notice Req'd",
 'exclusivity_noncompete':'Exclusivity / Non-Compete','mfn':'MFN','termination_convenience':'Termination for Convenience',
 'expiry_renewal':'Expiry / Renewal Date','material':'Material?','risk_rating':'Risk Rating','summary':'Key Findings / Summary',
 'follow_up':'Follow-Up Req\'d?','request_ref':'Request List Ref','disclosure_ref':'Disclosure Schedule Ref',
 'qc_reviewer':'QC Reviewer','qc_status':'QC Status','comments':'Comments',
 'file_name':'File Name','source_external_id':'Source ID'}
REQUIRED={'source_external_id','vdr_index','folder_path','file_name'}


def writable(db,actor,matter):
    w.legal(actor,matter)
    db.scalar(select(Matter).where(Matter.id==matter).with_for_update())
    from kestrel.services.lifecycle import mutable
    mutable(db,matter)


def profile_output(row):
    return {'id':row.id,'name':row.name,'source_system':row.source_system,'version_number':row.version_number,
        'columns':json.loads(row.mapping_json),'delimiter':row.delimiter,'content_hash':row.content_hash}


def profiles(db,actor,matter):
    w.legal(actor,matter)
    return [profile_output(r) for r in db.scalars(select(VdrMappingProfile).where(VdrMappingProfile.matter_id==matter).order_by(VdrMappingProfile.created_at,VdrMappingProfile.version_number))]


def create_profile(db,actor,p):
    writable(db,actor,p.matter_id)
    if not set(p.columns)<=set(FIELDS) or not REQUIRED<=set(p.columns) or any(not v.strip() or len(v)>160 for v in p.columns.values()):
        raise HTTPException(422,'Map every required identity/file field to a CSV header; security fields are not importable')
    rows=list(db.scalars(select(VdrMappingProfile).where(VdrMappingProfile.matter_id==p.matter_id,VdrMappingProfile.name==p.name).order_by(VdrMappingProfile.version_number.desc())))
    encoded=canonical(p.columns);h=digest(canonical({'source':p.source_system,'columns':p.columns,'delimiter':p.delimiter}).encode())
    if rows and rows[0].content_hash==h:return profile_output(rows[0])
    version=rows[0].version_number if rows else 0
    if p.expected_previous_version!=version:raise HTTPException(409,'Mapping changed; refresh before creating a new version')
    row=VdrMappingProfile(matter_id=p.matter_id,name=p.name,source_system=p.source_system,version_number=version+1,
        mapping_json=encoded,delimiter=p.delimiter,author_id=actor.id,content_hash=h,created_at=clock())
    db.add(row);db.flush();audit(db,'vdr.mapping.create','allowed',actor.id,category='legal_sme',matter_id=p.matter_id,object_id=row.id);db.commit()
    return profile_output(row)


def parse(text,profile):
    if len(text.encode('utf-8'))>262144 or '\0' in text:raise HTTPException(413,'CSV exceeds safe staging limits')
    mapping=json.loads(profile.mapping_json)
    try:
        reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')),delimiter=profile.delimiter,strict=True)
        headers=reader.fieldnames or []
        if len(headers)>60 or len(headers)!=len(set(headers)) or not set(mapping.values())<=set(headers):raise HTTPException(422,'CSV headers must be unique and include every mapped column')
        result=[];seen=set()
        for index,raw in enumerate(reader,2):
            if index>101:raise HTTPException(413,'Stage at most 100 CSV rows per batch')
            errors=[]
            if None in raw or any(v is None or len(v)>2000 for v in raw.values()):
                errors.append('ROW_SHAPE_OR_VALUE_LIMIT')
            values={target:(raw.get(header) or '').strip() for target,header in mapping.items()}
            if any(not values.get(k) for k in REQUIRED):errors.append('MISSING_SOURCE_IDENTITY_OR_FILE')
            if any(len(values.get(k,''))>limit for k,limit in [('source_external_id',160),('vdr_index',160),('folder_path',1000),('file_name',160)]):errors.append('SOURCE_METADATA_LIMIT')
            path=values.get('file_name','').replace('\\','/')
            if not path or path.startswith('/') or ':' in path or '..' in PurePosixPath(path).parts or any(ord(c)<32 for c in path):errors.append('UNSAFE_FILE_NAME')
            identity=tuple(values.get(k,'') for k in ['source_external_id','vdr_index','folder_path'])
            if identity in seen:errors.append('DUPLICATE_SOURCE_IDENTITY_IN_BATCH')
            seen.add(identity)
            key=values.get('doc_id') or 'VDR_'+digest(canonical([profile.source_system,*identity]).encode())[:32]
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,96}',key):errors.append('INVALID_DOCUMENT_KEY')
            values['logical_key']=key
            result.append((index,raw,values,errors))
        if not result:raise HTTPException(422,'CSV has no data rows')
        return result
    except csv.Error:raise HTTPException(422,'Malformed CSV')


def batch_access(db,actor,batch):
    w.legal(actor,batch.matter_id)
    if batch.actor_id!=actor.id:raise HTTPException(403,'Staged metadata is restricted to its uploader')
    # Recheck current policy for every referenced existing version before returning even counts.
    rows=list(db.scalars(select(VdrImportRow).where(VdrImportRow.batch_id==batch.id).order_by(VdrImportRow.row_number)))
    for row in rows:
        key=json.loads(row.mapped_json).get('logical_key')
        for source in db.scalars(select(SourceVersion).where(SourceVersion.matter_id==batch.matter_id,SourceVersion.logical_key==key)):
            w.source(db,actor,source.id,historical=True)
    return rows


def get_batch(db,actor,batch_id):
    batch=db.get(VdrImportBatch,batch_id)
    if not batch:raise HTTPException(404,'Import batch unavailable')
    rows=batch_access(db,actor,batch)
    linked=[]
    for r in rows:
        refs=list(db.scalars(select(DocumentSource).where(DocumentSource.import_row_id==r.id)))
        linked.append({'id':r.id,'row_number':r.row_number,'mapped':json.loads(r.mapped_json),'errors':json.loads(r.errors_json),
            'state':'quarantined' if json.loads(r.errors_json) else 'linked' if refs else 'ready',
            'source_ids':[x.source_id for x in refs]})
    return {'id':batch.id,'profile_id':batch.profile_id,'wave':batch.wave,'csv_hash':batch.csv_hash,'rows':linked,
        'notice':'CSV metadata is staged, not approved. Reviewer assignments, risk answers, QC and comments are retained proposals only. Classification and audience release use their existing approval workflows.'}


def stage(db,actor,p):
    profile=db.get(VdrMappingProfile,p.profile_id)
    if not profile:raise HTTPException(404,'Mapping unavailable')
    writable(db,actor,profile.matter_id)
    if not p.synthetic or '/' in p.file_name or '\\' in p.file_name or not p.file_name.lower().endswith('.csv'):raise HTTPException(422,'Choose a synthetic CSV file')
    h=digest(canonical(p.model_dump()).encode())
    old=db.scalar(select(VdrImportBatch).where(VdrImportBatch.actor_id==actor.id,VdrImportBatch.request_key==p.request_key))
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Import request key reused with changed content')
        return get_batch(db,actor,old.id)
    parsed=parse(p.csv_text,profile)
    # An importer may not stage a CSV identifying a source they cannot currently access.
    for _,_,values,_ in parsed:
        for source in db.scalars(select(SourceVersion).where(SourceVersion.matter_id==profile.matter_id,SourceVersion.logical_key==values['logical_key'])):
            w.source(db,actor,source.id,historical=True)
    batch=VdrImportBatch(matter_id=profile.matter_id,profile_id=profile.id,actor_id=actor.id,request_key=p.request_key,input_hash=h,
        csv_hash=digest(p.csv_text.encode()),raw_csv=p.csv_text,file_name=p.file_name,wave=p.wave,created_at=clock())
    db.add(batch);db.flush()
    for index,raw,values,errors in parsed:
        encoded=canonical(raw)
        db.add(VdrImportRow(batch_id=batch.id,row_number=index,raw_json=encoded,mapped_json=canonical(values),errors_json=canonical(errors),row_hash=digest(encoded.encode())))
    db.flush();audit(db,'vdr.batch.stage','allowed',actor.id,category='legal_sme',matter_id=batch.matter_id,object_id=batch.id)
    result=get_batch(db,actor,batch.id);db.commit();return result


def upload_context(db,actor,meta):
    rid=getattr(meta,'import_row_id',None)
    if not rid:return None
    row=db.get(VdrImportRow,rid)
    if not row:raise HTTPException(404,'Import row unavailable')
    batch=db.get(VdrImportBatch,row.batch_id);batch_access(db,actor,batch)
    values=json.loads(row.mapped_json)
    if json.loads(row.errors_json):raise HTTPException(409,'Quarantined import row cannot ingest a document')
    if batch.matter_id!=meta.matter_id or values['logical_key']!=meta.logical_key or batch.wave!=meta.wave or PurePosixPath(values['file_name'].replace('\\','/')).name!=meta.file_name:
        raise HTTPException(409,'File, matter, document key or wave does not match staged metadata')
    return row,batch,db.get(VdrMappingProfile,batch.profile_id),values


def record_source(db,actor,context,row,doc):
    if context is None:return
    imported,batch,profile,v=context
    if db.scalar(select(DocumentSource.id).where(DocumentSource.import_row_id==imported.id,DocumentSource.source_id==row.id)):return
    db.add(DocumentSource(matter_id=row.matter_id,document_id=doc.id,source_id=row.id,import_row_id=imported.id,
        source_system=profile.source_system,source_external_id=v['source_external_id'],vdr_index_number=v['vdr_index'],folder_path=v['folder_path'],created_at=clock()))
    w.event(db,actor,db.get(w.Policy,row.policy_id),'vdr.source.link',row.id)
