"""Authorization precedes every cluster, count, signal and drilldown."""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import upload
from test_observability_governance import post
from kestrel import models as m

B='/api/v1/intelligence'


def mount(env):
    from kestrel.api.intelligence import router
    if not any(getattr(route,'path','')==B+'/query' for route in env[3].routes):env[3].include_router(router)


def query(env,csrf,**kw):
    mount(env)
    return post(env[0],B+'/query',csrf,{'matter_id':env[2]['matter'],'view':'workstream',**kw})


def test_unknown_is_not_zero_and_domains_are_independent():
    from kestrel.services.intelligence import weighted_score,component
    unknown=weighted_score([component('missing',None,70,'No approved assessment')])
    assert unknown['status']=='UNKNOWN' and unknown['score'] is None
    partial=weighted_score([component('known',100,30,'Observed'),component('missing',None,70,'Unknown')])
    assert partial['status']=='PARTIAL' and partial['score']==100 and partial['coverage_weight']==30
    assert partial['components'][1]['value'] is None


def test_source_counts_groups_paths_and_evidence_are_authorized(env):
    h,_,ids,_=env;c=login(h).json()['csrf_token']
    s=upload(h,c,ids['matter']).json()
    r=query(env,c);assert r.status_code==200,r.text
    result=r.json();assert result['authorized_count']==1 and result['groups'][0]['count']==1
    assert result['rows'][0]['reader']['id']==s['id']
    assert result['rows'][0]['scores']['legal']['status']=='UNKNOWN'
    assert result['rows'][0]['scores']['financial']['status']=='UNKNOWN'
    drill=query(env,c,path=[result['groups'][0]['key']]).json()
    assert drill['matched_count']==1 and drill['level']=='custodian'
    assert query(env,c,path=['unavailable group']).json()['matched_count']==0
    root=login(h,'root').json()['csrf_token'];assert query(env,root).status_code==403


def test_denied_clean_team_and_retained_names_never_change_counts(env):
    from kestrel.services.auth import clock
    h,sessions,ids,_=env;c=login(h).json()['csrf_token'];ordinary=upload(h,c,ids['matter']).json()
    with sessions() as db:db.add(m.CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
    secret=upload(h,c,ids['matter'],logical_key='SECRET-GROUP-999',classification='clean_team',clean_team_scope='pricing').json()
    r=post(h,'/api/v1/review-work/sources/'+secret['id']+'/custodians',c,{'display_name':'Hidden custodian 999','custodian_type':'person','custody_role':'origin','provenance':'Protected synthetic inventory','request_key':'secret-custodian-test'})
    assert r.status_code==201,r.text
    with sessions() as db:
        db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;db.commit()
    r=query(env,c);assert r.status_code==200,r.text
    assert r.json()['authorized_count']==1 and r.json()['rows'][0]['id']==ordinary['id']
    assert secret['id'] not in r.text and 'Hidden custodian' not in r.text and 'SECRET-GROUP' not in r.text
    assert query(env,c,view='topic',search='Hidden custodian').json()['matched_count']==0


def test_review_task_delay_components_reuse_existing_timing(env):
    from test_review_work import task
    h,_,_,_=env;s,t,c=task(env)
    r=query(env,c,view='review');assert r.status_code==200,r.text
    row=r.json()['rows'][0]
    assert row['scores']['delay']['score'] is not None
    assert any(x['key']=='reassignments' and x['value']==0 for x in row['scores']['delay']['components'])
    assert row['tasks'][0]['id']==t['id']
    assert row['tasks'][0]['timing']['sla']['status']=='unconfigured'
    assert 'business days' not in row['scores']['delay']['explanation'].lower()


def test_bank_gate_released_facts_only_and_no_reviewer_details(env):
    from test_financial_workflow import source,payload
    h,_,ids,app=env;s,c=source(env)
    assert post(h,'/api/v1/financial/facts',c,payload(s['id'])).status_code==201
    mount(env)
    with TestClient(app,base_url='https://bank.localhost') as bank:
        b=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
        def ask(view='financial'):
            return bank.post(B+'/query',json={'matter_id':ids['matter'],'view':view},headers={'origin':'https://bank.localhost','x-csrf-token':b})
        assert ask().status_code==403
        root=login(h,'root').json()['csrf_token'];assert post(h,'/api/v1/financial/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Feature gate only, no release permission'}).status_code==200
        from test_financial_workflow import enable_org
        enable_org(h,root)
        r=ask();assert r.status_code==200,r.text
        assert r.json()['authorized_count']==0 and r.json()['groups']==[]
        assert s['id'] not in r.text
        assert ask('review').status_code==403


