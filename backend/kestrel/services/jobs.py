"""Authorized first-source analysis and embedded synthetic tests; no automatic release."""
import json
import time
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from kestrel.models import AnalysisJob,Account,GovernanceVersion,SourceVersion,DocumentPolicyVersion as Policy
from kestrel.domain import Role as R
from kestrel.repositories.identity import principal
from kestrel.services import governance
from kestrel.services.auth import audit
from kestrel.diagnostics import emit, activity

MAX_ATTEMPTS=2
LEASE_SECONDS=600

def authorize(db,actor,version):
    row=governance.read(db,actor,version)
    if R.SME not in actor.roles:raise HTTPException(403,'Scoped Legal SME authorization required')
    if row.kind!='legal_playbook' or row.state!='published' or row.approved_hash!=row.content_hash or not row.reviewer_id or row.reviewer_id==row.author_id:
        raise HTTPException(409,'Independently approved published playbook required')
    if db.scalar(select(GovernanceVersion.id).where(GovernanceVersion.base_playbook_id==row.id,GovernanceVersion.state=='published')):raise HTTPException(409,'Playbook replaced; select the current published version')
    if governance.definition(json.loads(row.definition_json))[1]!=row.content_hash:raise HTTPException(409,'Playbook integrity mismatch')
    return row

def enqueue(db,actor,payload):
    version=authorize(db,actor,payload.playbook_id)
    document_id=getattr(payload,'document_version_id',None)
    engine=getattr(payload,'engine_name','literal')
    if engine=='openai':
        from kestrel.adapters.openai_review import configuration
        enabled,key=configuration()
        if not document_id or not enabled or not key:raise HTTPException(409,'A source version and enabled OpenAI configuration are required')
    if document_id:
        from kestrel.services import workflow
        source,policy=workflow.source(db,actor,document_id)
        workflow.require_policy(db,actor,policy,'analyze');workflow.processing_allowed(db,policy,external=engine=='openai')
        if source.matter_id!=version.matter_id or source.extraction_status!='ready':raise HTTPException(409,'Extracted same-matter source version required')
        workflow.source_integrity(source,policy)
    existing=db.scalar(select(AnalysisJob).where(AnalysisJob.requested_by==actor.id,AnalysisJob.idempotency_key==payload.idempotency_key))
    if existing:
        if existing.playbook_id!=version.id or existing.rationale!=payload.rationale or existing.document_version_id!=document_id or existing.engine_name!=engine:raise HTTPException(409,'Idempotency key already bound to another request')
        return existing
    if document_id and db.scalar(select(AnalysisJob.id).where(AnalysisJob.document_version_id==document_id)):
        raise HTTPException(409,'Source version already has an analysis request; use recovery or the separate impact/rerun approval workflow')
    # Prevent unbounded accidental submission from the demo UI.
    count=db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.requested_by==actor.id,AnalysisJob.state.in_(['queued','running'])))
    if count>=20:raise HTTPException(429,'Outstanding job limit reached')
    now=int(time.time())
    row=AnalysisJob(matter_id=version.matter_id,playbook_id=version.id,playbook_hash=version.content_hash,
        requested_by=actor.id,idempotency_key=payload.idempotency_key,rationale=payload.rationale,created_at=now,available_at=now,document_version_id=document_id,engine_name=engine)
    db.add(row)
    try:
        db.flush()
        if document_id:workflow.event(db,actor,policy,'analysis.enqueue',row.id,'authorized')
        else:audit(db,'analysis.enqueue','authorized',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(AnalysisJob).where(AnalysisJob.requested_by==actor.id,AnalysisJob.idempotency_key==payload.idempotency_key))
        if not existing or existing.playbook_id!=version.id or existing.rationale!=payload.rationale or existing.document_version_id!=document_id or existing.engine_name!=engine:raise HTTPException(409,'Conflicting queue request')
        return existing
    return row

def read(db,actor,job_id,historical=False):
    row=db.get(AnalysisJob,job_id)
    if row is None:raise HTTPException(404,'Job unavailable')
    if row.document_version_id:
        from kestrel.services.workflow import source
        source(db,actor,row.document_version_id,historical)
    else:governance.read(db,actor,row.playbook_id)
    return row

