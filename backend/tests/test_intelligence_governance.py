"""Additive governed profiles, source-bound alerts and default-off organization gate."""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_observability_governance import post
from test_review_work import task
from kestrel import models as m

B='/api/v1/intelligence'


def profile(env):
    h,_,ids,_=env;c=login(h,'root').json()['csrf_token']
    result=post(h,B+'/profiles',c,{'matter_id':ids['matter'],'name':'Synthetic deterministic profile','expected_previous_version':0,'alert_threshold':0,'minimum_coverage':1,'recipient_ids':[ids['lawyer']],'assignee_id':ids['lawyer'],'rationale':'Explicit synthetic operational prioritization profile','request_key':uuid.uuid4().hex})
    assert result.status_code==201,result.text
    row=result.json();c=login(h,'sme').json()['csrf_token']
    result=post(h,B+'/profiles/'+row['id']+'/decisions',c,{'operation':'approve','content_hash':row['content_hash'],'rationale':'Independently approve exact operational weights and named recipients'})
    assert result.status_code==200,result.text
    result=post(h,B+'/profiles/'+row['id']+'/decisions',c,{'operation':'publish','content_hash':row['content_hash'],'rationale':'Publish independently approved operational profile'})
    assert result.status_code==200,result.text
    return result.json()


def test_org_gate_default_off_independent_from_matter_gate(env):
    h,_,ids,app=env;c=login(h,'root').json()['csrf_token']
    assert h.get('/api/v1/financial/organization-gate').json()['enabled'] is False
    assert post(h,'/api/v1/financial/bank-gate?matter_id='+ids['matter'],c,{'expected_revision':0,'enabled':True,'rationale':'Matter feature only must not enable organization'}).status_code==200
    with TestClient(app,base_url='https://bank.localhost') as bank:
        b=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
        def query():return bank.post('/api/v1/financial/query',json={'matter_id':ids['matter']},headers={'origin':'https://bank.localhost','x-csrf-token':b})
        assert query().status_code==403
        assert post(h,'/api/v1/financial/organization-gate',c,{'expected_revision':0,'enabled':True,'rationale':'Explicit organization feature gate with no content grants'}).status_code==200
        assert query().json()['authorized_count']==0
        assert post(h,'/api/v1/financial/organization-gate',c,{'expected_revision':1,'enabled':False,'rationale':'Disable organization access independently of matter setting'}).status_code==200
        assert query().status_code==403


def test_profile_requires_independent_sme_and_append_only_versions(env):
    h,sessions,ids,_=env;c=login(h,'sme').json()['csrf_token']
    result=post(h,B+'/profiles',c,{'matter_id':ids['matter'],'name':'No self approval','expected_previous_version':0,'recipient_ids':[ids['lawyer']],'assignee_id':ids['lawyer'],'rationale':'Synthetic versioned operational weights','request_key':uuid.uuid4().hex})
    assert result.status_code==201,result.text;row=result.json()
    assert post(h,B+'/profiles/'+row['id']+'/decisions',c,{'operation':'approve','content_hash':row['content_hash'],'rationale':'Self approval remains forbidden'}).status_code==403
    c=login(h,'root').json()['csrf_token']
    assert post(h,B+'/profiles/'+row['id']+'/decisions',c,{'operation':'approve','content_hash':row['content_hash'],'rationale':'Root cannot confer approval'}).status_code==403
    with sessions() as db:
        with pytest.raises(DBAPIError):db.execute(text("UPDATE intelligence_profiles SET name='changed'"));db.commit()
        db.rollback()


