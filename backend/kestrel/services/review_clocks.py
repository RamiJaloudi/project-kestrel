"""Bounded interaction estimates and explicitly approved, version-pinned operational SLA."""
import json,io
from datetime import datetime,date,time,timedelta,timezone
from importlib import resources,metadata
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.services import review_work as rw
from kestrel.services.auth import clock,audit
from kestrel.services.lifecycle import mutable
from kestrel.adapters.extraction import canonical,digest

MAX_INTERVAL=30
LEASE_SECONDS=90
NOTICE='Interaction-based estimates, not verified work or billable time. Missing, hidden or delayed observations are not credited as active review. Quiet reading may be unobserved. No client elapsed times are accepted.'


def config_access(db,actor,matter,write=False):
    if actor.org!=O.FIRM or not actor.roles&{R.ROOT_ADMIN,R.SME} or not member_and_not_walled(actor,matter):raise HTTPException(403,'Scoped operational configuration role required')
    if write:
        db.scalar(select(m.Matter).where(m.Matter.id==matter).with_for_update());mutable(db,matter)


def zone(name):
    try:
        if any(p in {'','.','..'} for p in name.split('/')):raise ValueError()
        with resources.files('tzdata.zoneinfo').joinpath(*name.split('/')).open('rb') as f:return ZoneInfo.from_file(f,key=name)
    except (OSError,ValueError):raise HTTPException(422,'Supported IANA timezone required')


def calendar_output(c):
    return {**{k:getattr(c,k) for k in ['id','matter_id','name','version_number','timezone','tzdata_version','start_minute','end_minute','content_hash']},'weekdays':json.loads(c.weekdays_json),'holidays':json.loads(c.holidays_json)}


def policy_output(db,p):
    decisions=list(db.scalars(select(m.ReviewSlaDecision).where(m.ReviewSlaDecision.policy_id==p.id).order_by(m.ReviewSlaDecision.revision)))
    return {**{k:getattr(p,k) for k in ['id','matter_id','name','stage','calendar_id','version_number','max_business_seconds','exclude_paused','idle_timeout_seconds','author_id','content_hash']},
        'state':decisions[-1].state if decisions else 'draft','revision':decisions[-1].revision if decisions else 0}


def configuration(db,actor,matter):
    # Source reviewers may read published operational policy; admin can draft without source access.
    if actor.org!=O.FIRM or not actor.roles&({R.ROOT_ADMIN,R.SME}|rw.w.LEGAL) or not member_and_not_walled(actor,matter):raise HTTPException(403,'Matter configuration denied')
    return {'calendars':[calendar_output(c) for c in db.scalars(select(m.SlaCalendarVersion).where(m.SlaCalendarVersion.matter_id==matter).order_by(m.SlaCalendarVersion.created_at,m.SlaCalendarVersion.version_number))],
        'policies':[policy_output(db,p) for p in db.scalars(select(m.ReviewSlaVersion).where(m.ReviewSlaVersion.matter_id==matter).order_by(m.ReviewSlaVersion.created_at,m.ReviewSlaVersion.version_number))]}


def create_calendar(db,actor,p):
    config_access(db,actor,p.matter_id,True);zone(p.timezone)
    try:
        if len(set(p.holidays))!=len(p.holidays):raise ValueError()
        for value in p.holidays:
            if date.fromisoformat(value).isoformat()!=value:raise ValueError()
    except ValueError:raise HTTPException(422,'Distinct ISO holiday dates required')
    version=metadata.version('tzdata');h=digest(canonical({**p.model_dump(exclude={'expected_previous_version'}),'tzdata_version':version}).encode())
    old=db.scalar(select(m.SlaCalendarVersion).where(m.SlaCalendarVersion.matter_id==p.matter_id,m.SlaCalendarVersion.name==p.name).order_by(m.SlaCalendarVersion.version_number.desc()))
    if old and old.content_hash==h:return calendar_output(old)
    if p.expected_previous_version!=(old.version_number if old else 0):raise HTTPException(409,'Calendar version changed')
    c=m.SlaCalendarVersion(matter_id=p.matter_id,name=p.name,version_number=p.expected_previous_version+1,timezone=p.timezone,tzdata_version=version,
        weekdays_json=canonical(p.weekdays),holidays_json=canonical(p.holidays),start_minute=p.start_minute,end_minute=p.end_minute,author_id=actor.id,content_hash=h,created_at=clock())
    db.add(c);db.flush();audit(db,'review.calendar.create','allowed',actor.id,category='administrative',matter_id=p.matter_id,object_id=c.id);db.commit();return calendar_output(c)


