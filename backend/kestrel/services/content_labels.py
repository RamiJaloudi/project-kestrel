"""Immutable multi-label assertions. Proposals/contests never relax source access."""
import json
from sqlalchemy import select
from fastapi import HTTPException
from kestrel import models as m
from kestrel.domain import Role as R,Organization as O
from kestrel.repositories.identity import clean_scope
from kestrel.services import review_work as rw,workflow as w
from kestrel.services.auth import clock
from kestrel.adapters.extraction import canonical,digest
LABELS={'legal','financial','mixed','commercial','corporate','operational','privileged','clean_team','competitively_sensitive','personal_data','export_controlled','ai_restricted','bank_eligible'}
RESTRICTED={'privileged','clean_team','competitively_sensitive','personal_data','export_controlled','ai_restricted'}
CONTENT=['source_id','matter_id','version_number','labels_json','label_scope','unit_number','start_offset','end_offset','evidence_hash','source_bytes_hash','source_text_hash','provenance_kind','classifier_version','confidence','rationale','created_by','created_at','retained_classification','retained_scope']


def content(row):return {k:getattr(row,k) for k in CONTENT}


def rows(db,sid):
    result=list(db.scalars(select(m.ContentLabelAssertion).where(m.ContentLabelAssertion.source_id==sid).order_by(m.ContentLabelAssertion.version_number).limit(201)))
    if len(result)>200:raise ValueError('Content label limit exceeded')
    return result


def decisions(db,row):return list(db.scalars(select(m.ContentLabelDecision).where(m.ContentLabelDecision.assertion_id==row.id).order_by(m.ContentLabelDecision.sequence)))


def checked(db,row):
    if digest(canonical(content(row)).encode())!=row.content_hash:raise ValueError('Attribute integrity mismatch')
    labels=json.loads(row.labels_json)
    if not isinstance(labels,list) or not labels or not set(labels)<=LABELS:raise ValueError('Unknown attribute')
    if bool(set(labels)&{'clean_team','competitively_sensitive'})!=bool(row.label_scope):raise ValueError('Missing sensitive scope')
    history=decisions(db,row)
    for i,d in enumerate(history,1):
        if d.sequence!=i or d.operation not in {'confirm','contest'} or d.content_hash!=row.content_hash:raise ValueError('Unknown attribute state')
    return labels,history


def revision(db,sid):return sum(1+len(decisions(db,row)) for row in rows(db,sid))


def policy_records(db,pid):
    sid=db.scalar(select(m.SourceVersion.id).where(m.SourceVersion.policy_id==pid))
    if not sid:return []
    result=[]
    for row in rows(db,sid):
        labels,history=checked(db,row)
        result.append({'id':row.id,'hash':row.content_hash,'labels':labels,'scope':row.label_scope,'decisions':[{'id':d.id,'operation':d.operation,'actor_id':d.actor_id,'at':d.occurred_at} for d in history]})
    return result


def guard(db,actor,item,action,now):
    try:records=policy_records(db,item.id)
    except (ValueError,TypeError,KeyError):return 'CONTENT_ATTRIBUTES_INDETERMINATE'
    for row in records:
        labels=set(row['labels'])
        if action=='analyze' and labels&{'ai_restricted','personal_data','export_controlled'}:return 'CONTENT_AI_RESTRICTED'
        if labels&{'clean_team','competitively_sensitive'} and (not row['scope'] or not clean_scope(db,actor.id,item.matter_id,row['scope'],now)):return 'CONTENT_CLEAN_TEAM_REQUIRED'
        if actor.org!=O.FIRM and labels&RESTRICTED:return 'CONTENT_RESTRICTED_RELEASE_REQUIRED'
    return None


def output(db,actor,row,src):
    rw.retained(db,actor,row);labels,history=checked(db,row)
    # Captured label scopes AND current source policy apply, even during a contest.
    if row.label_scope and not clean_scope(db,actor.id,row.matter_id,row.label_scope,clock()):raise HTTPException(403,'Content scope denied')
    unit=next((u for u in json.loads(src.units_json) if u['number']==row.unit_number),None)
    quote=unit['text'][row.start_offset:row.end_offset] if unit else None
    if unit and digest(quote.encode())!=row.evidence_hash:raise HTTPException(409,'Attribute evidence mismatch')
    return {'id':row.id,'version':row.version_number,'state':'CONFIRMED' if history and history[-1].operation=='confirm' else 'CONTESTED' if history else 'PROPOSED',
        'labels':labels,'clean_team_scope':row.label_scope,'unit_number':row.unit_number,'start':row.start_offset,'end':row.end_offset,'locator':unit['locator'] if unit else 'Whole document',
        'quote':quote,'created_by':row.created_by,'created_at':row.created_at,'content_hash':row.content_hash,'rationale':row.rationale,'provenance':row.provenance_kind,
        'classifier_version':row.classifier_version,'confidence':row.confidence,'source_bytes_hash':row.source_bytes_hash,'source_text_hash':row.source_text_hash,
        'decisions':[{'operation':d.operation,'actor_id':d.actor_id,'rationale':d.rationale,'occurred_at':d.occurred_at} for d in history]}