def test_hot_alert_dedup_task_recipient_disposition_and_freeze(env):
    h,sessions,ids,_=env;s,t,c=task(env);p=profile(env);c=login(h).json()['csrf_token']
    def scan():return post(h,B+'/profiles/'+p['id']+'/scan',c,{'rationale':'Evaluate current authorized deterministic source signals'})
    first=scan();assert first.status_code==200,first.text;assert first.json()['created']>=1
    assert scan().json()['created']==0
    alerts=h.get(B+'/alerts?matter_id='+ids['matter']).json();assert alerts
    row=alerts[0];assert row['task_id']!=t['id'] and row['state']=='open'
    assert post(h,B+'/alerts/'+row['id']+'/read',c,{}).json()['read'] is True
    assert h.get(B+'/alerts?matter_id='+ids['matter']).json()[0]['state']=='open'
    result=post(h,B+'/alerts/'+row['id']+'/dispositions',c,{'operation':'acknowledge','expected_revision':0,'rationale':'Lawyer acknowledges operational follow-up only'})
    assert result.status_code==200,result.text
    with sessions() as db:
        from kestrel.services.review_work import audit_records
        event=db.scalar(select(m.IntelligenceAlertDisposition).where(m.IntelligenceAlertDisposition.alert_id==row['id']))
        assert any(isinstance(record,m.IntelligenceAlert) and record.id==row['id'] for record in audit_records(db,event.id))
    with sessions() as db:db.add(m.MatterLifecycle(matter_id=ids['matter'],frozen=True));db.commit()
    assert scan().status_code==409
    assert post(h,B+'/alerts/'+row['id']+'/dispositions',c,{'operation':'close','expected_revision':1,'rationale':'Cannot alter retained disposition after freeze'}).status_code==409
    with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert h.get(B+'/alerts?matter_id='+ids['matter']).status_code==403


def test_override_cannot_self_approve_and_is_source_snapshot_bound(env):
    h,sessions,ids,_=env;s,t,c=task(env);p=profile(env);c=login(h).json()['csrf_token']
    projection=post(h,B+'/query',c,{'matter_id':ids['matter'],'view':'workstream','profile_id':p['id']}).json();row=projection['rows'][0]
    result=post(h,B+'/overrides',c,{'source_id':s['id'],'profile_id':p['id'],'domain':'delay','value':42,'base_hash':row['scores']['delay']['base_hash'],'expires_in_hours':1,'rationale':'Human operational exception; preserve deterministic baseline','request_key':uuid.uuid4().hex})
    assert result.status_code==201,result.text;override=result.json()
    assert post(h,B+'/overrides/'+override['id']+'/decisions',c,{'operation':'approve','content_hash':override['content_hash'],'rationale':'Self approval cannot change score'}).status_code==403
    c=login(h,'sme').json()['csrf_token'];assert post(h,B+'/overrides/'+override['id']+'/decisions',c,{'operation':'approve','content_hash':override['content_hash'],'rationale':'Independent checked operational exception'}).status_code==200
    result=post(h,B+'/query',c,{'matter_id':ids['matter'],'view':'workstream','profile_id':p['id']}).json()['rows'][0]['scores']['delay']
    assert result['override']['value']==42 and result['score']!=42


def test_changed_task_revision_prevents_stale_override_approval(env):
    from test_review_work import change
    h,_,ids,_=env;s,t,c=task(env);p=profile(env);c=login(h).json()['csrf_token']
    row=post(h,B+'/query',c,{'matter_id':ids['matter'],'profile_id':p['id']}).json()['rows'][0]
    override=post(h,B+'/overrides',c,{'source_id':s['id'],'profile_id':p['id'],'domain':'delay','value':42,'base_hash':row['scores']['delay']['base_hash'],'expires_in_hours':1,'rationale':'Propose exact before a task revision changes','request_key':uuid.uuid4().hex}).json()
    assert change(h,t,c,'accept').status_code==201
    sme=login(h,'sme').json()['csrf_token']
    result=post(h,B+'/overrides/'+override['id']+'/decisions',sme,{'operation':'approve','content_hash':override['content_hash'],'rationale':'Stale underlying task revision must not approve'})
    assert result.status_code==409,result.text