def create_policy(db,actor,p):
    config_access(db,actor,p.matter_id,True);cal=db.get(m.SlaCalendarVersion,p.calendar_id)
    if not cal or cal.matter_id!=p.matter_id:raise HTTPException(403,'Calendar outside matter')
    h=digest(canonical({**p.model_dump(exclude={'expected_previous_version'}),'calendar_hash':cal.content_hash}).encode())
    old=db.scalar(select(m.ReviewSlaVersion).where(m.ReviewSlaVersion.matter_id==p.matter_id,m.ReviewSlaVersion.name==p.name).order_by(m.ReviewSlaVersion.version_number.desc()))
    if old and old.content_hash==h:return policy_output(db,old)
    if p.expected_previous_version!=(old.version_number if old else 0):raise HTTPException(409,'SLA version changed')
    data=p.model_dump(exclude={'expected_previous_version'})
    row=m.ReviewSlaVersion(**data,version_number=p.expected_previous_version+1,author_id=actor.id,content_hash=h,created_at=clock())
    db.add(row);db.flush();audit(db,'review.sla.draft','allowed',actor.id,category='administrative',matter_id=p.matter_id,object_id=row.id);db.commit();return policy_output(db,row)


def decide_policy(db,actor,pid,operation,p):
    row=db.get(m.ReviewSlaVersion,pid)
    if not row:raise HTTPException(404,'SLA policy unavailable')
    config_access(db,actor,row.matter_id,True);v=policy_output(db,row)
    if p.expected_revision!=v['revision'] or p.content_hash!=row.content_hash:raise HTTPException(409,'Exact current SLA revision/hash required')
    expected={'submit':'draft','approve':'submitted','reject':'submitted','publish':'approved'}
    if operation not in expected or v['state']!=expected[operation]:raise HTTPException(409,'SLA state does not permit this decision')
    if operation in {'approve','reject'} and (R.SME not in actor.roles or row.author_id==actor.id):raise HTTPException(403,'Independent scoped SME approval required')
    state={'submit':'submitted','approve':'approved','reject':'rejected','publish':'published'}[operation]
    db.add(m.ReviewSlaDecision(matter_id=row.matter_id,policy_id=row.id,revision=v['revision']+1,state=state,actor_id=actor.id,content_hash=row.content_hash,rationale=p.rationale,created_at=clock()))
    audit(db,'review.sla.'+operation,'allowed',actor.id,category='administrative',matter_id=row.matter_id,object_id=row.id);db.flush();value=policy_output(db,row);db.commit();return value


def assignment(history):return next(e for e in reversed(history) if e.operation in {'assign','reassign','reopen'})


def current_binding(db,task,history):
    aid=assignment(history).id
    return db.scalar(select(m.ReviewSlaBinding).join(m.ReviewTaskEvent,m.ReviewTaskEvent.id==m.ReviewSlaBinding.event_id).where(m.ReviewSlaBinding.task_id==task.id,m.ReviewSlaBinding.assignment_event_id==aid).order_by(m.ReviewTaskEvent.revision.desc()))


def bind(db,actor,tid,p):
    task,history=rw.task_row(db,actor,tid,True);last=history[-1]
    if actor.id!=task.created_by and R.SME not in actor.roles:raise HTTPException(403,'Task creator or scoped SME required')
    h=rw.fingerprint(p);old=next((e for e in history if e.actor_id==actor.id and e.request_key==p.request_key),None)
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Binding request changed')
        return rw.task_output(db,actor,task)
    if p.expected_revision!=last.revision or last.to_state in {'completed','cancelled'}:raise HTTPException(409,'Current open task revision required')
    version=db.get(m.ReviewSlaVersion,p.policy_id)
    if not version or version.matter_id!=task.matter_id or version.stage!=task.stage or policy_output(db,version)['state']!='published':raise HTTPException(403,'Published same-matter/stage SLA required')
    src,policy=rw.source(db,actor,task.source_id,True)
    e=rw.add_event(db,actor,task,src,policy,last.revision+1,'sla',last.to_state,last.assignee_id,last.due_at,p.rationale,p.request_key,h,last)
    db.add(m.ReviewSlaBinding(**rw.capture(src,policy),task_id=task.id,assignment_event_id=assignment(history).id,policy_id=version.id,event_id=e.id,created_at=clock()))
    db.flush();value=rw.task_output(db,actor,task);db.commit();return value


