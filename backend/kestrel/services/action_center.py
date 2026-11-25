"""Durable, document-scoped impact decisions. Publication never authorizes analysis."""
import json
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Role as R
from kestrel.repositories.identity import principal
from kestrel.services import workflow as w
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest


def record(db,source_id,action,outcome,object_id,actor_id=None):
    from types import SimpleNamespace
    source=db.get(m.SourceVersion,source_id)
    policy=db.get(m.DocumentPolicyVersion,source.policy_id)
    w.event(db,SimpleNamespace(id=actor_id),policy,action,object_id,outcome)


def diff(before,after,path=''):
    if before==after:return []
    if isinstance(before,dict) and isinstance(after,dict):
        result=[]
        for key in sorted(before.keys()|after.keys()):
            field=path+'/'+key
            if key not in before:result.append({'path':field,'change':'added','before':None,'after':after[key]})
            elif key not in after:result.append({'path':field,'change':'removed','before':before[key],'after':None})
            else:result.extend(diff(before[key],after[key],field))
        return result
    if path=='/rules':return diff({r['id']:r for r in before},{r['id']:r for r in after},path)
    return [{'path':path,'change':'modified','before':before,'after':after}]


def publication(db,target):
    if not target.base_playbook_id:return
    # Serialize branches of the same matter before publishing a replacement.
    db.scalar(select(m.Matter).where(m.Matter.id==target.matter_id).with_for_update())
    from kestrel.services.lifecycle import mutable
    mutable(db,target.matter_id)
    base=db.get(m.GovernanceVersion,target.base_playbook_id)
    if base is None or base.kind!='legal_playbook' or base.state!='published' or base.matter_id!=target.matter_id:raise HTTPException(409,'Published same-matter base required')
    if db.scalar(select(m.GovernanceVersion.id).where(m.GovernanceVersion.base_playbook_id==base.id,m.GovernanceVersion.state=='published',m.GovernanceVersion.id!=target.id)):
        raise HTTPException(409,'Base already replaced; draft against its current successor')
    changes=diff(json.loads(base.definition_json),json.loads(target.definition_json))
    if not changes:raise HTTPException(409,'Replacement is unchanged; retain the existing published version')
    db.add(m.ImpactPublication(target_id=target.id,base_id=base.id,created_at=clock()))
    audit(db,'impact.requested','pending',target.author_id,category='legal_sme',matter_id=target.matter_id,object_id=target.id)


def current_target(db,target):
    if target.state!='published' or target.approved_hash!=target.content_hash:raise HTTPException(409,'Target no longer eligible')
    if db.scalar(select(m.GovernanceVersion.id).where(m.GovernanceVersion.base_playbook_id==target.id,m.GovernanceVersion.state=='published')):raise HTTPException(409,'Target replaced; use the current impact assessment')


def snapshot(db,target,source,baseline):
    policy=db.get(m.DocumentPolicyVersion,source.policy_id)
    findings=list(db.scalars(select(m.SourceFinding).where(m.SourceFinding.job_id==baseline.id).order_by(m.SourceFinding.id)))
    ids=[f.id for f in findings]
    revisions=list(db.scalars(select(m.LegalFindingRevision).where(m.LegalFindingRevision.candidate_id.in_(ids)).order_by(m.LegalFindingRevision.id)))
    references=set(ids)|{r.id for r in revisions}|{r.record_key for r in revisions}
    releases=[]
    for release in db.scalars(select(m.ReleasePackage).join(m.DocumentPolicyVersion,m.ReleasePackage.policy_id==m.DocumentPolicyVersion.id).where(m.DocumentPolicyVersion.matter_id==source.matter_id).order_by(m.ReleasePackage.id)):
        refs=json.loads(release.references_json)
        if any(r.get('finding_id') in references or r.get('revision_id') in references for r in refs):
            p=db.get(m.DocumentPolicyVersion,release.policy_id)
            releases.append({'id':release.id,'hash':release.content_hash,'snapshot':w.snapshot(db,p),'released':p.released})
    state={'schema':'impact-v1','target':target.id,'target_hash':target.content_hash,'source':source.id,'bytes_hash':source.bytes_hash,'text_hash':source.text_hash,
        'source_snapshot':w.snapshot(db,policy),'baseline_job':baseline.id,'baseline_hash':baseline.playbook_hash,
        'findings':[{'id':f.id,'policy':w.snapshot(db,db.get(m.DocumentPolicyVersion,f.policy_id))} for f in findings],
        'reviews':[{'id':r.id,'decision':r.decision} for r in db.scalars(select(m.FindingReview).where(m.FindingReview.finding_id.in_(ids)).order_by(m.FindingReview.id))],
        'revisions':[{'id':r.id,'policy':w.snapshot(db,db.get(m.DocumentPolicyVersion,r.policy_id))} for r in revisions], 'releases':releases}
    return state,digest(canonical(state).encode())


