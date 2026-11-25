"""Excel proposals update retained database registers; exports are separate releases."""
import io,json
from datetime import date,datetime
from pathlib import PurePath
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Organization as O,member_and_not_walled
from kestrel.repositories.identity import principal
from kestrel.services import diligence as d,workflow as w
from kestrel.services.auth import clock
from kestrel.services.lifecycle import mutable
from kestrel.adapters.extraction import canonical,digest,office_guard
from kestrel.adapters.tracker_workbooks import build

HEADERS={'coverage':['RecordID','ExpectedRevision','Title','Counterparty','Scope','CoverageState'],
 'risk':['RecordID','ExpectedRevision','Severity','Materiality','Exposure','Status','Action','OwnerUPN','DueOn'],
 'consent':['RecordID','ExpectedRevision','Severity','Materiality','Exposure','Status','Action','OwnerUPN','DueOn']}


def kind(value):
    if value not in HEADERS:raise HTTPException(422,'Choose coverage, risk or consent')


def current(db,actor,matter,register,key):
    w.legal(actor,matter)
    if register=='coverage':
        source,policy=w.source(db,actor,key)
        if source.matter_id!=matter:raise HTTPException(403,'Record unavailable')
        record=d.latest_review(db,source.id)
        data={'RecordID':source.id,'ExpectedRevision':record.version_number if record else 0,'Title':record.title if record else source.file_name,
            'Counterparty':record.counterparty if record else '', 'Scope':record.scope if record else 'other','CoverageState':record.coverage_state if record else 'not_started'}
    else:
        row,policy=d.resolve(db,actor,key);source,source_policy=w.source(db,actor,row.source_id)
        if source.matter_id!=matter:raise HTTPException(403,'Record unavailable')
        if policy.review_state!='reviewed':raise HTTPException(409,'Lawyer-reviewed current finding required')
        item=d.output(db,row,policy)
        if register=='consent' and item['topic'] not in {'change_of_control','assignment','termination'}:raise HTTPException(422,'Finding is outside the consent register')
        data={'RecordID':key,'ExpectedRevision':item['revision'],'Severity':item['severity'],'Materiality':item['materiality'],'Exposure':item['exposure'],
            'Status':item['workflow_status'],'Action':item['action'],'OwnerUPN':item['owner'] or '', 'DueOn':item['due_on'] or ''}
    return source,policy,data


def normalized(db,actor,matter,register,values,rationale):
    source,policy,before=current(db,actor,matter,register,values['RecordID'])
    if type(values['ExpectedRevision']) is not int or values['ExpectedRevision']!=before['ExpectedRevision']:raise HTTPException(409,'Record revision changed; download a fresh template')
    from kestrel.api.diligence import Assessment,DocumentReview
    try:
        if register=='coverage':
            payload=DocumentReview(expected_revision=values['ExpectedRevision'],title=values['Title'],counterparty=values['Counterparty'],scope=values['Scope'],coverage_state=values['CoverageState'],rationale=rationale)
            if payload.coverage_state=='complete':
                w.require_verified_ocr(db,source)
                if not policy.classification_confirmed or source.extraction_status!='ready':raise HTTPException(409,'Confirmed extracted source required for completed coverage')
                if any(f['review_state']=='candidate' and f['source_id']==source.id for f in d.visible_findings(db,actor,matter,audited=False)):raise HTTPException(409,'Decide every candidate before completing coverage')
        else:
            row,_=d.resolve(db,actor,values['RecordID']);item=d.output(db,row,policy)
            owner=None
            if values['OwnerUPN']:
                owner=db.scalar(select(m.Account).where(m.Account.username==values['OwnerUPN'].strip().casefold()))
                if owner is None:raise HTTPException(422,'Owner must be an active cleared legal account')
                d.owner_allowed(db,actor,source.id,owner.id)
            payload=Assessment(source_id=source.id,expected_revision=before['ExpectedRevision'],decision='reviewed',summary=item['summary'],topic=item['topic'],severity=values['Severity'],materiality=values['Materiality'],exposure=values['Exposure'],workflow_status=values['Status'],action=values['Action'],owner_id=owner.id if owner else None,due_on=values['DueOn'] or None,rationale=rationale,evidence=[{'unit':e['unit'],'quote':e['quote'],'start':e['start']} for e in item['evidence']])
        if policy.signing_frozen or policy.superseded:raise HTTPException(409,'Current unfrozen record required')
    except ValidationError:raise HTTPException(422,'Invalid category, date or required field; see the template guide') from None
    fingerprint=digest(canonical({'revision':before['ExpectedRevision'],'policy':w.snapshot(db,policy),'source':w.snapshot(db,db.get(m.DocumentPolicyVersion,source.policy_id))}).encode())
    return payload,before,fingerprint,source,policy