def windows(cal,start,end):
    if end<=start:return []
    if end-start>366*86400:raise HTTPException(413,'SLA calculation exceeds the bounded one-year window')
    if cal.tzdata_version!=metadata.version('tzdata'):raise HTTPException(409,'Timezone data version changed; create and approve a new calendar')
    z=zone(cal.timezone);first=datetime.fromtimestamp(start,timezone.utc).astimezone(z).date();last=datetime.fromtimestamp(end,timezone.utc).astimezone(z).date()
    days=set(json.loads(cal.weekdays_json));holidays=set(json.loads(cal.holidays_json));result=[];day=first
    while day<=last:
        if day.weekday() in days and day.isoformat() not in holidays:
            def at(minute):
                local=datetime.combine(day,time())+timedelta(minutes=minute);aware=local.replace(tzinfo=z,fold=0);stamp=int(aware.timestamp())
                if datetime.fromtimestamp(stamp,z).replace(tzinfo=None)!=local:raise HTTPException(422,'Calendar hours intersect a nonexistent DST boundary')
                return stamp
            a=max(start,at(cal.start_minute));b=min(end,at(cal.end_minute))
            if b>a:result.append((a,b))
        day+=timedelta(days=1)
    return result


def business_seconds(cal,start,end):return sum(b-a for a,b in windows(cal,start,end))


def add_business_seconds(cal,start,seconds):
    for a,b in windows(cal,start,start+366*86400):
        if seconds<=b-a:return a+seconds
        seconds-=b-a
    raise HTTPException(413,'Projected SLA deadline exceeds one year')


def receipts(db,session):
    rows=list(db.scalars(select(m.ReviewSessionReceipt).where(m.ReviewSessionReceipt.session_id==session.id).order_by(m.ReviewSessionReceipt.sequence).limit(5001)))
    if len(rows)>5000:raise HTTPException(413,'Timing session receipt limit reached; start a new session')
    return rows


def session_totals(session,rows,as_of):
    totals={'active_seconds':0,'idle_seconds':0,'unobserved_seconds':0}
    for r in rows:
        seconds=max(0,min(r.interval_end_at,as_of)-r.interval_start_at)
        totals[{'active':'active_seconds','idle':'idle_seconds'}.get(r.mode,'unobserved_seconds')]+=seconds
    last=rows[-1] if rows else None
    if not last or last.operation not in {'close','task_stop'}:
        last_time=last.occurred_at if last else session.started_at
        totals['unobserved_seconds']+=max(0,min(as_of,last_time+LEASE_SECONDS)-last_time)
    return totals


def session_output(db,actor,s):
    rw.retained(db,actor,s);rows=receipts(db,s)
    for r in rows:rw.retained(db,actor,r)
    lease=db.get(m.ReviewSessionLease,s.account_id)
    active=bool(lease and lease.session_id==s.id and lease.lease_until>clock())
    return {'id':s.id,'task_id':s.task_id,'sequence':rows[-1].sequence if rows else 0,'active':active,'idle_timeout_seconds':s.idle_timeout_seconds,
        'heartbeat_seconds':15,'max_interval_seconds':MAX_INTERVAL,'lease_until':lease.lease_until if active else None,
        **session_totals(s,rows,clock()),'notice':NOTICE}


def begin(db,actor,tid,p):
    task,history=rw.task_row(db,actor,tid,True);last=history[-1]
    if last.assignee_id!=actor.id or last.to_state!='in_progress':raise HTTPException(403,'Current assignee must start review before enabling timing')
    db.scalar(select(m.Account).where(m.Account.id==actor.id).with_for_update())
    h=digest(canonical({'task_id':tid,'input':p.model_dump()}).encode())
    old=db.scalar(select(m.ReviewSession).where(m.ReviewSession.account_id==actor.id,m.ReviewSession.request_key==p.request_key))
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Session request changed')
        return session_output(db,actor,old)
    if p.expected_revision!=last.revision:raise HTTPException(409,'Task revision changed; refresh before timing')
    lease=db.get(m.ReviewSessionLease,actor.id)
    if lease and lease.lease_until>clock():raise HTTPException(409,'Another timing session is active for this account; stop it or wait for expiry')
    binding=current_binding(db,task,history);idle=db.get(m.ReviewSlaVersion,binding.policy_id).idle_timeout_seconds if binding else 300
    src,policy=rw.source(db,actor,task.source_id,True)
    s=m.ReviewSession(**rw.capture(src,policy),task_id=task.id,assignment_event_id=assignment(history).id,account_id=actor.id,request_key=p.request_key,input_hash=h,idle_timeout_seconds=idle,started_at=clock())
    db.add(s);db.flush()
    if lease:lease.session_id=s.id;lease.lease_until=clock()+LEASE_SECONDS
    else:db.add(m.ReviewSessionLease(account_id=actor.id,session_id=s.id,lease_until=clock()+LEASE_SECONDS))
    rw.audit_work(db,actor,policy,'review.clock.begin',s,[task,*history]);db.flush();value=session_output(db,actor,s);db.commit();return value


