"""Isolated synthetic ACL, approval, retention and query-contract regressions."""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login,PASSWORD
from test_document_workflow import upload,BASE
from test_observability_governance import post
V='/api/v1/table-views'

@pytest.fixture
def views(env):
 h,sessions,ids,app=env
 from kestrel.api.table_views import router
 if not any(getattr(route,'path','')==V for route in app.routes):app.include_router(router)
 return env

def config(ids,**extra):
 return {'matter_id':ids['matter'],'dataset':'inventory','name':'Synthetic private investigation','query':{'matter_id':ids['matter'],'search':'confidential project nickname'},'handling':'private_unclassified','rationale':'Retain my private synthetic table configuration only','request_key':uuid.uuid4().hex,**extra}

def confirmed(h,c,ids,**extra):
 source=upload(h,c,ids['matter'],**extra).json()
 r=post(h,BASE+'/documents/'+source['id']+'/confirm',c,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm synthetic evidence classification before saved-view binding'})
 assert r.status_code==200,r.text
 return source

def recipient(sessions,ids,name='recipient'):
 from kestrel.bootstrap import provision
 from kestrel.models import MatterAssignment
 from kestrel.services.auth import clock
 with sessions() as db:
  user=provision(db,name,'firm',['firm_lawyer'],PASSWORD);db.add(MatterAssignment(account_id=user.id,matter_id=ids['matter'],expires_at=clock()+3600));db.commit();return user.id

def shared(views):
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];source=confirmed(h,c,ids);uid=recipient(sessions,ids)
 r=post(h,V,c,config(ids,handling='source_bound',evidence_refs=[{'kind':'source','id':source['id']}]))
 assert r.status_code==201,r.text;view=r.json()
 r=post(h,V+'/'+view['id']+'/share-requests',c,{'version_hash':view['version_hash'],'recipient_ids':[uid],'expires_in_days':1,'rationale':'Named synthetic firm recipient; no expansion of source policy','request_key':uuid.uuid4().hex})
 assert r.status_code==201,r.text
 return source,view,r.json(),uid,c

def decision(h,c,share,operation='approve',**extra):
 return post(h,V+'/share-requests/'+share['id']+'/decisions',c,{'operation':operation,'content_hash':share['content_hash'],'content_reviewed':True,'rationale':'Independently reviewed exact configuration text, names, provenance and named audience',**extra})

def test_private_owner_isolation_cross_matter_root_and_safe_filter_contract(views):
 h,_,ids,_=views;c=login(h).json()['csrf_token'];p=config(ids)
 r=post(h,V,c,p);assert r.status_code==201,r.text;view=r.json()
 assert view['is_owner'] and not view['shared'] and view['query']['start']==0
 assert post(h,V,c,p).json()['id']==view['id']
 assert h.get(V+'/'+view['id']).status_code==200
 assert post(h,V,c,{**config(ids),'query':{'matter_id':ids['other']}}).status_code==422
 assert post(h,V,c,{**config(ids),'matter_id':ids['other'],'query':{'matter_id':ids['other']}}).status_code==403
 for query in [{'matter_id':ids['matter'],'sort':'file_name; DROP TABLE accounts'},{'matter_id':ids['matter'],'column_filters':{'password_hash':'x'}},{'matter_id':ids['matter'],'search':{'regex':True}},{'matter_id':ids['matter'],'regex':True}]:
  assert post(h,V,c,config(ids,query=query)).status_code==422
 assert post(h,V+'/'+view['id']+'/share-requests',c,{'version_hash':view['version_hash'],'recipient_ids':[ids['sme']],'expires_in_days':1,'rationale':'Unclassified private text must never be shared directly','request_key':uuid.uuid4().hex}).status_code==409
 login(h,'sme');assert h.get(V+'?matter_id='+ids['matter']+'&dataset=inventory').json()==[]
 denied=h.get(V+'/'+view['id']);assert denied.status_code==403 and p['query']['search'] not in denied.text
 root=login(h,'root').json()['csrf_token'];assert h.get(V+'/'+view['id']).status_code==403
 assert post(h,V,root,config(ids)).status_code==403