def parse(data,register):
    if not data or len(data)>3*1024*1024:raise HTTPException(413,'Upload a nonempty XLSX of at most 3 MiB')
    office_guard(data,'xl/workbook.xml')
    from openpyxl import load_workbook
    try:
        book=load_workbook(io.BytesIO(data),read_only=False,data_only=False,keep_links=False)
        try:
            if 'Records' not in book.sheetnames or set(book.sheetnames)-{'Records','Guide'}:raise ValueError()
            for sheet in book:
                if sheet.sheet_state!='visible' or sheet.max_row>102 or sheet.max_column>16 or sheet.merged_cells.ranges:raise ValueError()
                if any(d.hidden for d in sheet.row_dimensions.values()) or any(d.hidden for d in sheet.column_dimensions.values()):raise ValueError()
                for row in sheet:
                    for cell in row:
                        if cell.data_type=='f' or cell.hyperlink is not None:raise ValueError()
            sheet=book['Records'];headers=[c.value for c in sheet[1]]
            if headers!=HEADERS[register]:raise HTTPException(422,'Columns must exactly match the selected register template')
            rows=[]
            for number,row in enumerate(sheet.iter_rows(min_row=2,values_only=True),2):
                if all(v is None or v=='' for v in row):continue
                values=[]
                for label,v in zip(headers,row):
                    if isinstance(v,(datetime,date)):v=v.date().isoformat() if isinstance(v,datetime) else v.isoformat()
                    if v is None:v=''
                    if label=='ExpectedRevision':
                        if isinstance(v,float) and v.is_integer():v=int(v)
                    elif not isinstance(v,str):raise ValueError()
                    if isinstance(v,str):
                        if len(v)>2000 or any(ord(c)<32 and c not in '\n\r\t' for c in v):raise ValueError()
                        if len(v)>1 and v[0]=="'" and v[1] in '=+-@':v=v[1:]
                    values.append(v)
                rows.append({'row_number':number,'values':dict(zip(headers,values))})
            if not rows or len(rows)>100:raise HTTPException(422,'Provide one to 100 nonblank proposal rows')
            return rows
        finally:book.close()
    except HTTPException:raise
    except Exception:raise HTTPException(422,'Use a visible, formula-free XLSX template without macros, links or hidden content') from None


def stage(db,actor,matter,register,name,data):
    kind(register);w.legal(actor,matter);mutable(db,matter)
    if PurePath(name).suffix.lower()!='.xlsx' or len(name)>160 or '/' in name or '\\' in name or any(ord(c)<32 for c in name):raise HTTPException(422,'A plain .xlsx file name is required')
    proposals=parse(data,register)
    keys=[r['values']['RecordID'] for r in proposals]
    for proposal in proposals:
        proposal['duplicate']=keys.count(proposal['values']['RecordID'])>1
        try:
            _,_,fingerprint,source,policy=normalized(db,actor,matter,register,proposal['values'],'Excel preview validation only')
            proposal['snapshot_hash']=fingerprint
            w.event(db,actor,policy,'tracker.import_preview',source.id)
        except HTTPException:proposal['snapshot_hash']=None
    row=m.TrackerImport(matter_id=matter,uploaded_by=actor.id,register=register,file_name=name,file_hash=digest(data),data=data,proposals_json=canonical(proposals),created_at=clock())
    db.add(row);db.flush();db.commit();return row


def read_import(db,actor,import_id):
    row=db.get(m.TrackerImport,import_id)
    if row is None or row.uploaded_by!=actor.id:raise HTTPException(404,'Import preview unavailable')
    w.legal(actor,row.matter_id)
    if digest(row.data)!=row.file_hash:raise HTTPException(409,'Import integrity check failed')
    return row


