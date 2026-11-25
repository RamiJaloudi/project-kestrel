"""Contract inventory is an authorized typed inventory predicate, not a dataset alias."""
import csv,io,json,uuid
import pytest
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import upload,BASE
from test_observability_governance import post
from kestrel import models as m
from kestrel.adapters.extraction import canonical,digest
from kestrel.services.auth import clock

T='/api/v1/tables/inventory'
V='/api/v1/table-views'


def source(http,csrf,matter,key,kind='contract',**changes):
    response=upload(http,csrf,matter,logical_key=key,file_name=key+'.txt',resource_type=kind,**changes)
    assert response.status_code==201,response.text
    return response.json()


def test_contract_inventory_predicate_precedes_authorized_counts_search_and_paging(env):
    http,_,ids,_=env;csrf=login(http).json()['csrf_token']
    created=[source(http,csrf,ids['matter'],'TYPE-'+kind,kind) for kind in ['contract','licence','financial','tracker','report','legal_advice']]
    p={'matter_id':ids['matter'],'source_filters':{'contracts_only':True},'length':1,'sort':'file_name','direction':'desc','draw':13}
    response=post(http,T+'/query',csrf,p);assert response.status_code==200,response.text
    data=response.json();assert data['draw']==13 and data['recordsTotal']==2 and data['recordsFiltered']==2 and len(data['data'])==1
    assert data['data'][0]['resource_type'] in {'contract','licence'}
    second=post(http,T+'/query',csrf,{**p,'start':1}).json()['data'][0]
    assert second['id']!=data['data'][0]['id'] and {second['id'],data['data'][0]['id']}=={created[0]['id'],created[1]['id']}
    searched=post(http,T+'/query',csrf,{**p,'search':'TYPE-financial'}).json()
    assert searched['recordsTotal']==2 and searched['recordsFiltered']==0 and searched['data']==[]
    assert created[2]['id'] not in response.text and created[2]['file_name'] not in response.text
    assert post(http,T+'/query',csrf,{'matter_id':ids['matter']}).json()['recordsTotal']==6
    assert post(http,T+'/query',csrf,{**p,'source_filters':{'contracts_only':False}}).json()['recordsTotal']==6
    assert post(http,'/api/v1/tables/contracts/query',csrf,{'matter_id':ids['matter']}).status_code==422


def test_contract_filter_keeps_current_historical_triage_and_protected_scope_rules(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    old=source(http,csrf,ids['matter'],'VERSIONED')
    assert post(http,BASE+'/documents/'+old['id']+'/confirm',csrf,{'snapshot_hash':old['snapshot_hash'],'rationale':'Confirm original handling before retaining a superseded source version'}).status_code==200
    current=source(http,csrf,ids['matter'],'VERSIONED',previous_id=old['id'],wave='wave2')
    licence=source(http,csrf,ids['matter'],'VISIBLE-LICENCE','licence')
    with sessions() as db:
        db.add(m.CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600))
        db.add(m.MatterAssignment(account_id=ids['lawyer'],matter_id=ids['other'],expires_at=clock()+3600));db.commit()
    hidden=source(http,csrf,ids['matter'],'PRIVATE-PRICING-CONTRACT',classification='clean_team',clean_team_scope='pricing')
    quarantined=source(http,csrf,ids['matter'],'PRIVATE-QUARANTINE')
    foreign=source(http,csrf,ids['other'],'OTHER-MATTER-CONTRACT')
    with sessions() as db:
        db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'])).revoked=True
        db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,quarantined['id']).policy_id).quarantined=True;db.commit()
    p={'matter_id':ids['matter'],'source_filters':{'contracts_only':True}}
    response=post(http,T+'/query',csrf,p);assert response.status_code==200,response.text
    value=response.json();assert value['recordsTotal']==2 and {row['id'] for row in value['data']}=={current['id'],licence['id']}
    assert all(row['classification_confirmed'] is False for row in value['data'])  # permitted triage is not an approval
    history=post(http,T+'/query',csrf,{**p,'source_filters':{'contracts_only':True,'historical':True}})
    assert history.status_code==200 and history.json()['recordsTotal']==3,history.text
    assert {row['id'] for row in history.json()['data']}=={old['id'],current['id'],licence['id']}
    for denied in [hidden,quarantined,foreign]:assert denied['id'] not in history.text and denied['file_name'] not in history.text
    assert post(http,T+'/query',csrf,{**p,'search':'PRIVATE-PRICING'}).json()['recordsFiltered']==0
    root=login(http,'root').json()['csrf_token'];assert post(http,T+'/query',root,p).status_code==403
    csrf=login(http).json()['csrf_token']
    with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    response=post(http,T+'/query',csrf,p);assert response.status_code==403 and 'recordsTotal' not in response.text and current['file_name'] not in response.text


@pytest.mark.parametrize('invalid',[1,0,'true','false',None,[],{}])
def test_contracts_only_is_a_strict_boolean(env,invalid):
    http,_,ids,_=env;csrf=login(http).json()['csrf_token']
    assert post(http,T+'/query',csrf,{'matter_id':ids['matter'],'source_filters':{'contracts_only':invalid}}).status_code==422


@pytest.mark.parametrize('dataset',['financial','tasks','findings'])
def test_contract_predicate_cannot_be_silently_applied_to_another_dataset(env,dataset):
    http,_,ids,_=env;csrf=login(http).json()['csrf_token']
    assert post(http,'/api/v1/tables/'+dataset+'/query',csrf,{'matter_id':ids['matter'],'source_filters':{'contracts_only':True}}).status_code==422
    assert post(http,V,csrf,{'matter_id':ids['matter'],'dataset':'financial','name':'Rejected mixed query','query':{'matter_id':ids['matter'],'source_filters':{'contracts_only':True}},
        'rationale':'Never reinterpret a contract inventory predicate as a financial fact query','request_key':uuid.uuid4().hex}).status_code==422