def eligible(db,actor,target,source_id):
    w.legal(actor,target.matter_id)
    if R.SME not in actor.roles or actor.id==target.author_id:raise HTTPException(403,'Independent scoped Legal SME required')
    row,policy=w.source(db,actor,source_id)
    return row,policy


def assess(db,target,source,baseline):
    state,fingerprint=snapshot(db,target,source,baseline)
    existing=db.scalar(select(m.ImpactSnapshot).where(m.ImpactSnapshot.target_id==target.id,m.ImpactSnapshot.source_id==source.id,m.ImpactSnapshot.snapshot_hash==fingerprint))
    if existing:return db.scalar(select(m.GovernanceTask).where(m.GovernanceTask.impact_id==existing.id))
    base=db.get(m.GovernanceVersion,target.base_playbook_id)
    impact=m.ImpactSnapshot(target_id=target.id,source_id=source.id,baseline_job_id=baseline.id,matter_id=source.matter_id,snapshot_hash=fingerprint,
        snapshot_json=canonical(state),diff_json=canonical(diff(json.loads(base.definition_json),json.loads(target.definition_json))),created_at=clock())
    db.add(impact);db.flush()
    recipients=[]
    for account in db.scalars(select(m.Account).join(m.RoleGrant,m.RoleGrant.account_id==m.Account.id).join(m.Role,m.Role.id==m.RoleGrant.role_id).where(m.Role.name=='legal_sme',m.Account.active.is_(True)).order_by(m.Account.id)):
        try:eligible(db,principal(db,account,clock()),target,source.id);recipients.append(account.id)
        except HTTPException as error:
            if error.status_code not in {403,409}:raise
    urgent=any(r['released'] for r in state['releases'])
    task=m.GovernanceTask(impact_id=impact.id,assigned_json=canonical(recipients),priority='urgent' if urgent else 'normal',created_at=clock(),due_at=clock()+(86400 if urgent else 3*86400))
    db.add(task);db.flush()
    for account_id in recipients:db.add(m.TaskNotification(task_id=task.id,account_id=account_id,created_at=clock()))
    record(db,source.id,'impact.assessed','assigned' if recipients else 'unassigned',task.id)
    return task


def process_one(sessions):
    with sessions() as db:
        stmt=select(m.ImpactPublication).where(m.ImpactPublication.state=='pending').order_by(m.ImpactPublication.created_at,m.ImpactPublication.id).limit(1)
        if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(skip_locked=True)
        event=db.scalar(stmt)
        if not event:return False
        event_id=event.id
        try:
            target=db.get(m.GovernanceVersion,event.target_id);current_target(db,target)
            ancestors=[];base=target.base_playbook_id
            while base:
                if base in ancestors or len(ancestors)>=100:raise HTTPException(409,'Invalid playbook lineage')
                ancestors.append(base);base=db.get(m.GovernanceVersion,base).base_playbook_id
            rows=list(db.scalars(select(m.AnalysisJob).where(m.AnalysisJob.playbook_id.in_(ancestors),m.AnalysisJob.document_version_id.is_not(None),m.AnalysisJob.state=='succeeded').order_by(m.AnalysisJob.created_at.desc(),m.AnalysisJob.id)))
            selected={}
            for row in sorted(rows,key=lambda j:ancestors.index(j.playbook_id)):
                if row.document_version_id not in selected:selected[row.document_version_id]=row
            for source_id,baseline in selected.items():assess(db,target,db.get(m.SourceVersion,source_id),baseline)
            event.state='processed';event.processed_at=clock();db.commit()
            from kestrel.diagnostics import activity
            activity('worker','impact.assessed')
        except Exception as error:
            db.rollback()
            from kestrel.diagnostics import emit
            emit('impact.assessment_failed',component='worker',exception=error)
            event=db.get(m.ImpactPublication,event_id);event.state='failed';event.processed_at=clock()
            audit(db,'impact.assessment_failed','manual_recovery_required',category='legal_sme',object_id=event.target_id);db.commit()
        return True


