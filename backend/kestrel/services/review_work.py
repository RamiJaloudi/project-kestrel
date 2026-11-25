"""Source-bound custody and parallel coordination. Task completion is not legal approval."""
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Organization as O,Role as R
from kestrel.repositories.identity import principal
from kestrel.repositories.document_identity import attach
from kestrel.services import workflow as w
from kestrel.services.lifecycle import mutable
from kestrel.services.policy import require_retained
from kestrel.services.auth import clock
from kestrel.adapters.extraction import canonical,digest


def internal(actor):
    if actor.org!=O.FIRM or not actor.roles&w.LEGAL:raise HTTPException(403,'Internal source-work access required')


def source(db,actor,sid,write=False):
    internal(actor)
    raw=db.get(m.SourceVersion,sid)
    if raw is None:raise HTTPException(404,'Source unavailable')
    w.legal(actor,raw.matter_id)
    if write:
        db.scalar(select(m.Matter).where(m.Matter.id==raw.matter_id).with_for_update())
        mutable(db,raw.matter_id)
    row,policy=w.source(db,actor,sid,historical=not write)
    w.source_integrity(row,policy)
    if write and (policy.superseded or policy.signing_frozen):raise HTTPException(409,'Current unfrozen source required')
    return row,policy


def retained(db,actor,row):
    src,policy=source(db,actor,row.source_id)
    action='historical_read' if policy.superseded else 'read' if policy.classification_confirmed else 'triage'
    require_retained(db,actor,policy,row.retained_classification,row.retained_scope,action,clock())
    return src,policy


def capture(src,policy):
    return {'matter_id':src.matter_id,'source_id':src.id,'retained_classification':policy.classification,'retained_scope':policy.clean_team_scope}


def fingerprint(p):return digest(canonical(p.model_dump()).encode())


def audit_work(db,actor,policy,action,record,related=()):
    from types import SimpleNamespace
    scopes={p.retained_scope for p in [record,*related] if p.retained_classification=='clean_team'}
    if policy.classification=='clean_team':scopes.add(policy.clean_team_scope)
    if scopes:
        for scope in sorted(s for s in scopes if s):
            marker=SimpleNamespace(id=policy.id,matter_id=policy.matter_id,classification='clean_team',clean_team_scope=scope)
            w.event(db,actor,marker,action,record.id)
    else:w.event(db,actor,policy,action,record.id)


def retry(db,model,actor,key,input_hash):
    row=db.scalar(select(model).where(model.created_by==actor.id,model.request_key==key))
    if row and row.input_hash!=input_hash:raise HTTPException(409,'Request key reused with changed content')
    return row


def person(db,uid):
    a=db.get(m.Account,uid)
    if not a:raise HTTPException(409,'Assigned identity unavailable')
    return {'id':a.id,'name':a.display_name or a.username,'upn':a.username}


def eligible(db,actor,sid,required_records=()):
    account=db.get(m.Account,actor)
    if not account or not account.active:raise HTTPException(403,'Assignee is not eligible for this source')
    other=principal(db,account,clock())
    source(db,other,sid)
    for record in required_records:retained(db,other,record)
    return person(db,account.id)


def events(db,task):
    rows=list(db.scalars(select(m.ReviewTaskEvent).where(m.ReviewTaskEvent.task_id==task.id).order_by(m.ReviewTaskEvent.revision).limit(501)))
    if not rows:raise HTTPException(409,'Task has no initial assignment')
    if len(rows)>500:raise HTTPException(413,'Task event history exceeds the local review limit')
    return rows


def task_row(db,actor,tid,write=False):
    internal(actor)
    row=db.get(m.ReviewTask,tid)
    if row is None:raise HTTPException(404,'Task unavailable')
    source(db,actor,row.source_id,write)
    if write:row=db.scalar(select(m.ReviewTask).where(m.ReviewTask.id==tid).with_for_update().execution_options(populate_existing=True))
    retained(db,actor,row)
    history=events(db,row)
    for e in history:retained(db,actor,e)
    return row,history


