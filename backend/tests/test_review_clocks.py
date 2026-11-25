import json
import pytest
from datetime import datetime,timezone
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_observability_governance import post
from test_review_work import task,change
from kestrel.models import EthicalWall

B='/api/v1/review-clocks'


def running(env):
    http,_,_,_=env;s,t,csrf=task(env)
    a=change(http,t,csrf,'accept').json();t=change(http,a,csrf,'start').json()
    return s,t,csrf


def begin(http,t,csrf,key='clock-session-001'):
    return post(http,B+'/tasks/'+t['id']+'/sessions',csrf,{'expected_revision':t['revision'],'request_key':key})


def sample(http,s,csrf,key,seq,activity=True):
    return post(http,B+'/sessions/'+s['id']+'/receipts',csrf,{'request_key':key,'expected_sequence':seq,'operation':'sample','interaction':activity})


def test_server_intervals_replay_gaps_and_single_account_lease(env,monkeypatch):
    from kestrel.services import review_clocks as c
    from kestrel.services.auth import clock
    http,_,ids,_=env;_,t,csrf=running(env);now=[clock()];monkeypatch.setattr(c,'clock',lambda:now[0])
    s=begin(http,t,csrf);assert s.status_code==201,s.text
    s=s.json();assert s['sequence']==0
    assert begin(http,t,csrf).json()['id']==s['id']
    assert begin(http,t,csrf,key='second-session-002').status_code==409
    now[0]+=15
    one=sample(http,s,csrf,'first-sample-001',0);assert one.status_code==201,one.text
    assert one.json()['active_seconds']==15
    assert sample(http,s,csrf,'first-sample-001',0).json()['active_seconds']==15
    assert sample(http,s,csrf,'different-sample-002',0).status_code==409
    now[0]+=60
    gap=sample(http,s,csrf,'gap-sample-003',1).json()
    assert gap['active_seconds']==15 and gap['unobserved_seconds']>=60
    # No client-supplied elapsed seconds or timestamps are accepted.
    assert post(http,B+'/sessions/'+s['id']+'/receipts',csrf,{'request_key':'forged-sample-004','expected_sequence':2,'operation':'sample','interaction':True,'elapsed_seconds':5000}).status_code==422
    assert post(http,B+'/sessions/'+s['id']+'/receipts',csrf,{'request_key':'close-session-005','expected_sequence':2,'operation':'close','interaction':False}).status_code==201
    assert begin(http,t,csrf,key='new-session-006').status_code==201


def test_idle_threshold_pause_and_revoked_assignee(env,monkeypatch):
    from kestrel.services import review_clocks as c
    from kestrel.services.auth import clock
    http,sessions,ids,_=env;_,t,csrf=running(env);now=[clock()];monkeypatch.setattr(c,'clock',lambda:now[0])
    s=begin(http,t,csrf).json()
    for seq in range(21):
        now[0]+=15;r=sample(http,s,csrf,'idle-sample-'+str(seq).zfill(4),seq,False);assert r.status_code==201,r.text
    assert r.json()['active_seconds']==0 and r.json()['idle_seconds']>=15
    assert change(http,t,csrf,'pause').status_code==201
    assert sample(http,s,csrf,'after-pause-0022',21).status_code==409
    with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    assert http.get(B+'/sessions/'+s['id']).status_code==403


def create_sla(env,**calendar_changes):
    http,_,ids,_=env;csrf=login(http,'root').json()['csrf_token']
    cal=post(http,B+'/calendars',csrf,{'matter_id':ids['matter'],'name':'London synthetic calendar','expected_previous_version':0,
        'timezone':'Europe/London','weekdays':[0,1,2,3,4],'holidays':['2026-12-25'],'start_minute':540,'end_minute':1020,**calendar_changes}).json()
    assert 'id' in cal
    p=post(http,B+'/policies',csrf,{'matter_id':ids['matter'],'calendar_id':cal['id'],'name':'Synthetic five-day review','stage':'review',
        'expected_previous_version':0,'max_business_seconds':144000,'exclude_paused':True,'idle_timeout_seconds':300}).json()
    assert 'id' in p
    body={'expected_revision':0,'content_hash':p['content_hash'],'rationale':'Submit operational SLA for independent review'}
    assert post(http,B+'/policies/'+p['id']+'/submit',csrf,body).status_code==200
    assert post(http,B+'/policies/'+p['id']+'/approve',csrf,{**body,'expected_revision':1}).status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,B+'/policies/'+p['id']+'/approve',csrf,{**body,'expected_revision':1}).status_code==200
    assert post(http,B+'/policies/'+p['id']+'/publish',csrf,{**body,'expected_revision':2}).status_code==200
    return cal,p


