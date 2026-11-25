"""Durable internal DDR authority. Graph acknowledgements never approve content."""
import json
from fastapi import HTTPException
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from kestrel import models as m
from kestrel.domain import Role as R
from kestrel.repositories.identity import principal
from kestrel.services import workflow as w,governance,lifecycle,review_work as rw,ddr_evidence
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest

GRAPH_VERSION='ddr-graph-1'
LIVE_GRAPH_READY=True

def person(db,uid):
    account=db.get(m.Account,uid)
    if not account or not account.active:raise HTTPException(403,'Run identity unavailable')
    return principal(db,account,clock())

def configuration(db,actor,matter,playbook_id,engine,agent_profile_ids=None,*,for_new_run=True):
    w.legal(actor,matter)
    book=db.get(m.GovernanceVersion,playbook_id)
    if not book or book.matter_id!=matter or book.kind!='legal_playbook' or book.state!='published' or book.approved_hash!=book.content_hash or book.tested_hash!=book.content_hash or not book.reviewer_id or book.reviewer_id==book.author_id:raise HTTPException(409,'Independently approved tested published legal playbook required')
    if governance.definition(json.loads(book.definition_json))[1]!=book.content_hash:raise HTTPException(409,'Legal configuration integrity failed')
    reviewer=person(db,book.reviewer_id);w.legal(reviewer,matter)
    if R.SME not in reviewer.roles:raise HTTPException(403,'Legal configuration approval no longer current')
    if db.scalar(select(m.GovernanceVersion.id).where(m.GovernanceVersion.base_playbook_id==book.id,m.GovernanceVersion.state=='published')):raise HTTPException(409,'Legal playbook replaced; select its current version')
    value={'graph_version':GRAPH_VERSION,'playbook_id':book.id,'playbook_hash':book.content_hash,'engine':engine,'specialists':['contracts'],
        'max_concurrency':2,'max_model_calls':3,'total_tokens':12000,'max_output_tokens':1200,'max_cost_cents':200,'automatic_paid_retries':0}
    value['agent_profile_ids']=[]
    if agent_profile_ids:
        from kestrel.services.agent_registry import resolve_versions
        resolved=resolve_versions(db,actor,agent_profile_ids,for_new_run=for_new_run)
        if any(p['matter_id']!=matter for p in resolved['profiles']):raise HTTPException(403,'Agent profiles outside requested matter')
        supported={'coordinator','evidence','contracts','drafter','quality','citation_validator'}
        provider='offline' if engine=='offline' else 'openai'
        if any(p['definition']['agent_kind'] not in supported or p['definition']['provider']!=provider for p in resolved['profiles']):raise HTTPException(422,'Selected profile role or provider is unavailable in this bounded graph')
        required={'coordinator':{'validate_current_scope','request_attorney_review'},'evidence':{'read_reviewed_findings','read_exact_evidence'},'contracts':{'read_reviewed_findings','read_exact_evidence'},'drafter':{'write_internal_draft'},'quality':{'read_reviewed_findings','validate_citations'},'citation_validator':{'validate_citations'}}
        for profile in resolved['profiles']:
            definition=profile['definition']
            if not required[definition['agent_kind']]<=set(definition['tools']):raise HTTPException(422,'Profile disables a tool required by its implemented stage')
            for key in ['max_concurrency','max_model_calls','total_tokens','max_output_tokens','max_cost_cents']:
                value[key]=min(value[key],definition[key])
        value.update(agent_profile_ids=resolved['agent_profile_ids'],agent_profiles=resolved['profiles'],agent_profiles_hash=resolved['hash'])
    if engine=='openai':
        from kestrel.adapters.ddr_provider import manifest,validate_config
        try:
            value['live_provider_manifest']=manifest(value)
            validate_config(value)
        except (ValueError,TypeError,KeyError):raise HTTPException(422,'Exact supported independently published live-stage profiles and provider configuration required')
    if len(canonical(value).encode())>128000:raise HTTPException(413,'Pinned configuration exceeds bounded run storage')
    return value,digest(canonical(value).encode())

def row(db,rid):
    value=db.get(m.DDRRun,rid)
    if not value:raise HTTPException(404,'Internal run unavailable')
    return value

def evidence_rows(db,run):return list(db.scalars(select(m.DDREvidence).where(m.DDREvidence.run_id==run.id).order_by(m.DDREvidence.finding_id)))

