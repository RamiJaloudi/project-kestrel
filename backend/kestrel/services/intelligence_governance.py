"""Independently governed operational scoring. No legal or publication authority."""
import json
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel import models as m
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.repositories.identity import principal
from kestrel.services import workflow as w,review_work as rw,review_clocks as clocks,lifecycle
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest

WEIGHTS={'delay':{'sla_overdue':40,'queue_age':20,'reassignments':10,'paused_qc':10,'manual_deadline':10,'stalled_active_sessions':10},
    'legal':{'reviewed_severity':70,'reviewed_materiality':20,'transaction_deadline':10},
    'financial':{'comparable_variance':60,'financial_materiality':20,'period_consistency':10,'verified_evidence':10}}


def access(actor,matter,write=False,db=None):
    if actor.org==O.FIRM and R.ROOT_ADMIN in actor.roles:clocks.config_access(db,actor,matter,write)
    else:
        w.legal(actor,matter)
        if write:
            db.scalar(select(m.Matter).where(m.Matter.id==matter).with_for_update());lifecycle.mutable(db,matter)


def profile_output(db,row):
    ops={d.operation for d in db.scalars(select(m.IntelligenceProfileDecision).where(m.IntelligenceProfileDecision.profile_id==row.id))}
    state='revoked' if 'revoke' in ops else 'rejected' if 'reject' in ops else 'published' if 'publish' in ops else 'approved' if 'approve' in ops else 'draft'
    return {k:getattr(row,k) for k in ['id','matter_id','name','version_number','author_id','content_hash','created_at']}|{'state':state,'definition':json.loads(row.definition_json)}


def profile_read(db,actor,pid,published=False):
    row=db.get(m.IntelligenceProfile,pid)
    if not row:raise HTTPException(404,'Scoring profile unavailable')
    access(actor,row.matter_id,db=db)
    if digest(row.definition_json.encode())!=row.content_hash:raise HTTPException(409,'Scoring profile integrity mismatch')
    if published:
        if profile_output(db,row)['state']!='published':raise HTTPException(409,'Published scoring profile required')
        approval=db.scalar(select(m.IntelligenceProfileDecision).where(m.IntelligenceProfileDecision.profile_id==pid,m.IntelligenceProfileDecision.operation=='approve'))
        account=db.get(m.Account,approval.actor_id) if approval else None
        if not account or not account.active:raise HTTPException(403,'Profile approving identity unavailable')
        reviewer=principal(db,account,clock());w.legal(reviewer,row.matter_id)
        if R.SME not in reviewer.roles or reviewer.id==row.author_id or approval.content_hash!=row.content_hash:raise HTTPException(403,'Independent profile approval no longer valid')
    return row


def approving_actor(db,profile):
    decision=db.scalar(select(m.IntelligenceProfileDecision).where(m.IntelligenceProfileDecision.profile_id==profile.id,m.IntelligenceProfileDecision.operation=='approve'))
    account=db.get(m.Account,decision.actor_id) if decision else None
    if not account or not account.active or decision.content_hash!=profile.content_hash:raise HTTPException(403,'Profile approving identity unavailable')
    actor=principal(db,account,clock());w.legal(actor,profile.matter_id)
    if R.SME not in actor.roles or actor.id==profile.author_id:raise HTTPException(403,'Independent approving SME required')
    return actor


def configuration_people(db,actor,matter):
    clocks.config_access(db,actor,matter)
    result=[]
    for account in db.scalars(select(m.Account).where(m.Account.active==True).order_by(m.Account.id)):
        other=principal(db,account,clock())
        if other.org==O.FIRM and other.roles&w.LEGAL and member_and_not_walled(other,matter):result.append(rw.person(db,account.id))
    return result


def profiles(db,actor,matter):
    access(actor,matter,db=db)
    return [profile_output(db,p) for p in db.scalars(select(m.IntelligenceProfile).where(m.IntelligenceProfile.matter_id==matter).order_by(m.IntelligenceProfile.created_at.desc(),m.IntelligenceProfile.id))]