def escalate_one(sessions):
    """A retained one-time escalation; never approves, closes or reruns a task."""
    with sessions() as db:
        prior=select(m.AuditEvent.id).where(m.AuditEvent.action=='impact.escalate',m.AuditEvent.object_id==m.GovernanceTask.id).exists()
        frozen=select(m.MatterLifecycle.matter_id).where(m.MatterLifecycle.matter_id==m.ImpactSnapshot.matter_id,m.MatterLifecycle.frozen.is_(True)).exists()
        stmt=select(m.GovernanceTask).join(m.ImpactSnapshot,m.GovernanceTask.impact_id==m.ImpactSnapshot.id).where(m.GovernanceTask.due_at<clock(),m.GovernanceTask.state.not_in(['closed','rejected','superseded']),~prior,~frozen).order_by(m.GovernanceTask.due_at,m.GovernanceTask.id).limit(1)
        if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(of=m.GovernanceTask,skip_locked=True)
        task=db.scalar(stmt)
        if task is None:return False
        impact=db.get(m.ImpactSnapshot,task.impact_id)
        target=db.get(m.GovernanceVersion,impact.target_id)
        recipients=set(json.loads(task.assigned_json))
        accounts=db.scalars(select(m.Account).join(m.RoleGrant,m.RoleGrant.account_id==m.Account.id).join(m.Role,m.Role.id==m.RoleGrant.role_id).where(m.Account.active.is_(True),m.Role.name.in_(['legal_sme','antitrust_counsel'])).distinct())
        for account in accounts:
            actor=principal(db,account,clock())
            try:
                _,_,_,policy=access(db,actor,task.id)
                if account.id==target.author_id:continue
                if R.SME not in actor.roles and policy.classification!='clean_team':continue
                notice=db.scalar(select(m.TaskNotification).where(m.TaskNotification.task_id==task.id,m.TaskNotification.account_id==account.id))
                if notice is None:
                    notice=m.TaskNotification(task_id=task.id,account_id=account.id,created_at=clock());db.add(notice)
                notice.state='unread';notice.escalated_at=clock()
                try:eligible(db,actor,target,impact.source_id);recipients.add(account.id)
                except HTTPException:pass
            except HTTPException as error:
                if error.status_code!=403:raise
        task.assigned_json=canonical(sorted(recipients));task.priority='critical'
        record(db,impact.source_id,'impact.escalate','overdue_manual_review',task.id)
        db.commit()
        from kestrel.diagnostics import activity
        activity('worker','impact.escalated')
        return True


def access(db,actor,task_id,lock=False):
    stmt=select(m.GovernanceTask).where(m.GovernanceTask.id==task_id)
    if lock:stmt=stmt.with_for_update()
    task=db.scalar(stmt)
    if task is None:raise HTTPException(404,'Task unavailable')
    impact=db.get(m.ImpactSnapshot,task.impact_id)
    w.legal(actor,impact.matter_id)
    source,policy=w.source(db,actor,impact.source_id,historical=True)
    # Comparison metadata never grants a passage/source exception.
    for finding in db.scalars(select(m.SourceFinding).where(m.SourceFinding.job_id==impact.baseline_job_id)):
        w.require_policy(db,actor,db.get(m.DocumentPolicyVersion,finding.policy_id),'historical_read')
    return task,impact,source,policy