def listing(db,actor,sid):
    src,policy=rw.source(db,actor,sid)
    value={'source_id':sid,'actor_id':actor.id,'can_confirm':R.SME in actor.roles,'revision':revision(db,sid),'assertions':[output(db,actor,r,src) for r in rows(db,sid)],
        'notice':'Proposed and contested restrictions apply to the whole original and its lineage. Bank eligible is descriptive, never an entitlement. Restriction removal and sanitized derivative release are unavailable in this increment.'}
    w.event(db,actor,policy,'content.labels.view',src.id);db.commit();return value


def impacts(db,actor,matter):
    rw.internal(actor);w.legal(actor,matter);result=[]
    for row in db.scalars(select(m.ContentLabelImpact).where(m.ContentLabelImpact.matter_id==matter).order_by(m.ContentLabelImpact.created_at.desc()).limit(500)):
        try:
            rw.retained(db,actor,row);src,_=rw.source(db,actor,row.source_id)
            routing=db.scalar(select(m.ContentImpactTask).where(m.ContentImpactTask.impact_id==row.id))
            task_state=rw.events(db,db.get(m.ReviewTask,routing.task_id))[-1].to_state if routing else 'unassigned'
            result.append({'task_id':routing.task_id if routing else None,'task_state':task_state,'id':row.id,'source_id':row.source_id,'policy_id':row.policy_id,'kind':row.kind,'created_at':row.created_at,'state':'counsel_review_required'})
        except HTTPException as e:
            if e.status_code!=403:raise
    return result


def propose(db,actor,sid,p):
    src,policy=rw.source(db,actor,sid,True)
    fingerprint=digest(canonical({'source':sid,'payload':p.model_dump()}).encode())
    old=db.scalar(select(m.ContentLabelAssertion).where(m.ContentLabelAssertion.created_by==actor.id,m.ContentLabelAssertion.request_key==p.request_key))
    if old:
        if old.input_hash!=fingerprint:raise HTTPException(409,'Attribute request key changed')
        return output(db,actor,old,src)
    if p.expected_revision!=revision(db,sid):raise HTTPException(409,'Attribute revision changed; refresh')
    prior=rows(db,sid)
    if len(prior)>=200:raise HTTPException(413,'Local attribute history limit reached')
    if p.clean_team_scope and not clean_scope(db,actor.id,src.matter_id,p.clean_team_scope,clock()):raise HTTPException(403,'Active named clean-team scope required')
    quote=None
    if p.unit_number is not None:
        unit=next((u for u in json.loads(src.units_json) if u['number']==p.unit_number),None)
        if not unit or p.end>len(unit['text']):raise HTTPException(422,'Exact existing source evidence range required')
        quote=unit['text'][p.start:p.end]
    row=m.ContentLabelAssertion(**rw.capture(src,policy),version_number=len(prior)+1,labels_json=canonical(sorted(p.labels)),label_scope=p.clean_team_scope,unit_number=p.unit_number,
        start_offset=p.start,end_offset=p.end,evidence_hash=digest(quote.encode()) if quote is not None else src.text_hash,source_bytes_hash=src.bytes_hash,source_text_hash=src.text_hash,
        provenance_kind='human',classifier_version='human-assertion-v1',confidence=None,rationale=p.rationale,created_by=actor.id,request_key=p.request_key,input_hash=fingerprint,created_at=clock())
    row.content_hash=digest(canonical(content(row)).encode());db.add(row);db.flush()
    # Retain a durable counsel-review impact for each already released descendant.
    for artifact in db.scalars(select(m.DocumentPolicyVersion).where(m.DocumentPolicyVersion.matter_id==src.matter_id,m.DocumentPolicyVersion.released==True)):
        if any(item.id==policy.id for item in w.lineage(db,artifact)):
            impact=m.ContentLabelImpact(**rw.capture(src,policy),assertion_id=row.id,policy_id=artifact.id,kind='released_lineage_attributes_changed',created_at=clock())
            db.add(impact);db.flush()
            # Route to the recorded senior approver only if they remain eligible; otherwise retain unassigned.
            derivative=db.scalar(select(m.DisclosureArtifact).where(m.DisclosureArtifact.policy_id==artifact.id))
            if derivative:
                approver=db.scalar(select(m.DisclosureDecision.actor_id).where(m.DisclosureDecision.artifact_id==derivative.id,m.DisclosureDecision.operation=='legal_approve'))
                if approver:
                    try:assign_impact(db,actor,impact.id,approver,commit=False)
                    except HTTPException as e:
                        if e.status_code not in {403,404,422}:raise
    # New segment scopes are indexed in their own audit partition as well.
    rw.audit_work(db,actor,policy,'content.labels.propose',row)
    if row.label_scope:
        from kestrel.services.auth import audit
        audit(db,'content.labels.propose','allowed',actor.id,category='clean_team',matter_id=src.matter_id,object_id=row.id,clean_team_scope=row.label_scope)
    value=output(db,actor,row,src);db.commit();return value