def test_immutable_versions_optimistic_concurrency_and_idempotency(views):
 from kestrel.models import TableViewVersion
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];p=config(ids);view=post(h,V,c,p).json()
 update={k:v for k,v in config(ids,name='Second synthetic configuration').items() if k not in {'matter_id','dataset'}}
 update['expected_version_hash']=view['version_hash']
 r=post(h,V+'/'+view['id']+'/versions',c,update);assert r.status_code==201,r.text
 second=r.json();assert second['revision']==2 and second['version_hash']!=view['version_hash']
 assert post(h,V+'/'+view['id']+'/versions',c,update).json()['version_hash']==second['version_hash']
 assert post(h,V+'/'+view['id']+'/versions',c,{**update,'request_key':uuid.uuid4().hex}).status_code==409
 assert post(h,V,c,{**p,'name':'Request key reused with new private text'}).status_code==409
 with sessions() as db:
  assert db.scalar(select(TableViewVersion).where(TableViewVersion.id==view['version_id'])).name==view['name']
  with pytest.raises(DBAPIError):db.execute(text('UPDATE table_view_versions SET name=:name WHERE id=:id'),{'name':'Overwrite retained config','id':view['version_id']});db.commit()
 with sessions() as db:
  with pytest.raises(DBAPIError):db.execute(text('DELETE FROM table_views WHERE id=:id'),{'id':view['id']});db.commit()

def test_named_same_org_sharing_requires_independent_exact_content_approval(views):
 h,sessions,ids,app=views;source,view,share,uid,c=shared(views)
 candidates=h.get(V+'/recipients?matter_id='+ids['matter']+'&dataset=inventory').json()
 assert uid in {x['id'] for x in candidates} and not {ids['root'],ids['client'],ids['bank']} & {x['id'] for x in candidates}
 assert decision(h,c,share).status_code==403
 login(h,'recipient');assert h.get(V+'/'+view['id']).status_code==403
 sme=login(h,'sme').json()['csrf_token'];queue=h.get(V+'/share-requests?matter_id='+ids['matter']+'&dataset=inventory')
 assert queue.status_code==200,queue.text;assert queue.json()[0]['configuration']['query']['search']=='confidential project nickname' and queue.json()[0]['can_review']
 assert decision(h,sme,share,content_hash='0'*64).status_code==409
 assert decision(h,sme,share,content_reviewed=False).status_code==422
 assert decision(h,sme,share).status_code==200
 assert decision(h,sme,share).status_code==409
 login(h,'recipient');r=h.get(V+'/'+view['id']);assert r.status_code==200,r.text
 assert r.json()['shared'] and not r.json()['is_owner']
 assert h.get(V+'?matter_id='+ids['matter']+'&dataset=inventory').json()[0]['id']==view['id']
 # New private revisions never inherit an older version's sharing decision.
 c=login(h).json()['csrf_token'];p={k:v for k,v in config(ids,name='New private revision').items() if k not in {'matter_id','dataset'}};p['expected_version_hash']=view['version_hash']
 assert post(h,V+'/'+view['id']+'/versions',c,p).status_code==201
 owner_history=h.get(V+'/share-requests?matter_id='+ids['matter']+'&dataset=inventory')
 assert owner_history.status_code==200,owner_history.text
 assert owner_history.json()[0]['id']==share['id'] and owner_history.json()[0]['version_hash']==view['version_hash'] and not owner_history.json()[0]['can_review']
 login(h,'recipient');assert h.get(V+'/'+view['id']).json()['version_hash']==view['version_hash']
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');denied=bank.get(V+'/'+view['id']);assert denied.status_code==403 and source['id'] not in denied.text

