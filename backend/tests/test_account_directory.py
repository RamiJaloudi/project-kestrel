"""Root-only account metadata, pinned profiles and fresh authority checks."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,delete,func
from test_auth_policy import env,login,PASSWORD
from test_observability_governance import post
from kestrel import models as m

A='/api/v1/admin/accounts'
FIELDS={'id','upn','display_name','employee_id','organization','roles','active','revision'}


def root(http):return login(http,'root').json()['csrf_token']


def revoke(sessions,ids,kind):
    with sessions() as db:
        if kind=='root':
            role=db.scalar(select(m.Role.id).where(m.Role.name=='root_admin'))
            db.execute(delete(m.RoleGrant).where(m.RoleGrant.account_id==ids['root'],m.RoleGrant.role_id==role))
        else:
            for session in db.scalars(select(m.ServerSession).where(m.ServerSession.account_id==ids['root'])):session.revoked=True
        db.commit()


def test_root_directory_filters_stable_id_paging_and_secret_free_projection(env):
    http,sessions,ids,_=env
    with sessions() as db:
        for name in ['lawyer','sme']:
            account=db.get(m.Account,ids[name]);account.display_name='Same Directory Name';account.employee_id='0000'+('1' if name=='lawyer' else '2')
            account.password_hash='PASSWORD_HASH_CANARY_NOT_A_REAL_PASSWORD';account.email='SECRET_EMAIL_CANARY@example.test'
            if name=='sme':account.email='OTHER_SECRET_EMAIL_CANARY@example.test'
        db.get(m.Account,ids['bank']).active=False;db.commit()
    csrf=root(http)
    p={'draw':8,'start':0,'length':1,'sort':'display_name','direction':'asc','account_filters':{'organization':'firm'},'column_filters':{'display_name':'Same Directory Name'}}
    response=post(http,A+'/query',csrf,p);assert response.status_code==200,response.text
    first=response.json();assert (first['draw'],first['recordsTotal'],first['recordsFiltered'])==(8,3,2)
    second=post(http,A+'/query',csrf,{**p,'start':1}).json()
    assert [first['data'][0]['id'],second['data'][0]['id']]==sorted([ids['lawyer'],ids['sme']])
    assert all(set(row)==FIELDS for row in [*first['data'],*second['data']])
    assert first['data'][0]['employee_id'].startswith('0000')
    assert 'CANARY' not in response.text and 'password' not in response.text and 'token' not in response.text and 'email' not in response.text
    inactive=post(http,A+'/query',csrf,{'account_filters':{'active':False}})
    assert inactive.status_code==200 and inactive.json()['recordsTotal']==1 and inactive.json()['data'][0]['id']==ids['bank'],inactive.text
    searched=post(http,A+'/query',csrf,{'search':'00001','account_filters':{'organization':'firm'}}).json()
    assert searched['recordsTotal']==3 and searched['recordsFiltered']==1 and searched['data'][0]['id']==ids['lawyer']
    assert post(http,A+'/query',csrf,{'search':'CANARY'}).json()['recordsFiltered']==0


@pytest.mark.parametrize('name,host',[('lawyer','firm'),('sme','firm'),('bank','bank'),('client','client')])
def test_non_root_roles_cannot_list_query_or_pin_directory_metadata(env,name,host):
    _,_,ids,app=env
    with TestClient(app,base_url='https://'+host+'.localhost') as http:
        origin='https://'+host+'.localhost';csrf=login(http,name,origin=origin).json()['csrf_token']
        response=http.post(A+'/query',json={},headers={'origin':origin,'x-csrf-token':csrf})
        assert response.status_code==403,response.text
        assert http.get(A).status_code==403
        assert http.get(A+'/'+ids['root'],params={'revision':1}).status_code==403
        assert 'employee_id' not in response.text and 'recordsTotal' not in response.text


def test_directory_root_authority_is_independent_of_legal_matter_access(env):
    http,sessions,ids,_=env;csrf=root(http)
    with sessions() as db:
        for row in db.scalars(select(m.MatterAssignment).where(m.MatterAssignment.account_id==ids['root'])):row.revoked=True
        db.add(m.EthicalWall(account_id=ids['root'],matter_id=ids['matter'],active=True));db.commit()
    response=post(http,A+'/query',csrf,{});assert response.status_code==200 and response.json()['recordsTotal']==5,response.text
    assert post(http,'/api/v1/tables/inventory/query',csrf,{'matter_id':ids['matter']}).status_code==403


@pytest.mark.parametrize('extra',[{'draw':True},{'start':-1},{'length':51},{'length':0},{'sort':'password_hash'},{'direction':'sideways'},
    {'search':{'regex':True}},{'column_filters':{'password_hash':'x'}},{'account_filters':{'organization':'unknown'}},
    {'account_filters':{'active':'true'}},{'account_filters':{'active':1}},{'account_filters':{'role':'root_admin'}},
    {'matter_id':'unrelated'},{'saved_view_id':'unsupported'},{'source_filters':{}},{'export':'csv'}])
def test_directory_query_rejects_untyped_or_non_directory_contracts(env,extra):
    http,_,_,_=env;csrf=root(http)
    assert post(http,A+'/query',csrf,extra).status_code==422


def test_pinned_detail_requires_positive_current_profile_revision_and_keeps_patch_contract(env):
    http,sessions,ids,_=env;csrf=root(http)
    response=http.get(A+'/'+ids['lawyer'],params={'revision':1});assert response.status_code==200,response.text
    value=response.json();assert set(value)==FIELDS and value['revision']==1
    for params in [{},{'revision':0},{'revision':-1},{'revision':'not-an-integer'}]:assert http.get(A+'/'+ids['lawyer'],params=params).status_code==422
    response=http.patch(A+'/'+ids['lawyer'],json={'display_name':'Exact Pinned Lawyer','employee_id':'000012','expected_revision':1},headers={'origin':'https://firm.localhost','x-csrf-token':csrf})
    assert response.status_code==200 and response.json()['revision']==2 and response.json()['employee_id']=='000012',response.text
    response=http.get(A+'/'+ids['lawyer'],params={'revision':1});assert response.status_code==409 and 'Exact Pinned Lawyer' not in response.text
    assert http.get(A+'/'+ids['lawyer'],params={'revision':2}).json()['display_name']=='Exact Pinned Lawyer'
    located=post(http,A+'/query',csrf,{'length':2,'column_filters':{'id':ids['lawyer']}}).json()
    assert located['recordsFiltered']==1 and located['data'][0]['revision']==2
    # The string employee ID is unique within an employer, not across employers.
    cross_employer=http.patch(A+'/'+ids['bank'],json={'display_name':'Bank Directory Identity','employee_id':'000012','expected_revision':1},headers={'origin':'https://firm.localhost','x-csrf-token':csrf})
    assert cross_employer.status_code==200 and cross_employer.json()['employee_id']=='000012',cross_employer.text


@pytest.mark.parametrize('operation',['query','list','detail'])
@pytest.mark.parametrize('kind',['root','session'])
def test_prepared_directory_reads_withhold_metadata_after_root_or_session_loss(env,monkeypatch,operation,kind):
    from kestrel.services import account_directory as directory
    http,sessions,ids,_=env;csrf=root(http);original=directory.rows;fired=False
    def prepared_then_revoke(*args,**kwargs):
        nonlocal fired
        result=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return result
    monkeypatch.setattr(directory,'rows',prepared_then_revoke)
    response=post(http,A+'/query',csrf,{}) if operation=='query' else http.get(A) if operation=='list' else http.get(A+'/'+ids['lawyer'],params={'revision':1})
    assert fired and response.status_code in {401,403},response.text
    assert 'employee_id' not in response.text and 'recordsTotal' not in response.text and 'lawyer' not in response.text


@pytest.mark.parametrize('kind',['root','session'])
def test_patch_rolls_back_metadata_and_allowed_audit_when_authority_is_lost_before_commit(env,monkeypatch,kind):
    from kestrel.services import account_directory as directory
    http,sessions,ids,_=env;csrf=root(http);original=directory.prepare_edit;fired=False
    with sessions() as db:
        before=(db.get(m.Account,ids['lawyer']).display_name,db.get(m.Account,ids['lawyer']).employee_id,db.get(m.Account,ids['lawyer']).profile_revision)
        audits=db.scalar(select(func.count()).select_from(m.AuditEvent).where(m.AuditEvent.action=='account.metadata',m.AuditEvent.outcome=='allowed'))
    def prepared_then_revoke(*args,**kwargs):
        nonlocal fired
        value=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return value
    monkeypatch.setattr(directory,'prepare_edit',prepared_then_revoke)
    response=http.patch(A+'/'+ids['lawyer'],json={'display_name':'MUST NOT COMMIT','employee_id':'000099','expected_revision':1},headers={'origin':'https://firm.localhost','x-csrf-token':csrf})
    assert fired and response.status_code in {401,403},response.text
    with sessions() as db:
        account=db.get(m.Account,ids['lawyer']);assert (account.display_name,account.employee_id,account.profile_revision)==before
        assert db.scalar(select(func.count()).select_from(m.AuditEvent).where(m.AuditEvent.action=='account.metadata',m.AuditEvent.outcome=='allowed'))==audits


def test_root_self_name_edit_receipt_preserves_current_authority_and_other_fields(env):
    http,sessions,ids,_=env;csrf=root(http)
    response=http.get(A+'/'+ids['root'],params={'revision':1});assert response.status_code==200,response.text;before=response.json()
    response=http.patch(A+'/'+ids['root'],json={'display_name':'Renamed Root Operator','employee_id':'000001','expected_revision':1},headers={'origin':'https://firm.localhost','x-csrf-token':csrf})
    assert response.status_code==200,response.text;after=response.json()
    assert after['revision']==2 and after['display_name']=='Renamed Root Operator' and after['employee_id']=='000001'
    assert all(after[key]==before[key] for key in ['id','upn','organization','roles','active'])
    assert post(http,A+'/query',csrf,{}).status_code==200


@pytest.mark.parametrize('kind',['root','session'])
def test_legacy_full_directory_get_rechecks_authority_after_projecting_a_row(env,monkeypatch,kind):
    from kestrel.api import profile
    http,sessions,ids,_=env;root(http);original=profile.metadata;fired=False
    def projection_then_revoke(*args,**kwargs):
        nonlocal fired
        value=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return value
    monkeypatch.setattr(profile,'metadata',projection_then_revoke)
    response=http.get(A)
    assert fired and response.status_code in {401,403},response.text
    assert 'employee_id' not in response.text and 'lawyer' not in response.text


@pytest.mark.parametrize('kind',['root','session'])
def test_legacy_metadata_patch_never_commits_after_initial_root_check_is_revoked(env,monkeypatch,kind):
    from kestrel.api import profile
    http,sessions,ids,_=env;csrf=root(http);original=profile.root;fired=False
    with sessions() as db:before=db.get(m.Account,ids['lawyer']).display_name
    def permission_then_revoke(*args,**kwargs):
        nonlocal fired
        result=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return result
    monkeypatch.setattr(profile,'root',permission_then_revoke)
    response=http.patch(A+'/'+ids['lawyer'],json={'display_name':'LEGACY MUST NOT COMMIT','employee_id':'000088','expected_revision':1},headers={'origin':'https://firm.localhost','x-csrf-token':csrf})
    assert fired and response.status_code in {401,403},response.text
    with sessions() as db:assert db.get(m.Account,ids['lawyer']).display_name==before


def test_account_directory_query_exposes_a_typed_secret_free_page_in_openapi(env):
    http,_,_,app=env;csrf=root(http)
    response=post(http,A+'/query',csrf,{'length':2});assert response.status_code==200,response.text
    assert set(response.json())=={'draw','recordsTotal','recordsFiltered','data','count_basis'}
    assert all(set(row)==FIELDS for row in response.json()['data'])
    spec=app.openapi()
    schema=spec['paths'][A+'/query']['post']['responses']['200']['content']['application/json']['schema']
    assert schema=={'$ref':'#/components/schemas/AccountDirectoryPage'}
    page=spec['components']['schemas']['AccountDirectoryPage']
    assert set(page['properties'])=={'draw','recordsTotal','recordsFiltered','data','count_basis'}
    assert page['properties']['data']['maxItems']==50
    assert page['properties']['data']['items']=={'$ref':'#/components/schemas/AccountMetadata'}
    assert set(spec['components']['schemas']['AccountMetadata']['properties'])==FIELDS