def read(db,actor,rid):
    run=row(db,rid);w.legal(actor,run.matter_id)
    refs=evidence_rows(db,run)
    if not refs:raise HTTPException(403,'Run evidence unavailable')
    for ref in refs:rw.retained(db,actor,ref);w.source(db,actor,ref.source_id,historical=True)
    if digest(run.snapshot_json.encode())!=run.snapshot_hash or digest(run.config_json.encode())!=run.config_hash:raise HTTPException(409,'Run snapshot integrity failed')
    return run

def create(db,actor,p,*,impact_grant=None):
    w.legal(actor,p.matter_id);lifecycle.mutable(db,p.matter_id)
    if p.request_key.startswith('agent-impact-'):
        if impact_grant is None:raise HTTPException(403,'Reserved server-derived impact request key')
        verify_impact_binding(db,p,impact_grant)
    if p.engine=='openai':
        from kestrel.adapters.ddr_provider import availability
        if not LIVE_GRAPH_READY or not availability()['enabled']:raise HTTPException(409,'Live graph processing requires the verified adapter and enabled private provider settings')
    config,config_hash=configuration(db,actor,p.matter_id,p.playbook_id,p.engine,p.agent_profile_ids)
    bundle=ddr_evidence.capture(db,actor,p.matter_id,p.finding_ids,external_processing=p.engine=='openai')
    request_hash=digest(canonical(p.model_dump(mode='json')).encode())
    old=db.scalar(select(m.DDRRun).where(m.DDRRun.requested_by==actor.id,m.DDRRun.request_key==p.request_key))
    if old:
        if old.input_hash!=request_hash or old.snapshot_hash!=bundle['hash'] or old.config_hash!=config_hash:raise HTTPException(409,'Request key already bound to different input or evidence')
        return read(db,actor,old.id)
    outstanding=db.scalar(select(func.count()).select_from(m.DDRExecution).join(m.DDRRun,m.DDRRun.id==m.DDRExecution.run_id).where(m.DDRRun.requested_by==actor.id,m.DDRExecution.state.in_(['queued','running','awaiting_attorney'])))
    if outstanding>=20:raise HTTPException(429,'Outstanding internal run limit reached')
    db.scalar(select(m.Matter).where(m.Matter.id==p.matter_id).with_for_update())
    now=clock();run=m.DDRRun(matter_id=p.matter_id,requested_by=actor.id,request_key=p.request_key,input_hash=request_hash,
        snapshot_json=canonical(bundle['snapshot']),snapshot_hash=bundle['hash'],config_json=canonical(config),config_hash=config_hash,graph_version=GRAPH_VERSION,
        playbook_id=p.playbook_id,title=p.title,audience=p.audience,kind=p.kind,engine=p.engine,rationale=p.rationale,created_at=now,deadline=now+7*86400)
    db.add(run);db.flush()
    for descriptor in bundle['snapshot']['items']:
        source,policy=w.source(db,actor,descriptor['source_id'])
        db.add(m.DDREvidence(run_id=run.id,finding_id=descriptor['finding_id'],revision_id=descriptor['revision_id'],descriptor_json=canonical(descriptor),descriptor_hash=digest(canonical(descriptor).encode()),**rw.capture(source,policy)))
    db.add(m.DDRExecution(run_id=run.id,state='queued',phase='queued',updated_at=now));db.flush()
    record(db,run,actor.id,'created','queued')
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent run request; refresh before retrying')
    return run

def record(db,run,actor_id,kind,outcome,rationale='Operational graph transition'):
    event=m.DDREvent(matter_id=run.matter_id,run_id=run.id,actor_id=actor_id,kind=kind,outcome=outcome,rationale=rationale,created_at=clock());db.add(event);db.flush()
    audit(db,'ddr.'+kind,outcome,actor_id,category='legal_sme',matter_id=run.matter_id,object_id=event.id)
    return event