def legacy_query(matter):
    return {'matter_id':matter,'draw':0,'start':0,'length':20,'sort':'file_name','direction':'asc','search':'','column_filters':{},
        'source_filters':{'historical':False,'classification':None,'language':None,'wave':None},'financial_filters':None}


def test_old_normalized_json_version_hash_and_request_key_replay_are_preserved(env):
    from kestrel.schemas.data_tables import TableQuery
    from kestrel.services.table_views import normalized
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];now=clock();query=legacy_query(ids['matter'])
    payload={'matter_id':ids['matter'],'dataset':'inventory','name':'Retained pre-filter inventory','query':query,
        'handling':'private_unclassified','evidence_refs':[],'rationale':'Retain exact pre-contract-filter configuration bytes','request_key':uuid.uuid4().hex}
    raw_query={**query,'saved_view_id':None,'saved_view_version_hash':None,'task_filters':None,'finding_filters':None}
    original_input=digest(canonical({**payload,'query':raw_query}).encode())
    with sessions() as db:
        view=m.TableView(matter_id=ids['matter'],dataset='inventory',owner_id=ids['lawyer'],organization='firm',created_at=now)
        db.add(view);db.flush()
        content={'view_id':view.id,'matter_id':ids['matter'],'dataset':'inventory','owner_id':ids['lawyer'],'organization':'firm','revision':1,
            'previous_hash':None,'name':payload['name'],'query_json':canonical(query),'handling':'private_unclassified','rationale':payload['rationale'],
            'created_by':ids['lawyer'],'created_at':now,'evidence':[]}
        original_hash=digest(canonical(content).encode())
        version=m.TableViewVersion(view_id=view.id,matter_id=ids['matter'],revision=1,previous_hash=None,name=payload['name'],query_json=canonical(query),
            handling='private_unclassified',rationale=payload['rationale'],created_by=ids['lawyer'],created_at=now,request_key=payload['request_key'],input_hash=original_input,content_hash=original_hash)
        db.add(version);db.flush();view_id=view.id;version_id=version.id;db.commit()
    assert normalized(TableQuery(**query),ids['matter'],'inventory')==query
    explicit=TableQuery(**{**query,'source_filters':{**query['source_filters'],'contracts_only':False}})
    assert normalized(explicit,ids['matter'],'inventory')==query
    response=http.get(V+'/'+view_id);assert response.status_code==200,response.text
    assert response.json()['version_hash']==original_hash
    replay=post(http,V,csrf,payload);assert replay.status_code==201 and replay.json()['id']==view_id,replay.text
    assert post(http,T+'/query',csrf,{'matter_id':ids['matter'],'saved_view_id':view_id,'saved_view_version_hash':original_hash}).status_code==200
    with sessions() as db:
        stored=db.get(m.TableViewVersion,version_id)
        assert (stored.query_json,stored.content_hash,stored.input_hash)==(canonical(query),original_hash,original_input)


def test_explicit_true_saved_filter_roundtrips_and_remains_authoritative(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    allowed=source(http,csrf,ids['matter'],'SAVED-CONTRACT');source(http,csrf,ids['matter'],'NONCONTRACT','financial')
    payload={'matter_id':ids['matter'],'dataset':'inventory','name':'Current contract inventory','query':{'matter_id':ids['matter'],'source_filters':{'contracts_only':True,'historical':False}},
        'rationale':'Retain the exact current contract and licence inventory predicate','request_key':uuid.uuid4().hex}
    response=post(http,V,csrf,payload);assert response.status_code==201,response.text;view=response.json()
    assert view['query']['source_filters']['contracts_only'] is True and view['query']['source_filters']['historical'] is False
    with sessions() as db:assert json.loads(db.get(m.TableViewVersion,view['version_id']).query_json)['source_filters']['contracts_only'] is True
    response=post(http,T+'/query',csrf,{'matter_id':ids['matter'],'saved_view_id':view['id'],'saved_view_version_hash':view['version_hash'],'source_filters':{'contracts_only':False}})
    assert response.status_code==200 and response.json()['recordsTotal']==1 and response.json()['data'][0]['id']==allowed['id'],response.text
    changed={**payload,'query':{'matter_id':ids['matter'],'source_filters':{'contracts_only':False,'historical':False}}}
    assert post(http,V,csrf,changed).status_code==409


def test_selected_export_remains_generic_inventory_authority_with_each_id_rechecked(env):
    http,_,ids,_=env;csrf=login(http).json()['csrf_token']
    items=[source(http,csrf,ids['matter'],'EXPORT-CONTRACT'),source(http,csrf,ids['matter'],'EXPORT-FINANCIAL','financial')]
    for row in items:assert post(http,BASE+'/documents/'+row['id']+'/confirm',csrf,{'snapshot_hash':row['snapshot_hash'],'rationale':'Confirm synthetic metadata before generic authorized inventory export'}).status_code==200
    response=post(http,T+'/export',csrf,{'matter_id':ids['matter'],'ids':[row['id'] for row in items],'format':'csv'})
    assert response.status_code==200,response.text
    assert {row['id'] for row in csv.DictReader(io.StringIO(response.text))}=={row['id'] for row in items}