def assignment(db,actor,task,impact):
    target=db.get(m.GovernanceVersion,impact.target_id)
    eligible(db,actor,target,impact.source_id)
    if actor.id not in json.loads(task.assigned_json):raise HTTPException(403,'Assigned Legal SME required')
    return target


def refresh(db,actor,task_id):
    task,impact,source,policy=access(db,actor,task_id,True)
    from kestrel.services.lifecycle import mutable
    mutable(db,impact.matter_id)
    target=db.get(m.GovernanceVersion,impact.target_id);eligible(db,actor,target,source.id);current_target(db,target)
    if task.state not in {'open','claimed','superseded'}:raise HTTPException(409,'Only undecided tasks may be reassessed')
    replacement=assess(db,target,source,db.get(m.AnalysisJob,impact.baseline_job_id))
    if replacement.id!=task.id:task.state='superseded'
    elif actor.id not in json.loads(task.assigned_json):
        recipients=sorted(set(json.loads(task.assigned_json))|{actor.id});task.assigned_json=canonical(recipients)
        db.add(m.TaskNotification(task_id=task.id,account_id=actor.id,created_at=clock()))
    record(db,impact.source_id,'impact.reassess','allowed',task.id,actor.id);db.commit()
    return replacement


def claim(db,actor,task_id,rationale=''):
    task,impact,_,_=access(db,actor,task_id,True);assignment(db,actor,task,impact)
    from kestrel.services.lifecycle import mutable
    mutable(db,impact.matter_id)
    if task.state=='claimed' and task.claimed_by==actor.id:return task
    if task.state=='claimed':
        old=db.get(m.Account,task.claimed_by);valid=False
        if old and old.active:
            try:eligible(db,principal(db,old,clock()),db.get(m.GovernanceVersion,impact.target_id),impact.source_id);valid=True
            except HTTPException:pass
        if valid and task.due_at>=clock():raise HTTPException(409,'Another eligible SME holds this claim; wait for its return or overdue recovery')
        if len(rationale.strip())<5:raise HTTPException(422,'Recovery rationale required')
        db.add(m.AdministrationDecision(matter_id=impact.matter_id,actor_id=actor.id,target_id=task.claimed_by,kind='impact.claim_recover-'+task.id,rationale=rationale,occurred_at=clock(),revision=0))
        task.state='open'
    if task.state!='open':raise HTTPException(409,'Open unclaimed task required')
    task.claimed_by=actor.id;task.state='claimed'
    record(db,impact.source_id,'impact.claim','allowed',task.id,actor.id);db.commit();return task


def return_claim(db,actor,task_id,rationale):
    task,impact,_,_=access(db,actor,task_id,True);assignment(db,actor,task,impact)
    from kestrel.services.lifecycle import mutable
    mutable(db,impact.matter_id)
    if task.state!='claimed' or task.claimed_by!=actor.id:raise HTTPException(403,'Only the current claimant may return an undecided task')
    db.add(m.AdministrationDecision(matter_id=impact.matter_id,actor_id=actor.id,target_id=actor.id,kind='impact.claim_return-'+task.id,rationale=rationale,occurred_at=clock(),revision=0))
    task.state='open';task.claimed_by=None
    record(db,impact.source_id,'impact.claim_return','allowed',task.id,actor.id);db.commit();return task


