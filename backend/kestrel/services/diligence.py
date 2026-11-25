"""Lawyer-owned, append-only diligence assessments and permission-filtered board registers."""
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel.models import (SourceFinding,LegalFindingRevision as Revision,DocumentReviewVersion as Review,
    DocumentPolicyVersion as Policy,PolicySource,SourceVersion,FindingReview,AnalysisJob,Account)
from kestrel.services import workflow as w
from kestrel.services.auth import clock
from kestrel.repositories.identity import principal
from kestrel.adapters.extraction import canonical,digest

TOPICS={'COC':'change_of_control','CONSENT':'assignment','ASSIGNMENT':'assignment','PRICING':'other','EXCLUSIVITY':'exclusivity','NON_COMPETE':'non_compete','TERMINATION':'termination','LIABILITY_CAP':'liability_cap','GOVERNING_LAW':'governing_law','DATA_PROTECTION':'data_protection'}

def latest(db,key):
    return db.scalar(select(Revision).where(Revision.record_key==key).order_by(Revision.version_number.desc()).limit(1))

def resolve(db,actor,key,historical=False):
    from kestrel.services.finding_tables import authorize_chain
    scope=authorize_chain(db,actor,key,historical)
    return scope.row,scope.policy

def output(db,row,policy):
    revision=isinstance(row,Revision);candidate=db.get(SourceFinding,row.candidate_id) if revision and row.candidate_id else row if not revision else None
    source=db.get(SourceVersion,row.source_id)
    old_review=db.scalar(select(FindingReview).where(FindingReview.finding_id==candidate.id)) if candidate else None
    result={'id':row.record_key if revision else row.id,'revision':row.version_number if revision else 0,'revision_id':row.id,
        'source_id':source.id,'file_name':source.file_name,'version_number':source.version_number,'logical_key':source.logical_key,
        'rule_id':candidate.rule_id if candidate else 'MANUAL','summary':row.summary,'original_summary':candidate.summary if candidate else None,
        'origin':'ai_candidate' if candidate else 'lawyer','evidence':json.loads(row.evidence_json),
        'playbook_id':candidate.playbook_id if candidate else None,'playbook_hash':candidate.playbook_hash if candidate else None,
        'model_config':candidate.model_config if candidate else 'human-authored','taxonomy_version':candidate.taxonomy_version if candidate else 'lawyer-assessment-v1',
        'review_state':policy.review_state,'classification':policy.classification,'reviewer_id':row.reviewer_id if revision else old_review.reviewer_id if old_review else None,
        'topic':row.topic if revision else TOPICS.get(row.rule_id,'other'),'severity':row.severity if revision else 'unassessed',
        'materiality':row.materiality if revision else 'unassessed','exposure':row.exposure if revision else 'unclear',
        'workflow_status':row.workflow_status if revision else 'open','action':row.action if revision else '',
        'owner_id':row.owner_id if revision else None,'due_on':row.due_on if revision else None,
        'rationale':row.rationale if revision else old_review.rationale if old_review else '', 'created_at':row.created_at}
    from kestrel.services.finding_tables import eligible_person
    owner=eligible_person(db,result['owner_id'],result['id'],historical=True)
    result['owner']=owner['username'] if owner else None
    if not owner:result['owner_id']=None
    if result['reviewer_id'] and eligible_person(db,result['reviewer_id'],result['id'],historical=True) is None:result['reviewer_id']=None
    result['ai_contexts']=[]
    if candidate:
        job=db.get(AnalysisJob,candidate.job_id)
        if job and job.document_version_id==candidate.source_id and job.result_json:
            data=json.loads(job.result_json);result['ai_contexts']=next((f.get('contexts',[]) for f in data.get('findings',[]) if f['rule_id']==candidate.rule_id),[])
    return result

def visible_findings(db,actor,matter,historical=False,audited=True):
    w.legal(actor,matter)
    keys=list(db.scalars(select(SourceFinding.id).join(SourceVersion,SourceFinding.source_id==SourceVersion.id).where(SourceVersion.matter_id==matter)))
    keys+=list(db.scalars(select(Revision.record_key).join(SourceVersion,Revision.source_id==SourceVersion.id).where(SourceVersion.matter_id==matter,Revision.candidate_id.is_(None)).distinct()))
    rows=[]
    for key in keys:
        try:
            row,policy=resolve(db,actor,key,historical);rows.append(output(db,row,policy))
            if audited:
                from kestrel.services.finding_tables import authorize_chain,event
                event(db,actor,authorize_chain(db,actor,key,historical),'finding.view')
        except HTTPException as error:
            if error.status_code!=403:raise
    return rows