def execution_authority(db,rid):
    run=row(db,rid);actor=person(db,run.requested_by);read(db,actor,rid);lifecycle.mutable(db,run.matter_id)
    if run.request_key.startswith('agent-impact-'):
        from kestrel.services.agent_registry import authorize_rerun
        grant=authorize_rerun(db,actor,run.request_key.removeprefix('agent-impact-'))
        original=row(db,grant['original_run_id'])
        config=json.loads(run.config_json);snapshot=json.loads(run.snapshot_json)
        if (set(config.get('agent_profile_ids',[]))!=set(grant['agent_profile_ids']) or {i['finding_id'] for i in snapshot['items']}!=set(grant['finding_ids']) or run.snapshot_hash!=original.snapshot_hash or any(getattr(run,k)!=getattr(original,k) for k in ['matter_id','audience','kind','engine','playbook_id','title'])):raise HTTPException(403,'Queued rerun no longer matches its exact authorization')
    execution=db.get(m.DDRExecution,run.id)
    if not execution or execution.state in {'cancelled','failed','rejected','paused_ambiguous'} or clock()>=run.deadline:raise HTTPException(409,'Run execution is closed or expired')
    config,hash_value=configuration(db,actor,run.matter_id,run.playbook_id,run.engine,json.loads(run.config_json).get('agent_profile_ids',[]),for_new_run=False)
    if hash_value!=run.config_hash:raise HTTPException(409,'Run configuration changed; new authorized run required')
    if run.engine=='openai':
        from kestrel.adapters.ddr_provider import availability
        if not LIVE_GRAPH_READY or not availability()['enabled']:raise HTTPException(403,'Live graph processing is currently unavailable')
    bundle=ddr_evidence.validate(db,actor,json.loads(run.snapshot_json))
    if bundle['hash']!=run.snapshot_hash:raise HTTPException(409,'Run evidence changed')
    return run,actor,bundle

def cancel(db,actor,rid,rationale):
    run=read(db,actor,rid)
    if actor.id!=run.requested_by and R.SME not in actor.roles:raise HTTPException(403,'Requester or scoped Legal SME required')
    db.scalar(select(m.Matter).where(m.Matter.id==run.matter_id).with_for_update())
    execution=db.get(m.DDRExecution,run.id)
    if execution.state=='cancelled':return run
    if execution.state in {'internally_approved','rejected','complete'}:raise HTTPException(409,'Completed run cannot be cancelled; use report revocation')
    execution.state='cancelled';execution.phase='cancelled';execution.lease_until=0;execution.worker_token=None;execution.updated_at=clock()
    record(db,run,actor.id,'cancel','cancelled',rationale);db.commit();return run

def audit_records(db,object_id):
    direct=db.get(m.DDREvidence,object_id)
    if direct:return [direct]
    run=db.get(m.DDRRun,object_id)
    if not run:
        for model in [m.DDRArtifact,m.DDRAttempt,m.DDRTask,m.DDREvent,m.DDRReportLink]:
            entry=db.get(model,object_id)
            if entry:run=db.get(m.DDRRun,entry.run_id);break
    if not run:
        decision=db.get(m.DDRDecision,object_id)
        if decision:run=db.get(m.DDRRun,db.get(m.DDRTask,decision.task_id).run_id)
        result=db.get(m.DDRNodeResult,object_id)
        if result:run=db.get(m.DDRRun,db.get(m.DDRAttempt,result.attempt_id).run_id)
    return evidence_rows(db,run) if run else []


def artifact(db,run,ref,kind):
    from kestrel.ddr.schemas import canonical as graph_json,digest as graph_hash
    value=db.get(m.DDRArtifact,ref.id)
    if not value or value.run_id!=run.id or value.kind!=kind or value.content_hash!=ref.content_hash or graph_hash(value.payload_json)!=value.content_hash:raise HTTPException(409,'Graph artifact integrity failed')
    return json.loads(value.payload_json)


def linked_report(db,task):
    link=db.scalar(select(m.DDRReportLink).where(m.DDRReportLink.task_id==task.id))
    if not link:raise HTTPException(409,'Complete report package unavailable')
    report=db.get(m.ReportVersion,link.report_id);release=db.get(m.ReleasePackage,report.release_id)
    if digest(report.body_json.encode())!=release.content_hash:raise HTTPException(409,'Report package integrity failed')
    return report,release,link