def decide(db,actor,task_id,operation,payload):
    task,impact,source,policy=access(db,actor,task_id,True)
    target=assignment(db,actor,task,impact)
    prior=db.scalar(select(m.ImpactDecision).where(m.ImpactDecision.task_id==task.id))
    if prior:
        if (prior.actor_id,prior.operation,prior.idempotency_key,prior.snapshot_hash,prior.engine_name,prior.rationale)!=(actor.id,operation,payload.idempotency_key,payload.snapshot_hash,payload.engine_name,payload.rationale):raise HTTPException(409,'Task already decided; decision replay must match exactly')
        return task
    if task.state!='claimed' or task.claimed_by!=actor.id:raise HTTPException(403,'Claim this task before deciding')
    current_target(db,target)
    from kestrel.services.lifecycle import mutable
    mutable(db,impact.matter_id)
    source,policy=w.source(db,actor,source.id,lock=True)
    _,actual=snapshot(db,target,source,db.get(m.AnalysisJob,impact.baseline_job_id))
    if payload.snapshot_hash!=impact.snapshot_hash or actual!=impact.snapshot_hash:raise HTTPException(409,'Impact changed; reassess before deciding')
    if operation=='approve':
        from kestrel.services import jobs
        w.require_policy(db,actor,policy,'analyze')
        from sqlalchemy import func
        if db.scalar(select(func.count()).select_from(m.AnalysisJob).where(m.AnalysisJob.requested_by==actor.id,m.AnalysisJob.state.in_(['queued','running'])))>=20:raise HTTPException(429,'Outstanding job limit reached')
        jobs.authorize(db,actor,target.id);w.processing_allowed(db,policy,external=payload.engine_name=='openai');w.require_verified_ocr(db,source)
        if payload.engine_name=='openai':
            from kestrel.adapters.openai_review import configuration
            enabled,key=configuration()
            if not enabled or not key:raise HTTPException(409,'Enabled OpenAI configuration required')
        if source.extraction_status!='ready':raise HTTPException(409,'Extracted source required')
        w.source_integrity(source,policy)
        db.add(m.AnalysisJob(matter_id=impact.matter_id,playbook_id=target.id,playbook_hash=target.content_hash,requested_by=actor.id,
            idempotency_key='impact-'+task.id,rationale=payload.rationale,created_at=clock(),available_at=clock(),document_version_id=source.id,engine_name=payload.engine_name,impact_task_id=task.id))
    db.add(m.ImpactDecision(task_id=task.id,actor_id=actor.id,operation=operation,rationale=payload.rationale,snapshot_hash=impact.snapshot_hash,idempotency_key=payload.idempotency_key,engine_name=payload.engine_name,created_at=clock()))
    task.state='approved' if operation=='approve' else 'rejected'
    w.event(db,actor,policy,'impact.'+operation,task.id)
    db.commit();return task


def execution_authority(db,job,now):
    task=db.get(m.GovernanceTask,job.impact_task_id);impact=db.get(m.ImpactSnapshot,task.impact_id)
    decision=db.scalar(select(m.ImpactDecision).where(m.ImpactDecision.task_id==task.id))
    target=db.get(m.GovernanceVersion,impact.target_id);current_target(db,target)
    actor=principal(db,db.get(m.Account,job.requested_by),now);assignment(db,actor,task,impact)
    if not decision or decision.operation!='approve' or decision.actor_id!=job.requested_by or decision.engine_name!=job.engine_name or decision.snapshot_hash!=impact.snapshot_hash:raise HTTPException(403,'Exact rerun approval required')
    if task.state not in {'approved','in_progress','failed'} or job.document_version_id!=impact.source_id or job.playbook_id!=impact.target_id:raise HTTPException(409,'Rerun task binding changed')
    if snapshot(db,target,db.get(m.SourceVersion,impact.source_id),db.get(m.AnalysisJob,impact.baseline_job_id))[1]!=impact.snapshot_hash:raise HTTPException(409,'Approved impact snapshot changed')


def reconcile(db,job):
    task=db.get(m.GovernanceTask,job.impact_task_id);impact=db.get(m.ImpactSnapshot,task.impact_id)
    db.flush()
    old={f.rule_id:f for f in db.scalars(select(m.SourceFinding).where(m.SourceFinding.job_id==impact.baseline_job_id))}
    new={f.rule_id:f for f in db.scalars(select(m.SourceFinding).where(m.SourceFinding.job_id==job.id))}
    from kestrel.services.diligence import latest
    for rule in sorted(old.keys()|new.keys()):
        a,b=old.get(rule),new.get(rule);previous=(latest(db,a.id) or a) if a else None
        change='added' if a is None else 'not_redetected' if b is None else 'unchanged' if (previous.summary,previous.evidence_json)==(b.summary,b.evidence_json) else 'changed'
        db.add(m.FindingReconciliation(task_id=task.id,old_finding_id=a.id if a else None,new_finding_id=b.id if b else None,rule_id=rule,change=change,created_at=clock()))
    task.state='pending_attorney_review'


