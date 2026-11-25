import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import candidate,BASE,allow_processing
from test_observability_governance import post as firm_post

def post(http,path,csrf,payload=None,origin='https://firm.localhost'):
    return http.post(path,json=payload or {},headers={'origin':origin,'x-csrf-token':csrf})
from test_reports import generate,R
from kestrel.models import EthicalWall,DocumentPolicyVersion,SourceVersion,QuestionAnswer,AIOperation,AIBudgetPeriod,OperationReservation

Q='/api/v1/questions'

def test_qa_exact_evidence_wall_history_and_root_denial(env):
    http,sessions,ids,_=env;source,finding,csrf=candidate(env)
    answer=post(http,Q,csrf,{'matter_id':ids['matter'],'question':'Which agreements contain change of control consent?'});assert answer.status_code==201,answer.text
    row=answer.json();assert row['status']=='evidence_found' and row['citations']
    with sessions() as db:
        raw=db.get(SourceVersion,source['id']);units={u['number']:u for u in json.loads(raw.units_json)}
        for ref in row['citations']:
            span=ref['reader'];assert units[span['unit']]['text'][span['start']:span['end']]==ref['text']
        db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert http.get(Q+'/'+row['id']).status_code==403
    csrf=login(http,'root').json()['csrf_token'];assert post(http,Q,csrf,{'matter_id':ids['matter'],'question':'Change of control?'}).status_code==403
    csrf=login(http,'sme').json()['csrf_token'];assert http.get(Q+'/'+row['id']).status_code==403
    refused=post(http,Q,csrf,{'matter_id':ids['matter'],'question':'Are there uranium mining permits?'}).json()
    assert refused['status']=='insufficient_evidence' and refused['citations']==[]

def test_external_qa_only_approved_audience_and_revocation(env):
    http,sessions,ids,app=env;source,finding,csrf=candidate(env)
    report=generate(http,csrf,ids['matter'],finding['id']).json()
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        assert post(client,Q,token,{'matter_id':ids['matter'],'question':'Change of control?'},origin='https://client.localhost').json()['status']=='insufficient_evidence'
    csrf=login(http,'sme').json()['csrf_token']
    approval={'content_hash':report['content_hash'],'snapshot_hash':report['snapshot_hash'],'rationale':'Independent full audience package review'}
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,approval).status_code==200
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        response=post(client,Q,token,{'matter_id':ids['matter'],'question':'Change of control?'},origin='https://client.localhost');assert response.status_code==201,response.text
        answer=response.json();assert answer['status']=='evidence_found' and all(c['kind']=='report' and c['reader'] is None for c in answer['citations'])
        with sessions() as db:db.get(DocumentPolicyVersion,db.get(SourceVersion,source['id']).policy_id).quarantined=True;db.commit()
        assert client.get(Q+'/'+answer['id']).status_code==403
        assert all(r['id']!=answer['id'] for r in client.get(Q,params={'matter_id':ids['matter']}).json())
    with TestClient(app,base_url='https://bank.localhost') as bank:
        token=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
        assert post(bank,Q,token,{'matter_id':ids['matter'],'question':'Change of control?'},origin='https://bank.localhost').json()['citations']==[]

@pytest.mark.parametrize('revoke',[False,True])
def test_ai_report_new_unapproved_version_shared_budget_and_reauth(env,monkeypatch,revoke):
    from kestrel.adapters import openai_review
    from kestrel.models import Account
    http,sessions,ids,_=env;source,finding,csrf=candidate(env,cloud_block=False)
    report=generate(http,csrf,ids['matter'],finding['id']).json();calls=[]
    monkeypatch.setattr(openai_review,'configuration',lambda:(True,'synthetic-test-key'))
    def send(payload):
        calls.append(payload)
        if revoke:
            with sessions() as db:db.get(Account,ids['lawyer']).active=False;db.commit()
        return {'status':'completed','usage':{'input_tokens':1500,'output_tokens':500},'output':[{'content':[{'type':'output_text','text':json.dumps({'overview':'AI draft limited to the selected reviewed finding.','sections':[{'index':0,'text':'The reviewed change-of-control finding requires counsel follow-up.'}]})}]}]}
    monkeypatch.setattr(openai_review,'send',send)
    key={'request_key':'report-ai-once-only'}
    response=post(http,R+'/'+report['id']+'/ai-draft',csrf,key)
    assert response.status_code==(401 if revoke else 201),response.text
    with sessions() as db:
        operation=db.scalar(select(AIOperation));reservation=db.get(OperationReservation,operation.id);budget=db.get(AIBudgetPeriod,reservation.period)
        assert reservation.state=='settled' and budget.spent_cents==1 and budget.reserved_cents==0
        assert operation.state==('failed' if revoke else 'succeeded')
    if not revoke:
        result=response.json();assert result['version']==2 and not result['released'] and result['content_hash']!=report['content_hash']
        assert result['body']['risks']==report['body']['risks'] and result['body']['sections'][0]['reference']==report['body']['sections'][0]['reference']
        replay=post(http,R+'/'+report['id']+'/ai-draft',csrf,key);assert replay.status_code==201 and replay.json()['id']==result['id'] and len(calls)==1

def test_ai_report_refuses_missing_budget_without_call(env,monkeypatch):
    from kestrel.adapters import openai_review
    from kestrel.services.ai_budget import period
    http,sessions,ids,_=env;_,finding,csrf=candidate(env,cloud_block=False)
    report=generate(http,csrf,ids['matter'],finding['id']).json()
    monkeypatch.setattr(openai_review,'configuration',lambda:(True,'synthetic-test-key'))
    monkeypatch.setattr(openai_review,'send',lambda _:pytest.fail('No provider call permitted'))
    with sessions() as db:db.add(AIBudgetPeriod(period=period(),spent_cents=801,reserved_cents=0));db.commit()
    assert post(http,R+'/'+report['id']+'/ai-draft',csrf,{'request_key':'budget-denial-test'}).status_code==429