def preview(db,actor,row):
    row=read_import(db,actor,row.id);result=[]
    for item in json.loads(row.proposals_json):
        value={'row_number':item['row_number'],'status':'invalid','errors':[],'current':None,'proposed':None}
        try:
            # Authorize before showing any caller-supplied text or record ID again.
            _,_,before=current(db,actor,row.matter_id,row.register,item['values']['RecordID'])
            value.update(current=before,proposed=item['values'])
            source,policy,_=current(db,actor,row.matter_id,row.register,item['values']['RecordID'])
            w.event(db,actor,policy,'tracker.import_view',row.id)
            if item['duplicate']:raise HTTPException(422,'Duplicate RecordID in this workbook')
            _,_,fingerprint,source,policy=normalized(db,actor,row.matter_id,row.register,item['values'],'Excel preview validation only')
            if item['snapshot_hash'] is None or fingerprint!=item['snapshot_hash']:raise HTTPException(409,'Record or policy changed; upload a fresh preview')
            value['status']='valid' if any(before[k]!=item['values'][k] for k in HEADERS[row.register][2:]) else 'unchanged'
        except HTTPException as error:
            if error.status_code in {403,404}:value.update(current=None,proposed=None,errors=['Record unavailable for your current permissions'])
            else:value.update(status='conflict' if error.status_code==409 else 'invalid',errors=[error.detail])
        result.append(value)
    applied=db.scalar(select(m.TrackerImportApplication.id).where(m.TrackerImportApplication.import_id==row.id)) is not None
    return {'id':row.id,'matter_id':row.matter_id,'register':row.register,'file_name':row.file_name,'file_hash':row.file_hash,'applied':applied,'rows':result}


def apply(db,actor,import_id,payload):
    row=read_import(db,actor,import_id)
    row=db.scalar(select(m.TrackerImport).where(m.TrackerImport.id==row.id).with_for_update())
    mutable(db,row.matter_id)
    selection=sorted(payload.row_numbers)
    if len(selection)!=len(set(selection)):raise HTTPException(422,'Select each proposal row once')
    prior=db.scalar(select(m.TrackerImportApplication).where(m.TrackerImportApplication.import_id==row.id))
    if prior:
        if (prior.idempotency_key,prior.selection_json,prior.rationale)!=(payload.idempotency_key,canonical(selection),payload.rationale):raise HTTPException(409,'Import already applied with another selection or rationale')
        return {'id':row.id,'applied':True,'applied_rows':len(selection)}
    items={r['row_number']:r for r in json.loads(row.proposals_json)};checked=[]
    for number in selection:
        item=items.get(number)
        if not item or item['duplicate']:raise HTTPException(409,'Selected rows must be valid and unique')
        try:
            proposal,before,fingerprint,source,policy=normalized(db,actor,row.matter_id,row.register,item['values'],payload.rationale)
        except HTTPException as error:
            if error.status_code in {403,404}:raise HTTPException(403,'Selected record is no longer permitted') from None
            raise HTTPException(409,'Selected proposal is stale or invalid; upload a fresh preview') from None
        if not any(before[k]!=item['values'][k] for k in HEADERS[row.register][2:]):raise HTTPException(409,'Selected row is unchanged; no new version is required')
        if fingerprint!=item['snapshot_hash']:raise HTTPException(409,'Selected record or policy changed')
        checked.append((number,item,proposal,source.id))
    results=[]
    for number,item,proposal,source_id in checked:
        if row.register=='coverage':saved=d.save_document_review(db,actor,source_id,proposal,commit=False)
        else:saved=d.save_assessment(db,actor,proposal,item['values']['RecordID'],commit=False)
        source=db.get(m.SourceVersion,source_id)
        w.event(db,actor,db.get(m.DocumentPolicyVersion,source.policy_id),'tracker.import_apply',row.id)
        results.append({'row_number':number,'record_id':item['values']['RecordID'],'revision':saved['revision']})
    db.add(m.TrackerImportApplication(import_id=row.id,actor_id=actor.id,selection_json=canonical(selection),result_json=canonical(results),rationale=payload.rationale,idempotency_key=payload.idempotency_key,created_at=clock()))
    db.commit();return {'id':row.id,'applied':True,'applied_rows':len(selection)}