def test_auth_changes_during_projection_fail_closed(env,monkeypatch):
    from kestrel.services import intelligence as s
    h,sessions,ids,_=env;c=login(h).json()['csrf_token'];upload(h,c,ids['matter'])
    original=s.project
    def change(*args,**kwargs):
        result=original(*args,**kwargs)
        with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
        return result
    monkeypatch.setattr(s,'project',change)
    r=query(env,c);assert r.status_code in {403,409}
    assert 'file_name' not in r.text


def test_lexical_mfn_group_and_bounded_paths(env,monkeypatch):
    import test_document_workflow as dw
    monkeypatch.setattr(dw,'TEXT','Synthetic most-favored-nation clause. Equal commercial treatment requires legal review.')
    h,_,ids,_=env;c=login(h).json()['csrf_token'];s=upload(h,c,ids['matter']).json()
    assert post(h,dw.BASE+'/documents/'+s['id']+'/confirm',c,{'snapshot_hash':s['snapshot_hash'],'rationale':'Confirmed lexical topic evidence only'}).status_code==200
    r=query(env,c,view='topic',search='most-favored-nation');assert r.status_code==200,r.text
    assert any(g['label']=='Most favored nation' for g in r.json()['groups'])
    assert r.json()['rows'][0]['scores']['legal']['score'] is None
    assert query(env,c,path=['x']*5).status_code==422
    assert query(env,c,combined_priority=True).status_code==422


def test_released_bank_fact_drilldown_is_derivative_only_then_revoked(env,monkeypatch):
    import test_document_workflow as dw,test_disclosures as dis
    from test_financial_workflow import TEXT,payload,decision
    content=dw.TEXT+' '+TEXT;monkeypatch.setattr(dw,'TEXT',content);monkeypatch.setattr(dis,'TEXT',content)
    h,_,ids,app=env;src,plan,artifact,c=dis.prepared(env)
    sme=login(h,'sme').json()['csrf_token']
    assert post(h,dis.D+'/artifacts/'+artifact['id']+'/decisions',sme,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Approve exact synthetic sanitized financial disclosure'}).status_code==200
    c=login(h).json()['csrf_token'];text=h.get(dis.D+'/artifacts/'+artifact['id']+'/reader').json()['units'][0]['text']
    fact=post(h,'/api/v1/financial/facts',c,payload(artifact['id'],text,'derivative')).json()
    sme=login(h,'sme').json()['csrf_token'];assert decision(h,sme,fact,'verify').status_code==200;assert decision(h,sme,fact,'release').status_code==200
    root=login(h,'root').json()['csrf_token'];assert post(h,'/api/v1/financial/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Enable feature only after independent derivative/fact releases'}).status_code==200
    from test_financial_workflow import enable_org
    enable_org(h,root)
    mount(env)
    with TestClient(app,base_url='https://bank.localhost') as bank:
        b=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
        def ask(path=[]):
            return bank.post(B+'/query',json={'matter_id':ids['matter'],'view':'financial','path':path},headers={'origin':'https://bank.localhost','x-csrf-token':b})
        r=ask();assert r.status_code==200,r.text;result=r.json()
        assert result['authorized_count']==1 and result['rows'][0]['reader']['kind']=='disclosure'
        assert src['id'] not in r.text and ids['sme'] not in r.text and 'assignee' not in r.text and 'tasks' not in result['rows'][0]
        assert ask([result['groups'][0]['key']]).json()['level']=='period'
        sme=login(h,'sme').json()['csrf_token'];assert decision(h,sme,fact,'revoke').status_code==200
        assert ask().json()['authorized_count']==0


def test_cached_semantic_projection_never_calls_provider_and_rechecks_scope(env,monkeypatch):
    from test_document_workflow import candidate
    from kestrel.adapters import embeddings
    h,sessions,ids,_=env;source,_,c=candidate(env,cloud_block=False);calls=[]
    monkeypatch.setattr(embeddings,'configuration',lambda:(True,'synthetic-only-provider-key'))
    def send(texts):calls.append(len(texts));return [[1.0]+[0.0]*255 for _ in texts],100
    monkeypatch.setattr(embeddings,'send',send)
    result=post(h,'/api/v1/questions',c,{'matter_id':ids['matter'],'question':'Which assignment requires consent?','mode':'semantic','request_key':'intelligence-cache-fixture'})
    assert result.status_code==201,result.text;before=len(calls)
    r=query(env,c,view='semantic',seed_source_id=source['id']);assert r.status_code==200,r.text
    assert r.json()['rows'][0]['similarity']==1 and len(calls)==before
    assert query(env,c,view='hybrid',seed_source_id=source['id'],search='assignment').status_code==200
    assert len(calls)==before
    assert query(env,c,view='semantic',seed_source_id='unavailable-source').status_code==403
