import json
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from test_auth_policy import env,login
from test_document_workflow import upload,BASE
from test_observability_governance import post
from kestrel.models import Client,MatterValidation,MatterAssignment,Role,RoleGrant,EthicalWall,SourceVersion,DocumentPolicyVersion
from kestrel.services.auth import clock
W='/api/v1/wall-checker'

def setup(env):
    http,sessions,ids,_=env
    with sessions() as db:
        validation=db.get(MatterValidation,ids['matter']);client=db.get(Client,validation.client_id);client.client_number='012345';validation.matter_number='789012'
        db.get(MatterValidation,ids['other']).matter_number='789013'
        role=db.scalar(select(Role).where(Role.name=='conflicts_approver'))
        if not role:role=Role(name='conflicts_approver');db.add(role);db.flush()
        db.add(RoleGrant(account_id=ids['sme'],role_id=role.id))
        for user in ['root','sme','lawyer']:db.add(MatterAssignment(account_id=ids[user],matter_id=ids['other'],expires_at=clock()+3600))
        db.commit()
    return login(http,'root').json()['csrf_token']

def propose(http,csrf,**changes):
    body={'client_number':'012345','entry_type':'restriction','username':'lawyer','days':30,'rationale':'Synthetic explicit restriction for independent Conflicts review',**changes}
    result=post(http,W+'/controls',csrf,body);assert result.status_code==201,result.text
    return result.json()

def approve(http,row):
    csrf=login(http,'sme').json()['csrf_token']
    result=post(http,W+'/controls/'+row['id']+'/approve',csrf,{'rationale':'Independent scoped Conflicts review of exact policy version'})
    assert result.status_code==200,result.text
    return result.json()

def check(http,csrf,matter='789012',**changes):
    return post(http,W+'/check',csrf,{'client_number':'012345','matter_number':matter,'username':'lawyer','action':'read',**changes})

def test_client_wall_inherits_all_matters_and_retirement_preserves_history(env):
    http,_,ids,_=env;csrf=setup(env);row=propose(http,csrf)
    assert check(http,csrf).json()['person']['eligible']
    assert post(http,W+'/controls/'+row['id']+'/approve',csrf,{'rationale':'Root cannot approve policy'}).status_code==403
    approve(http,row)
    csrf=login(http,'root').json()['csrf_token']
    for matter in ['789012','789013']:
        value=check(http,csrf,matter).json();assert value['person']['client_restricted'] and not value['person']['eligible']
    login(http,'lawyer')
    assert http.get('/test/source/'+ids['matter']).status_code==403 and http.get('/test/source/'+ids['other']).status_code==403
    csrf=login(http,'root').json()['csrf_token']
    retirement=post(http,W+'/controls/'+row['id']+'/retire',csrf,{'rationale':'Propose retirement after independent re-evaluation of the wall'}).json()
    assert not check(http,csrf).json()['person']['eligible']
    approve(http,retirement)
    csrf=login(http,'root').json()['csrf_token'];assert check(http,csrf).json()['person']['eligible']
    controls=http.get(W+'/controls',params={'client_number':'012345'}).json()
    assert len(controls)==2 and any(c['id']==row['id'] and c['retired'] for c in controls)

def test_matter_wall_does_not_conflict_person_at_client_or_other_matter(env):
    http,_,ids,_=env;csrf=setup(env);row=propose(http,csrf,matter_number='789012');approve(http,row)
    csrf=login(http,'root').json()['csrf_token']
    client=check(http,csrf,None).json();assert not client['person']['client_restricted'] and client['person']['eligible'] is None
    denied=check(http,csrf).json();assert denied['person']['matter_restricted'] and not denied['person']['client_restricted']
    assert check(http,csrf,'789013').json()['person']['eligible']
    login(http,'lawyer');assert http.get('/test/source/'+ids['matter']).status_code==403 and http.get('/test/source/'+ids['other']).status_code==200

def test_role_and_relationship_rule_are_conjunctive_and_neutral_relationship_grants_nothing(env):
    http,_,ids,_=env;csrf=setup(env)
    rule=propose(http,csrf,username=None,role_name='firm_lawyer',relationship_kind='external_adviser');approve(http,rule)
    csrf=login(http,'root').json()['csrf_token'];assert check(http,csrf).json()['person']['eligible']
    relation=propose(http,csrf,entry_type='relationship',relationship_kind='external_adviser');approve(http,relation)
    csrf=login(http,'root').json()['csrf_token'];assert check(http,csrf).json()['person']['client_restricted']
    # A role alone does not satisfy the relationship selector.
    assert check(http,csrf,username='sme').json()['person']['eligible']

