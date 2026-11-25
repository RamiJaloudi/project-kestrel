"""Registry metadata and assignment authority, separate from legal-source access."""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete,func,select
from test_auth_policy import env,login
from test_observability_governance import post
from kestrel import models as m
from kestrel.services.auth import clock

B='/api/v1/validation'
ACCESS={'id','account_id','matter_id','username','organization','assigned','blocked','effective_blocked','active'}
HISTORY={'id','matter_id','kind','rationale','actor_id','target_id','occurred_at','revision'}
CONTEXT={'matter_id','matter_name','client_id','client_name','client_number','matter_number','client_matter_number','validation_status','revision'}
TARGET={'account_id','username','organization','assigned','blocked','effective_blocked','active','matter_revision'}


def root(http):return login(http,'root').json()['csrf_token']


def grid(http,csrf,ids,dataset='access',**changes):return post(http,B+'/tables/'+dataset+'/query',csrf,{'matter_id':ids['matter'],**changes})


def deny(response,*private):
    assert response.status_code in {401,403,409},response.text
    assert 'recordsTotal' not in response.text and all(value not in response.text for value in private)


def revoke(sessions,ids,kind):
    with sessions() as db:
        if kind=='role':
            role=db.scalar(select(m.Role.id).where(m.Role.name=='root_admin'))
            db.execute(delete(m.RoleGrant).where(m.RoleGrant.account_id==ids['root'],m.RoleGrant.role_id==role))
        elif kind=='session':
            for row in db.scalars(select(m.ServerSession).where(m.ServerSession.account_id==ids['root'])):row.revoked=True
        elif kind=='assignment':
            for row in db.scalars(select(m.MatterAssignment).where(m.MatterAssignment.account_id==ids['root'],m.MatterAssignment.matter_id==ids['matter'])):row.expires_at=clock()-1
        elif kind=='wall':db.add(m.EthicalWall(account_id=ids['root'],matter_id=ids['matter'],active=True))
        elif kind=='target':db.get(m.Account,ids['lawyer']).active=False
        db.commit()


def command(ids,**changes):return {'username':'lawyer','assigned':True,'blocked':False,'days':14,'expected_revision':1,'rationale':'Explicit synthetic assignment update',**changes}


def decision(sessions,ids,**changes):
    with sessions() as db:
        row=m.AdministrationDecision(**{'matter_id':ids['matter'],'actor_id':ids['root'],'kind':'matter.pending','rationale':'Synthetic registry event',
            'revision':1,'occurred_at':20,**changes});db.add(row);db.flush();key=row.id;db.commit();return key


@pytest.mark.parametrize('status',['pending','rejected'])
def test_pending_and_rejected_matter_management_uses_direct_root_scope_not_validated_legal_scope(env,status):
    http,sessions,ids,_=env;csrf=root(http)
    with sessions() as db:db.get(m.MatterValidation,ids['matter']).status=status;db.commit()
    r=grid(http,csrf,ids);assert r.status_code==200 and r.json()['recordsTotal']==5,r.text
    assert r.json()['matter_revision']==1 and set(r.json()['data'][0])==ACCESS
    assert post(http,'/api/v1/tables/inventory/query',csrf,{'matter_id':ids['matter']}).status_code==403
    context=http.get(B+'/matters/'+ids['matter']+'/context',params={'revision':1})
    assert context.status_code==200 and set(context.json())==CONTEXT and context.json()['validation_status']==status,context.text


