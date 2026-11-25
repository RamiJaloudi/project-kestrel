import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel.models import ReportVersion,ReleasePackage,DocumentPolicyVersion as Policy,PolicySource
from kestrel.services import workflow as w,diligence
from kestrel.services.auth import clock
from kestrel.adapters.extraction import canonical,digest

def read(db,actor,report_id):
    row=db.get(ReportVersion,report_id)
    if row is None:raise HTTPException(404,'Report unavailable')
    release,policy=w.package(db,actor,row.release_id,internal=actor.org.value=='firm')
    body=json.loads(row.body_json)
    if digest(canonical(body).encode())!=release.content_hash:raise HTTPException(409,'Report integrity check failed')
    return row,release,policy

def output(db,row,release,policy,internal=True):
    result={'id':row.id,'report_key':row.report_key,'version':row.version_number,'created_at':row.created_at,'kind':row.kind,'body':json.loads(row.body_json),
        'audience':policy.audience,'released':policy.released,'release_id':release.id,'content_hash':release.content_hash}
    if internal:result.update(snapshot_hash=w.snapshot(db,policy),created_by=release.created_by,approvals=w.package_output(db,release,policy,True)['approvals'],
        lineage_stale=any(p.superseded for p in w.lineage(db,policy)),clean_team_required=any(p.classification=='clean_team' for p in w.lineage(db,policy)))
    if internal:
        from kestrel.models import LegalFindingRevision,SourceFinding
        result['citations']=[]
        result['section_findings']=[]
        result['previous_id']=row.previous_id
        for ref in json.loads(release.references_json):
            item=db.get(LegalFindingRevision,ref['revision_id']) or db.get(SourceFinding,ref['revision_id'])
            detail=diligence.output(db,item,db.get(Policy,item.policy_id))
            result['section_findings'].append({k:detail[k] for k in ['id','revision_id','revision','summary','source_id','file_name','version_number','topic','review_state']})
            span=json.loads(item.evidence_json)[0]
            result['citations'].append({'id':item.source_id,'historical':True,'unit':span['unit'],'start':span['start'],'end':span['end']})
    return result

def persist(db,actor,matter,audience,kind,body,refs,previous=None,*,commit=True):
    w.legal(actor,matter);policies=[]
    for ref in refs:
        row,policy=diligence.resolve(db,actor,ref['finding_id'])
        if row.id!=ref['revision_id'] or policy.matter_id!=matter or policy.review_state!='reviewed':raise HTTPException(409,'Reviewed finding version changed; regenerate the draft')
        lineage=w.lineage(db,policy)
        if any(p.signing_frozen or p.superseded for p in lineage):raise HTTPException(409,'Historical or frozen source cannot be used')
        if audience=='castlegate' and any(p.classification=='privileged' or p.resource_type=='legal_advice' for p in lineage):raise HTTPException(403,'Privileged material cannot be included in a bank report')
        policies.append(policy)
    hash_value=digest(canonical(body).encode())
    policy=Policy(matter_id=matter,document_id='report-package',source_hash=hash_value,resource_type='report',classification='ordinary',classification_confirmed=True,review_state='candidate',audience=audience)
    db.add(policy);db.flush()
    for source in policies:db.add(PolicySource(artifact_id=policy.id,source_id=source.id))
    release=ReleasePackage(policy_id=policy.id,created_by=actor.id,title=body['title'],summary=body['overview'][:6000],references_json=canonical(refs),content_hash=hash_value,created_at=clock())
    db.add(release);db.flush()
    report=ReportVersion(report_key=previous.report_key if previous else str(uuid4()),version_number=previous.version_number+1 if previous else 1,
        previous_id=previous.id if previous else None,release_id=release.id,kind=kind,body_json=canonical(body),created_at=clock())
    db.add(report);db.flush()
    from kestrel.services.finding_release_guard import denial
    if denial(db,policy):raise HTTPException(409,'Retained finding restrictions are not bound to this new report')
    from kestrel.services.checklist_records import snapshot_report
    snapshot_report(db,actor,report,refs,previous)
    if previous:
        from kestrel.services.ddr_runs import revised_report
        revised_report(db,actor,previous,report)
    w.event(db,actor,policy,'report.version',report.id)
    try:db.commit() if commit else db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent report edit; refresh latest version')
    return output(db,report,release,policy)

def generate(db,actor,payload):
    w.legal(actor,payload.matter_id);findings=[];refs=[]
    for key in payload.finding_ids:
        row,policy=diligence.resolve(db,actor,key)
        if policy.review_state!='reviewed':raise HTTPException(409,'Select reviewed findings only')
        item=diligence.output(db,row,policy);findings.append(item)
        refs.append({'finding_id':key,'revision_id':row.id,'public_reference':f"{item['logical_key']}, version {item['version_number']}; "+'; '.join(e['locator'] for e in item['evidence'])})
    sections=[];risks=[];consents=[]
    for i,item in enumerate(findings):
        label=refs[i]['public_reference']
        entry={'reference':label,'finding':item['summary'],'severity':item['severity'],'materiality':item['materiality'],'requirement':item['exposure'],
            'action':item['action'] or 'Lawyer to confirm follow-up action.','status':item['workflow_status'],'due_on':item['due_on'] or 'Unscheduled'}
        risks.append(entry)
        if item['topic'] in {'change_of_control','assignment','termination'}:consents.append(entry.copy())
        sections.append({'heading':item['topic'].replace('_',' ').capitalize(),'text':item['summary']+'\n\nNext action: '+entry['action'],'reference':label})
    body={'title':payload.title,'overview':f"{'Board briefing' if payload.kind=='board_pack' else 'Due diligence draft'} for {payload.audience.capitalize()}. This version assembles {len(findings)} lawyer-reviewed finding{'' if len(findings)==1 else 's'} for review and audience approval.",
        'coverage':f"This package covers {len(findings)} selected finding{'' if len(findings)==1 else 's'} from {len({f['source_id'] for f in findings})} contributing source version{'' if len({f['source_id'] for f in findings})==1 else 's'}. It does not establish complete diligence coverage. Documents arrive over six weeks; the board checkpoint is week five and signing is week ten. Unprocessed scans, later waves and matters outside this package require separate follow-up.",
        'sections':sections,'risks':risks,'consents':consents,'generator':'local-reviewed-findings-v1'}
    return persist(db,actor,payload.matter_id,payload.audience,payload.kind,body,refs)

def revise(db,actor,report_id,payload):
    old,release,policy=read(db,actor,report_id);w.legal(actor,policy.matter_id)
    if db.scalar(select(ReportVersion.id).where(ReportVersion.previous_id==old.id)):raise HTTPException(409,'A newer version exists; open it before editing')
    body=json.loads(old.body_json)
    if len(payload.sections)!=len(body['sections']):raise HTTPException(422,'Keep the source-linked section structure; regenerate to change findings')
    body.update(title=payload.title,overview=payload.overview,coverage=payload.coverage)
    body['sections']=[{**section,'heading':edit.heading,'text':edit.text} for section,edit in zip(body['sections'],payload.sections)]
    return persist(db,actor,policy.matter_id,policy.audience,old.kind,body,json.loads(release.references_json),old)