def test_person_documents_uses_real_pdp_and_does_not_grant_admin_source_access(env):
    http,sessions,ids,_=env;setup(env)
    csrf=login(http,'lawyer').json()['csrf_token'];source=upload(http,csrf,ids['matter']).json()
    assert post(http,BASE+'/documents/'+source['id']+'/confirm',csrf,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm synthetic source classification'}).status_code==200
    csrf=login(http,'root').json()['csrf_token']
    result=check(http,csrf,document_version_ids=[source['id']]).json()
    assert result['allowed'] and result['documents'][0]['allowed'] and result['simulation_only']
    assert 'Synthetic contract.' not in json.dumps(result) and 'classification' not in result['documents'][0]
    assert http.get(BASE+'/documents/'+source['id']+'/reader').status_code==403
    assert not check(http,csrf,username='root',document_version_ids=[source['id']]).json()['allowed']
    catalogue=http.get(W+'/documents',params={'client_number':'012345','matter_number':'789012'}).json()
    assert catalogue['documents'] and all(not d['can_read'] and 'file_name' not in d for d in catalogue['documents'])
    with sessions() as db:
        from kestrel.models import DocumentPolicyVersion
        db.get(DocumentPolicyVersion,db.get(SourceVersion,source['id']).policy_id).quarantined=True;db.commit()
    assert not check(http,csrf,document_version_ids=[source['id']]).json()['allowed']

def test_checker_denies_ordinary_users_walled_operators_self_changes_and_wrong_scope(env):
    http,sessions,ids,_=env;csrf=setup(env)
    assert post(http,W+'/controls',csrf,{'client_number':'012345','entry_type':'restriction','username':'root','days':30,'rationale':'Attempt to change own access'}).status_code==403
    csrf=login(http,'lawyer').json()['csrf_token'];assert check(http,csrf).status_code==403
    csrf=login(http,'root').json()['csrf_token'];assert check(http,csrf,client_number='999999').status_code==403
    with sessions() as db:db.add(EthicalWall(account_id=ids['root'],matter_id=ids['matter']));db.commit()
    assert check(http,csrf).status_code==403
    assert check(http,csrf,None).status_code==403

def test_checker_legacy_wall_and_unavailable_subject_fail_closed(env):
    http,sessions,ids,_=env;csrf=setup(env)
    with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert check(http,csrf).json()['person']['matter_restricted']
    result=check(http,csrf,username='missing',document_version_ids=['unknown']).json()
    assert not result['allowed'] and not result['documents'][0]['allowed']
    assert post(http,W+'/check','bad-csrf',{'client_number':'012345','username':'lawyer','action':'read'}).status_code==403

def test_relationship_alone_does_not_assign_and_default_controls_do_not_expire(env):
    from kestrel.bootstrap import provision
    from test_auth_policy import PASSWORD
    http,sessions,ids,_=env;csrf=setup(env)
    with sessions() as db:provision(db,'unassigned-person','firm',['firm_lawyer'],PASSWORD)
    relation=propose(http,csrf,entry_type='relationship',username='unassigned-person',relationship_kind='relationship_partner',days=None)
    assert relation['expires_at'] is None
    approve(http,relation)
    csrf=login(http,'root').json()['csrf_token'];value=check(http,csrf,username='unassigned-person').json()
    assert not value['person']['eligible'] and not value['person']['client_restricted'] and 'NO_ACTIVE_MATTER_ASSIGNMENT' in value['person']['reason_codes']

def test_client_wall_covers_future_matters_and_compatibility_contracts(env):
    from kestrel.models import Matter,Account
    from kestrel.repositories.identity import principal
    http,sessions,ids,_=env;csrf=setup(env)
    with sessions() as db:db.get(Account,ids['lawyer']).email='lawyer@synthetic.example';db.commit()
    before=post(http,'/api/ethical-walls',csrf,{'clientId':'012345','matterId':'789012','emails':['lawyer@synthetic.example']})
    assert before.json()['results'][0]['allowed']
    wall=propose(http,csrf,days=None);approve(http,wall)
    with sessions() as db:
        client_id=db.get(MatterValidation,ids['matter']).client_id
        future=Matter(name='Future synthetic matter');db.add(future);db.flush()
        db.add(MatterValidation(matter_id=future.id,client_id=client_id,matter_number='789014',status='validated'))
        db.add(MatterAssignment(account_id=ids['lawyer'],matter_id=future.id,expires_at=clock()+3600));db.commit()
        assert future.id in principal(db,db.get(Account,ids['lawyer']),clock()).walls
    csrf=login(http,'root').json()['csrf_token']
    response=post(http,'/api/ethical-walls',csrf,{'clientId':'012345','matterId':'789012','emails':['lawyer@synthetic.example']})
    # The reference response shape is retained, including when a subject is unavailable.
    assert response.status_code==200 and set(response.json())=={'mode','policyRevision','results'} and not response.json()['results'][0]['allowed']
    csrf=login(http,'lawyer').json()['csrf_token']
    assert not http.post('/api/client-matter-validations',json={'clientId':'012345','matterId':'789012'},headers={'origin':'https://firm.localhost','x-csrf-token':csrf}).json()['valid']

def test_client_relationship_rule_does_not_lift_matter_relationship_to_entire_client(env):
    http,_,_,_=env;csrf=setup(env)
    relation=propose(http,csrf,entry_type='relationship',relationship_kind='external_adviser',matter_number='789012');approve(http,relation)
    csrf=login(http,'root').json()['csrf_token'];rule=propose(http,csrf,username=None,relationship_kind='external_adviser');approve(http,rule)
    csrf=login(http,'root').json()['csrf_token']
    assert check(http,csrf).json()['person']['eligible'] and check(http,csrf,'789013').json()['person']['eligible']
    local=propose(http,csrf,username=None,relationship_kind='external_adviser',matter_number='789012');approve(http,local)
    csrf=login(http,'root').json()['csrf_token']
    assert not check(http,csrf).json()['person']['eligible'] and check(http,csrf,'789013').json()['person']['eligible']

def test_restricted_interest_denies_and_control_receipts_are_immutable(env):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    http,sessions,_,_=env;csrf=setup(env)
    relation=propose(http,csrf,entry_type='relationship',relationship_kind='restricted_interest');approve(http,relation)
    csrf=login(http,'root').json()['csrf_token'];assert check(http,csrf).json()['person']['client_restricted']
    with sessions() as db:
        for sql in ["UPDATE wall_controls SET rationale='changed'","DELETE FROM wall_control_decisions","DELETE FROM wall_check_records"]:
            with pytest.raises(DBAPIError):db.execute(text(sql));db.commit()
            db.rollback()

def test_checker_oauth_requires_check_scope_and_human_decisions_require_session(env):
    from kestrel.models import ServiceClient,ServiceToken
    from kestrel.services.auth import HASHER,digest
    http,sessions,ids,_=env;csrf=setup(env)
    with sessions() as db:
        client=ServiceClient(client_name='checker-service',account_id=ids['root'],scopes='Documents.Authorize EthicalWalls.Check',secret_hash=HASHER.hash('test-only-scoped-client-secret'))
        db.add(client);db.flush()
        for token,scope in [('wrong-scope-token','Documents.Authorize'),('correct-scope-token','EthicalWalls.Check')]:db.add(ServiceToken(client_id=client.id,token_hash=digest(token),scopes=scope,expires_at=clock()+300))
        db.commit()
    http.cookies.clear();body={'client_number':'012345','matter_number':'789012','username':'lawyer','action':'read'}
    assert http.post(W+'/check',json=body,headers={'authorization':'Bearer wrong-scope-token'}).status_code==403
    assert http.post(W+'/check',json=body,headers={'authorization':'Bearer correct-scope-token'}).json()['person']['eligible']
    assert http.post(W+'/controls',json={'client_number':'012345','entry_type':'restriction','username':'lawyer','rationale':'Token must not publish or draft human governance decisions'},headers={'authorization':'Bearer correct-scope-token'}).status_code==401

def test_history_is_historical_and_walled_operator_loses_receipt_access(env):
    http,sessions,ids,_=env;csrf=setup(env)
    original=check(http,csrf).json();assert original['person']['eligible']
    wall=propose(http,csrf,matter_number='789012');approve(http,wall)
    csrf=login(http,'root').json()['csrf_token']
    assert not check(http,csrf).json()['person']['eligible']
    receipt=http.get(W+'/checks/'+original['receipt_id']).json()
    assert receipt['person']['eligible'] and 'Historical decision' in receipt['notice']
    assert http.get(W+'/checks',params={'client_number':'012345','matter_number':'789012'}).json()
    with sessions() as db:db.add(EthicalWall(account_id=ids['root'],matter_id=ids['matter']));db.commit()
    assert http.get(W+'/checks/'+original['receipt_id']).status_code==403

def test_check_does_not_accept_asserted_roles_or_document_attributes(env):
    http,_,_,_=env;csrf=setup(env)
    assert check(http,csrf,roles=['root_admin']).status_code==422
    assert check(http,csrf,document_attributes={'classification':'ordinary','released':True}).status_code==422
    assert check(http,csrf,action='delete').status_code==422

def test_missing_person_policy_view_is_unhealthy_not_unrestricted(env):
    from sqlalchemy import text
    http,sessions,_,_=env
    assert http.get('/health/ready').status_code==200
    with sessions() as db:
        db.execute(text('DROP VIEW vw_person_wall_rules'));db.execute(text('DROP VIEW vw_person_relationships'));db.execute(text('DROP VIEW vw_person_wall_entries'));db.commit()
    assert http.get('/health/ready').status_code==503

def test_assignment_is_reported_separately_from_matter_validation(env):
    http,sessions,ids,_=env;csrf=setup(env)
    with sessions() as db:db.get(MatterValidation,ids['matter']).status='pending';db.commit()
    value=check(http,csrf).json()
    assert value['person']['assignment_active'] and not value['person']['eligible']
    assert 'MATTER_NOT_VALIDATED' in value['person']['reason_codes'] and 'NO_ACTIVE_MATTER_ASSIGNMENT' not in value['person']['reason_codes']