def retry(db,actor,row,rationale):
    authorize(db,actor,row.playbook_id)
    if row.engine_name=='openai':raise HTTPException(409,'Live provider requests are never automatically resent; reconcile their budget reservation first')
    now=int(time.time())
    if row.impact_task_id:
        from kestrel.services.action_center import execution_authority as rerun_authority
        rerun_authority(db,row,now)
    if row.state not in {'failed','running'} or (row.state=='running' and (row.lease_until or 0)>now) or row.attempts>=MAX_ATTEMPTS:
        raise HTTPException(409,'No recoverable failed or expired job; maximum two attempts')
    result=db.execute(update(AnalysisJob).where(AnalysisJob.id==row.id,AnalysisJob.state==row.state,
        AnalysisJob.attempts==row.attempts,AnalysisJob.lease_token==row.lease_token).values(state='queued',available_at=now,
        lease_until=None,lease_token=None,error_code=None))
    if result.rowcount!=1:raise HTTPException(409,'Job changed; refresh')
    # Rationale retained as an additional decision, not in technical logs.
    from kestrel.models import AdministrationDecision
    db.add(AdministrationDecision(matter_id=row.matter_id,actor_id=actor.id,kind='analysis.retry',rationale=rationale,occurred_at=now,revision=row.attempts))
    if row.document_version_id:
        from kestrel.services.workflow import source,event
        _,policy=source(db,actor,row.document_version_id)
        event(db,actor,policy,'analysis.retry',row.id,'authorized')
    else:audit(db,'analysis.retry','authorized',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id)
    db.commit();return row

def claim(sessions,now=None):
    now=int(time.time()) if now is None else now
    with sessions() as db:
        stmt=select(AnalysisJob).where(AnalysisJob.state=='queued',AnalysisJob.available_at<=now,AnalysisJob.attempts<MAX_ATTEMPTS).order_by(AnalysisJob.created_at,AnalysisJob.id).limit(1)
        if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(skip_locked=True)
        row=db.scalar(stmt)
        if not row:return None
        token=str(uuid4())
        result=db.execute(update(AnalysisJob).where(AnalysisJob.id==row.id,AnalysisJob.state=='queued',AnalysisJob.attempts==row.attempts)
            .values(state='running',lease_token=token,lease_until=now+LEASE_SECONDS,attempts=row.attempts+1))
        if result.rowcount!=1:db.rollback();return None
        if row.impact_task_id:
            from kestrel.models import GovernanceTask
            db.get(GovernanceTask,row.impact_task_id).state='in_progress'
        job_id=row.id;db.commit();return job_id,token

def execution_authority(db,row,now):
    account=db.get(Account,row.requested_by)
    if account is None or not account.active:raise HTTPException(403,'Requester inactive')
    version=authorize(db,principal(db,account,now),row.playbook_id)
    if version.matter_id!=row.matter_id or version.content_hash!=row.playbook_hash:raise HTTPException(409,'Snapshot mismatch')
    if row.document_version_id:
        from kestrel.services import workflow
        actor=principal(db,account,now)
        source,policy=workflow.source(db,actor,row.document_version_id)
        workflow.require_policy(db,actor,policy,'analyze');workflow.processing_allowed(db,policy,external=row.engine_name=='openai')
        workflow.source_integrity(source,policy)
        if source.matter_id!=row.matter_id or source.extraction_status!='ready':raise HTTPException(409,'Source snapshot unavailable')
    return version

def analyze(value):
    # Reuses the exact literal baseline. No network, provider or source documents.
    return governance.analyze_examples(value)

def finish(sessions,job_id,token,result,now=None):
    now=int(time.time()) if now is None else now
    with sessions() as db:
        row=db.scalar(select(AnalysisJob).where(AnalysisJob.id==job_id).with_for_update())
        if not row or row.state!='running' or row.lease_token!=token or row.lease_until<=now:return False
        execution_authority(db,row,now)
        if row.document_version_id:
            from kestrel.services.workflow import save_findings
            save_findings(db,row,result)
            if row.impact_task_id:
                from kestrel.services.action_center import reconcile
                reconcile(db,row)
        row.state='succeeded';row.finished_at=now;row.lease_token=None;row.lease_until=None
        row.result_json=json.dumps({'status':'candidate_only','mode':'openai_candidate' if row.engine_name=='openai' else 'synthetic_literal_baseline','playbook_hash':row.playbook_hash,**result})
        if row.document_version_id:
            from kestrel.services.workflow import event
            event(db,principal(db,db.get(Account,row.requested_by),now),db.get(Policy,db.get(SourceVersion,row.document_version_id).policy_id),'analysis.complete',row.id,'candidate_only')
        else:audit(db,'analysis.complete','candidate_only',row.requested_by,category='legal_sme',matter_id=row.matter_id,object_id=row.id)
        db.commit();return True

