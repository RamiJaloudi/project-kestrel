import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import candidate
from test_observability_governance import post
from kestrel.models import SourceArchive,EthicalWall

def test_internal_ai_qa_citations_budget_replay_and_external_denial(env,monkeypatch):
    from kestrel.adapters import openai_review
    http,_,ids,app=env;_,_,csrf=candidate(env,cloud_block=False)
    answer=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which contract contains change of control consent?'}).json()
    monkeypatch.setattr(openai_review,'configuration',lambda:(True,'synthetic-test-key'));calls=[]
    def send(payload):
        calls.append(payload)
        return {'status':'completed','usage':{'input_tokens':1000,'output_tokens':200},'output':[{'content':[{'type':'output_text','text':json.dumps({'insufficient_evidence':False,'claims':[{'text':'The cited synthetic agreement requires prior written consent on a change of control.','citations':[1]}]})}]}]}
    monkeypatch.setattr(openai_review,'send',send)
    path='/api/v1/questions/'+answer['id']+'/synthesize';key={'request_key':'qa-synthesize-once'}
    result=post(http,path,csrf,key);assert result.status_code==201,result.text
    assert result.json()['status']=='unreviewed_candidate' and '[1]' in result.json()['answer']
    assert post(http,path,csrf,key).json()['id']==result.json()['id'] and len(calls)==1
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        response=client.post(path,json=key,headers={'origin':'https://client.localhost','x-csrf-token':token});assert response.status_code==403

def test_archived_source_roundtrip_tampering_wall_and_worm_fail_closed(env,tmp_path,monkeypatch):
    from kestrel.adapters import archive_store
    http,sessions,ids,_=env;_,_,csrf=candidate(env)
    monkeypatch.setattr(archive_store,'ROOT',tmp_path/'protected-archives')
    monkeypatch.setattr(archive_store,'crypt',lambda value,protect:b'protected:'+value if protect else value[len(b'protected:'):])
    response=post(http,'/api/v1/archives',csrf,{'matter_id':ids['matter']});assert response.status_code==201,response.text
    row=response.json();assert row['source_count']==1 and not row['worm']
    assert post(http,'/api/v1/archives/'+row['id']+'/verify',csrf,{}).json()['verified']
    assert post(http,'/api/v1/archives',csrf,{'matter_id':ids['matter'],'require_worm':True}).status_code==503
    with sessions() as db:
        record=db.get(SourceArchive,row['id']);target=archive_store.path(record.storage_key)
    target.write_bytes(target.read_bytes()+b'tampered')
    assert post(http,'/api/v1/archives/'+row['id']+'/verify',csrf,{}).status_code==409
    csrf=login(http,'sme').json()['csrf_token'];assert post(http,'/api/v1/archives/'+row['id']+'/verify',csrf,{}).status_code==403
    csrf=login(http,'root').json()['csrf_token'];assert post(http,'/api/v1/archives/'+row['id']+'/verify',csrf,{}).status_code==403

def test_pdf_audit_retains_scoped_selection_and_hash(env,monkeypatch):
    from kestrel.adapters import audit_pdf
    import io,zipfile,hashlib
    http,_,_,_=env;login(http,'root')
    calls=[]
    monkeypatch.setattr(audit_pdf,'render',lambda rows,actor,filters:(calls.append(rows) or b'%PDF scoped test'))
    response=http.get('/api/v1/audit/export',params={'category':'administrative','format':'pdf'})
    assert response.status_code==200,response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest=json.loads(archive.read('manifest.json'));data=archive.read('events.pdf')
        assert manifest['event_ids']==[r['id'] for r in calls[0]] and manifest['sha256']==hashlib.sha256(data).hexdigest()

@pytest.mark.parametrize('revoke',[False,True])
def test_ai_qa_rejects_fabricated_citation_and_permission_loss(env,monkeypatch,revoke):
    from kestrel.adapters import openai_review
    from kestrel.models import QuestionAnswer
    http,sessions,ids,_=env;_,_,csrf=candidate(env,cloud_block=False)
    original=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Change of control consent requirements?'}).json()
    monkeypatch.setattr(openai_review,'configuration',lambda:(True,'synthetic-test-key'))
    def send(_):
        if revoke:
            with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
        return {'status':'completed','usage':{'input_tokens':1000,'output_tokens':200},'output':[{'content':[{'type':'output_text','text':json.dumps({'insufficient_evidence':False,'claims':[{'text':'Candidate legal text for strict citation validation.','citations':[1 if revoke else 999]}]})}]}]}
    monkeypatch.setattr(openai_review,'send',send)
    response=post(http,'/api/v1/questions/'+original['id']+'/synthesize',csrf,{'request_key':'denial-case-single-request'})
    assert response.status_code==(403 if revoke else 502),response.text
    with sessions() as db:assert len(list(db.scalars(select(QuestionAnswer))))==1

def test_audit_time_window_is_recorded_and_restricts_rows(env):
    from kestrel.models import AuditEvent
    http,sessions,ids,_=env;login(http,'lawyer')
    with sessions() as db:
        for instant in [10,20]:db.add(AuditEvent(occurred_at=instant,actor_id=ids['lawyer'],action='synthetic.window',outcome='allowed',category='legal_sme',matter_id=ids['matter']))
        db.commit()
    response=http.get('/api/v1/audit/events',params={'category':'legal_sme','matter_id':ids['matter'],'from_time':15,'to_time':25})
    assert response.status_code==200 and [r['occurred_at'] for r in response.json()]==[20]
    assert http.get('/api/v1/audit/events',params={'category':'legal_sme','from_time':30,'to_time':20}).status_code==422