def test_access_historical_participants_direct_and_effective_walls_stable_paging(env):
    http,sessions,ids,_=env
    with sessions() as db:
        for row in db.scalars(select(m.MatterAssignment).where(m.MatterAssignment.account_id==ids['lawyer'])):row.revoked=True
        for row in db.scalars(select(m.MatterAssignment).where(m.MatterAssignment.account_id==ids['bank'])):row.expires_at=clock()-1
        db.get(m.Account,ids['bank']).active=False
        db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True))
        db.add(m.GovernanceVersion(matter_id=ids['matter'],author_id=ids['root'],kind='wall_policy',name='Synthetic published restriction',
            definition_json=json.dumps({'deny_account_ids':[ids['sme']]}),content_hash='0'*64,state='published'))
        db.commit()
    csrf=root(http);r=grid(http,csrf,ids,length=50);assert r.status_code==200,r.text
    value=r.json();assert value['recordsTotal']==5
    rows={row['account_id']:row for row in value['data']}
    assert rows[ids['lawyer']]['assigned'] is False and rows[ids['lawyer']]['blocked'] is True and rows[ids['lawyer']]['effective_blocked'] is True
    assert rows[ids['sme']]['blocked'] is False and rows[ids['sme']]['effective_blocked'] is True
    assert rows[ids['bank']]['assigned'] is False and rows[ids['bank']]['active'] is False
    assert all(row['id']==row['account_id'] and row['matter_id']==ids['matter'] and set(row)==ACCESS for row in rows.values())
    pages=[grid(http,csrf,ids,sort='organization',length=1,start=n).json()['data'][0]['id'] for n in range(5)]
    expected=sorted(rows,key=lambda key:(rows[key]['organization'],key));assert pages==expected
    searched=grid(http,csrf,ids,search='bank').json();assert searched['recordsTotal']==5 and searched['recordsFiltered']==1
    assert grid(http,csrf,ids,column_filters={'effective_blocked':'true'}).json()['recordsFiltered']==2
    assert grid(http,csrf,ids,search='.*').json()['recordsFiltered']==0


def test_history_real_ids_permitted_prefixes_order_and_literal_rationale_filters(env):
    http,sessions,ids,_=env
    first=decision(sessions,ids,id='decision-a',revision=2,rationale='Matched retained rationale')
    second=decision(sessions,ids,id='decision-b',kind='access.assigned_1.wall_0',revision=2,rationale='Matched retained rationale')
    decision(sessions,ids,kind='legal.secret',rationale='PRIVATE_NONREGISTRY_HISTORY')
    decision(sessions,ids,matter_id=ids['other'],rationale='PRIVATE_FOREIGN_HISTORY')
    csrf=root(http);r=grid(http,csrf,ids,'history',draw=9,length=1,sort='revision',direction='desc',search='Matched')
    assert r.status_code==200,r.text;value=r.json()
    assert (value['draw'],value['recordsTotal'],value['recordsFiltered'],value['matter_revision'])==(9,2,2,1)
    assert value['data'][0]['id']==first and set(value['data'][0])==HISTORY
    assert grid(http,csrf,ids,'history',start=1,length=1).json()['data'][0]['id']==second
    assert 'PRIVATE_' not in r.text and value['data'][0]['matter_id']==ids['matter']


@pytest.mark.parametrize('name,host',[('lawyer','firm'),('sme','firm'),('bank','bank'),('client','client')])
def test_registry_grids_and_pinned_reads_deny_non_root_before_metadata(env,name,host):
    _,_,ids,app=env
    with TestClient(app,base_url='https://'+host+'.localhost') as http:
        origin='https://'+host+'.localhost';csrf=login(http,name,origin).json()['csrf_token']
        for dataset in ['access','history']:
            r=http.post(B+'/tables/'+dataset+'/query',json={'matter_id':ids['matter']},headers={'origin':origin,'x-csrf-token':csrf});deny(r)
        for suffix,params in [('context',{'revision':1}),('access-target',{'revision':1,'username':'lawyer'})]:deny(http.get(B+'/matters/'+ids['matter']+'/'+suffix,params=params))


@pytest.mark.parametrize('kind',['unassigned','assignment','wall'])
def test_current_root_scope_required_before_counts(env,kind):
    http,sessions,ids,_=env;csrf=root(http)
    if kind=='unassigned':ids={**ids,'matter':ids['other']}
    else:revoke(sessions,ids,kind)
    deny(grid(http,csrf,ids));deny(grid(http,csrf,ids,'history'))


@pytest.mark.parametrize('dataset,extra',[('access',{'draw':True}),('access',{'start':-1}),('history',{'length':51}),('access',{'sort':'password_hash'}),
    ('history',{'sort':'username'}),('access',{'column_filters':{'rationale':'x'}}),('history',{'column_filters':{'password':'x'}}),
    ('access',{'search':{'regex':True}}),('history',{'direction':'sideways'}),('access',{'account_filters':{}}),('history',{'audit_filters':{}}),
    ('access',{'source_filters':{}}),('history',{'saved_view_id':'no'}),('access',{'format':'csv'}),('access',{'selected_ids':['no']})])