def review_task(db,actor,run,draft_ref,validation_ref,key):
    from kestrel.services import reports,diligence
    from kestrel.ddr.schemas import DraftReport,CitationValidation
    read(db,actor,run.id);execution_authority(db,run.id)
    old=db.scalar(select(m.DDRTask).where(m.DDRTask.run_id==run.id,m.DDRTask.draft_id==draft_ref.id))
    if old:return old
    draft=DraftReport.model_validate(artifact(db,run,draft_ref,'draft'))
    validation=CitationValidation.model_validate(artifact(db,run,validation_ref,'validation'))
    if not validation.passed:raise HTTPException(409,'Exact evidence validation must pass before human review')
    task=m.DDRTask(matter_id=run.matter_id,run_id=run.id,draft_id=draft_ref.id,validation_id=validation_ref.id,created_at=clock());db.add(task);db.flush()
    grouped={}
    for claim in draft.claims:grouped.setdefault(claim.finding_ref,[]).append(claim)
    refs=[];sections=[];risks=[];consents=[]
    for descriptor in json.loads(run.snapshot_json)['items']:
        finding,policy=diligence.resolve(db,actor,descriptor['finding_id']);item=diligence.output(db,finding,policy)
        claims=grouped.get(descriptor['finding_id'],[])
        if not claims:raise HTTPException(409,'Draft omitted a reviewed finding')
        text='\n\n'.join(dict.fromkeys(c.text for c in claims))
        if len(text)>2000:raise HTTPException(413,'Draft section exceeds editable report bounds; regenerate a smaller run')
        label=f"{item['logical_key']}, version {item['version_number']}; "+'; '.join(e['locator'] for e in item['evidence'])
        refs.append({'finding_id':item['id'],'revision_id':finding.id,'public_reference':label})
        sections.append({'heading':item['topic'].replace('_',' ').capitalize(),'text':text,'reference':label})
        risk={'reference':label,'finding':item['summary'],'severity':item['severity'],'materiality':item['materiality'],'requirement':item['exposure'],'action':item['action'] or 'Lawyer to confirm follow-up action.','status':item['workflow_status'],'due_on':item['due_on'] or 'Unscheduled'}
        risks.append(risk)
        if item['topic'] in {'change_of_control','assignment','termination'}:consents.append(risk.copy())
    if set(grouped)!={r['finding_id'] for r in refs}:raise HTTPException(409,'Draft contains unknown finding references')
    body={'title':run.title,'overview':'Internal draft assembled from selected lawyer-reviewed findings; independent internal and audience approval remain required.',
        'coverage':f"This package covers {len(refs)} selected reviewed findings. It does not establish complete diligence coverage. Missing documents, later waves and conditional applicability require separate lawyer follow-up.",
        'sections':sections,'risks':risks,'consents':consents,'generator':'langgraph-'+run.engine+'-reviewed-v1'}
    output=reports.persist(db,actor,run.matter_id,run.audience,run.kind,body,refs,commit=False)
    db.add(m.DDRReportLink(matter_id=run.matter_id,run_id=run.id,report_id=output['id'],task_id=task.id,draft_hash=draft_ref.content_hash,created_at=clock()))
    record(db,run,actor.id,'review_requested','awaiting_attorney');db.flush();return task


def approval(db,actor,run,draft_ref,validation_ref):
    from kestrel.ddr.schemas import ApprovalReceipt
    read(db,actor,run.id)
    task=db.scalar(select(m.DDRTask).where(m.DDRTask.run_id==run.id,m.DDRTask.draft_id==draft_ref.id,m.DDRTask.validation_id==validation_ref.id))
    if not task:return None
    report,release,link=linked_report(db,task)
    decisions=list(db.scalars(select(m.DDRDecision).where(m.DDRDecision.task_id==task.id)))
    if any(d.operation=='revoke' for d in decisions):return None
    decision=next((d for d in decisions if d.operation in {'approve','reject'}),None)
    if not decision:return None
    reviewer=person(db,decision.actor_id);read(db,reviewer,run.id)
    if R.SME not in reviewer.roles or reviewer.id==run.requested_by:raise HTTPException(403,'Independent current internal reviewer required')
    if (decision.draft_hash,decision.report_hash,decision.snapshot_hash,decision.config_hash)!=(draft_ref.content_hash,release.content_hash,run.snapshot_hash,run.config_hash):raise HTTPException(409,'Exact internal report approval changed')
    ddr_evidence.validate(db,reviewer,json.loads(run.snapshot_json))
    _,config_hash=configuration(db,reviewer,run.matter_id,run.playbook_id,run.engine,json.loads(run.config_json).get('agent_profile_ids',[]),for_new_run=False)
    if config_hash!=run.config_hash:raise HTTPException(409,'Report configuration changed')
    return ApprovalReceipt(id=decision.id,decision=decision.operation,reviewer_id=reviewer.id,draft_hash=decision.draft_hash,snapshot_hash=decision.snapshot_hash,config_hash=decision.config_hash)