def task_output(db,actor,row):
    from kestrel.services.review_clocks import metrics
    _,history=task_row(db,actor,row.id);last=history[-1]
    timestamps={'created_at':row.created_at,'notified_at':history[0].occurred_at}
    names={'assign':'assigned_at','reassign':'reassigned_at','accept':'accepted_at','start':'review_started_at','pause':'review_paused_at',
        'resume':'review_resumed_at','complete':'completed_at','cancel':'cancelled_at','reopen':'reopened_at'}
    for e in history:
        if e.operation in names:timestamps[names[e.operation]]=e.occurred_at
        if e.operation in {'assign','reassign','reopen'}:timestamps['assigned_at']=e.occurred_at
        if e.operation=='opened':
            timestamps.setdefault('first_opened_at',e.occurred_at);timestamps['latest_opened_at']=e.occurred_at
    timestamps['last_activity_at']=last.occurred_at
    assigned=timestamps['assigned_at'];end=last.occurred_at if last.to_state in {'completed','cancelled'} else clock()
    return {'id':row.id,'source_id':row.source_id,'document_id':row.document_id,'stage':row.stage,'created_by':row.created_by,
        'state':last.to_state,'revision':last.revision,'assignee':person(db,last.assignee_id),'due_at':last.due_at,'timestamps':timestamps,
        'timing':metrics(db,actor,row,history),
        'events':[{'id':e.id,'revision':e.revision,'operation':e.operation,'from_state':e.from_state,'to_state':e.to_state,
            'assignee':person(db,e.assignee_id),'actor_id':e.actor_id,'occurred_at':e.occurred_at,'due_at':e.due_at,'rationale':e.rationale} for e in history]}


def add_event(db,actor,task,src,policy,revision,operation,state,assignee,due,rationale,key,h,prior=None):
    e=m.ReviewTaskEvent(**capture(src,policy),task_id=task.id,revision=revision,operation=operation,
        from_state=prior.to_state if prior else None,to_state=state,assignee_id=assignee,actor_id=actor.id,due_at=due,
        rationale=rationale,request_key=key,input_hash=h,occurred_at=clock())
    db.add(e);db.flush()
    recipients={assignee,task.created_by}
    if prior:recipients.add(prior.assignee_id)
    for uid in sorted(recipients):db.add(m.ReviewTaskNotification(matter_id=src.matter_id,task_id=task.id,event_id=e.id,account_id=uid,created_at=e.occurred_at))
    # Audit references resolve the immutable event, retaining its captured clean-team restriction.
    audit_work(db,actor,policy,'review.task.'+operation,e,[task,*events(db,task)])
    return e


def create_task(db,actor,sid,p,*,commit=True):
    src,policy=source(db,actor,sid,True);h=digest(canonical({'source_id':sid,'input':p.model_dump()}).encode())
    old=retry(db,m.ReviewTask,actor,p.request_key,h)
    if old:return task_output(db,actor,old)
    eligible(db,p.assignee_id,sid)
    if p.due_at is not None and p.due_at<clock():raise HTTPException(422,'Choose a future UTC deadline')
    doc=attach(db,src)
    row=m.ReviewTask(**capture(src,policy),document_id=doc.id,stage=p.stage,created_by=actor.id,request_key=p.request_key,input_hash=h,source_snapshot_hash=w.snapshot(db,policy),created_at=clock())
    db.add(row);db.flush();add_event(db,actor,row,src,policy,1,'assign','assigned',p.assignee_id,p.due_at,p.rationale,p.request_key,h)
    db.flush();result=task_output(db,actor,row);db.commit() if commit else db.flush();return result