def template(db,actor,matter,register):
    kind(register);w.legal(actor,matter)
    if register=='coverage':keys=[s['id'] for s in w.source_list(db,actor,matter)]
    else:keys=[f['id'] for f in d.visible_findings(db,actor,matter,audited=False) if f['review_state']=='reviewed' and (register!='consent' or f['topic'] in {'change_of_control','assignment','termination'})]
    rows=[]
    for key in keys[:100]:
        source,policy,values=current(db,actor,matter,register,key);rows.append([values[k] for k in HEADERS[register]])
        w.event(db,actor,policy,'tracker.template',source.id)
    guide=[['Field','Instructions'],['Purpose','Synthetic internal proposals. Database records remain authoritative.'],['RecordID / ExpectedRevision','Keep identifiers and revision numbers unchanged. Download a fresh template before editing.'],['Apply','Upload, inspect the preview, select valid rows and attest that you reviewed every selected change.'],['Severity','critical, high, medium, low, information. Unassessed values must be assessed before applying.'],['Materiality','material, not_material, undetermined'],['Exposure','consent, notice, termination, none, unclear'],['Status','open, in_progress, resolved'],['OwnerUPN','Blank or an existing active legal account cleared for that source.'],['DueOn','Excel date or YYYY-MM-DD; blank clears the due date.'],['CoverageState','not_started, in_review, complete. Complete requires decided findings and verified source text.'],['Scope','customer, supplier, licence, corporate, employment, ip, real_estate, litigation, financial, other'],['Sharing','Use a separately approved recipient-specific export. Hidden sheets/rows are rejected.']]
    content=build({'sheets':[{'name':'Records','rows':[HEADERS[register],*rows],'editable':HEADERS[register][2:]},{'name':'Guide','rows':guide}]})
    db.commit();return content


def recipients(db,actor,matter,audience):
    w.legal(actor,matter);result=[]
    for account in db.scalars(select(m.Account).join(m.Organization,m.Account.organization_id==m.Organization.id).where(m.Organization.code==audience,m.Account.active.is_(True)).order_by(m.Account.username)):
        if member_and_not_walled(principal(db,account,clock()),matter):result.append({'upn':account.username,'name':account.display_name})
    return result