def create_profile(db,actor,p):
    clocks.config_access(db,actor,p.matter_id,True)
    weights={domain:dict(values) for domain,values in WEIGHTS.items()}
    if set(p.weights)-set(weights):raise HTTPException(422,'Unknown scoring domain')
    for domain,values in p.weights.items():
        if set(values)!=set(weights[domain]) or any(type(v) is not int or not 0<=v<=100 for v in values.values()) or sum(values.values())!=100:raise HTTPException(422,'Each supplied domain must give every allowed component and weights totaling 100')
        weights[domain]=values
    for uid in p.recipient_ids:
        account=db.get(m.Account,uid)
        other=principal(db,account,clock()) if account and account.active else None
        if not other or other.org!=O.FIRM or not other.roles&w.LEGAL or not member_and_not_walled(other,p.matter_id):raise HTTPException(403,'Named recipients must be active cleared matter legal accounts')
    h=digest(canonical(p.model_dump()).encode());old=db.scalar(select(m.IntelligenceProfile).where(m.IntelligenceProfile.author_id==actor.id,m.IntelligenceProfile.request_key==p.request_key))
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Profile request key changed')
        return profile_output(db,old)
    previous=db.scalar(select(m.IntelligenceProfile).where(m.IntelligenceProfile.matter_id==p.matter_id,m.IntelligenceProfile.name==p.name).order_by(m.IntelligenceProfile.version_number.desc()))
    if p.expected_previous_version!=(previous.version_number if previous else 0):raise HTTPException(409,'Scoring profile version changed')
    definition=canonical({'version':'deterministic-review-intelligence-v1','matter_id':p.matter_id,'name':p.name,'rationale':p.rationale,'weights':weights,'alert_threshold':p.alert_threshold,'minimum_coverage':p.minimum_coverage,'recipient_ids':sorted(p.recipient_ids),'assignee_id':p.assignee_id})
    row=m.IntelligenceProfile(matter_id=p.matter_id,name=p.name,version_number=p.expected_previous_version+1,author_id=actor.id,definition_json=definition,content_hash=digest(definition.encode()),rationale=p.rationale,request_key=p.request_key,input_hash=h,created_at=clock())
    db.add(row);db.flush();audit(db,'intelligence.profile.create','allowed',actor.id,matter_id=p.matter_id,category='administrative',object_id=row.id);db.commit();return profile_output(db,row)


def decide_profile(db,actor,pid,p):
    row=profile_read(db,actor,pid);access(actor,row.matter_id,p.operation!='revoke',db);db.scalar(select(m.IntelligenceProfile).where(m.IntelligenceProfile.id==pid).with_for_update())
    state=profile_output(db,row)['state']
    if p.content_hash!=row.content_hash:raise HTTPException(409,'Exact scoring profile hash required')
    if p.operation in {'approve','reject','revoke'} and (R.SME not in actor.roles or actor.id==row.author_id):raise HTTPException(403,'Independent scoped SME decision required')
    if p.operation in {'approve','reject'} and state!='draft' or p.operation=='publish' and state!='approved' or p.operation=='revoke' and state not in {'approved','published'}:raise HTTPException(409,'Profile state does not permit this decision')
    if p.operation=='publish' and not actor.roles&{R.ROOT_ADMIN,R.SME}:raise HTTPException(403,'Scoped configuration role required')
    if p.operation=='publish':approving_actor(db,row)
    db.add(m.IntelligenceProfileDecision(matter_id=row.matter_id,profile_id=pid,operation=p.operation,content_hash=p.content_hash,actor_id=actor.id,rationale=p.rationale,occurred_at=clock()))
    audit(db,'intelligence.profile.'+p.operation,'allowed',actor.id,matter_id=row.matter_id,category='administrative',object_id=pid);db.flush();result=profile_output(db,row);db.commit();return result