def receipt(db,actor,sid,p):
    rw.internal(actor);s=db.get(m.ReviewSession,sid)
    if not s or s.account_id!=actor.id:raise HTTPException(403,'Own timing session required')
    task,history=rw.task_row(db,actor,s.task_id,True);rw.retained(db,actor,s)
    db.scalar(select(m.Account).where(m.Account.id==actor.id).with_for_update())
    rows=receipts(db,s);last=rows[-1] if rows else None;h=rw.fingerprint(p)
    old=next((r for r in rows if r.request_key==p.request_key),None)
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Receipt request changed')
        return session_output(db,actor,s)
    lease=db.get(m.ReviewSessionLease,actor.id)
    if not lease or lease.session_id!=s.id or lease.lease_until<=clock() or history[-1].to_state!='in_progress' or history[-1].assignee_id!=actor.id or assignment(history).id!=s.assignment_event_id:raise HTTPException(409,'Timing session stopped, expired or reassigned')
    if p.expected_sequence!=(last.sequence if last else 0):raise HTTPException(409,'Timing sequence changed; do not resend a different observation')
    previous=last.occurred_at if last else s.started_at;now=clock();elapsed=now-previous
    if elapsed<0:raise HTTPException(409,'Server clock moved backwards; wait before recording another interval')
    last_activity=last.last_interaction_at if last else s.started_at
    mode='unobserved'
    if p.operation=='sample' and 0<=elapsed<=MAX_INTERVAL:
        if p.interaction:mode='active'
        elif previous>=last_activity+s.idle_timeout_seconds:mode='idle'
    if p.interaction and p.operation=='sample':last_activity=now
    src,policy=rw.source(db,actor,s.source_id,True)
    r=m.ReviewSessionReceipt(**rw.capture(src,policy),session_id=s.id,sequence=(last.sequence if last else 0)+1,
        operation=p.operation,mode=mode,interaction=p.interaction,interval_start_at=previous,interval_end_at=max(previous,now),last_interaction_at=last_activity,
        actor_id=actor.id,request_key=p.request_key,input_hash=h,occurred_at=now)
    db.add(r);lease.lease_until=now if p.operation=='close' else now+LEASE_SECONDS
    if p.operation=='close':rw.audit_work(db,actor,policy,'review.clock.close',s,[task,*history])
    db.flush();value=session_output(db,actor,s);db.commit();return value


def stop_for_task(db,task,actor):
    """Task state invalidates observation authority; it never attributes work to a manager."""
    roots=list(db.scalars(select(m.ReviewSession).where(m.ReviewSession.task_id==task.id)))
    for s in roots:
        lease=db.get(m.ReviewSessionLease,s.account_id)
        if not lease or lease.session_id!=s.id or lease.lease_until<=clock():continue
        db.scalar(select(m.Account).where(m.Account.id==s.account_id).with_for_update())
        # Receipt interval after the last sample is unobserved, not productive time.
        rows=receipts(db,s);last=rows[-1] if rows else None;now=clock()
        src,policy=rw.source(db,actor,s.source_id,True)
        db.add(m.ReviewSessionReceipt(**rw.capture(src,policy),session_id=s.id,sequence=(last.sequence if last else 0)+1,operation='task_stop',mode='unobserved',interaction=False,
            interval_start_at=last.occurred_at if last else s.started_at,interval_end_at=max(now,last.occurred_at if last else s.started_at),
            last_interaction_at=last.last_interaction_at if last else s.started_at,actor_id=actor.id,request_key='task-stop-'+str(len(rows)+1),input_hash=digest(str(now).encode()),occurred_at=now))
        lease.lease_until=now


