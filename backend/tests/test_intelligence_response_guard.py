"""Prepared governance metadata is withheld after current person/scope changes."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,delete
from test_auth_policy import env,login
from test_observability_governance import post
from test_intelligence_governance import profile
from kestrel import models as m
from kestrel.services.auth import clock

B='/api/v1/intelligence'


def withheld(response,*canaries):
    assert response.status_code in {401,403,409},response.text
    assert all(value not in response.text for value in canaries)


def test_profile_list_withholds_metadata_after_role_removal(env,monkeypatch):
    from kestrel.services import intelligence_governance as g
    h,sessions,ids,_=env;p=profile(env);login(h,'sme');original=g.profiles
    def changed(db,actor,matter):
        result=original(db,actor,matter)
        with sessions() as writer:writer.execute(delete(m.RoleGrant).where(m.RoleGrant.account_id==ids['sme']));writer.commit()
        return result
    monkeypatch.setattr(g,'profiles',changed)
    withheld(h.get(B+'/profiles?matter_id='+ids['matter']),p['id'],p['name'])


def test_people_list_rechecks_root_role_before_returning_names(env,monkeypatch):
    from kestrel.services import intelligence_governance as g
    h,sessions,ids,_=env;login(h,'root')
    with sessions() as writer:writer.get(m.Account,ids['lawyer']).display_name='Scoped person canary 987';writer.commit()
    original=g.configuration_people
    def changed(db,actor,matter):
        result=original(db,actor,matter)
        with sessions() as writer:writer.execute(delete(m.RoleGrant).where(m.RoleGrant.account_id==ids['root']));writer.commit()
        return result
    monkeypatch.setattr(g,'configuration_people',changed)
    withheld(h.get(B+'/profiles/people?matter_id='+ids['matter']),'Scoped person canary 987',ids['lawyer'])


def test_alert_inbox_withholds_prepared_clean_team_rows_after_scope_revoked(env,monkeypatch):
    from kestrel.services import intelligence_governance as g
    from test_document_workflow import upload
    h,sessions,ids,_=env
    with sessions() as writer:
        for uid in [ids['lawyer'],ids['sme']]:writer.add(m.CleanTeamMembership(account_id=uid,matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600))
        writer.commit()
    c=login(h).json()['csrf_token'];source=upload(h,c,ids['matter'],classification='clean_team',clean_team_scope='pricing').json()
    task=post(h,'/api/v1/review-work/sources/'+source['id']+'/tasks',c,{'stage':'review','assignee_id':ids['lawyer'],'rationale':'Explicit restricted synthetic operational task','request_key':'restricted-fresh-alert-001'});assert task.status_code==201,task.text
    p=profile(env);c=login(h).json()['csrf_token'];r=post(h,B+'/profiles/'+p['id']+'/scan',c,{'rationale':'Create restricted operational alert for freshness check'});assert r.status_code==200,r.text
    assert h.get(B+'/alerts?matter_id='+ids['matter']).json()
    original=g.inbox
    def changed(db,actor,matter):
        result=original(db,actor,matter)
        with sessions() as writer:
            writer.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;writer.commit()
        return result
    monkeypatch.setattr(g,'inbox',changed)
    withheld(h.get(B+'/alerts?matter_id='+ids['matter']),source['id'],task.json()['id'])


def test_bank_governance_reads_are_denied_before_preparing_any_metadata(env,monkeypatch):
    from kestrel.services import intelligence_governance as g
    h,_,ids,app=env;p=profile(env)
    def forbidden(*args,**kw):raise AssertionError('Bank must not prepare internal governance metadata')
    for name in ['profiles','configuration_people','inbox','overrides']:monkeypatch.setattr(g,name,forbidden)
    with TestClient(app,base_url='https://bank.localhost') as bank:
        login(bank,'bank',origin='https://bank.localhost')
        for path in ['/profiles?matter_id='+ids['matter'],'/profiles/people?matter_id='+ids['matter'],'/alerts?matter_id='+ids['matter'],'/overrides?source_id=unavailable-source']:
            withheld(bank.get(B+path),p['id'],p['name'],ids['matter'])


def test_profile_write_does_not_return_prepared_metadata_after_root_walled(env,monkeypatch):
    import uuid
    from kestrel.services import intelligence_governance as g
    h,sessions,ids,_=env;c=login(h,'root').json()['csrf_token'];original=g.create_profile
    def changed(db,actor,payload):
        result=original(db,actor,payload)
        with sessions() as writer:writer.add(m.EthicalWall(account_id=ids['root'],matter_id=ids['matter']));writer.commit()
        return result
    monkeypatch.setattr(g,'create_profile',changed)
    result=post(h,B+'/profiles',c,{'matter_id':ids['matter'],'name':'Post-write metadata canary 663','expected_previous_version':0,'recipient_ids':[ids['lawyer']],'assignee_id':ids['lawyer'],'rationale':'Profile mutation was authorized before current scope changed','request_key':uuid.uuid4().hex})
    withheld(result,'Post-write metadata canary 663',ids['matter'])
    # The authorized transaction committed before the later wall; withholding its
    # response must not claim that it silently rolled back the retained record.
    with sessions() as db:assert db.scalar(select(m.IntelligenceProfile.id).where(m.IntelligenceProfile.name=='Post-write metadata canary 663'))