def transition(db,actor,tid,p,*,commit=True):
    row,history=task_row(db,actor,tid,True);last=history[-1];h=fingerprint(p)
    replay=next((e for e in history if e.actor_id==actor.id and e.request_key==p.request_key),None)
    if replay:
        if replay.input_hash!=h:raise HTTPException(409,'Event request key reused with changed content')
        return task_output(db,actor,row)
    if p.expected_revision!=last.revision:raise HTTPException(409,'Task changed; refresh before deciding')
    manager=actor.id==row.created_by or R.SME in actor.roles
    operation=p.operation;state=last.to_state;assignee=last.assignee_id;due=last.due_at
    transitions={'accept':('assigned','accepted'),'start':('accepted','in_progress'),'pause':('in_progress','paused'),
        'resume':('paused','in_progress'),'complete':('in_progress','completed')}
    if operation in transitions:
        if actor.id!=assignee:raise HTTPException(403,'Only the current assignee may record their review activity')
        previous,state=transitions[operation]
        if last.to_state!=previous:raise HTTPException(409,'Task state does not permit this activity')
    elif operation=='opened':
        if actor.id!=assignee:raise HTTPException(403,'Only the current assignee may record opening their task')
        if state in {'completed','cancelled'}:raise HTTPException(409,'Reopen the task before recording source activity')
    else:
        if not manager:raise HTTPException(403,'Task creator or scoped Legal SME required')
        if operation=='reopen':
            if state not in {'completed','cancelled'}:raise HTTPException(409,'Only completed or cancelled tasks may reopen')
            eligible(db,assignee,row.source_id,[row,*history]);state='assigned'
        elif state in {'completed','cancelled'}:raise HTTPException(409,'Reopen the task before changing it')
        elif operation=='cancel':state='cancelled'
        elif operation=='reassign':
            if not p.assignee_id or p.assignee_id==assignee:raise HTTPException(422,'Choose a different eligible assignee')
            eligible(db,p.assignee_id,row.source_id,[row,*history]);assignee=p.assignee_id;state='assigned'
        elif operation=='deadline':
            if p.due_at is not None and p.due_at<clock():raise HTTPException(422,'Choose a future UTC deadline')
            due=p.due_at
    if operation not in {'reassign'} and p.assignee_id is not None:raise HTTPException(422,'Assignee changes require reassignment')
    if operation!='deadline' and p.due_at is not None:raise HTTPException(422,'Deadline changes require a deadline event')
    src,policy=source(db,actor,row.source_id,True)
    add_event(db,actor,row,src,policy,last.revision+1,operation,state,assignee,due,p.rationale,p.request_key,h,last)
    if operation in {'pause','complete','cancel','reassign','reopen'}:
        from kestrel.services.review_clocks import stop_for_task
        stop_for_task(db,row,actor)
    db.flush();result=task_output(db,actor,row);db.commit() if commit else db.flush();return result


def custodian_output(db,actor,link):
    retained(db,actor,link);custodian=db.get(m.RecordCustodian,link.custodian_id);retained(db,actor,custodian)
    retired=db.scalar(select(m.CustodianLinkRetirement).where(m.CustodianLinkRetirement.link_id==link.id))
    if retired:retained(db,actor,retired)
    return {'id':link.id,'custodian':{'id':custodian.id,'display_name':custodian.display_name,'custodian_type':custodian.custodian_type,'upn':custodian.upn},
        'custody_role':link.custody_role,'provenance':link.provenance,'effective_from':link.effective_from,'effective_until':link.effective_until,
        'retired':bool(retired),'retired_at':retired.created_at if retired else None,'retirement_rationale':retired.rationale if retired else None}


def create_custodian(db,actor,sid,p):
    src,policy=source(db,actor,sid,True);h=digest(canonical({'source_id':sid,'input':p.model_dump()}).encode())
    old=retry(db,m.DocumentCustodian,actor,p.request_key,h)
    if old:return custodian_output(db,actor,old)
    if p.custodian_id:
        custodian=db.get(m.RecordCustodian,p.custodian_id)
        if custodian is None:raise HTTPException(404,'Custodian unavailable')
        retained(db,actor,custodian)
        if custodian.matter_id!=src.matter_id:raise HTTPException(403,'Custodian outside source matter')
    else:
        custodian=m.RecordCustodian(**capture(src,policy),display_name=p.display_name,custodian_type=p.custodian_type,upn=p.upn,created_by=actor.id,created_at=clock())
        db.add(custodian);db.flush()
    doc=attach(db,src)
    link=m.DocumentCustodian(**capture(src,policy),document_id=doc.id,custodian_id=custodian.id,custody_role=p.custody_role,provenance=p.provenance,
        effective_from=p.effective_from,effective_until=p.effective_until,created_by=actor.id,request_key=p.request_key,input_hash=h,created_at=clock())
    db.add(link);db.flush();audit_work(db,actor,policy,'review.custodian.link',link,[custodian])
    result=custodian_output(db,actor,link);db.commit();return result


