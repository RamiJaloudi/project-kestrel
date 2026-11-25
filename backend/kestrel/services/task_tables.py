"""Internal task metadata: retained history is part of every row's authorization.

Bulk commands reuse actual source-work events. Successful rows consume the UUID;
an entirely unsuccessful attempt has no durable batch receipt or consumed key.
"""
from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from kestrel import models as m
from kestrel.domain import Role as R
from kestrel.adapters.extraction import canonical,digest
from kestrel.schemas.data_tables import Tasks
from kestrel.schemas.review_work import TaskEvent
from kestrel.services import review_work as rw,workflow as w,lifecycle
from kestrel.services.auth import clock,audit,authenticate
from kestrel.services.policy import require_retained

COLUMNS=['id','matter_id','source_id','document_id','logical_key','file_name','stage','status','revision',
    'assignee_id','assignee_name','created_by','created_by_name','due_at','created_at','last_activity_at','historical','can_reassign']
UNAVAILABLE={403,404,409,413}


@dataclass
class Scope:
    task:object
    history:list
    policy:object
    integrity_hash:str


def access(actor,matter):
    rw.internal(actor);w.legal(actor,matter)


def visible_person(db,uid,task,history):
    try:return rw.eligible(db,uid,task.source_id,[task,*history])
    except HTTPException as error:
        if error.status_code not in UNAVAILABLE:raise
        return None


def material(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns}


def record(db,actor,tid,*,historical=False,export=False):
    task,history=rw.task_row(db,actor,tid);last=history[-1]
    src,policy=rw.source(db,actor,task.source_id)
    if policy.superseded and not historical:raise HTTPException(404,'Current task source required')
    source_union={}
    for retained in [task,*history]:
        if retained.source_id not in source_union:
            bound_source,bound_policy=rw.source(db,actor,retained.source_id)
            source_union[retained.source_id]=(bound_source,bound_policy)
        bound_source,bound_policy=source_union[retained.source_id]
        if export:
            w.require_policy(db,actor,bound_policy,'export_metadata')
            require_retained(db,actor,bound_policy,retained.retained_classification,retained.retained_scope,'export_metadata',clock())
    assignee=visible_person(db,last.assignee_id,task,history)
    creator=visible_person(db,task.created_by,task,history)
    frozen=db.scalar(select(m.MatterLifecycle.frozen).where(m.MatterLifecycle.matter_id==task.matter_id))
    can_manage=actor.id==task.created_by or R.SME in actor.roles
    value={'id':task.id,'matter_id':task.matter_id,'source_id':src.id,'document_id':task.document_id,
        'logical_key':src.logical_key,'file_name':src.file_name,'stage':task.stage,'status':last.to_state,
        'revision':last.revision,'assignee_id':assignee['id'] if assignee else None,'assignee_name':assignee['name'] if assignee else None,
        'created_by':creator['id'] if creator else None,'created_by_name':creator['name'] if creator else None,
        'due_at':last.due_at,'created_at':task.created_at,'last_activity_at':last.occurred_at,
        'historical':policy.superseded,'can_reassign':bool(can_manage and last.to_state not in {'completed','cancelled'} and not policy.superseded and not policy.signing_frozen and not frozen)}
    version=digest(canonical({'task':material(task),'events':[material(e) for e in history],
        'sources':sorted([{'id':bound.id,'bytes_hash':bound.bytes_hash,'text_hash':bound.text_hash,'policy_hash':w.snapshot(db,bound_policy)}
            for bound,bound_policy in source_union.values()],key=lambda s:s['id'])}).encode())
    return value,Scope(task,history,policy,version)


def collect(db,actor,matter,filters=None,ids=None,*,export=False):
    access(actor,matter);filters=filters or Tasks()
    statement=select(m.ReviewTask.id).where(m.ReviewTask.matter_id==matter)
    if ids is not None:statement=statement.where(m.ReviewTask.id.in_(ids))
    if filters.stage:statement=statement.where(m.ReviewTask.stage==filters.stage)
    rows=[]
    for tid in db.scalars(statement.order_by(m.ReviewTask.created_at,m.ReviewTask.id)):
        try:value,scope=record(db,actor,tid,historical=filters.historical,export=export)
        except HTTPException as error:
            if error.status_code not in UNAVAILABLE:raise
            continue
        if filters.status and value['status']!=filters.status:continue
        if filters.assignee_id and value['assignee_id']!=filters.assignee_id:continue
        if filters.created_by and value['created_by']!=filters.created_by:continue
        if filters.mine and value['assignee_id']!=actor.id:continue
        rows.append((value,scope))
    return rows


def signature(records):
    return digest(canonical([(row,scope.integrity_hash) for row,scope in records]).encode())


def event(db,actor,scope,operation):
    rw.audit_work(db,actor,scope.policy,operation,scope.task,scope.history)


def managed(db,actor,matter,item):
    candidate=db.get(m.ReviewTask,item.id)
    if candidate is None or candidate.matter_id!=matter:raise HTTPException(404,'Selected task unavailable')
    task,history=rw.task_row(db,actor,item.id,True)
    if task.matter_id!=matter:raise HTTPException(403,'Selected task unavailable')
    if actor.id!=task.created_by and R.SME not in actor.roles:raise HTTPException(403,'Task creator or scoped Legal SME required')
    if history[-1].to_state in {'completed','cancelled'}:raise HTTPException(409,'Reopen the task before changing it')
    if history[-1].revision!=item.expected_revision:raise HTTPException(409,'Task changed; refresh before deciding')
    return task,history


