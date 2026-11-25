"""Explicitly approved in-app operational escalation; never a legal decision."""
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from kestrel import models as m
from kestrel.domain import Role as R
from kestrel.repositories.identity import principal
from kestrel.services import review_work as rw,review_clocks as c,workflow as w,lifecycle
from kestrel.services.auth import clock
from kestrel.adapters.extraction import canonical,digest


def recipients(db,plan):
    return list(db.scalars(select(m.ReviewSlaPlanRecipient.account_id).where(m.ReviewSlaPlanRecipient.plan_id==plan.id).order_by(m.ReviewSlaPlanRecipient.account_id)))


def decision(db,plan):return db.scalar(select(m.ReviewSlaPlanDecision).where(m.ReviewSlaPlanDecision.plan_id==plan.id))


def validate(db,actor,plan,write=False):
    task,history=rw.task_row(db,actor,plan.task_id,write);rw.retained(db,actor,plan)
    binding=c.current_binding(db,task,history)
    latest=db.scalar(select(m.ReviewSlaEscalationPlan).where(m.ReviewSlaEscalationPlan.task_id==task.id).order_by(m.ReviewSlaEscalationPlan.version_number.desc()))
    src,policy=rw.source(db,actor,task.source_id)
    if history[-1].to_state in {'completed','cancelled'} or not binding or binding.id!=plan.sla_binding_id or latest.id!=plan.id or w.snapshot(db,policy)!=plan.source_snapshot_hash:raise HTTPException(409,'Escalation plan is stale; propose a fresh plan')
    rw.retained(db,actor,binding)
    return task,history,policy


def output(db,actor,plan):
    rw.task_row(db,actor,plan.task_id);rw.retained(db,actor,plan)
    d=decision(db,plan)
    try:validate(db,actor,plan);stale=False
    except HTTPException as e:
        if e.status_code!=409:raise
        stale=True
    return {'id':plan.id,'task_id':plan.task_id,'version':plan.version_number,'warning_percent':plan.warning_percent,'created_by':plan.created_by,'content_hash':plan.content_hash,
        'recipient_ids':recipients(db,plan),'state':d.operation if d else 'proposed','stale':stale,'rationale':plan.rationale}


def plans(db,actor,tid):
    rw.task_row(db,actor,tid)
    return [output(db,actor,p) for p in db.scalars(select(m.ReviewSlaEscalationPlan).where(m.ReviewSlaEscalationPlan.task_id==tid).order_by(m.ReviewSlaEscalationPlan.version_number.desc()))]


def propose(db,actor,tid,p):
    task,history=rw.task_row(db,actor,tid,True)
    if actor.id!=task.created_by and R.SME not in actor.roles:raise HTTPException(403,'Task creator or scoped SME required')
    h=digest(canonical({'task':tid,'payload':p.model_dump()}).encode())
    old=db.scalar(select(m.ReviewSlaEscalationPlan).where(m.ReviewSlaEscalationPlan.created_by==actor.id,m.ReviewSlaEscalationPlan.request_key==p.request_key))
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Plan request key changed')
        return output(db,actor,old)
    binding=c.current_binding(db,task,history)
    if p.expected_revision!=history[-1].revision or not binding or history[-1].to_state in {'completed','cancelled'}:raise HTTPException(409,'Current open task and explicit SLA binding required')
    rw.retained(db,actor,binding)
    previous=db.scalar(select(m.ReviewSlaEscalationPlan).where(m.ReviewSlaEscalationPlan.task_id==tid).order_by(m.ReviewSlaEscalationPlan.version_number.desc()))
    src,policy=rw.source(db,actor,task.source_id,True)
    for account in p.recipient_ids:rw.eligible(db,account,task.source_id,[task,*history,binding])
    content={'task_id':tid,'binding_id':binding.id,'warning_percent':p.warning_percent,'recipient_ids':sorted(p.recipient_ids),'source_snapshot':w.snapshot(db,policy),'rationale':p.rationale}
    row=m.ReviewSlaEscalationPlan(**rw.capture(src,policy),task_id=tid,sla_binding_id=binding.id,version_number=previous.version_number+1 if previous else 1,warning_percent=p.warning_percent,
        created_by=actor.id,rationale=p.rationale,source_snapshot_hash=content['source_snapshot'],content_hash=digest(canonical(content).encode()),request_key=p.request_key,input_hash=h,created_at=clock())
    db.add(row);db.flush()
    for account in sorted(p.recipient_ids):db.add(m.ReviewSlaPlanRecipient(matter_id=task.matter_id,plan_id=row.id,account_id=account))
    rw.audit_work(db,actor,policy,'review.sla.plan.propose',row,[task,*history,binding]);db.flush();value=output(db,actor,row);db.commit();return value