def decide(db,actor,aid,op,p):
    row=db.get(m.ContentLabelAssertion,aid)
    if not row:raise HTTPException(404,'Attribute assertion unavailable')
    src,policy=rw.source(db,actor,row.source_id,True);output(db,actor,row,src)
    if p.expected_revision!=revision(db,row.source_id):raise HTTPException(409,'Attribute revision changed; refresh')
    history=decisions(db,row)
    if history and (history[-1].operation=='contest' or op=='confirm'):raise HTTPException(409,'Assertion already decided; contested restrictions remain protective')
    if op=='confirm' and (R.SME not in actor.roles or actor.id==row.created_by):raise HTTPException(403,'Independent source-cleared Legal SME required')
    event=m.ContentLabelDecision(**rw.capture(src,policy),assertion_id=aid,sequence=len(history)+1,operation=op,actor_id=actor.id,content_hash=row.content_hash,rationale=p.rationale,occurred_at=clock())
    db.add(event);rw.audit_work(db,actor,policy,'content.labels.'+op,event,[row]);db.flush();value=output(db,actor,row,src);db.commit();return value


def assign_impact(db,actor,impact_id,assignee_id,*,commit=True):
    impact=db.get(m.ContentLabelImpact,impact_id)
    if not impact:raise HTTPException(404,'Counsel impact unavailable')
    src,policy=rw.source(db,actor,impact.source_id,True);rw.retained(db,actor,impact)
    old=db.scalar(select(m.ContentImpactTask).where(m.ContentImpactTask.impact_id==impact_id))
    if old:
        rw.task_row(db,actor,old.task_id)
        return {'task_id':old.task_id}
    rw.eligible(db,assignee_id,src.id,[impact])
    from kestrel.repositories.identity import principal
    account=db.get(m.Account,assignee_id);other=principal(db,account,clock())
    if not other.roles&{R.SME,R.ANTITRUST}:raise HTTPException(422,'Source-cleared senior lawyer or antitrust counsel required')
    from kestrel.schemas.review_work import TaskCreate
    payload=TaskCreate(stage='specialized_legal',assignee_id=assignee_id,request_key='content-impact-'+impact.id,rationale='Counsel follow-up: source attributes changed after disclosure. Review exposure, access revocation and any new release. This is not a legal conclusion.')
    task=rw.create_task(db,actor,src.id,payload,commit=False)
    routing=m.ContentImpactTask(**rw.capture(src,policy),impact_id=impact.id,task_id=task['id'],created_by=actor.id,created_at=clock())
    db.add(routing);rw.audit_work(db,actor,policy,'content.impact.assign',routing,[impact]);db.flush()
    if commit:db.commit()
    return {'task_id':task['id']}


def eligible_counsel(db,actor,impact_id):
    impact=db.get(m.ContentLabelImpact,impact_id)
    if not impact:raise HTTPException(404,'Counsel impact unavailable')
    rw.retained(db,actor,impact);result=[]
    from kestrel.repositories.identity import principal
    for account in db.scalars(select(m.Account).where(m.Account.active==True).order_by(m.Account.id).limit(500)):
        other=principal(db,account,clock())
        if not other.roles&{R.SME,R.ANTITRUST}:continue
        try:result.append(rw.eligible(db,account.id,impact.source_id,[impact]))
        except HTTPException as e:
            if e.status_code!=403:raise
    return result