def apply(db,actor,p,rows):
    from kestrel.services.intelligence import weighted_score,VERSION
    profile=profile_read(db,actor,p.profile_id,True) if p.profile_id else None
    if profile and (profile.matter_id!=p.matter_id or actor.org!=O.FIRM):raise HTTPException(403,'Internal same-matter scoring profile required')
    definition=json.loads(profile.definition_json) if profile else None
    for row in rows:
        for domain,score in row['scores'].items():
            if definition:
                score=weighted_score([{**c,'weight':definition['weights'][domain][c['key']]} for c in score['components']]) if all(c['key'] in definition['weights'][domain] for c in score['components']) else score
                row['scores'][domain]=score
            snapshot=w.snapshot(db,row['_policy']) if '_policy' in row else row['id']
            score['base_hash']=digest(canonical({'profile':profile.content_hash if profile else VERSION,'snapshot':snapshot,'signal_revision':row.get('_signal_revision',row['id']),'components':score['components']}).encode())
            if profile and '_policy' in row:
                for override in db.scalars(select(m.IntelligenceOverride).where(m.IntelligenceOverride.source_id==row['id'],m.IntelligenceOverride.profile_id==profile.id,m.IntelligenceOverride.domain==domain).order_by(m.IntelligenceOverride.created_at.desc(),m.IntelligenceOverride.id.desc())):
                    try:
                        override_read(db,actor,override,approved=True)
                        if override.base_hash!=score['base_hash']:continue
                        score['override']={'id':override.id,'value':override.value,'expires_at':override.expires_at,'rationale':override.rationale,'content_hash':override.content_hash};break
                    except HTTPException as error:
                        if error.status_code not in {403,409}:raise
    return rows


def override_read(db,actor,row,approved=False):
    src,policy=rw.retained(db,actor,row);profile_read(db,actor,row.profile_id,True)
    if row.expires_at<=clock() or row.source_snapshot!=w.snapshot(db,policy):raise HTTPException(409,'Override expired or source attributes changed')
    if approved:
        decisions=list(db.scalars(select(m.IntelligenceOverrideDecision).where(m.IntelligenceOverrideDecision.override_id==row.id)))
        if {d.operation for d in decisions}&{'reject','revoke'}:raise HTTPException(409,'Override closed')
        d=next((d for d in decisions if d.operation=='approve'),None)
        if not d or d.actor_id==row.created_by or d.content_hash!=row.content_hash:raise HTTPException(409,'Independent override approval required')
        rw.retained(db,actor,d);rw.eligible(db,d.actor_id,src.id,[row,d])
        reviewer=principal(db,db.get(m.Account,d.actor_id),clock())
        if R.SME not in reviewer.roles:raise HTTPException(403,'Override approver lost SME authority')
    return src,policy


def create_override(db,actor,p):
    from kestrel.schemas.intelligence import IntelligenceQuery
    from kestrel.services.intelligence import collect
    src,policy=rw.source(db,actor,p.source_id,True);profile=profile_read(db,actor,p.profile_id,True)
    if profile.matter_id!=src.matter_id:raise HTTPException(403,'Profile outside source matter')
    args=IntelligenceQuery(matter_id=src.matter_id,profile_id=p.profile_id)
    row=next((r for r in apply(db,actor,args,collect(db,actor,args)) if r['id']==src.id),None)
    if row is None or row['scores'][p.domain]['base_hash']!=p.base_hash:raise HTTPException(409,'Current exact deterministic base score required')
    h=digest(canonical(p.model_dump()).encode());old=rw.retry(db,m.IntelligenceOverride,actor,p.request_key,h)
    if old:return override_output(db,actor,old)
    content={**p.model_dump(),'source_snapshot':w.snapshot(db,policy),'profile_hash':profile.content_hash,'expires_at':clock()+p.expires_in_hours*3600}
    row=m.IntelligenceOverride(**rw.capture(src,policy),profile_id=profile.id,domain=p.domain,value=p.value,base_hash=p.base_hash,source_snapshot=content['source_snapshot'],expires_at=content['expires_at'],created_by=actor.id,content_hash=digest(canonical(content).encode()),rationale=p.rationale,request_key=p.request_key,input_hash=h,created_at=clock())
    db.add(row);db.flush();rw.audit_work(db,actor,policy,'intelligence.override.propose',row);result=override_output(db,actor,row);db.commit();return result


def override_output(db,actor,row):
    override_read(db,actor,row)
    ops={d.operation for d in db.scalars(select(m.IntelligenceOverrideDecision).where(m.IntelligenceOverrideDecision.override_id==row.id))}
    return {k:getattr(row,k) for k in ['id','source_id','profile_id','domain','value','base_hash','content_hash','rationale','expires_at','created_by']}|{'state':'revoked' if 'revoke' in ops else 'rejected' if 'reject' in ops else 'approved' if 'approve' in ops else 'proposed'}


