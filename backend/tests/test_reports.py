import json
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_document_workflow import candidate,BASE
from test_observability_governance import post
R='/api/v1/reports'
def generate(http,csrf,matter,key,audience='halden'):
    return post(http,R+'/generate',csrf,{'matter_id':matter,'audience':audience,'kind':'board_pack','title':'Project Kestrel board briefing','finding_ids':[key]})
def test_reports_edit_approval_audience_and_immutability(env,monkeypatch):
    http,sessions,ids,_=env;source,finding,csrf=candidate(env)
    response=generate(http,csrf,ids['matter'],finding['id']);assert response.status_code==201,response.text
    report=response.json();assert report['section_findings'][0]['revision_id']==finding['id']
    assert report['section_findings'][0]['summary']==finding['summary']
    body=report['body'];assert body['sections'] and body['risks'] and isinstance(body['consents'],list)
    assert 'quote' not in json.dumps(body) and 'complete diligence coverage' in body['coverage']
    approval={'content_hash':report['content_hash'],'snapshot_hash':report['snapshot_hash'],'rationale':'Reviewed full report sections and annexes'}
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,approval).status_code==403
    from fastapi.testclient import TestClient
    from kestrel.adapters import report_export
    monkeypatch.setattr(report_export,'export',lambda *args:b'authorized artifact')
    with TestClient(env[3],base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get(R,params={'matter_id':ids['matter']}).json()==[]
        assert client.get(R+'/'+report['id']+'/download/pdf').status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,approval).status_code==200
    with TestClient(env[3],base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        visible=client.get(R,params={'matter_id':ids['matter']}).json()[0]
        assert visible['body']==body and 'citations' not in visible
        assert 'section_findings' not in visible and 'previous_id' not in visible
        assert client.get(R+'/'+report['id']+'/download/pdf').content==b'authorized artifact'
    with TestClient(env[3],base_url='https://bank.localhost') as bank:
        login(bank,'bank',origin='https://bank.localhost');assert bank.get(R+'/'+report['id']+'/download/pdf').status_code==403
    csrf=login(http,'lawyer').json()['csrf_token']
    edit={k:body[k] for k in ['title','overview','coverage']};edit['sections']=[{'heading':s['heading'],'text':'Lawyer corrected this section with a new explanation.'} for s in body['sections']]
    revised=post(http,R+'/'+report['id']+'/versions',csrf,edit)
    assert revised.status_code==201,revised.text
    assert revised.json()['version']==2 and not revised.json()['released']
    assert revised.json()['previous_id']==report['id']
    assert revised.json()['report_key']==report['report_key']
    assert revised.json()['section_findings']==report['section_findings']
    assert revised.json()['content_hash']!=report['content_hash']
    assert post(http,R+'/'+report['id']+'/versions',csrf,edit).status_code==409
    with sessions() as db:
        with pytest.raises(DBAPIError):db.execute(text("UPDATE report_versions SET body_json='{}'"));db.commit()
        db.rollback()
    from test_diligence import assessment
    assert post(http,'/api/v1/diligence/findings/'+finding['id']+'/revisions',csrf,assessment(source)).status_code==201
    with TestClient(env[3],base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get(R+'/'+report['id']+'/download/pdf').status_code==403
    login(http,'root');assert http.get(R,params={'matter_id':ids['matter']}).json()==[]
def test_report_bank_privilege_and_candidate_denial(env):
    http,sessions,ids,_=env;source,finding,csrf=candidate(env,'privileged')
    assert generate(http,csrf,ids['matter'],finding['id'],'castlegate').status_code==403
    from kestrel.models import SourceFinding,DocumentPolicyVersion
    with sessions() as db:
        db.get(DocumentPolicyVersion,db.get(SourceFinding,finding['id']).policy_id).review_state='candidate';db.commit()
    assert generate(http,csrf,ids['matter'],finding['id']).status_code==409

def test_download_reauthenticates_after_render(env,monkeypatch):
    from kestrel.adapters import report_export
    from kestrel.models import Account
    http,sessions,ids,_=env;_,finding,csrf=candidate(env)
    report=generate(http,csrf,ids['matter'],finding['id']).json()
    def slow_renderer(*args):
        with sessions() as db:db.get(Account,ids['lawyer']).active=False;db.commit()
        return b'not to be returned'
    monkeypatch.setattr(report_export,'export',slow_renderer)
    response=http.get(R+'/'+report['id']+'/download/pdf')
    assert response.status_code==401 and b'not to be returned' not in response.content
