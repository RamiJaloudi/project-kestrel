import hashlib
import io
import json
import zipfile
from pathlib import Path
import pytest
from sqlalchemy import select,update
from sqlalchemy.exc import DBAPIError
from fastapi.testclient import TestClient
from test_auth_policy import env,login
from kestrel.models import AuditEvent,GovernanceVersion,Role,RoleGrant,CleanTeamMembership
from kestrel.services.auth import audit,clock


def post(http,path,csrf,payload=None):
    return http.post(path,json=payload or {},headers={'origin':'https://firm.localhost','x-csrf-token':csrf})


def test_exception_diagnostics_redact_and_correlate(env,tmp_path,monkeypatch):
    _,_,_,app=env
    monkeypatch.setenv('KESTREL_LOG_DIR',str(tmp_path/'logs'))
    @app.get('/test/crash')
    def crash():raise RuntimeError('PASSWORD document passage API_TOKEN')
    with TestClient(app,base_url='https://firm.localhost',raise_server_exceptions=False) as http:
        r=http.get('/test/crash')
    assert r.status_code==503 and r.json()['correlation_id']
    content=(tmp_path/'logs'/'api.jsonl').read_text()
    assert all(s not in content for s in ['PASSWORD','document passage','API_TOKEN'])
    row=json.loads(content.splitlines()[-1])
    assert row['exception_type']=='RuntimeError' and row['frames'] and row['correlation_id']==r.json()['correlation_id']


def test_own_audit_exports_manifest_and_admin_no_clean_override(env):
    http,sessions,ids,_=env
    with sessions() as db:
        audit(db,'sme.example','allowed',ids['sme'],category='legal_sme',matter_id=ids['matter'])
        audit(db,'lawyer.example','allowed',ids['lawyer'],category='legal_sme',matter_id=ids['matter'])
        db.commit()
    login(http,'sme')
    rows=http.get('/api/v1/audit/events?category=legal_sme').json()
    assert {r['actor_id'] for r in rows}=={ids['sme']}
    for format in ['jsonl','csv','html']:
        result=http.get('/api/v1/audit/export?category=legal_sme&format='+format)
        assert result.status_code==200
        with zipfile.ZipFile(io.BytesIO(result.content)) as report:
            data=report.read('events.'+format);manifest=json.loads(report.read('manifest.json'))
            assert hashlib.sha256(data).hexdigest()==manifest['sha256']
            assert manifest['exported_by']==ids['sme'] and not manifest['immutable_storage']
    login(http,'root')
    assert http.get('/api/v1/audit/export?category=clean_team').status_code==403


def test_clean_team_guides_and_audit_require_active_membership(env):
    http,sessions,ids,_=env
    login(http)
    assert http.get('/api/v1/resources/engines').status_code==200
    assert http.get('/api/v1/resources/clean-team/download').status_code==403
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+100))
        audit(db,'ct.example','allowed',ids['lawyer'],category='clean_team',matter_id=ids['matter'],clean_team_scope='pricing')
        audit(db,'ct.other','allowed',ids['sme'],category='clean_team',matter_id=ids['matter'],clean_team_scope='pricing')
        db.commit()
    assert http.get('/api/v1/resources/clean-team/download').status_code==200
    rows=http.get('/api/v1/audit/events?category=clean_team').json()
    assert len(rows)==1 and rows[0]['actor_id']==ids['lawyer']
    with sessions() as db:
        role=Role(name='clean_team_auditor');db.add(role);db.flush()
        db.add(RoleGrant(account_id=ids['lawyer'],role_id=role.id));db.commit()
    assert len(http.get('/api/v1/audit/events?category=clean_team').json())==2
    with sessions() as db:
        db.scalar(select(CleanTeamMembership)).expires_at=clock()-1;db.commit()
    assert http.get('/api/v1/audit/events?category=clean_team').status_code==403