def overrides(db,actor,sid):
    rw.source(db,actor,sid);result=[]
    for row in db.scalars(select(m.IntelligenceOverride).where(m.IntelligenceOverride.source_id==sid).order_by(m.IntelligenceOverride.created_at.desc(),m.IntelligenceOverride.id)):
        try:result.append(override_output(db,actor,row))
        except HTTPException as error:
            if error.status_code not in {403,409}:raise
        if len(result)>=100:break
    return result


def decide_override(db,actor,oid,p):
    row=db.get(m.IntelligenceOverride,oid)
    if not row:raise HTTPException(404,'Override unavailable')
    src,policy=override_read(db,actor,row)
    if p.operation!='revoke':rw.source(db,actor,src.id,True)
    db.scalar(select(m.IntelligenceOverride).where(m.IntelligenceOverride.id==oid).with_for_update())
    if actor.id==row.created_by or R.SME not in actor.roles:raise HTTPException(403,'Independent source-cleared SME required')
    if p.operation not in {'approve','reject','revoke'}:raise HTTPException(422,'Override decisions cannot publish')
    state=override_output(db,actor,row)['state']
    if p.content_hash!=row.content_hash or p.operation in {'approve','reject'} and state!='proposed' or p.operation=='revoke' and state!='approved':raise HTTPException(409,'Override decision is stale or closed')
    if p.operation=='approve':
        from kestrel.schemas.intelligence import IntelligenceQuery
        from kestrel.services.intelligence import collect
        args=IntelligenceQuery(matter_id=src.matter_id,profile_id=row.profile_id)
        current=next((r for r in apply(db,actor,args,collect(db,actor,args)) if r['id']==src.id),None)
        if not current or current['scores'][row.domain]['base_hash']!=row.base_hash:raise HTTPException(409,'Deterministic score changed; propose a fresh override')
    d=m.IntelligenceOverrideDecision(**rw.capture(src,policy),override_id=oid,operation=p.operation,content_hash=p.content_hash,actor_id=actor.id,rationale=p.rationale,occurred_at=clock());db.add(d);db.flush();rw.audit_work(db,actor,policy,'intelligence.override.'+p.operation,d,[row]);result=override_output(db,actor,row);db.commit();return result


def scan(db,actor,pid,p):
    from kestrel.schemas.intelligence import IntelligenceQuery
    from kestrel.schemas.review_work import TaskCreate
    from kestrel.services.intelligence import collect
    profile=profile_read(db,actor,pid,True);reviewer=approving_actor(db,profile);w.legal(actor,profile.matter_id);lifecycle.mutable(db,profile.matter_id)
    definition=json.loads(profile.definition_json);args=IntelligenceQuery(matter_id=profile.matter_id,profile_id=pid)
    rows=apply(db,actor,args,collect(db,actor,args));created=0
    for row in rows:
        src,policy=rw.source(db,actor,row['id'],True)
        rw.source(db,reviewer,src.id)
        for domain,score in row['scores'].items():
            value=score.get('override',{}).get('value',score['score'])
            if value is None or value<definition['alert_threshold'] or score['coverage_weight']<definition['minimum_coverage']:continue
            key=digest(canonical({'profile':profile.content_hash,'source':w.snapshot(db,policy),'domain':domain,'revision':row['_signal_revision'],'override':score.get('override',{}).get('id')}).encode())
            if db.scalar(select(m.IntelligenceAlert.id).where(m.IntelligenceAlert.dedupe_key==key)):continue
            for uid in definition['recipient_ids']:rw.eligible(db,uid,src.id)
            try:
                with db.begin_nested():
                    task=rw.create_task(db,actor,src.id,TaskCreate(stage='review',assignee_id=definition['assignee_id'],request_key='intelligence-alert-'+key,rationale='Operational follow-up from independently approved scoring profile; not a legal approval'),commit=False)
                    alert=m.IntelligenceAlert(**rw.capture(src,policy),dedupe_key=key,profile_id=pid,source_snapshot=w.snapshot(db,policy),domain=domain,signal_json=canonical(score),task_id=task['id'],created_by=actor.id,created_at=clock());db.add(alert);db.flush()
                    for uid in definition['recipient_ids']:db.add(m.IntelligenceAlertRecipient(**rw.capture(src,policy),alert_id=alert.id,account_id=uid))
                    rw.audit_work(db,actor,policy,'intelligence.alert.create',alert);created+=1
            except IntegrityError:continue
    db.commit();return {'created':created,'profile_id':pid,'notice':'Durable operational tasks only; no legal finding or audience release is approved'}