def test_registry_queries_reject_cross_dataset_or_untyped_fields(env,dataset,extra):
    http,_,ids,_=env;csrf=root(http)
    assert grid(http,csrf,ids,dataset,**extra).status_code==422
    assert post(http,B+'/tables/'+dataset+'/query',csrf,{}).status_code==422


def test_context_and_free_upn_target_are_exact_revision_pinned_and_preserve_first_assignment(env):
    from kestrel.bootstrap import provision
    from test_auth_policy import PASSWORD
    http,sessions,ids,_=env;csrf=root(http)
    with sessions() as db:
        account=provision(db,'unassigned@example.test','firm',['firm_lawyer'],PASSWORD);target_id=account.id;db.commit()
    base=B+'/matters/'+ids['matter']
    for path in ['/context','/access-target']:
        for revision in [None,0,-1,'bad']:
            params={'username':'unassigned@example.test',**({} if revision is None else {'revision':revision})}
            assert http.get(base+path,params=params).status_code==422
    r=http.get(base+'/access-target',params={'username':'  UNASSIGNED@example.test  ','revision':1})
    assert r.status_code==200 and set(r.json())==TARGET,r.text
    assert r.json()['account_id']==target_id and r.json()['assigned'] is False and r.json()['blocked'] is False and r.json()['active'] is True
    assert grid(http,csrf,ids).json()['recordsTotal']==5
    r=post(http,base+'/access',csrf,command(ids,username='unassigned@example.test'));assert r.status_code==200 and r.json()['revision']==2,r.text
    assert grid(http,csrf,ids).json()['recordsTotal']==6
    assert http.get(base+'/context',params={'revision':1}).status_code==409
    assert http.get(base+'/access-target',params={'username':'unassigned@example.test','revision':1}).status_code==409
    assert http.get(base+'/access-target',params={'username':'absent@example.test','revision':2}).status_code==404
    assert post(http,base+'/access',csrf,command(ids,username='root',expected_revision=2)).status_code==403
    assert post(http,base+'/access',csrf,command(ids,expected_revision=2,blocked=True)).status_code==403


def test_assignment_preserves_every_existing_wall_row_and_only_changes_assignments(env):
    http,sessions,ids,_=env;csrf=root(http)
    with sessions() as db:
        db.add_all([m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True),m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=False)])
        db.commit();before=[tuple(row) for row in db.execute(select(m.EthicalWall.id,m.EthicalWall.account_id,m.EthicalWall.matter_id,m.EthicalWall.active).order_by(m.EthicalWall.id))]
    r=post(http,B+'/matters/'+ids['matter']+'/access',csrf,command(ids,blocked=True));assert r.status_code==200,r.text
    with sessions() as db:
        after=[tuple(row) for row in db.execute(select(m.EthicalWall.id,m.EthicalWall.account_id,m.EthicalWall.matter_id,m.EthicalWall.active).order_by(m.EthicalWall.id))]
        assert after==before


@pytest.mark.parametrize('kind',['session','role','assignment','wall'])
def test_legacy_access_read_rechecks_root_scope_after_rows_are_prepared(env,monkeypatch,kind):
    from kestrel.services import administration
    http,sessions,ids,_=env;root(http);original=administration.access_rows;fired=False
    def prepare_then_revoke(*args,**kwargs):
        nonlocal fired
        result=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return result
    monkeypatch.setattr(administration,'access_rows',prepare_then_revoke)
    r=http.get(B+'/matters/'+ids['matter']+'/access');assert fired;deny(r,'organization','username')