def decide(db,actor,pid,operation,p):
    plan=db.get(m.ReviewSlaEscalationPlan,pid)
    if not plan:raise HTTPException(404,'Plan unavailable')
    task,history,policy=validate(db,actor,plan,True)
    if R.SME not in actor.roles or actor.id==plan.created_by:raise HTTPException(403,'Independent scoped Legal SME required')
    if p.content_hash!=plan.content_hash:raise HTTPException(409,'Exact plan hash required')
    if decision(db,plan):raise HTTPException(409,'Plan already decided')
    for account in recipients(db,plan):rw.eligible(db,account,task.source_id,[plan,task,*history])
    src,_=rw.source(db,actor,task.source_id)
    row=m.ReviewSlaPlanDecision(**rw.capture(src,policy),plan_id=pid,actor_id=actor.id,operation=operation,content_hash=plan.content_hash,rationale=p.rationale,created_at=clock())
    db.add(row);rw.audit_work(db,actor,policy,'review.sla.plan.'+operation,row,[plan,task,*history]);db.flush();value=output(db,actor,plan);db.commit();return value


def alert_access(db,actor,aid):
    row=db.get(m.ReviewSlaAlert,aid)
    if not row:raise HTTPException(404,'Alert unavailable')
    rw.task_row(db,actor,row.task_id);rw.retained(db,actor,row)
    plan=db.get(m.ReviewSlaEscalationPlan,row.plan_id);rw.retained(db,actor,plan)
    recipient=db.scalar(select(m.ReviewSlaAlertRecipient).where(m.ReviewSlaAlertRecipient.alert_id==aid,m.ReviewSlaAlertRecipient.account_id==actor.id))
    if not recipient:raise HTTPException(403,'Own scoped alert required')
    return row,recipient


def alert_output(db,actor,row,recipient):
    events=list(db.scalars(select(m.ReviewSlaAlertDisposition).where(m.ReviewSlaAlertDisposition.alert_id==row.id).order_by(m.ReviewSlaAlertDisposition.revision)))
    for e in events:rw.retained(db,actor,e)
    return {'id':row.id,'task_id':row.task_id,'source_id':row.source_id,'level':row.level,'created_at':row.created_at,'business_elapsed_seconds':row.business_elapsed_seconds,'budget_seconds':row.budget_seconds,
        'read':db.scalar(select(m.ReviewSlaAlertRead.id).where(m.ReviewSlaAlertRead.recipient_id==recipient.id)) is not None,'revision':events[-1].revision if events else 0,
        'state':events[-1].operation if events else 'open','history':[{'operation':e.operation,'actor_id':e.actor_id,'rationale':e.rationale,'created_at':e.created_at} for e in events]}


def inbox(db,actor,matter):
    rw.internal(actor);w.legal(actor,matter);result=[]
    query=select(m.ReviewSlaAlert).join(m.ReviewSlaAlertRecipient,m.ReviewSlaAlertRecipient.alert_id==m.ReviewSlaAlert.id).where(m.ReviewSlaAlert.matter_id==matter,m.ReviewSlaAlertRecipient.account_id==actor.id).order_by(m.ReviewSlaAlert.created_at.desc(),m.ReviewSlaAlert.id).limit(500)
    for row in db.scalars(query):
        try:row,recipient=alert_access(db,actor,row.id);result.append(alert_output(db,actor,row,recipient))
        except HTTPException as e:
            if e.status_code!=403:raise
    return result