def alert_access(db,actor,aid):
    row=db.get(m.IntelligenceAlert,aid)
    if not row:raise HTTPException(404,'Alert unavailable')
    rw.retained(db,actor,row);rw.task_row(db,actor,row.task_id)
    recipient=db.scalar(select(m.IntelligenceAlertRecipient).where(m.IntelligenceAlertRecipient.alert_id==aid,m.IntelligenceAlertRecipient.account_id==actor.id))
    if not recipient:raise HTTPException(403,'Own source-cleared alert required')
    rw.retained(db,actor,recipient);return row


def alert_output(db,actor,row):
    alert_access(db,actor,row.id)
    history=list(db.scalars(select(m.IntelligenceAlertDisposition).where(m.IntelligenceAlertDisposition.alert_id==row.id).order_by(m.IntelligenceAlertDisposition.revision)))
    for event in history:rw.retained(db,actor,event)
    return {k:getattr(row,k) for k in ['id','source_id','profile_id','domain','task_id','created_at']}|{'signal':json.loads(row.signal_json),'revision':history[-1].revision if history else 0,'state':history[-1].operation if history else 'open','read':db.scalar(select(m.IntelligenceAlertRead.id).where(m.IntelligenceAlertRead.alert_id==row.id,m.IntelligenceAlertRead.account_id==actor.id)) is not None,'history':[{'operation':e.operation,'actor_id':e.actor_id,'rationale':e.rationale,'occurred_at':e.occurred_at} for e in history]}


def inbox(db,actor,matter):
    w.legal(actor,matter);rows=[]
    for row in db.scalars(select(m.IntelligenceAlert).join(m.IntelligenceAlertRecipient,m.IntelligenceAlertRecipient.alert_id==m.IntelligenceAlert.id).where(m.IntelligenceAlert.matter_id==matter,m.IntelligenceAlertRecipient.account_id==actor.id).order_by(m.IntelligenceAlert.created_at.desc(),m.IntelligenceAlert.id)):
        try:
            rows.append(alert_output(db,actor,row))
            if len(rows)>=100:break
        except HTTPException as error:
            if error.status_code!=403:raise
    return rows


def read_alert(db,actor,aid):
    row=alert_access(db,actor,aid);db.scalar(select(m.IntelligenceAlert).where(m.IntelligenceAlert.id==aid).with_for_update())
    if not db.scalar(select(m.IntelligenceAlertRead.id).where(m.IntelligenceAlertRead.alert_id==aid,m.IntelligenceAlertRead.account_id==actor.id)):db.add(m.IntelligenceAlertRead(alert_id=aid,account_id=actor.id,occurred_at=clock()))
    _,policy=rw.source(db,actor,row.source_id)
    rw.audit_work(db,actor,policy,'intelligence.alert.read',row)
    db.commit();return {'read':True}


def disposition(db,actor,aid,p):
    row=alert_access(db,actor,aid);src,policy=rw.source(db,actor,row.source_id,True);db.scalar(select(m.IntelligenceAlert).where(m.IntelligenceAlert.id==aid).with_for_update())
    current=alert_output(db,actor,row)
    if current['revision']!=p.expected_revision or current['state']=='close':raise HTTPException(409,'Alert disposition changed or closed')
    if p.operation=='close' and actor.id!=row.created_by and R.SME not in actor.roles:raise HTTPException(403,'Alert creator or source-cleared SME required to close')
    event=m.IntelligenceAlertDisposition(**rw.capture(src,policy),alert_id=aid,revision=p.expected_revision+1,operation=p.operation,actor_id=actor.id,rationale=p.rationale,occurred_at=clock());db.add(event);db.flush();rw.audit_work(db,actor,policy,'intelligence.alert.'+p.operation,event,[row]);result=alert_output(db,actor,row);db.commit();return result