@pytest.mark.parametrize('operation',['access','decision'])
@pytest.mark.parametrize('kind',['session','role','assignment','wall'])
def test_legacy_commands_rollback_when_root_authority_changes_after_initial_scope_check(env,monkeypatch,operation,kind):
    from kestrel.services import administration
    http,sessions,ids,_=env;csrf=root(http);original=administration.advance;fired=False
    with sessions() as db:
        before=(db.scalar(select(func.count()).select_from(m.MatterAssignment)),db.scalar(select(func.count()).select_from(m.AdministrationDecision)))
    def revoke_before_write(*args,**kwargs):
        nonlocal fired
        if not fired:fired=True;revoke(sessions,ids,kind)
        return original(*args,**kwargs)
    monkeypatch.setattr(administration,'advance',revoke_before_write)
    payload=command(ids) if operation=='access' else {'expected_revision':1,'status':'pending','rationale':'Synthetic administrative decision'}
    r=post(http,B+'/matters/'+ids['matter']+'/'+operation,csrf,payload);assert fired;deny(r)
    with sessions() as db:
        assert db.get(m.MatterValidation,ids['matter']).revision==1
        assert (db.scalar(select(func.count()).select_from(m.MatterAssignment)),db.scalar(select(func.count()).select_from(m.AdministrationDecision)))==before


def test_registry_openapi_has_typed_pages_and_exact_pinned_lookup_models(env):
    _,_,_,app=env;schema=app.openapi()
    for dataset,fields in [('access',ACCESS),('history',HISTORY)]:
        page_ref=schema['paths'][B+'/tables/'+dataset+'/query']['post']['responses']['200']['content']['application/json']['schema']['$ref'].split('/')[-1]
        page=schema['components']['schemas'][page_ref]
        assert set(page['properties'])=={'draw','recordsTotal','recordsFiltered','data','matter_revision','count_basis'}
        row_ref=page['properties']['data']['items']['$ref'].split('/')[-1]
        assert set(schema['components']['schemas'][row_ref]['properties'])==fields


@pytest.mark.parametrize('operation,kind',[(operation,kind) for operation in ['access','history','context','target'] for kind in ['session','role','assignment','wall']]+[('access','target'),('target','target')])
def test_last_preparation_cannot_emit_after_root_or_target_security_changes(env,monkeypatch,operation,kind):
    from kestrel.services import registry_tables
    http,sessions,ids,_=env;csrf=root(http);decision(sessions,ids,rationale='PRIVATE_REGISTRY_HISTORY')
    name={'access':'access_rows','history':'history_rows','context':'context_row','target':'target_row'}[operation]
    original=getattr(registry_tables,name);calls=0
    def last_prepare_then_revoke(*args,**kwargs):
        nonlocal calls
        result=original(*args,**kwargs);calls+=1
        if calls==2:revoke(sessions,ids,kind)
        return result
    monkeypatch.setattr(registry_tables,name,last_prepare_then_revoke)
    if operation in {'access','history'}:r=grid(http,csrf,ids,operation)
    else:r=http.get(B+'/matters/'+ids['matter']+('/context' if operation=='context' else '/access-target'),params={'revision':1,'username':'lawyer'})
    assert calls==2;deny(r,'PRIVATE_REGISTRY_HISTORY','username','validation_status')


@pytest.mark.parametrize('operation',['clients','matters','access','history'])
@pytest.mark.parametrize('kind',['role','session'])
def test_original_registry_reads_recheck_final_prepared_authority(env,monkeypatch,operation,kind):
    from kestrel.services import administration,registry_tables
    http,sessions,ids,_=env;root(http);decision(sessions,ids,rationale='PRIVATE_REGISTRY_HISTORY')
    module=registry_tables if operation=='history' else administration
    name={'clients':'client_rows','matters':'registry','access':'access_rows','history':'history_rows'}[operation]
    original=getattr(module,name);calls=0
    def after_final_projection(*args,**kwargs):
        nonlocal calls
        result=original(*args,**kwargs);calls+=1
        if calls==2:revoke(sessions,ids,kind)
        return result
    monkeypatch.setattr(module,name,after_final_projection)
    r=http.get(B+'/'+operation if operation in {'clients','matters'} else B+'/matters/'+ids['matter']+'/'+operation)
    assert calls==2;deny(r,'PRIVATE_REGISTRY_HISTORY','username','client_name')