def people(db,actor,p,request):
    from kestrel.services import data_tables as tables
    tables.throttle(actor);access(actor,p.matter_id);before,actor=tables.begin(db,request,p.matter_id)
    def prepare(fresh):
        selected=[managed(db,fresh,p.matter_id,item) for item in p.items]
        excluded={history[-1].assignee_id for _,history in selected};result=[]
        for uid in db.scalars(select(m.Account.id).where(m.Account.active==True).order_by(m.Account.id)):
            if uid in excluded:continue
            try:
                person=None
                for task,history in selected:person=rw.eligible(db,uid,task.source_id,[task,*history])
            except HTTPException as error:
                if error.status_code not in UNAVAILABLE:raise
                continue
            result.append(person)
            if len(result)>500:raise HTTPException(413,'Narrow the eligible people directory before bulk assignment')
        stamp=[record(db,fresh,t.id)[1].integrity_hash for t,_ in selected]
        return result,stamp
    result,stamp=prepare(actor);actor=tables.finish(db,request,p.matter_id,before)
    current,current_stamp=prepare(actor)
    if current!=result or current_stamp!=stamp:raise HTTPException(409,'Task selection or eligible people changed; refresh before assigning')
    return result


def reassign(db,actor,p,request):
    from kestrel.services import data_tables as tables
    tables.throttle(actor);access(actor,p.matter_id);before,actor=tables.begin(db,request,p.matter_id)
    # Python sqlite3 legacy transaction control does not BEGIN on SELECT. A bare
    # first SAVEPOINT would otherwise commit on RELEASE before the final PDP check.
    connection=db.connection()
    if connection.dialect.name=='sqlite' and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    if connection.dialect.name=='postgresql':
        # Review clocks already lock Matter -> Task -> Account. A new Account ->
        # Matter order would deadlock; this private namespace precedes Matter and
        # is acquired only here, across this actor's batches in any matter.
        namespace=int(digest(('kestrel.taskbulk.actor:'+actor.id).encode())[:16],16)
        if namespace>=2**63:namespace-=2**64
        db.execute(select(func.pg_advisory_xact_lock(namespace)))
    # Matter lock also serializes source-work governance/signing.
    db.scalar(select(m.Matter).where(m.Matter.id==p.matter_id).with_for_update())
    lifecycle.mutable(db,p.matter_id)
    prefix='taskbulk:'+str(p.request_key)+':'
    request_hash=digest(canonical(p.model_dump(mode='json')).encode());key=prefix+request_hash
    used=list(db.scalars(select(m.ReviewTaskEvent.request_key).where(m.ReviewTaskEvent.actor_id==actor.id,m.ReviewTaskEvent.request_key.startswith(prefix,autoescape=True))))
    if any(value!=key for value in used):raise HTTPException(409,'Successful reassignment key reused with changed content')
    results=[]
    for item in p.items:
        # Each item starts from current server identity; the caller cannot supply roles.
        db.expire_all();actor=authenticate(db,request)[2];access(actor,p.matter_id)
        try:
            with db.begin_nested():
                candidate=db.get(m.ReviewTask,item.id)
                if candidate is None or candidate.matter_id!=p.matter_id:raise HTTPException(404,'Selected task unavailable')
                task,history=rw.task_row(db,actor,item.id,True)
                if task.matter_id!=p.matter_id:raise HTTPException(403,'Selected task unavailable')
                if actor.id!=task.created_by and R.SME not in actor.roles:raise HTTPException(403,'Task creator or scoped Legal SME required')
                replay=next((e for e in history if e.actor_id==actor.id and e.request_key==key),None)
                # Replays also require current target clearance for the full retained union.
                rw.eligible(db,p.assignee_id,task.source_id,[task,*history])
                event_input=TaskEvent(operation='reassign',expected_revision=item.expected_revision,request_key=key,assignee_id=p.assignee_id,rationale=p.rationale)
                value=rw.transition(db,actor,item.id,event_input,commit=False)
                results.append({'id':task.id,'revision':value['revision'],'status':'replayed' if replay else 'reassigned'})
        except HTTPException as error:
            if error.status_code not in {403,404,409,413,422}:raise
        except IntegrityError:
            # A competing revision/idempotency winner makes this selected row unavailable.
            pass
    actor=tables.finish(db,request,p.matter_id,before);access(actor,p.matter_id)
    # Nothing commits if authority/target/history changed while preparing successes.
    for result in results:
        task,history=rw.task_row(db,actor,result['id'],True)
        if task.matter_id!=p.matter_id or (actor.id!=task.created_by and R.SME not in actor.roles):raise HTTPException(409,'Task authority changed before reassignment receipt')
        if history[-1].revision!=result['revision']:raise HTTPException(409,'Task changed before reassignment receipt')
        rw.eligible(db,p.assignee_id,task.source_id,[task,*history])
    unavailable=len(p.items)-len(results)
    audit(db,'table.tasks.bulk_reassign_partial' if unavailable else 'table.tasks.bulk_reassign_complete','partial' if unavailable else 'allowed',actor.id,category='access',matter_id=p.matter_id)
    db.commit()
    return {'requested':len(p.items),'succeeded':len(results),'unavailable':unavailable,'results':results}