def comparison_output(db,actor,row):
    from kestrel.services.diligence import resolve,output
    result={'id':row.id,'rule_id':row.rule_id,'change':row.change,'old':None,'new':None}
    for side,key in [('old',row.old_finding_id),('new',row.new_finding_id)]:
        if key:
            finding,policy=resolve(db,actor,key,historical=True);result[side]=output(db,finding,policy)
    decision=db.scalar(select(m.ReconciliationDecision).where(m.ReconciliationDecision.comparison_id==row.id))
    result['disposition']=decision.disposition if decision else None
    result['rationale']=decision.rationale if decision else None
    return result


def output(db,actor,task,detail=True):
    task,impact,source,policy=access(db,actor,task.id)
    state=json.loads(impact.snapshot_json);target=db.get(m.GovernanceVersion,impact.target_id)
    job=db.scalar(select(m.AnalysisJob).where(m.AnalysisJob.impact_task_id==task.id))
    reviewed=0
    from kestrel.services.diligence import resolve
    for item in state['findings']:
        _,p=resolve(db,actor,item['id'],historical=True)
        if p.review_state=='reviewed':reviewed+=1
    released=[]
    for release in state['releases']:
        try:
            _,p=w.package(db,actor,release['id'],internal=True)
            if release['released']:released.append(release['id'])
        except HTTPException as error:
            if error.status_code!=403:raise
    comparisons=list(db.scalars(select(m.FindingReconciliation).where(m.FindingReconciliation.task_id==task.id).order_by(m.FindingReconciliation.rule_id)))
    result={'id':task.id,'matter_id':impact.matter_id,'source_id':source.id,'file_name':source.file_name,'source_version':source.version_number,'target_id':target.id,'target_name':target.name,
        'state':task.state,'priority':task.priority,'due_at':task.due_at,'overdue':task.due_at<clock() and task.state not in {'closed','rejected','superseded'},'claimed_by':task.claimed_by,
        'assigned_to_me':actor.id in json.loads(task.assigned_json),'independent':actor.id!=target.author_id,'snapshot_hash':impact.snapshot_hash,'created_at':impact.created_at,
        'classification':policy.classification,'clean_team_scope':policy.clean_team_scope,'job_id':job.id if job else None,'job_state':job.state if job else None,
        'counts':{'findings':len(state['findings']),'reviewed_findings':reviewed,'released_packages_visible':len(released)},'release_followup_required':bool(state['releases']),
        'stale':snapshot(db,target,source,db.get(m.AnalysisJob,impact.baseline_job_id))[1]!=impact.snapshot_hash if task.state in {'open','claimed'} else False,
        'diff':json.loads(impact.diff_json) if detail else [],'comparisons':[comparison_output(db,actor,c) for c in comparisons] if detail else []}
    decision=db.scalar(select(m.ImpactDecision).where(m.ImpactDecision.task_id==task.id))
    closure=db.scalar(select(m.TaskClosure).where(m.TaskClosure.task_id==task.id))
    claimant=db.get(m.Account,task.claimed_by) if task.claimed_by else None
    result['claimed_by_upn']=claimant.username if claimant else None
    result['decision']={'actor_id':decision.actor_id,'operation':decision.operation,'rationale':decision.rationale,'engine_name':decision.engine_name,'created_at':decision.created_at} if detail and decision else None
    result['closure']={'actor_id':closure.actor_id,'rationale':closure.rationale,'release_handling_rationale':closure.release_handling_rationale,'created_at':closure.created_at} if detail and closure else None
    return result