def run_once(sessions,heartbeat=None):
    from kestrel.services.action_center import process_one,escalate_one
    if process_one(sessions) or escalate_one(sessions):return True
    lease=claim(sessions)
    if not lease:return False
    job_id,token=lease
    activity('worker','job.started')
    try:
        with sessions() as db:
            row=db.get(AnalysisJob,job_id)
            version=execution_authority(db,row,int(time.time()))
            value=json.loads(version.definition_json)
            if row.document_version_id:
                if row.engine_name=='openai':
                    from kestrel.adapters.openai_review import request_payload
                    source=db.get(SourceVersion,row.document_version_id)
                    from kestrel.adapters import full_review
                    full_payloads=full_review.payloads(source,value) if full_review.applies(value) else None
                    payload=None if full_payloads else request_payload(source,value);result=None
                else:
                    from kestrel.services.workflow import analyze_source
                    result=analyze_source(db.get(SourceVersion,row.document_version_id),value)
            else:result=None
            live=row.engine_name=='openai'
        if live:
            from kestrel.services import ai_budget
            from kestrel.adapters.openai_review import send,convert
            ai_budget.reserve(sessions,job_id)
            with sessions() as db:
                active=db.get(AnalysisJob,job_id);execution_authority(db,active,int(time.time()))
            from kestrel.adapters import full_review
            if full_review.applies(value):
                parts=[];input_tokens=output_tokens=0
                for request,units,view in full_payloads:
                    if heartbeat:heartbeat()
                    with sessions() as db:execution_authority(db,db.get(AnalysisJob,job_id),int(time.time()))
                    response=send(request)
                    if heartbeat:heartbeat()
                    usage=response.get('usage') or {}
                    if type(usage.get('input_tokens')) is not int or type(usage.get('output_tokens')) is not int or min(usage['input_tokens'],usage['output_tokens'])<0:raise HTTPException(502,'Usage unavailable; reservation retained')
                    input_tokens+=usage['input_tokens'];output_tokens+=usage['output_tokens'];parts.append(full_review.convert(response,units,value))
                ai_budget.settle(sessions,job_id,input_tokens,output_tokens);result=full_review.merge(source,value,parts)
            else:
                response=send(payload)
                usage=response.get('usage') or {}
                ai_budget.settle(sessions,job_id,usage.get('input_tokens'),usage.get('output_tokens'))
                result=convert(source,value,response)
        elif result is None:result=analyze(value)
        if finish(sessions,job_id,token,result):activity('worker','job.completed')
    except Exception as error:
        denied=isinstance(error,HTTPException)
        emit('job.denied' if denied else 'job.exception',component='worker',exception=error)
        with sessions() as db:
            row=db.scalar(select(AnalysisJob).where(AnalysisJob.id==job_id).with_for_update())
            now=int(time.time())
            if row.state=='running' and row.lease_token==token and row.lease_until>now:
                row.state='denied' if denied else ('queued' if row.attempts<MAX_ATTEMPTS and row.engine_name!='openai' else 'failed')
                row.error_code=({401:'authorization_changed',403:'authorization_changed',409:'state_or_configuration_changed',413:'document_exceeds_review_limits',429:'ai_budget_unavailable',502:'ai_response_unusable',503:'provider_or_component_unavailable'}.get(error.status_code,'request_denied') if denied else 'execution_failed')
                row.available_at=now+10;row.lease_token=None;row.lease_until=None
                if row.state!='queued':
                    row.finished_at=now
                    if row.impact_task_id:
                        from kestrel.models import GovernanceTask
                        db.get(GovernanceTask,row.impact_task_id).state='failed'
                policy=db.get(Policy,db.get(SourceVersion,row.document_version_id).policy_id) if row.document_version_id else None
                ct=policy and policy.classification=='clean_team'
                audit(db,'analysis.failure',row.state,row.requested_by,category='clean_team' if ct else 'legal_sme',matter_id=row.matter_id,object_id=row.id,clean_team_scope=policy.clean_team_scope if ct else None)
                db.commit()
        activity('worker','job.failed',failed=True)
    return True