def read(db,actor,aid):
    row,recipient=alert_access(db,actor,aid)
    if not db.scalar(select(m.ReviewSlaAlertRead.id).where(m.ReviewSlaAlertRead.recipient_id==recipient.id)):
        db.add(m.ReviewSlaAlertRead(recipient_id=recipient.id,account_id=actor.id,occurred_at=clock()));db.flush()
    _,policy=rw.source(db,actor,row.source_id)
    rw.audit_work(db,actor,policy,'review.sla.alert.read',row)
    value=alert_output(db,actor,row,recipient);db.commit();return value


def disposition(db,actor,aid,p):
    row,recipient=alert_access(db,actor,aid);task,history=rw.task_row(db,actor,row.task_id,True)
    prior=db.scalar(select(m.ReviewSlaAlertDisposition).where(m.ReviewSlaAlertDisposition.alert_id==aid).order_by(m.ReviewSlaAlertDisposition.revision.desc()))
    if p.expected_revision!=(prior.revision if prior else 0) or (prior and prior.operation=='close'):raise HTTPException(409,'Alert disposition changed or closed')
    if p.operation=='close' and actor.id!=task.created_by and R.SME not in actor.roles:raise HTTPException(403,'Task creator or scoped SME required to close')
    src,policy=rw.source(db,actor,row.source_id,True)
    event=m.ReviewSlaAlertDisposition(**rw.capture(src,policy),alert_id=aid,revision=p.expected_revision+1,actor_id=actor.id,operation=p.operation,rationale=p.rationale,created_at=clock())
    db.add(event);rw.audit_work(db,actor,policy,'review.sla.alert.'+p.operation,event,[row,task,*history]);db.flush();value=alert_output(db,actor,row,recipient);db.commit();return value


def scan_due(sessions,limit=20):
    """Bounded round-robin scan. Recheck approving principal, source and each recipient."""
    emitted=0
    with sessions() as db:
        cursor=db.get(m.ReviewSlaAlertCursor,'worker')
        if not cursor:cursor=m.ReviewSlaAlertCursor(id='worker',last_plan_id=None);db.add(cursor);db.flush()
        query=select(m.ReviewSlaEscalationPlan).order_by(m.ReviewSlaEscalationPlan.id).limit(limit)
        if cursor.last_plan_id:query=query.where(m.ReviewSlaEscalationPlan.id>cursor.last_plan_id)
        rows=list(db.scalars(query))
        if not rows:cursor.last_plan_id=None;db.commit();return 0
        for plan in rows:
            cursor.last_plan_id=plan.id
            d=decision(db,plan)
            if not d or d.operation!='approve' or d.content_hash!=plan.content_hash:continue
            try:
                account=db.get(m.Account,d.actor_id)
                if not account or not account.active:continue
                actor=principal(db,account,clock())
                if R.SME not in actor.roles or actor.id==plan.created_by:continue
                task,history,policy=validate(db,actor,plan,True);rw.retained(db,actor,d)
                sla=c.metrics(db,actor,task,history)['sla']
                if sla['status'] not in {'within_budget','breached'}:continue
                elapsed=sla['business_elapsed_seconds'];budget=sla['budget_seconds']
                level='breach' if elapsed>budget else 'warning' if elapsed*100>=budget*plan.warning_percent else None
                if not level or db.scalar(select(m.ReviewSlaAlert.id).where(m.ReviewSlaAlert.plan_id==plan.id,m.ReviewSlaAlert.level==level)):continue
                permitted=[]
                for uid in recipients(db,plan):
                    try:rw.eligible(db,uid,task.source_id,[plan,d,task,*history]);permitted.append(uid)
                    except HTTPException as e:
                        if e.status_code not in {403,404}:raise
                if not permitted:continue
                src,_=rw.source(db,actor,task.source_id)
                alert=m.ReviewSlaAlert(**rw.capture(src,policy),plan_id=plan.id,task_id=task.id,level=level,business_elapsed_seconds=elapsed,budget_seconds=budget,created_at=clock())
                db.add(alert);db.flush()
                for uid in permitted:db.add(m.ReviewSlaAlertRecipient(matter_id=task.matter_id,alert_id=alert.id,account_id=uid))
                rw.audit_work(db,SimpleNamespace(id=None),policy,'review.sla.alert.'+level,alert,[plan,d,task,*history]);emitted+=1
            except HTTPException as e:
                if e.status_code not in {403,404,409,413}:raise
        try:db.commit()
        except IntegrityError:db.rollback();return 0
    return emitted
