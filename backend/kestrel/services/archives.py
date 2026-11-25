import io,json,zipfile
from fastapi import HTTPException
from sqlalchemy import select
from kestrel.models import SourceArchive,SourceVersion
from kestrel.services import workflow as w
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest
from kestrel.adapters import archive_store

def allowed(db,actor,row):
    w.legal(actor,row.matter_id)
    if row.created_by!=actor.id:raise HTTPException(403,'Archive creator access only; no administrator override')
    manifest=json.loads(row.manifest_json)
    for item in manifest['sources']:
        source,_=w.source(db,actor,item['id'],historical=True)
        if source.matter_id!=row.matter_id:raise HTTPException(403,'Archive lineage invalid')
    return manifest

def output(row):
    return {'id':row.id,'created_at':row.created_at,'content_hash':row.content_hash,'source_count':len(json.loads(row.manifest_json)['sources']),'storage':'Windows CurrentUser DPAPI, append-only creation','worm':False,'portable':False}

def create(db,actor,matter,require_worm=False):
    w.legal(actor,matter)
    sources=list(db.scalars(select(SourceVersion).where(SourceVersion.matter_id==matter).order_by(SourceVersion.id)))
    if not sources or len(sources)>1000:raise HTTPException(413,'Local source archive requires 1–1000 versions')
    manifest={'schema':'kestrel-source-archive-1','matter_id':matter,'sources':[],'scope':'Immutable source bytes and extracted units; not a PostgreSQL backup or complete matter-record restore','worm':False}
    stream=io.BytesIO();total=0
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as output:
        for source in sources:
            source,policy=w.source(db,actor,source.id,historical=True);w.source_integrity(source,policy)
            units=source.units_json.encode();total+=len(source.data)+len(units)
            if total>archive_store.MAX_BYTES-1024*1024:raise HTTPException(413,'Source archive exceeds bounded local limit')
            entry={'id':source.id,'logical_key':source.logical_key,'version':source.version_number,'bytes_hash':source.bytes_hash,'text_hash':source.text_hash,'file_name':source.file_name}
            manifest['sources'].append(entry);output.writestr(source.id+'.bin',source.data);output.writestr(source.id+'.json',units)
        output.writestr('manifest.json',canonical(manifest))
    for source in sources:
        _,policy=w.source(db,actor,source.id,historical=True);w.event(db,actor,policy,'source.archive',source.id)
    key,protected_hash,content_hash=archive_store.put(stream.getvalue(),require_worm=require_worm)
    row=SourceArchive(matter_id=matter,created_by=actor.id,storage_key=key,protected_hash=protected_hash,content_hash=content_hash,manifest_json=canonical(manifest),created_at=clock());db.add(row);db.flush()
    # Creation is not success until every source is reconstructed and verified.
    verify_content(archive_store.get(key,protected_hash,content_hash),manifest)
    audit(db,'archive.create','verified_source_roundtrip',actor.id,category='legal_sme',matter_id=matter,object_id=row.id);db.commit();return output_row(row)

def output_row(row):return output(row)

def verify_content(content,manifest):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries=archive.infolist()
            if sum(item.file_size for item in entries)>archive_store.MAX_BYTES or len(entries)!=len(manifest['sources'])*2+1:raise ValueError()
            if archive.read('manifest.json').decode()!=canonical(manifest):raise ValueError()
            for source in manifest['sources']:
                data=archive.read(source['id']+'.bin');units=json.loads(archive.read(source['id']+'.json'))
                if digest(data)!=source['bytes_hash'] or digest(canonical(units).encode())!=source['text_hash']:raise ValueError()
    except (ValueError,KeyError,zipfile.BadZipFile):raise HTTPException(409,'Source recovery verification failed')
    return {'verified':True,'reconstructed_source_versions':len(manifest['sources']),'database_restore_verified':False,'worm':False}
