from fastapi.testclient import TestClient
from test_auth_policy import env,login
from test_observability_governance import post
from kestrel.models import EthicalWall
U='/api/v1/client-uploads'

def test_halden_submission_own_only_firm_acceptance_separate_record_and_walls(env):
    http,sessions,ids,app=env
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        params={'matter_id':ids['matter'],'file_name':'integration-plan.txt','synthetic':True}
        content=b'Synthetic integration plan. Phase one aligns the document registers.'
        def upload():return client.post(U,params=params,content=content,headers={'origin':'https://client.localhost','x-csrf-token':token,'content-type':'application/octet-stream'})
        response=upload();assert response.status_code==201,response.text
        row=response.json();assert client.get(U+'/'+row['id']+'/download').content==content
        assert upload().status_code==409
        with TestClient(app,base_url='https://bank.localhost') as bank:
            login(bank,'bank',origin='https://bank.localhost');assert bank.get(U+'/'+row['id']).status_code==403
        csrf=login(http,'root').json()['csrf_token'];assert http.get(U+'/'+row['id']).status_code==403
        csrf=login(http,'lawyer').json()['csrf_token'];assert http.get(U+'/'+row['id']).json()['units']
        body={'logical_key':'CLIENT-INTEGRATION-001','rationale':'Firm lawyer accepts the synthetic client submission for intake review'}
        accepted=post(http,U+'/'+row['id']+'/accept',csrf,body);assert accepted.status_code==201,accepted.text
        assert not accepted.json()['classification_confirmed']
        assert post(http,U+'/'+row['id']+'/accept',csrf,body).status_code==409
        assert client.get('/api/v1/workflow/documents/'+accepted.json()['id']).status_code==403
        with sessions() as db:db.add(EthicalWall(account_id=ids['client'],matter_id=ids['matter']));db.commit()
        assert client.get(U+'/'+row['id']+'/download').status_code==403

def test_client_competitive_upload_requires_named_membership(env):
    _,_,ids,app=env
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        response=client.post(U,params={'matter_id':ids['matter'],'file_name':'pricing.txt','synthetic':True},content=b'Synthetic clean-team pricing document.',headers={'origin':'https://client.localhost','x-csrf-token':token,'content-type':'application/octet-stream'})
        assert response.status_code==403