def owner_allowed(db,actor,source_id,owner_id,key=None):
    if not owner_id:return
    account=db.get(Account,owner_id)
    if not account or not account.active:raise HTTPException(422,'Active, cleared matter owner required')
    owner=principal(db,account,clock())
    try:w.legal(owner,db.get(SourceVersion,source_id).matter_id);w.source(db,owner,source_id)
    except HTTPException:raise HTTPException(422,'Owner must have current source access')
    if key:
        from kestrel.services.finding_tables import authorize_chain
        try:authorize_chain(db,owner,key)
        except HTTPException:raise HTTPException(422,'Owner must clear the complete retained finding scope') from None

def evidence(row,items):
    units={u['number']:u for u in json.loads(row.units_json)};result=[]
    for item in items:
        unit=units.get(item.unit)
        if not unit or not item.quote:raise HTTPException(422,'Evidence unit and exact quote required')
        start=item.start
        if start is None:
            start=unit['text'].find(item.quote)
            if start>=0 and unit['text'].find(item.quote,start+1)>=0:raise HTTPException(422,'Ambiguous quote; provide a longer passage or exact offset')
        end=start+len(item.quote)
        if start<0 or unit['text'][start:end]!=item.quote:raise HTTPException(422,'Quote does not match the original source')
        result.append({'unit':item.unit,'locator':unit['locator'],'start':start,'end':end,'quote':item.quote})
    return result

def save_assessment(db,actor,payload,key=None,*,commit=True):
    source,source_policy=w.source(db,actor,payload.source_id,lock=True);w.legal(actor,source.matter_id)
    w.source_integrity(source,source_policy);w.require_verified_ocr(db,source)
    if not source_policy.classification_confirmed or source_policy.signing_frozen or source_policy.superseded:raise HTTPException(409,'Confirmed current unfrozen source required')
    old=None;candidate=None
    if key:
        old,old_policy=resolve(db,actor,key)
        if old.source_id!=source.id:raise HTTPException(409,'Finding belongs to a different source version')
        candidate=db.get(SourceFinding,old.candidate_id) if isinstance(old,Revision) and old.candidate_id else old if isinstance(old,SourceFinding) else None
    else:key=str(uuid4())
    prior=old if isinstance(old,Revision) else None
    if payload.expected_revision!=(prior.version_number if prior else 0):raise HTTPException(409,'Finding changed; refresh the current revision')
    owner_allowed(db,actor,source.id,payload.owner_id,key if old else None)
    spans=evidence(source,payload.evidence)
    value=payload.model_dump(mode='json');value['evidence']=spans
    policy=Policy(matter_id=source.matter_id,document_id=source.logical_key,source_hash=digest(canonical(value).encode()),resource_type='finding',
        classification=source_policy.classification,classification_confirmed=True,review_state=payload.decision,
        clean_team_scope=source_policy.clean_team_scope,ai_restricted=source_policy.ai_restricted)
    db.add(policy);db.flush();db.add(PolicySource(artifact_id=policy.id,source_id=source_policy.id))
    row=Revision(record_key=key,version_number=(prior.version_number if prior else 0)+1,previous_id=prior.id if prior else None,
        candidate_id=candidate.id if candidate else None,source_id=source.id,policy_id=policy.id,
        **{k:getattr(payload,k) for k in ['summary','topic','severity','materiality','exposure','workflow_status','action','owner_id','decision','rationale']},
        due_on=payload.due_on.isoformat() if payload.due_on else None,evidence_json=canonical(spans),reviewer_id=actor.id,created_at=clock())
    db.add(row)
    if old:db.get(Policy,old.policy_id).superseded=True
    if payload.decision=='reviewed':source_policy.review_state='reviewed'
    w.event(db,actor,policy,'finding.correct' if old else 'finding.manual',key)
    try:db.commit() if commit else db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent review decision; refresh')
    return output(db,row,policy)

def history(db,actor,key,*,audited=True):
    current,policy=resolve(db,actor,key,historical=True)
    if audited:
        from kestrel.services.finding_tables import authorize_chain,event
        event(db,actor,authorize_chain(db,actor,key,True),'finding.history')
    candidate_id=current.candidate_id if isinstance(current,Revision) else current.id
    rows=[]
    if candidate_id:
        candidate=db.get(SourceFinding,candidate_id);original=output(db,candidate,db.get(Policy,candidate.policy_id));original['historical']=True;rows.append(original)
    for item in db.scalars(select(Revision).where(Revision.record_key==key).order_by(Revision.version_number)):
        data=output(db,item,db.get(Policy,item.policy_id));data['historical']=item.id!=current.id;rows.append(data)
    return rows

def latest_review(db,source_id):
    return db.scalar(select(Review).where(Review.source_id==source_id).order_by(Review.version_number.desc()).limit(1))