def test_calendar_business_time_holidays_and_dst(env):
    from kestrel.services import review_clocks as c
    http,sessions,ids,_=env;cal,p=create_sla(env)
    from kestrel.models import SlaCalendarVersion
    ts=lambda value:int(datetime.fromisoformat(value).timestamp())
    with sessions() as db:
        row=db.get(SlaCalendarVersion,cal['id'])
        assert c.business_seconds(row,ts('2026-03-27T09:00:00+00:00'),ts('2026-03-30T16:00:00+00:00'))==16*3600
        assert c.business_seconds(row,ts('2026-12-24T09:00:00+00:00'),ts('2026-12-28T17:00:00+00:00'))==16*3600
        assert c.add_business_seconds(row,ts('2026-03-27T16:00:00+00:00'),2*3600)==ts('2026-03-30T09:00:00+00:00')


def test_explicit_sla_binding_retains_calendar_version_and_no_admin_task_access(env):
    http,_,ids,_=env;cal,p=create_sla(env);_,t,csrf=running(env)
    assert http.get('/api/v1/review-work/tasks/'+t['id']).json()['timing']['sla']['status']=='unconfigured'
    bound=post(http,B+'/tasks/'+t['id']+'/sla',csrf,{'policy_id':p['id'],'expected_revision':t['revision'],'request_key':'bind-sla-policy-001','rationale':'Apply this approved operational budget prospectively'})
    assert bound.status_code==201,bound.text
    timing=bound.json()['timing'];assert timing['sla']['policy_id']==p['id'] and timing['sla']['calendar_id']==cal['id']
    csrf=login(http,'root').json()['csrf_token']
    assert http.get('/api/v1/review-work/tasks/'+t['id']).status_code==403
    assert begin(http,t,csrf).status_code==403


def test_clock_evidence_is_immutable_and_blocks_signing_until_stopped(env,monkeypatch):
    from test_lifecycle import propose,approve
    http,sessions,ids,_=env;_,t,csrf=running(env);s=begin(http,t,csrf).json()
    assert sample(http,s,csrf,'retained-receipt-001',0).status_code==201
    # Signing must wait for an active reader lease, without modifying source history.
    from kestrel.services import lifecycle
    from kestrel.repositories.identity import principal
    from kestrel.models import Account
    from kestrel.services.auth import clock
    with sessions() as db:
        actor=principal(db,db.get(Account,ids['lawyer']),clock())
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as denied:lifecycle.manifest(db,actor,ids['matter'])
        assert denied.value.status_code==409
        for table in ['review_sessions','review_session_receipts']:
            with pytest.raises(DBAPIError):db.execute(text('DELETE FROM '+table));db.commit()
            db.rollback()
    assert post(http,B+'/sessions/'+s['id']+'/receipts',csrf,{'request_key':'close-before-sign','expected_sequence':1,'operation':'close','interaction':False}).status_code==201
    signing=propose(http,ids,'sign');assert approve(http,signing).status_code==200
    assert begin(http,t,login(http).json()['csrf_token'],key='after-freeze-open').status_code==409
    first=http.get('/api/v1/review-work/tasks/'+t['id']).json()['timing']
    from kestrel.services import review_clocks as c
    later=clock()+3600;monkeypatch.setattr(c,'clock',lambda:later)
    second=http.get('/api/v1/review-work/tasks/'+t['id']).json()['timing']
    assert first['as_of']==second['as_of'] and first['queue_age_seconds']==second['queue_age_seconds']