def cutoff(db,matter):
    state=db.get(m.MatterLifecycle,matter)
    if not state or not state.frozen:return clock(),'current server time'
    sign=db.scalar(select(m.LifecycleDecision).where(m.LifecycleDecision.matter_id==matter,m.LifecycleDecision.kind=='sign',m.LifecycleDecision.state=='approved').order_by(m.LifecycleDecision.created_at.desc()))
    if not sign:return None,'frozen workspace has no recorded timing cutoff'
    payload=json.loads(sign.payload_json)
    return payload.get('review_clock_as_of',sign.created_at),'retained signing snapshot time'


def metrics(db,actor,task,history):
    as_of,basis=cutoff(db,task.matter_id);start=assignment(history).occurred_at;last=history[-1]
    end=min(as_of,last.occurred_at) if as_of is not None and last.to_state in {'completed','cancelled'} else as_of
    base={'queue_age_seconds':max(0,end-start) if end is not None else None,'active_seconds':None,'idle_seconds':None,'unobserved_seconds':None,'business_days_open':None,
        'as_of':end,'cutoff_basis':basis,'sla':{'status':'unconfigured'},'notice':NOTICE}
    if end is None:return base
    cycle=[e for e in history if e.revision>=assignment(history).revision and e.occurred_at<=end]
    accepted=next((e for e in cycle if e.operation=='accept'),None)
    base['time_to_accept_seconds']=max(0,accepted.occurred_at-start) if accepted else None
    base['turnaround_seconds']=max(0,end-start) if last.to_state in {'completed','cancelled'} else None
    roots=list(db.scalars(select(m.ReviewSession).where(m.ReviewSession.task_id==task.id,m.ReviewSession.assignment_event_id==assignment(history).id)))
    if roots and (actor.id==last.assignee_id or R.AUDITOR in actor.roles):
        totals={'active_seconds':0,'idle_seconds':0,'unobserved_seconds':0}
        try:
            for s in roots:
                rw.retained(db,actor,s);rows=receipts(db,s)
                for r in rows:rw.retained(db,actor,r)
                for key,value in session_totals(s,rows,end).items():totals[key]+=value
        except HTTPException as e:
            if e.status_code!=403:raise
            base['notice']='Timing evidence is unavailable in your current scope.';return base
        base.update(totals)
    try:
        binding=current_binding(db,task,history)
        if not binding:return base
        rw.retained(db,actor,binding);p=db.get(m.ReviewSlaVersion,binding.policy_id);cal=db.get(m.SlaCalendarVersion,p.calendar_id)
        beginning=max(start,binding.created_at);paused=0;pause_start=None
        # State at policy binding may already be paused.
        for e in cycle:
            if e.operation=='pause':pause_start=e.occurred_at
            elif e.operation in {'resume','complete','cancel','reassign','reopen'} and pause_start is not None:
                paused+=business_seconds(cal,max(beginning,pause_start),min(end,e.occurred_at));pause_start=None
        if pause_start is not None:paused+=business_seconds(cal,max(beginning,pause_start),end)
        elapsed=max(0,business_seconds(cal,beginning,end)-(paused if p.exclude_paused else 0));day=(cal.end_minute-cal.start_minute)*60
        base['business_days_open']=round(elapsed/day,4)
        base['sla']={'status':'breached' if elapsed>p.max_business_seconds else 'within_budget','policy_id':p.id,'calendar_id':cal.id,'timezone':cal.timezone,
            'effective_from':beginning,'business_elapsed_seconds':elapsed,'paused_business_seconds':paused,'budget_seconds':p.max_business_seconds,
            'overdue_business_seconds':max(0,elapsed-p.max_business_seconds),'projected_due_at':None if last.to_state=='paused' else add_business_seconds(cal,beginning,p.max_business_seconds+(paused if p.exclude_paused else 0)),
            'notice':'Prospective operational SLA; projection assumes no future pauses. Manual deadline remains separate.'}
        return base
    except HTTPException as error:
        if error.status_code not in {409,413,422}:raise
        base['business_days_open']=None
        base['sla']={'status':'calculation_unavailable','notice':'The pinned calendar cannot calculate this interval within its validated timezone/version and one-year bounds. Retained task history remains available.'}
        return base