def require_internal(db,release_id):
    """Used by every legacy audience read/release path, not just the DDR API."""
    report=db.scalar(select(m.ReportVersion).where(m.ReportVersion.release_id==release_id))
    link=db.scalar(select(m.DDRReportLink).where(m.DDRReportLink.report_id==report.id)) if report else None
    if not link:return
    from kestrel.ddr.schemas import ArtifactRef
    run=row(db,link.run_id);task=db.get(m.DDRTask,link.task_id)
    draft=db.get(m.DDRArtifact,task.draft_id);validation=db.get(m.DDRArtifact,task.validation_id)
    try:
        receipt=approval(db,person(db,run.requested_by),run,ArtifactRef(id=draft.id,kind='draft',content_hash=draft.content_hash,creator_id=run.requested_by),ArtifactRef(id=validation.id,kind='validation',content_hash=validation.content_hash,creator_id=run.requested_by))
        if not receipt or receipt.decision!='approve':raise HTTPException(403,'Independent internal approval required before audience access')
    except HTTPException:raise HTTPException(403,'Current exact internal DDR approval required')


def decide(db,actor,task_id,p):
    task=db.get(m.DDRTask,task_id)
    if not task:raise HTTPException(404,'Internal review task unavailable')
    run=read(db,actor,task.run_id)
    if R.SME not in actor.roles or actor.id==run.requested_by:raise HTTPException(403,'Independent scoped Legal SME required')
    db.scalar(select(m.Matter).where(m.Matter.id==run.matter_id).with_for_update())
    report,release,link=linked_report(db,task);draft=db.get(m.DDRArtifact,task.draft_id)
    if (p.draft_hash,p.report_hash,p.snapshot_hash,p.config_hash)!=(draft.content_hash,release.content_hash,run.snapshot_hash,run.config_hash):raise HTTPException(409,'Review the exact complete report version and snapshots')
    old=list(db.scalars(select(m.DDRDecision).where(m.DDRDecision.task_id==task.id)))
    if any(d.operation==p.operation for d in old) or any(d.operation=='revoke' for d in old):raise HTTPException(409,'Decision already retained')
    if p.operation!='revoke':
        lifecycle.mutable(db,run.matter_id)
        if any(d.operation in {'approve','reject'} for d in old) or db.scalar(select(m.ReportVersion.id).where(m.ReportVersion.previous_id==report.id)):raise HTTPException(409,'Current undecided report version required')
        if not p.content_reviewed:raise HTTPException(422,'Explicit review of the complete report and annexes is required')
        if p.operation=='approve':execution_authority(db,run.id);ddr_evidence.validate(db,actor,json.loads(run.snapshot_json))
    elif not any(d.operation=='approve' for d in old):raise HTTPException(409,'Approved report required for revocation')
    decision=m.DDRDecision(matter_id=run.matter_id,task_id=task.id,actor_id=actor.id,operation=p.operation,draft_hash=p.draft_hash,report_hash=p.report_hash,snapshot_hash=p.snapshot_hash,config_hash=p.config_hash,rationale=p.rationale,created_at=clock());db.add(decision);db.flush()
    execution=db.get(m.DDRExecution,run.id)
    if p.operation=='revoke':execution.state='rejected';execution.phase='internal_approval_revoked'
    elif p.operation=='reject':execution.state='rejected';execution.phase='attorney_rejected'
    elif report.version_number>1:execution.state='complete';execution.phase='human_revision_approved'
    else:execution.state='queued';execution.phase='human_decision_recorded'
    execution.worker_token=None;execution.lease_until=0;execution.updated_at=clock()
    record(db,run,actor.id,'internal_'+p.operation,p.operation,p.rationale);db.commit();return decision


def output(db,actor,run,detail=False):
    read(db,actor,run.id);execution=db.get(m.DDRExecution,run.id)
    links=list(db.scalars(select(m.DDRReportLink).where(m.DDRReportLink.run_id==run.id)))
    linked=[(db.get(m.ReportVersion,l.report_id).version_number,l) for l in links]
    current=max(linked,key=lambda pair:pair[0])[1] if linked else None
    value={k:getattr(run,k) for k in ['id','matter_id','title','audience','kind','engine','created_at','snapshot_hash','config_hash']}
    value.update(requested_by=run.requested_by,can_cancel=actor.id==run.requested_by or R.SME in actor.roles,state=execution.state,phase=execution.phase,error_code=execution.error_code,report_id=current.report_id if current else None)
    if detail:
        tasks=[]
        for task in db.scalars(select(m.DDRTask).where(m.DDRTask.run_id==run.id).order_by(m.DDRTask.created_at,m.DDRTask.id)):
            report,release,link=linked_report(db,task);draft=db.get(m.DDRArtifact,task.draft_id)
            operations={d.operation for d in db.scalars(select(m.DDRDecision).where(m.DDRDecision.task_id==task.id))}
            state='revoked' if 'revoke' in operations else 'rejected' if 'reject' in operations else 'approved' if 'approve' in operations else 'pending'
            latest=not db.scalar(select(m.ReportVersion.id).where(m.ReportVersion.previous_id==report.id))
            tasks.append({'id':task.id,'draft_hash':draft.content_hash,'report_hash':release.content_hash,'snapshot_hash':run.snapshot_hash,'config_hash':run.config_hash,
                'state':state,'report_id':report.id,'can_decide':R.SME in actor.roles and actor.id!=run.requested_by and (latest or state=='approved'),'current_version':latest})
        value['tasks']=tasks
        value['events']=[{'kind':e.kind,'outcome':e.outcome,'created_at':e.created_at} for e in db.scalars(select(m.DDREvent).where(m.DDREvent.run_id==run.id).order_by(m.DDREvent.created_at,m.DDREvent.id))]
    return value