def test_prospective_business_budget_pause_exclusion_and_assignment_reset(env,monkeypatch):
    from kestrel.services import review_clocks as c,review_work as w
    from kestrel.services.auth import clock
    http,_,ids,_=env;_,p=create_sla(env,timezone='UTC',weekdays=list(range(7)),holidays=[],start_minute=0,end_minute=1440)
    _,t,csrf=running(env);base=clock();now=[base+100]
    monkeypatch.setattr(c,'clock',lambda:now[0]);monkeypatch.setattr(w,'clock',lambda:now[0])
    bound=post(http,B+'/tasks/'+t['id']+'/sla',csrf,{'policy_id':p['id'],'expected_revision':t['revision'],'request_key':'prospective-bind-001','rationale':'Budget starts at this explicit binding'}).json()
    assert bound['timing']['sla']['business_elapsed_seconds']==0
    now[0]=base+200;paused=change(http,bound,csrf,'pause').json()
    now[0]=base+400;resumed=change(http,paused,csrf,'resume').json()
    now[0]=base+500;shown=http.get('/api/v1/review-work/tasks/'+t['id']).json()
    assert shown['timing']['sla']['business_elapsed_seconds']==200
    assert shown['timing']['sla']['paused_business_seconds']==200
    reassigned=change(http,resumed,csrf,'reassign',assignee_id=ids['sme']);assert reassigned.status_code==201,reassigned.text
    assert reassigned.json()['timing']['sla']['status']=='unconfigured'


def test_precise_timing_is_not_exposed_to_unassigned_coworker(env,monkeypatch):
    from kestrel.services import review_clocks as c
    from kestrel.services.auth import clock
    http,_,ids,_=env;_,t,csrf=running(env);now=[clock()];monkeypatch.setattr(c,'clock',lambda:now[0])
    s=begin(http,t,csrf).json();now[0]+=15
    assert sample(http,s,csrf,'private-sample-001',0).json()['active_seconds']==15
    login(http,'sme')
    assert http.get(B+'/sessions/'+s['id']).status_code==403
    assert http.get('/api/v1/review-work/tasks/'+t['id']).json()['timing']['active_seconds'] is None


def test_long_term_task_history_survives_bounded_sla_calculation(env,monkeypatch):
    from kestrel.services import review_clocks as c
    from kestrel.services.auth import clock
    http,_,_,_=env;_,p=create_sla(env);_,t,csrf=running(env)
    bound=post(http,B+'/tasks/'+t['id']+'/sla',csrf,{'policy_id':p['id'],'expected_revision':t['revision'],'request_key':'long-record-bind-001','rationale':'Bind a versioned budget without rewriting prior history'})
    assert bound.status_code==201
    future=clock()+367*86400;monkeypatch.setattr(c,'clock',lambda:future)
    read=http.get('/api/v1/review-work/tasks/'+t['id']);assert read.status_code==200
    assert read.json()['timing']['sla']['status']=='calculation_unavailable'
    assert read.json()['events']


def test_timing_receipts_keep_restrictions_after_source_relaxation(env,monkeypatch):
    from kestrel.models import SourceVersion,DocumentPolicyVersion,CleanTeamMembership
    from kestrel.services import review_clocks as c
    from kestrel.services.auth import clock
    http,sessions,ids,_=env;source,t,csrf=running(env)
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
    now=[clock()];monkeypatch.setattr(c,'clock',lambda:now[0]);s=begin(http,t,csrf).json()
    with sessions() as db:
        policy=db.get(DocumentPolicyVersion,db.get(SourceVersion,source['id']).policy_id);policy.classification='clean_team';policy.clean_team_scope='pricing';db.commit()
    now[0]+=15;assert sample(http,s,csrf,'restricted-interval-001',0).status_code==201
    with sessions() as db:
        policy=db.get(DocumentPolicyVersion,db.get(SourceVersion,source['id']).policy_id);policy.classification='ordinary';policy.clean_team_scope=None
        db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;db.commit()
    assert http.get('/api/v1/workflow/documents/'+source['id']).status_code==200
    assert http.get(B+'/sessions/'+s['id']).status_code==403
    assert http.get('/api/v1/review-work/tasks/'+t['id']).json()['timing']['active_seconds'] is None