def retire_custodian(db,actor,lid,p):
    internal(actor);link=db.get(m.DocumentCustodian,lid)
    if not link:raise HTTPException(404,'Custodian link unavailable')
    src,policy=source(db,actor,link.source_id,True);custodian_output(db,actor,link)
    if actor.id!=link.created_by and R.SME not in actor.roles:raise HTTPException(403,'Link creator or scoped Legal SME required')
    old=db.scalar(select(m.CustodianLinkRetirement).where(m.CustodianLinkRetirement.link_id==lid))
    if old:
        if old.rationale!=p.rationale:raise HTTPException(409,'Retirement already recorded; history is immutable')
    else:
        old=m.CustodianLinkRetirement(**capture(src,policy),link_id=lid,actor_id=actor.id,rationale=p.rationale,created_at=clock());db.add(old);db.flush()
        audit_work(db,actor,policy,'review.custodian.retire',old,[link,db.get(m.RecordCustodian,link.custodian_id)])
    result=custodian_output(db,actor,link);db.commit();return result


def party_output(db,actor,row):
    retained(db,actor,row)
    return {k:getattr(row,k) for k in ['id','name','party_role','provenance','created_at','created_by']}


def create_party(db,actor,sid,p):
    src,policy=source(db,actor,sid,True);h=digest(canonical({'source_id':sid,'input':p.model_dump()}).encode())
    old=retry(db,m.DocumentParty,actor,p.request_key,h)
    if old:return party_output(db,actor,old)
    row=m.DocumentParty(**capture(src,policy),document_id=attach(db,src).id,name=p.name,party_role=p.party_role,provenance=p.provenance,
        created_by=actor.id,request_key=p.request_key,input_hash=h,created_at=clock())
    db.add(row);db.flush();audit_work(db,actor,policy,'review.party.record',row)
    result=party_output(db,actor,row);db.commit();return result


def source_panel(db,actor,sid):
    src,policy=source(db,actor,sid)
    def permitted(model,render):
        result=[]
        for row in db.scalars(select(model).where(model.source_id==sid).order_by(model.created_at,model.id).limit(101)):
            try:result.append(render(db,actor,row))
            except HTTPException as e:
                if e.status_code!=403:raise
        if len(result)>100:raise HTTPException(413,'Source work exceeds local panel limit')
        return result
    result={'source_id':sid,'custodians':permitted(m.DocumentCustodian,custodian_output),'parties':permitted(m.DocumentParty,party_output),'tasks':permitted(m.ReviewTask,task_output)}
    w.event(db,actor,policy,'review.source_work.view',sid);db.commit();return result


def eligible_people(db,actor,sid):
    source(db,actor,sid);result=[]
    for account in db.scalars(select(m.Account).where(m.Account.active==True).order_by(m.Account.id).limit(501)):
        try:result.append(eligible(db,account.id,sid))
        except HTTPException as e:
            if e.status_code!=403:raise
    return result


def notifications(db,actor,matter):
    internal(actor);w.legal(actor,matter);result=[]
    for n in db.scalars(select(m.ReviewTaskNotification).where(m.ReviewTaskNotification.matter_id==matter,m.ReviewTaskNotification.account_id==actor.id).order_by(m.ReviewTaskNotification.created_at.desc(),m.ReviewTaskNotification.id).limit(1000)):
        try:
            task,history=task_row(db,actor,n.task_id)
            # Old assignees may read only if current source and retained task policy still allow it.
            result.append({'id':n.id,'task_id':n.task_id,'source_id':task.source_id,'stage':task.stage,'state':history[-1].to_state,
                'created_at':n.created_at,'read':db.scalar(select(m.ReviewNotificationRead.id).where(m.ReviewNotificationRead.notification_id==n.id)) is not None})
        except HTTPException as e:
            if e.status_code!=403:raise
    return result


def acknowledge(db,actor,nid):
    internal(actor);n=db.get(m.ReviewTaskNotification,nid)
    if not n or n.account_id!=actor.id:raise HTTPException(403,'Own permitted notification required')
    task_row(db,actor,n.task_id)
    # Operational receipt is allowed after freeze, does not alter signed work content.
    db.scalar(select(m.ReviewTaskNotification).where(m.ReviewTaskNotification.id==nid).with_for_update())
    old=db.scalar(select(m.ReviewNotificationRead).where(m.ReviewNotificationRead.notification_id==nid))
    if not old:db.add(m.ReviewNotificationRead(notification_id=nid,account_id=actor.id,occurred_at=clock()))
    db.commit();return {'read':True}