@pytest.mark.parametrize('operation',['client','matter'])
@pytest.mark.parametrize('kind',['role','session'])
def test_registry_creation_rolls_back_if_initial_authority_is_lost_before_commit(env,monkeypatch,operation,kind):
    from kestrel.services import administration
    http,sessions,ids,_=env;csrf=root(http);fired=False
    with sessions() as db:
        client_id=db.get(m.MatterValidation,ids['matter']).client_id
        before=(db.scalar(select(func.count()).select_from(m.Client)),db.scalar(select(func.count()).select_from(m.Matter)))
    name='next_number' if operation=='client' else 'client_rows';original=getattr(administration,name)
    def prepare_then_revoke(*args,**kwargs):
        nonlocal fired
        result=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return result
    monkeypatch.setattr(administration,name,prepare_then_revoke)
    payload={'name':'PRIVATE_UNCOMMITTED_CREATE',**({'client_id':client_id} if operation=='matter' else {})}
    r=post(http,B+('/clients' if operation=='client' else '/matters'),csrf,payload)
    assert fired;deny(r,'PRIVATE_UNCOMMITTED_CREATE')
    with sessions() as db:assert (db.scalar(select(func.count()).select_from(m.Client)),db.scalar(select(func.count()).select_from(m.Matter)))==before


def test_client_person_wall_is_effective_readonly_and_does_not_become_a_direct_wall(env):
    from test_wall_checker import setup,propose,approve
    http,sessions,ids,_=env;csrf=setup(env);wall=propose(http,csrf,username='lawyer');approve(http,wall)
    csrf=root(http)
    state=http.get(B+'/matters/'+ids['matter']+'/access-target',params={'username':'lawyer','revision':1})
    assert state.status_code==200,state.text
    assert state.json()['blocked'] is False and state.json()['effective_blocked'] is True
    with sessions() as db:before=[tuple(row) for row in db.execute(select(m.EthicalWall.id,m.EthicalWall.active))]
    r=post(http,B+'/matters/'+ids['matter']+'/access',csrf,command(ids));assert r.status_code==200,r.text
    with sessions() as db:assert [tuple(row) for row in db.execute(select(m.EthicalWall.id,m.EthicalWall.active))]==before
    after=http.get(B+'/matters/'+ids['matter']+'/access-target',params={'username':'lawyer','revision':2})
    assert after.status_code==200 and after.json()['effective_blocked'] is True and after.json()['blocked'] is False


@pytest.mark.parametrize('kind',['assignment','wall'])
def test_empty_management_scope_keeps_legacy_global_empty_list_and_own_client_reads(env,kind):
    http,sessions,ids,_=env;root(http);revoke(sessions,ids,kind)
    matters=http.get(B+'/matters');assert matters.status_code==200 and matters.json()==[],matters.text
    clients=http.get(B+'/clients');assert clients.status_code==200 and len(clients.json())==1,clients.text


def test_new_matter_self_assignment_cannot_replace_expired_existing_client_authority(env,monkeypatch):
    from kestrel.services import administration,registry_tables,auth
    http,sessions,ids,_=env;csrf=root(http);instant=clock()
    with sessions() as db:
        client_id=db.get(m.MatterValidation,ids['matter']).client_id;db.get(m.Client,client_id).created_by=ids['sme']
        for row in db.scalars(select(m.MatterAssignment).where(m.MatterAssignment.account_id==ids['root'])):row.expires_at=instant+1
        before=(db.scalar(select(func.count()).select_from(m.Matter)),db.scalar(select(func.count()).select_from(m.MatterAssignment)),db.scalar(select(func.count()).select_from(m.AdministrationDecision)))
        db.commit()
    monkeypatch.setattr(auth,'clock',lambda:instant);monkeypatch.setattr(administration,'clock',lambda:instant)
    original=registry_tables.client_allowed;calls=0
    def client_allowed_then_expire(*args,**kwargs):
        nonlocal calls
        result=original(*args,**kwargs);calls+=1
        if calls==2:
            monkeypatch.setattr(auth,'clock',lambda:instant+2);monkeypatch.setattr(administration,'clock',lambda:instant+2)
        return result
    monkeypatch.setattr(registry_tables,'client_allowed',client_allowed_then_expire)
    r=post(http,B+'/matters',csrf,{'client_id':client_id,'name':'PRIVATE_EXPIRED_CLIENT_CREATE'})
    assert calls==2;deny(r,'PRIVATE_EXPIRED_CLIENT_CREATE')
    with sessions() as db:assert (db.scalar(select(func.count()).select_from(m.Matter)),db.scalar(select(func.count()).select_from(m.MatterAssignment)),db.scalar(select(func.count()).select_from(m.AdministrationDecision)))==before