def save_document_review(db,actor,source_id,payload,*,commit=True):
    source,policy=w.source(db,actor,source_id,lock=True);w.legal(actor,source.matter_id)
    from kestrel.services.finding_tables import owner_scopes
    owner_scopes(db,actor,source_id)
    if policy.signing_frozen or policy.superseded:raise HTTPException(409,'Current unfrozen document required')
    old=latest_review(db,source_id)
    if payload.expected_revision!=(old.version_number if old else 0):raise HTTPException(409,'Document review changed; refresh')
    if payload.coverage_state=='complete':
        w.require_verified_ocr(db,source)
        if not policy.classification_confirmed or source.extraction_status!='ready':raise HTTPException(409,'Confirmed text-ready source required for completed review')
        if any(f['review_state']=='candidate' for f in visible_findings(db,actor,source.matter_id,audited=False) if f['source_id']==source.id):raise HTTPException(409,'Decide all candidates before completing document review')
        policy.review_state='reviewed'
    row=Review(source_id=source.id,version_number=(old.version_number if old else 0)+1,previous_id=old.id if old else None,
        **{k:getattr(payload,k) for k in ['title','counterparty','scope','coverage_state','rationale']},reviewer_id=actor.id,created_at=clock())
    db.add(row);w.event(db,actor,policy,'document.review',source.id)
    try:db.commit() if commit else db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent document review; refresh')
    return {'revision':row.version_number}

def board(db,actor,matter,*,audited=True):
    w.legal(actor,matter)
    sources=w.source_list(db,actor,matter);findings=visible_findings(db,actor,matter,audited=audited)
    risks=[f for f in findings if f['review_state']=='reviewed']
    contracts=[];profiles={}
    jobs=list(db.scalars(select(AnalysisJob).where(AnalysisJob.matter_id==matter).order_by(AnalysisJob.created_at.desc(),AnalysisJob.id.desc())))
    pending_sources={f['source_id'] for f in findings if f['review_state']=='candidate'}
    for s in sources:
        from kestrel.services.finding_tables import sanitized_metadata
        s.update(sanitized_metadata(db,actor,db.get(SourceVersion,s['id'])))
        profiles[s['id']]=s['document_review']['metadata_withheld']
        source_findings=[f for f in findings if f['source_id']==s['id']]
        s['finding_progress']={'total':len(source_findings),'pending':sum(f['review_state']=='candidate' for f in source_findings),
            'reviewed':sum(f['review_state']=='reviewed' for f in source_findings),'rejected':sum(f['review_state']=='rejected' for f in source_findings)}
        if s['resource_type'] in {'contract','licence'}:
            contracts.append({**s,'title':s['file_name'],'counterparty':'',
                'scope':'other','coverage_state':s['document_review']['coverage_state'],'review_revision':s['document_review']['revision'],
                'findings':[f for f in findings if f['source_id']==s['id']]})
    visible_ids={s['id'] for s in sources};analyzed={j.document_version_id for j in jobs if j.state=='succeeded'}&visible_ids
    metrics={'received':len(sources),'text_ready':sum(s['extraction_status']=='ready' for s in sources),
        'ocr_pending':sum(s['extraction_status']!='ready' for s in sources),'analyzed':None if any(s['analysis']['metadata_withheld'] for s in sources) else 0,
        'fully_reviewed':None if any(profiles.values()) else 0,
        'candidate_findings':sum(f['review_state']=='candidate' for f in findings),
        'unassessed_findings':sum(f['review_state']!='rejected' and f['severity']=='unassessed' for f in findings),
        'material_open_risks':sum(f['materiality']=='material' and f['severity'] in {'critical','high'} and f['workflow_status']!='resolved' for f in risks)}
    consents=[f for f in risks if f['topic'] in {'change_of_control','assignment','termination'}]
    waves=[{'wave':wave,'received':sum(s['wave']==wave for s in sources)} for wave in ['wave1','wave2','manual']]
    rank={'critical':0,'high':1,'medium':2,'low':3,'information':4,'unassessed':5}
    risks.sort(key=lambda f:(f['workflow_status']=='resolved',rank.get(f['severity'],5),f['file_name']))
    return {'scope':'Current documents visible to your account; restricted sources are excluded.','metrics':metrics,
        'review_metrics_withheld':any(profiles.values()),'analysis_metrics_withheld':any(s['analysis']['metadata_withheld'] for s in sources),
        'metadata_notice':'Prior document-review text and analysis coverage have no retained historical handling receipt. They and their aggregate counts are withheld; defaults create a new review and do not describe prior human activity.',
        'milestones':{'board_week':5,'signing_week':10,'delivery_weeks':6,'end_state_document_target':12000,'end_state_page_target':400000},
        'waves':waves,'contracts':contracts,'findings':findings,'risks':risks,'consents':consents,'sources':sources}