def test_share_expiry_revocation_and_current_approver_clearance(views,monkeypatch):
 from kestrel import models as m
 from kestrel.services import table_views as service
 h,sessions,ids,_=views;source,view,share,uid,c=shared(views);sme=login(h,'sme').json()['csrf_token'];assert decision(h,sme,share).status_code==200
 login(h,'recipient');assert h.get(V+'/'+view['id']).status_code==200
 with sessions() as db:db.add(m.EthicalWall(account_id=ids['sme'],matter_id=ids['matter'],active=True));db.commit()
 assert h.get(V+'/'+view['id']).status_code==403
 with sessions() as db:db.scalar(select(m.EthicalWall).where(m.EthicalWall.account_id==ids['sme'])).active=False;db.commit()
 now=service.clock();monkeypatch.setattr(service,'clock',lambda:now+86401)
 assert h.get(V+'/'+view['id']).status_code==403
 monkeypatch.setattr(service,'clock',lambda:now)
 c=login(h).json()['csrf_token'];assert decision(h,c,share,'revoke').status_code==200
 login(h,'recipient');assert h.get(V+'/'+view['id']).status_code==403
 with sessions() as db:assert len(list(db.scalars(select(m.TableViewShareDecision).where(m.TableViewShareDecision.share_id==share['id']))))==2

def test_bound_source_drift_retained_clean_scope_and_recipient_revalidation(views):
 from kestrel import models as m
 from kestrel.services.auth import clock
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];uid=recipient(sessions,ids)
 with sessions() as db:
  for person in [ids['lawyer'],ids['sme'],uid]:db.add(m.CleanTeamMembership(account_id=person,matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600))
  db.commit()
 source=confirmed(h,c,ids,classification='clean_team',clean_team_scope='pricing')
 view=post(h,V,c,config(ids,handling='source_bound',evidence_refs=[{'kind':'source','id':source['id']}])).json()
 share=post(h,V+'/'+view['id']+'/share-requests',c,{'version_hash':view['version_hash'],'recipient_ids':[uid],'expires_in_days':1,'rationale':'Internal recipient independently cleared for pricing scope','request_key':uuid.uuid4().hex}).json()
 sme=login(h,'sme').json()['csrf_token'];assert decision(h,sme,share).status_code==200
 login(h,'recipient');assert h.get(V+'/'+view['id']).status_code==200
 with sessions() as db:db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==uid)).revoked=True;db.commit()
 assert h.get(V+'/'+view['id']).status_code==403
 c=login(h).json()['csrf_token']
 with sessions() as db:src=db.get(m.SourceVersion,source['id']);db.get(m.DocumentPolicyVersion,src.policy_id).quarantined=True;db.commit()
 assert h.get(V+'/'+view['id']).status_code==403
 # Owner may tighten access after evidence drift without returning stale text.
 assert decision(h,c,share,'revoke').status_code==200

def test_cross_matter_evidence_external_recipient_and_unreviewed_configs_denied(views):
 from kestrel import models as m
 from kestrel.services.auth import clock
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];source=confirmed(h,c,ids)
 with sessions() as db:db.add(m.MatterAssignment(account_id=ids['lawyer'],matter_id=ids['other'],expires_at=clock()+3600));db.commit()
 p=config(ids,matter_id=ids['other'],query={'matter_id':ids['other']},handling='source_bound',evidence_refs=[{'kind':'source','id':source['id']}])
 assert post(h,V,c,p).status_code==403
 view=post(h,V,c,config(ids,handling='source_bound',evidence_refs=[{'kind':'source','id':source['id']}])).json()
 for target in [ids['bank'],ids['client'],ids['root']]:
  r=post(h,V+'/'+view['id']+'/share-requests',c,{'version_hash':view['version_hash'],'recipient_ids':[target],'expires_in_days':1,'rationale':'External or administrative source-disclosure attempt must fail','request_key':uuid.uuid4().hex});assert r.status_code==403,r.text
 pending=upload(h,c,ids['matter'],logical_key='PENDING-TABLE-VIEW').json()
 assert post(h,V,c,config(ids,handling='source_bound',evidence_refs=[{'kind':'source','id':pending['id']}])).status_code==409