def create_export(db,actor,payload):
    kind(payload.register_kind);w.legal(actor,payload.matter_id);mutable(db,payload.matter_id)
    recipient=db.scalar(select(m.Account).where(m.Account.username==payload.recipient_upn.casefold()))
    if not recipient or recipient.username not in {r['upn'] for r in recipients(db,actor,payload.matter_id,payload.audience)}:raise HTTPException(403,'Active, assigned, unwalled recipient in the chosen audience required')
    if len(set(payload.record_ids))!=len(payload.record_ids):raise HTTPException(422,'Duplicate record selection')
    if set(payload.row_edits)-set(payload.record_ids):raise HTTPException(422,'Audience edits must belong to selected records')
    public_rows=[];policies=[];refs=[]
    for key in payload.record_ids:
        source,policy,values=current(db,actor,payload.matter_id,payload.register_kind,key)
        if any(p.superseded or p.signing_frozen for p in w.lineage(db,policy)):raise HTTPException(409,'Current unfrozen records required')
        if payload.audience=='castlegate' and any(p.classification=='privileged' or p.resource_type=='legal_advice' for p in w.lineage(db,policy)):raise HTTPException(403,'Bank privilege exclusion')
        if payload.register_kind=='coverage':
            review=d.latest_review(db,source.id)
            if not review or review.coverage_state!='complete' or policy.review_state!='reviewed':raise HTTPException(409,'Explicitly completed whole-document review required')
            if any(f['review_state']=='candidate' and f['source_id']==source.id for f in d.visible_findings(db,actor,payload.matter_id,audited=False)):raise HTTPException(409,'Outstanding source candidates require review first')
            public_rows.append({'Reference':source.logical_key+' v'+str(source.version_number),'Title':review.title,'Counterparty':review.counterparty,'Scope':review.scope,'Coverage':'complete'})
        else:
            row,_=d.resolve(db,actor,key);item=d.output(db,row,policy)
            reference=source.logical_key+' v'+str(source.version_number)+'; '+'; '.join(e['locator'] for e in item['evidence'])
            public_rows.append({'Reference':reference,'Summary':item['summary'],'Severity':item['severity'],'Materiality':item['materiality'],'Requirement':item['exposure'],'Action':item['action'] or 'Lawyer to confirm follow-up','Status':item['workflow_status'],'DueOn':item['due_on'] or ''})
            refs.append({'finding_id':key,'revision_id':row.id,'public_reference':reference})
        changes=payload.row_edits.get(key,{})
        allowed={'Title','Counterparty'} if payload.register_kind=='coverage' else {'Summary','Action'}
        if set(changes)-allowed or any(not isinstance(v,str) or not 1<=len(v.strip())<=2000 for v in changes.values()):raise HTTPException(422,'Audience edits may change only the permitted public text fields')
        public_rows[-1].update({k:v.strip() for k,v in changes.items()})
        policies.append(policy)
    validation=db.get(m.MatterValidation,payload.matter_id);client=db.get(m.Client,validation.client_id)
    client_matter=client.client_number+'-'+validation.matter_number
    metadata=[['Field','Value'],['ClientMatter',client_matter],['Title',payload.title],['Register',payload.register_kind],['Audience',payload.audience],['RecipientUPN',recipient.username],['Approval','Versioned snapshot. Current release status and revocation are recorded in the portal.']]
    headers=list(public_rows[0]);body={'client_matter_number':client_matter,'schema':'recipient-tracker-v1','title':payload.title,'register':payload.register_kind,'audience':payload.audience,'recipient_id':recipient.id,'recipient_upn':recipient.username,'rows':public_rows}
    content=build({'sheets':[{'name':'Tracker','rows':[headers,*[[r[h] for h in headers] for r in public_rows]]},{'name':'Package','rows':metadata}]})
    # Recheck source versions and recipient clearance after workbook generation.
    db.expire_all();fresh=principal(db,db.get(m.Account,actor.id),clock());w.legal(fresh,payload.matter_id)
    for key,old in zip(payload.record_ids,policies):
        _,policy,_=current(db,fresh,payload.matter_id,payload.register_kind,key)
        if policy.id!=old.id:raise HTTPException(409,'Record changed during generation; regenerate')
    if recipient.username not in {r['upn'] for r in recipients(db,fresh,payload.matter_id,payload.audience)}:raise HTTPException(403,'Recipient clearance changed')
    body['workbook_sha256']=digest(content)
    content_hash=digest(canonical(body).encode())
    policy=m.DocumentPolicyVersion(matter_id=payload.matter_id,document_id='recipient-tracker',source_hash=content_hash,resource_type='tracker',classification='ordinary',classification_confirmed=True,review_state='candidate',audience=payload.audience)
    db.add(policy);db.flush()
    for parent in policies:db.add(m.PolicySource(artifact_id=policy.id,source_id=parent.id))
    db.add(m.PolicyRecipient(policy_id=policy.id,account_id=recipient.id))
    release=m.ReleasePackage(policy_id=policy.id,created_by=actor.id,title=payload.title,summary='Versioned '+payload.register_kind+' tracker for '+payload.audience+'; recipient-specific workbook approval required.',references_json=canonical(refs),content_hash=content_hash,created_at=clock())
    db.add(release);db.flush()
    row=m.TrackerExport(release_id=release.id,register=payload.register_kind,body_json=canonical(body),data=content,bytes_hash=digest(content),created_at=clock())
    db.add(row);db.flush();w.event(db,fresh,policy,'tracker.export_draft',row.id);db.commit();return row


def read_export(db,actor,export_id):
    row=db.get(m.TrackerExport,export_id)
    if row is None:raise HTTPException(404,'Tracker export unavailable')
    release,policy=w.package(db,actor,row.release_id,internal=actor.org==O.FIRM)
    body=json.loads(row.body_json)
    if digest(row.data)!=row.bytes_hash or body.get('workbook_sha256')!=row.bytes_hash or digest(canonical(body).encode())!=release.content_hash:raise HTTPException(409,'Export integrity check failed')
    if set(db.scalars(select(m.PolicyRecipient.account_id).where(m.PolicyRecipient.policy_id==policy.id)))!={body['recipient_id']}:raise HTTPException(409,'Recipient scope integrity mismatch')
    return row,release,policy


def output_export(db,actor,row):
    row,release,policy=read_export(db,actor,row.id)
    body=json.loads(row.body_json)
    result={'id':row.id,'client_matter_number':body['client_matter_number'],'register':row.register,'title':body['title'],'audience':policy.audience,'recipient_upn':body['recipient_upn'],'released':policy.released,'release_id':release.id,'lineage_stale':any(p.superseded for p in w.lineage(db,policy)),'bytes_hash':row.bytes_hash,'rows':body['rows'],'created_at':row.created_at,'content_hash':release.content_hash}
    if actor.org==O.FIRM:result.update(snapshot_hash=w.snapshot(db,policy),created_by=release.created_by,clean_team_required=any(p.classification=='clean_team' for p in w.lineage(db,policy)),approvals=w.package_output(db,release,policy,True)['approvals'])
    return result