def revised_report(db,actor,previous,report):
    """An edited graph-origin report receives a new exact-version human task."""
    from kestrel.ddr.schemas import DraftReport,Claim,canonical as graph_json,digest as graph_hash
    old_link=db.scalar(select(m.DDRReportLink).where(m.DDRReportLink.report_id==previous.id))
    if not old_link:return
    run=read(db,actor,old_link.run_id);lifecycle.mutable(db,run.matter_id)
    old_task=db.get(m.DDRTask,old_link.task_id);old_draft=db.get(m.DDRArtifact,old_task.draft_id)
    old=DraftReport.model_validate_json(old_draft.payload_json)
    by_finding={}
    for claim in old.claims:by_finding.setdefault(claim.finding_ref,claim)
    release=db.get(m.ReleasePackage,report.release_id);refs=json.loads(release.references_json);body=json.loads(report.body_json)
    if len(refs)!=len(body['sections']):raise HTTPException(409,'Keep the exact finding-linked report structure')
    claims=tuple(Claim(finding_ref=ref['finding_id'],text=section['text'],severity=by_finding[ref['finding_id']].severity,citations=by_finding[ref['finding_id']].citations) for ref,section in zip(refs,body['sections']))
    draft=DraftReport(title=body['title'],claims=claims);encoded=graph_json(draft)
    entry=m.DDRArtifact(matter_id=run.matter_id,run_id=run.id,kind='draft',payload_json=encoded,content_hash=graph_hash(encoded),created_at=clock());db.add(entry);db.flush()
    task=m.DDRTask(matter_id=run.matter_id,run_id=run.id,draft_id=entry.id,validation_id=old_task.validation_id,created_at=clock());db.add(task);db.flush()
    db.add(m.DDRReportLink(matter_id=run.matter_id,run_id=run.id,report_id=report.id,task_id=task.id,draft_hash=entry.content_hash,created_at=clock()))
    execution=db.get(m.DDRExecution,run.id);execution.state='awaiting_attorney';execution.phase='human_revision_review';execution.worker_token=None;execution.lease_until=0;execution.updated_at=clock()
    record(db,run,actor.id,'report_revision','awaiting_attorney')


def rerun_impact(db,actor,task_id,rationale):
    from kestrel.services.agent_registry import authorize_rerun
    from kestrel.schemas.ddr_runs import Create
    grant=authorize_rerun(db,actor,task_id);original=row(db,grant['original_run_id'])
    p=Create(matter_id=original.matter_id,request_key='agent-impact-'+task_id,finding_ids=grant['finding_ids'],playbook_id=original.playbook_id,
        agent_profile_ids=grant['agent_profile_ids'],title=original.title,audience=original.audience,kind=original.kind,engine=original.engine,
        rationale=('SME-authorized agent impact '+task_id+': '+rationale)[:1000])
    result=create(db,actor,p,impact_grant=grant)
    # Revalidation remains mandatory during execution, not only enqueue.
    return result


def verify_impact_binding(db,p,grant):
    original=row(db,grant['original_run_id'])
    if (p.request_key!='agent-impact-'+grant['task_id'] or set(p.finding_ids)!=set(grant['finding_ids']) or set(p.agent_profile_ids)!=set(grant['agent_profile_ids']) or any(getattr(p,k)!=getattr(original,k) for k in ['matter_id','audience','kind','engine','playbook_id','title'])):raise HTTPException(403,'Server rerun input differs from its explicit authorization')


def live_availability():
    if not LIVE_GRAPH_READY:return False
    from kestrel.adapters.ddr_provider import availability
    return availability()['enabled']