def test_legal_playbook_independent_approval_exact_tests_immutability(env):
    http,sessions,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    starter=json.loads((Path(__file__).resolve().parents[2]/'data/playbooks/PB-STARTER-GOVERNED-DRAFT.json').read_text())
    draft=post(http,'/api/v1/policy-editor',csrf,{'name':'Synthetic draft','kind':'legal_playbook','matter_id':ids['matter'],'definition':starter})
    assert draft.status_code==201
    version=draft.json()['id'];path='/api/v1/policy-editor/'+version
    assert post(http,path+'/test',csrf).json()['passed']
    decision={'expected_revision':1,'rationale':'Synthetic tests reviewed'}
    assert post(http,path+'/submit',csrf,decision).status_code==200
    decision['expected_revision']=2
    assert post(http,path+'/approve',csrf,decision).status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,path+'/approve',csrf,decision).status_code==200
    csrf=login(http,'root').json()['csrf_token'];decision['expected_revision']=3
    assert post(http,path+'/publish',csrf,decision).json()['state']=='published'
    with sessions() as db:
        with pytest.raises(DBAPIError):
            db.execute(update(GovernanceVersion).where(GovernanceVersion.id==version).values(name='tampered'));db.commit()
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(update(AuditEvent).values(outcome='tampered'));db.commit()
        db.rollback()


def test_security_policy_needs_designated_role_and_enforces_environment(env):
    http,sessions,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    draft=post(http,'/api/v1/policy-editor',csrf,{'name':'EU no AI','kind':'environment_policy','matter_id':ids['matter'],
       'definition':{'block_ai':True,'block_cloud':False,'block_external':True,'allowed_regions':['EU']}}).json()
    path='/api/v1/policy-editor/'+draft['id']
    assert post(http,path+'/submit',csrf,{'expected_revision':1,'rationale':'Security review requested'}).status_code==200
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,path+'/approve',csrf,{'expected_revision':2,'rationale':'Legal title not security authority'}).status_code==403
    with sessions() as db:
        role=Role(name='security_approver');db.add(role);db.flush();db.add(RoleGrant(account_id=ids['sme'],role_id=role.id));db.commit()
    assert post(http,path+'/approve',csrf,{'expected_revision':2,'rationale':'Independent security review'}).status_code==200
    csrf=login(http,'root').json()['csrf_token']
    assert post(http,path+'/publish',csrf,{'expected_revision':3,'rationale':'Publish approved exact policy'}).status_code==200
    with sessions() as db:
        from kestrel.models import MatterValidation
        client=db.get(MatterValidation,ids['matter']).client_id
    payload={'clientId':client,'matterId':ids['matter'],'environment':{'hosting':'cloud','region':'EU','aiEnabled':False,'externalSharing':False}}
    assert post(http,'/api/client-matter-validations',csrf,payload).json()['workspaceAllowed']
    payload['environment']['aiEnabled']=True
    assert not post(http,'/api/client-matter-validations',csrf,payload).json()['workspaceAllowed']


def test_conflicts_policy_denies_existing_session_after_independent_publication(env):
    http,sessions,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    created=post(http,'/api/v1/policy-editor',csrf,{'name':'Additional wall','kind':'wall_policy','matter_id':ids['matter'],
        'definition':{'deny_account_ids':[ids['lawyer']]}})
    path='/api/v1/policy-editor/'+created.json()['id']
    assert post(http,path+'/submit',csrf,{'expected_revision':1,'rationale':'Conflicts review requested'}).status_code==200
    with sessions() as db:
        role=Role(name='conflicts_approver');db.add(role);db.flush();db.add(RoleGrant(account_id=ids['sme'],role_id=role.id));db.commit()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,path+'/approve',csrf,{'expected_revision':2,'rationale':'Independent conflicts decision'}).status_code==200
    csrf=login(http,'root').json()['csrf_token']
    assert post(http,path+'/publish',csrf,{'expected_revision':3,'rationale':'Publish additional deny'}).status_code==200
    login(http,'lawyer')
    assert http.get('/test/source/'+ids['matter']).status_code==403