def audit_records(db,object_id):
    """Resolve retained restrictions for scoped audit exports, without returning text."""
    from kestrel.services.financial_context import audit_records as context_records
    records=context_records(db,object_id)
    if records:return records
    from kestrel.services.agent_registry import audit_records as agent_records
    records=agent_records(db,object_id)
    if records:return records
    from kestrel.services.ddr_runs import audit_records as graph_records
    records=graph_records(db,object_id)
    if records:return records
    from kestrel.services.table_views import audit_records as table_records
    records=table_records(db,object_id)
    if records:return records
    case=db.get(m.FinancialReconciliation,object_id)
    if case:return [db.get(m.FinancialFact,case.left_id),db.get(m.FinancialFact,case.right_id)]
    request=db.get(m.ChecklistRequestEvent,object_id)
    if request:return list(db.scalars(select(m.ChecklistRequestEvidence).where(m.ChecklistRequestEvidence.request_event_id==object_id)))
    for model in [m.IntelligenceOverride,m.IntelligenceOverrideDecision,m.IntelligenceAlert,m.IntelligenceAlertRecipient,m.IntelligenceAlertDisposition,m.FinancialFact,m.FinancialFactDecision,m.SourceEmbedding,m.ContentImpactTask,m.DisclosurePlan,m.DisclosurePlanReview,m.DisclosureArtifact,m.DisclosureValidation,m.DisclosureDecision,m.ContentLabelAssertion,m.ContentLabelDecision,m.ContentLabelImpact,m.ChecklistRequestEvidence,m.ReviewSlaEscalationPlan,m.ReviewSlaPlanDecision,m.ReviewSlaAlert,m.ReviewSlaAlertDisposition,m.RecordCustodian,m.DocumentCustodian,m.CustodianLinkRetirement,m.DocumentParty,m.ReviewTask,m.ReviewTaskEvent,m.ReviewSession,m.ReviewSessionReceipt,m.ReviewSlaBinding]:
        row=db.get(model,object_id)
        if row is None:continue
        records=[row]
        if isinstance(row,m.IntelligenceOverrideDecision):records.append(db.get(m.IntelligenceOverride,row.override_id))
        if isinstance(row,(m.IntelligenceAlert,m.IntelligenceAlertRecipient,m.IntelligenceAlertDisposition)):
            alert=row if isinstance(row,m.IntelligenceAlert) else db.get(m.IntelligenceAlert,row.alert_id)
            task=db.get(m.ReviewTask,alert.task_id)
            records.extend([alert,task,*events(db,task)])
        if isinstance(row,m.CustodianLinkRetirement):
            link=db.get(m.DocumentCustodian,row.link_id);records.append(link);records.append(db.get(m.RecordCustodian,link.custodian_id))
        if isinstance(row,m.DocumentCustodian):records.append(db.get(m.RecordCustodian,row.custodian_id))
        if isinstance(row,(m.ReviewTask,m.ReviewTaskEvent)):
            task=row if isinstance(row,m.ReviewTask) else db.get(m.ReviewTask,row.task_id)
            records.extend([task,*events(db,task)])
        if isinstance(row,(m.ReviewSession,m.ReviewSessionReceipt,m.ReviewSlaBinding)):
            session=db.get(m.ReviewSession,row.session_id) if isinstance(row,m.ReviewSessionReceipt) else row if isinstance(row,m.ReviewSession) else None
            task=db.get(m.ReviewTask,session.task_id if session else row.task_id)
            records.extend([task,*events(db,task)])
            if session:
                records.append(session)
                records.extend(db.scalars(select(m.ReviewSessionReceipt).where(m.ReviewSessionReceipt.session_id==session.id)))
        if isinstance(row,(m.ReviewSlaEscalationPlan,m.ReviewSlaPlanDecision,m.ReviewSlaAlert,m.ReviewSlaAlertDisposition)):
            plan=db.get(m.ReviewSlaEscalationPlan,row.plan_id) if hasattr(row,'plan_id') else row if isinstance(row,m.ReviewSlaEscalationPlan) else db.get(m.ReviewSlaEscalationPlan,db.get(m.ReviewSlaAlert,row.alert_id).plan_id)
            task=db.get(m.ReviewTask,plan.task_id);records.extend([plan,task,*events(db,task)])
        return records
    return []
