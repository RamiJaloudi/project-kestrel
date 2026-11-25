from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import candidate,upload,BASE
from test_observability_governance import post
from test_reports import generate
from kestrel.models import ClientSubmission,SourceVersion,MatterLifecycle
L='/api/v1/lifecycle'

def propose(http,ids,kind):
    csrf=login(http,'lawyer').json()['csrf_token']
    result=post(http,L,csrf,{'matter_id':ids['matter'],'kind':kind,'rationale':'Explicit synthetic lifecycle action requested for controlled verification'})
    assert result.status_code==201,result.text
    return result.json()

def approve(http,row,account='sme'):
    csrf=login(http,account).json()['csrf_token']
    return post(http,L+'/'+row['id']+'/approve',csrf,{'content_hash':row['content_hash'],'rationale':'Independent exact lifecycle payload and authority review'})

def test_signing_freezes_content_but_retains_read_and_closing_legal_hold_separates_client_copies(env):
    http,sessions,ids,app=env;source,finding,csrf=candidate(env)
    from kestrel.bootstrap import provision
    from kestrel.models import MatterAssignment
    from kestrel.services.auth import clock
    from test_auth_policy import PASSWORD
    with sessions() as db:
        security=provision(db,'security-only','firm',['security_approver'],PASSWORD)
        db.add(MatterAssignment(account_id=security.id,matter_id=ids['matter'],expires_at=clock()+3600));db.commit()
    report=generate(http,csrf,ids['matter'],finding['id']).json()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,{'content_hash':report['content_hash'],'snapshot_hash':report['snapshot_hash'],'rationale':'Independent complete report approval'}).status_code==200
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        content=b'Synthetic client integration plan for post-closing records test.'
        response=client.post('/api/v1/client-uploads',params={'matter_id':ids['matter'],'file_name':'plan.txt','synthetic':True},content=content,headers={'origin':'https://client.localhost','x-csrf-token':token,'content-type':'application/octet-stream'})
        assert response.status_code==201,response.text
        client_upload=response.json()
        csrf=login(http,'lawyer').json()['csrf_token']
        firm=post(http,'/api/v1/client-uploads/'+client_upload['id']+'/accept',csrf,{'logical_key':'CLIENT-PLAN','rationale':'Accept client integration plan into a separate firm matter record'}).json()
        signing=propose(http,ids,'sign')
        assert approve(http,signing).status_code==200
        assert client.get(BASE+'/releases/'+report['release_id']).status_code==200
        csrf=login(http,'lawyer').json()['csrf_token']
        assert upload(http,csrf,ids['matter'],logical_key='AFTER-SIGNING').status_code==409
        assert generate(http,csrf,ids['matter'],finding['id']).status_code==409
        assert http.get(BASE+'/documents/'+source['id']+'/reader').status_code==200
        hold=propose(http,ids,'hold');assert approve(http,hold).status_code==200
        closing=propose(http,ids,'close');assert approve(http,closing,'security-only').status_code==200
        assert client.get(BASE+'/releases/'+report['release_id']).status_code==403
        deletion=propose(http,ids,'delete_client_copies');assert approve(http,deletion,'security-only').status_code==409
        release_hold=propose(http,ids,'release_hold');assert approve(http,release_hold).status_code==200
        assert approve(http,deletion,'security-only').status_code==200
        with sessions() as db:
            retained=db.get(SourceVersion,firm['id']);submission=db.get(ClientSubmission,client_upload['id']);state=db.get(MatterLifecycle,ids['matter'])
            assert retained.data==content and submission.data is None and submission.parsed_json is None
            assert submission.bytes_hash==retained.bytes_hash and state.frozen and state.external_closed and not state.legal_hold
            assert state.firm_retention=='indefinite_pending_approved_retention_schedule'

def test_stale_snapshot_self_approval_and_root_denied(env):
    http,_,ids,_=env;_,_,csrf=candidate(env)
    signing=propose(http,ids,'sign')
    csrf=login(http,'lawyer').json()['csrf_token']
    assert post(http,L+'/'+signing['id']+'/approve',csrf,{'content_hash':signing['content_hash'],'rationale':'Attempted self approval of snapshot'}).status_code==403
    assert upload(http,csrf,ids['matter'],logical_key='LATE-DOCUMENT').status_code==201
    assert approve(http,signing).status_code==409
    login(http,'root');assert http.get(L,params={'matter_id':ids['matter']}).status_code==403