def publications(db,actor):
    if R.SME not in actor.roles: return []
    from kestrel.services.governance import access
    result=[]
    for event,target in db.execute(select(m.ImpactPublication,m.GovernanceVersion).join(m.GovernanceVersion,m.ImpactPublication.target_id==m.GovernanceVersion.id).order_by(m.ImpactPublication.created_at.desc())):
        try:access(actor,target.matter_id)
        except HTTPException:continue
        result.append({'id':event.id,'target_id':target.id,'name':target.name,'state':event.state,'created_at':event.created_at})
    return result


def recover_publication(db,actor,event_id):
    event=db.scalar(select(m.ImpactPublication).where(m.ImpactPublication.id==event_id).with_for_update())
    if event is None:raise HTTPException(404,'Assessment event unavailable')
    target=db.get(m.GovernanceVersion,event.target_id)
    from kestrel.services.governance import access
    from kestrel.services.lifecycle import mutable
    access(actor,target.matter_id);mutable(db,target.matter_id)
    if R.SME not in actor.roles:raise HTTPException(403,'Scoped Legal SME required')
    current_target(db,target)
    if event.state!='failed':raise HTTPException(409,'Failed assessment required')
    event.state='pending';event.processed_at=None
    audit(db,'impact.assessment_retry','authorized',actor.id,category='legal_sme',matter_id=target.matter_id,object_id=event.id);db.commit()


def disposition(db,actor,comparison_id,payload):
    row=db.get(m.FindingReconciliation,comparison_id)
    if row is None:raise HTTPException(404,'Comparison unavailable')
    task,impact,source,policy=access(db,actor,row.task_id,True)
    if task.state!='pending_attorney_review':raise HTTPException(409,'Pending attorney review required')
    from kestrel.services.lifecycle import mutable
    mutable(db,impact.matter_id)
    comparison=comparison_output(db,actor,row)
    if payload.disposition=='accept_reviewed_candidate' and (not comparison['new'] or comparison['new']['review_state']!='reviewed'):raise HTTPException(409,'Reviewed new candidate required')
    if payload.disposition=='retain_prior' and not comparison['old']:raise HTTPException(409,'Prior finding required')
    if payload.disposition=='no_change' and row.change!='unchanged':raise HTTPException(409,'Exact unchanged comparison required')
    if payload.disposition=='not_redetected_reviewed' and row.new_finding_id:raise HTTPException(409,'Not-redetected comparison required')
    if db.scalar(select(m.ReconciliationDecision.id).where(m.ReconciliationDecision.comparison_id==row.id)):raise HTTPException(409,'Disposition already recorded')
    db.add(m.ReconciliationDecision(comparison_id=row.id,actor_id=actor.id,disposition=payload.disposition,rationale=payload.rationale,created_at=clock()))
    w.event(db,actor,policy,'impact.reconcile',row.id);db.commit()


def close(db,actor,task_id,payload):
    task,impact,source,policy=access(db,actor,task_id,True)
    if task.state!='pending_attorney_review':raise HTTPException(409,'Pending attorney review required')
    from kestrel.services.lifecycle import mutable
    mutable(db,impact.matter_id)
    rows=list(db.scalars(select(m.FindingReconciliation).where(m.FindingReconciliation.task_id==task.id)))
    from kestrel.services.diligence import resolve
    for row in rows:
        if not db.scalar(select(m.ReconciliationDecision.id).where(m.ReconciliationDecision.comparison_id==row.id)):raise HTTPException(409,'Record every comparison disposition first')
        if row.new_finding_id:
            _,p=resolve(db,actor,row.new_finding_id)
            if p.review_state not in {'reviewed','rejected'}:raise HTTPException(409,'Lawyer decisions on all new candidates required')
    if json.loads(impact.snapshot_json)['releases'] and len(payload.release_handling_rationale.strip())<5:raise HTTPException(409,'Explain separate audience-release handling before closure')
    db.add(m.TaskClosure(task_id=task.id,actor_id=actor.id,rationale=payload.rationale,release_handling_rationale=payload.release_handling_rationale,created_at=clock()))
    task.state='closed';w.event(db,actor,policy,'impact.close',task.id);db.commit();return task