def test_permission_change_during_configuration_response_withholds_text(views,monkeypatch):
 from kestrel import models as m
 from kestrel.services import table_views as service
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];view=post(h,V,c,config(ids)).json();original=service.configuration_output
 def changed(db,actor,row,version,include_requests=True):
  result=original(db,actor,row,version,include_requests)
  with sessions() as other:other.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));other.commit()
  return result
 monkeypatch.setattr(service,'configuration_output',changed)
 r=h.get(V+'/'+view['id']);assert r.status_code in {403,409},r.text
 assert view['name'] not in r.text and 'confidential project nickname' not in r.text

def test_bank_private_financial_requires_gate_released_derivative_and_current_fact(views,monkeypatch):
 import test_document_workflow as dw,test_disclosures as dis,test_financial_workflow as fin
 content=dw.TEXT+' '+fin.TEXT
 monkeypatch.setattr(dw,'TEXT',content);monkeypatch.setattr(dis,'TEXT',content)
 h,_,ids,app=views;source,plan,artifact,c=dis.prepared(views)
 sme=login(h,'sme').json()['csrf_token']
 assert post(h,dis.D+'/artifacts/'+artifact['id']+'/decisions',sme,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Independent release of exact synthetic financial transcript'}).status_code==200
 c=login(h).json()['csrf_token'];original=post(h,fin.F+'/facts',c,fin.payload(source['id'],content)).json()
 reader=h.get(dis.D+'/artifacts/'+artifact['id']+'/reader').json();fact=post(h,fin.F+'/facts',c,fin.payload(artifact['id'],reader['units'][0]['text'],'derivative')).json()
 assert 'id' in fact,fact
 with TestClient(app,base_url='https://bank.localhost') as bank:
  b=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token'];headers={'origin':'https://bank.localhost','x-csrf-token':b}
  def save(fid=fact['id']):
   return bank.post(V,json=config(ids,dataset='financial',name='Synthetic released financial view',query={'matter_id':ids['matter'],'financial_filters':{'currency':'EUR'}},handling='source_bound',evidence_refs=[{'kind':'financial','id':fid}]),headers=headers)
  assert save().status_code==403
  root=login(h,'root').json()['csrf_token'];assert post(h,fin.F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Enable synthetic bank feature without any source grant'}).status_code==200
  fin.enable_org(h,root)
  assert bank.post(V,json=config(ids,dataset='financial'),headers=headers).status_code==422
  assert save(original['id']).status_code==403 and save().status_code==403
  sme=login(h,'sme').json()['csrf_token'];assert fin.decision(h,sme,fact,'verify').status_code==200;assert fin.decision(h,sme,fact,'release').status_code==200
  r=save();assert r.status_code==201,r.text;view=r.json()
  assert source['id'] not in r.text and original['id'] not in r.text and 'retained_classification' not in r.text
  assert bank.get(V+'/'+view['id']).status_code==200
  assert bank.post(V+'/'+view['id']+'/share-requests',json={'version_hash':view['version_hash'],'recipient_ids':[ids['bank']],'expires_in_days':1,'rationale':'External saved-view sharing is outside the approved baseline','request_key':uuid.uuid4().hex},headers=headers).status_code==403
  root=login(h,'root').json()['csrf_token'];assert post(h,fin.F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':1,'enabled':False,'rationale':'Disable future saved bank financial access'}).status_code==200
  assert bank.get(V+'/'+view['id']).status_code==403
  assert post(h,fin.F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':2,'enabled':True,'rationale':'Re-enable feature while preserving individual evidence checks'}).status_code==200
  assert bank.get(V+'/'+view['id']).status_code==200
  sme=login(h,'sme').json()['csrf_token'];assert fin.decision(h,sme,fact,'revoke').status_code==200
  denied=bank.get(V+'/'+view['id']);assert denied.status_code==403 and source['id'] not in denied.text

def test_signing_manifest_retains_versions_and_freezes_writes_but_allows_revoke(views):
 import json
 from kestrel.models import LifecycleDecision,TableViewShareDecision
 from test_lifecycle import propose,approve
 h,sessions,ids,_=views;source,view,share,uid,c=shared(views);sme=login(h,'sme').json()['csrf_token'];assert decision(h,sme,share).status_code==200
 signing=propose(h,ids,'sign')
 with sessions() as db:
  manifest=json.loads(db.get(LifecycleDecision,signing['id']).payload_json)
  for name in ['table_views','table_view_versions','table_view_evidence','table_view_shares','table_view_share_recipients','table_view_share_decisions']:assert manifest[name]
 assert approve(h,signing).status_code==200
 c=login(h).json()['csrf_token'];assert post(h,V,c,config(ids)).status_code==409
 update={k:v for k,v in config(ids).items() if k not in {'matter_id','dataset'}};update['expected_version_hash']=view['version_hash']
 assert post(h,V+'/'+view['id']+'/versions',c,update).status_code==409
 assert decision(h,c,share,'revoke').status_code==200
 login(h,'recipient');assert h.get(V+'/'+view['id']).status_code==403
 with sessions() as db:
  assert len(list(db.scalars(select(TableViewShareDecision).where(TableViewShareDecision.share_id==share['id']))))==2
  assert json.loads(db.get(LifecycleDecision,signing['id']).payload_json)==manifest

def test_named_recipient_cannot_be_own_independent_share_approver(views):
 from kestrel import models as m
 h,sessions,ids,_=views;source,view,share,uid,c=shared(views)
 with sessions() as db:
  role=db.scalar(select(m.Role).where(m.Role.name=='legal_sme'));db.add(m.RoleGrant(account_id=uid,role_id=role.id));db.commit()
 recipient_token=login(h,'recipient').json()['csrf_token']
 assert decision(h,recipient_token,share).status_code==403
 assert h.get(V+'/share-requests?matter_id='+ids['matter']+'&dataset=inventory').json()==[]

def test_migration_refuses_retained_downgrade_without_dropping_any_saved_table(views):
 from alembic import command
 from alembic.config import Config
 from pathlib import Path
 from sqlalchemy import inspect
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];assert post(h,V,c,config(ids)).status_code==201
 with pytest.raises(RuntimeError,match='Retained saved table view records'):
  command.downgrade(Config(str(Path(__file__).resolve().parents[1]/'alembic.ini')),'0033')
 with sessions() as db:
  names=set(inspect(db.bind).get_table_names())
  assert {'table_views','table_view_versions','table_view_evidence','table_view_shares','table_view_share_recipients','table_view_share_decisions'}<=names

def test_saved_table_query_is_authoritative_preserves_draw_start_and_scope(views):
 h,_,ids,_=views;c=login(h).json()['csrf_token']
 a=upload(h,c,ids['matter'],file_name='alpha.txt',logical_key='SAVED-ALPHA').json();b=upload(h,c,ids['matter'],file_name='beta.txt',logical_key='SAVED-BETA').json()
 view=post(h,V,c,config(ids,query={'matter_id':ids['matter'],'length':1,'sort':'file_name','direction':'asc','search':''})).json()
 r=post(h,'/api/v1/tables/inventory/query',c,{'matter_id':ids['matter'],'saved_view_id':view['id'],'draw':17,'start':1,'length':50,'sort':'file_name','direction':'desc','search':'must not override saved query'})
 assert r.status_code==200,r.text;value=r.json()
 assert value['draw']==17 and value['recordsTotal']==2 and value['recordsFiltered']==2 and [row['id'] for row in value['data']]==[b['id']]
 assert post(h,'/api/v1/tables/financial/query',c,{'matter_id':ids['matter'],'saved_view_id':view['id']}).status_code==403
 assert post(h,'/api/v1/tables/inventory/query',c,{'matter_id':ids['other'],'saved_view_id':view['id']}).status_code==403
 assert post(h,V,c,config(ids,query={'matter_id':ids['matter'],'saved_view_id':view['id']})).status_code==422
 login(h,'sme');assert post(h,'/api/v1/tables/inventory/query',login(h,'sme').json()['csrf_token'],{'matter_id':ids['matter'],'saved_view_id':view['id']}).status_code==403

def test_same_query_new_immutable_version_during_scan_withholds_rows_and_counts(views,monkeypatch):
 from kestrel.services import data_tables as tables,table_views as service
 from kestrel.schemas.table_views import Version
 h,sessions,ids,_=views;c=login(h).json()['csrf_token'];source=upload(h,c,ids['matter']).json()
 view=post(h,V,c,config(ids,query={'matter_id':ids['matter']})).json();original=tables.collect
 def changed(db,actor,dataset,p):
  records=original(db,actor,dataset,p)
  update={k:v for k,v in config(ids,name='Renamed exact same filters').items() if k not in {'matter_id','dataset'}}
  update.update(expected_version_hash=view['version_hash'],query={'matter_id':ids['matter']})
  with sessions() as other:service.update(other,actor,view['id'],Version.model_validate(update))
  return records
 monkeypatch.setattr(tables,'collect',changed)
 r=post(h,'/api/v1/tables/inventory/query',c,{'matter_id':ids['matter'],'saved_view_id':view['id']})
 assert r.status_code==409,r.text;assert 'recordsTotal' not in r.text and source['id'] not in r.text

def test_share_revoked_during_saved_table_scan_withholds_rows_and_counts(views,monkeypatch):
 from kestrel.services import data_tables as tables,table_views as service
 from kestrel.schemas.table_views import ShareDecision
 from kestrel.repositories.identity import principal
 from kestrel.models import Account
 from kestrel.services.auth import clock
 h,sessions,ids,_=views;source,view,share,uid,c=shared(views);sme=login(h,'sme').json()['csrf_token'];assert decision(h,sme,share).status_code==200
 c=login(h,'recipient').json()['csrf_token'];original=tables.collect
 def changed(db,actor,dataset,p):
  records=original(db,actor,dataset,p)
  with sessions() as other:
   owner=principal(other,other.get(Account,ids['lawyer']),clock())
   service.decide(other,owner,share['id'],ShareDecision.model_validate({'operation':'revoke','content_hash':share['content_hash'],'rationale':'Owner revokes exact named share while recipient table is scanning'}))
  return records
 monkeypatch.setattr(tables,'collect',changed)
 r=post(h,'/api/v1/tables/inventory/query',c,{'matter_id':ids['matter'],'saved_view_id':view['id']})
 assert r.status_code==403,r.text;assert 'recordsTotal' not in r.text and source['id'] not in r.text

def test_loaded_saved_view_version_hash_prevents_cross_request_display_drift(views):
 h,_,ids,_=views;c=login(h).json()['csrf_token'];source=upload(h,c,ids['matter'],file_name='alpha.txt').json()
 view=post(h,V,c,config(ids,query={'matter_id':ids['matter'],'search':'alpha'})).json()
 query={'matter_id':ids['matter'],'saved_view_id':view['id'],'saved_view_version_hash':view['version_hash']}
 r=post(h,'/api/v1/tables/inventory/query',c,query);assert r.status_code==200,r.text;assert r.json()['recordsFiltered']==1
 update={k:v for k,v in config(ids,name='Updated filter controls').items() if k not in {'matter_id','dataset'}}
 update.update(expected_version_hash=view['version_hash'],query={'matter_id':ids['matter'],'search':'no matching document'})
 second=post(h,V+'/'+view['id']+'/versions',c,update).json()
 stale=post(h,'/api/v1/tables/inventory/query',c,query)
 assert stale.status_code==409 and 'recordsTotal' not in stale.text and source['id'] not in stale.text
 current=post(h,'/api/v1/tables/inventory/query',c,{**query,'saved_view_version_hash':second['version_hash']})
 assert current.status_code==200,current.text;assert current.json()['recordsFiltered']==0
 assert post(h,'/api/v1/tables/inventory/query',c,{**query,'saved_view_version_hash':'not-a-hash'}).status_code==422
 assert post(h,'/api/v1/tables/inventory/query',c,{'matter_id':ids['matter'],'saved_view_version_hash':view['version_hash']}).status_code==422
