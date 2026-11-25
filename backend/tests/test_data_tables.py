import csv,io
from test_auth_policy import env,login
from test_document_workflow import upload
from test_observability_governance import post
T='/api/v1/tables'

def test_inventory_server_paging_counts_filters_and_allowlisted_order(env):
 from kestrel.models import CleanTeamMembership
 from kestrel.services.auth import clock
 from sqlalchemy import select
 h,sessions,ids,_=env;c=login(h).json()['csrf_token']
 a=upload(h,c,ids['matter'],logical_key='TABLE-001',file_name='alpha.txt').json();b=upload(h,c,ids['matter'],logical_key='TABLE-002',file_name='beta.txt').json()
 with sessions() as db:db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
 secret=upload(h,c,ids['matter'],logical_key='TABLE-SECRET',file_name='restricted.txt',classification='clean_team',clean_team_scope='pricing').json()
 with sessions() as db:db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;db.commit()
 p={'matter_id':ids['matter'],'draw':7,'start':0,'length':1,'sort':'file_name','direction':'desc'}
 r=post(h,T+'/inventory/query',c,p);assert r.status_code==200,r.text;v=r.json()
 assert v['draw']==7 and v['recordsTotal']==2 and v['recordsFiltered']==2 and v['data'][0]['id']==b['id']
 assert secret['id'] not in r.text and 'restricted.txt' not in r.text
 assert post(h,T+'/inventory/query',c,{**p,'start':1}).json()['data'][0]['id']==a['id']
 r=post(h,T+'/inventory/query',c,{**p,'column_filters':{'logical_key':'TABLE-001'}}).json();assert r['recordsFiltered']==1 and r['recordsTotal']==2
 assert post(h,T+'/inventory/query',c,{**p,'sort':'file_name; DROP TABLE accounts'}).status_code==422
 assert post(h,T+'/inventory/query',c,{**p,'length':-1}).status_code==422
 assert post(h,T+'/inventory/query',c,{**p,'column_filters':{'password_hash':'x'}}).status_code==422

def test_internal_selected_exports_recheck_each_row_and_never_echo_denied_names(env):
 from kestrel.models import EthicalWall
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];a=upload(h,c,ids['matter']).json()
 from test_document_workflow import BASE
 assert post(h,BASE+'/documents/'+a['id']+'/confirm',c,{'snapshot_hash':a['snapshot_hash'],'rationale':'Confirm source attributes before internal metadata export'}).status_code==200
 p={'matter_id':ids['matter'],'ids':[a['id'],'00000000-0000-0000-0000-000000000000'],'format':'csv'}
 r=post(h,T+'/inventory/export',c,p);assert r.status_code==200,r.text
 assert r.headers['x-export-unavailable-count']=='1' and len(list(csv.DictReader(io.StringIO(r.text))))==1
 assert p['ids'][1] not in r.text
 r=post(h,T+'/inventory/export',c,{**p,'format':'xlsx'});assert r.status_code==200
 from openpyxl import load_workbook
 b=load_workbook(io.BytesIO(r.content),data_only=False);assert b.active.max_row==2 and all(cell.data_type!='f' for row in b.active for cell in row);b.close()
 with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 assert post(h,T+'/inventory/export',c,p).status_code==403
 root=login(h,'root').json()['csrf_token'];assert post(h,T+'/inventory/query',root,{'matter_id':ids['matter']}).status_code==403

def test_financial_table_sorts_exact_decimals_and_external_exports_stay_closed(env):
 from test_financial_workflow import source,payload,F
 from fastapi.testclient import TestClient
 h,_,ids,app=env;s,c=source(env)
 a=post(h,F+'/facts',c,payload(s['id'])).json();b=post(h,F+'/facts',c,payload(s['id'],token='9007199254740992.125')).json()
 r=post(h,T+'/financial/query',c,{'matter_id':ids['matter'],'sort':'amount_text','direction':'asc','length':1});assert r.status_code==200,r.text
 assert r.json()['data'][0]['id']==b['id'] and r.json()['recordsTotal']==2
 with TestClient(app,base_url='https://bank.localhost') as bank:
  bc=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  headers={'origin':'https://bank.localhost','x-csrf-token':bc}
  assert bank.post(T+'/financial/query',json={'matter_id':ids['matter']},headers=headers).status_code==403
  assert bank.post(T+'/financial/export',json={'matter_id':ids['matter'],'ids':[a['id']],'format':'csv'},headers=headers).status_code==403

def test_wall_changed_during_table_preparation_returns_no_rows_or_counts(env,monkeypatch):
 from kestrel.services import data_tables as tables
 from kestrel.models import EthicalWall
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];a=upload(h,c,ids['matter'],file_name='must-not-return-after-wall.txt').json();original=tables.collect
 def changed(db,actor,view,p):
  rows=original(db,actor,view,p)
  with sessions() as other:other.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));other.commit()
  return rows
 monkeypatch.setattr(tables,'collect',changed)
 r=post(h,T+'/inventory/query',c,{'matter_id':ids['matter']});assert r.status_code in {403,409},r.text
 assert a['id'] not in r.text and 'recordsTotal' not in r.text and 'must-not-return-after-wall' not in r.text

def test_pending_classification_is_readable_for_triage_but_not_metadata_export(env):
 h,_,ids,_=env;c=login(h).json()['csrf_token'];a=upload(h,c,ids['matter']).json()
 assert post(h,T+'/inventory/query',c,{'matter_id':ids['matter']}).json()['recordsTotal']==1
 r=post(h,T+'/inventory/export',c,{'matter_id':ids['matter'],'ids':[a['id']],'format':'csv'});assert r.status_code==200,r.text
 assert r.headers['x-export-unavailable-count']=='1' and a['id'] not in r.text

def test_clean_team_membership_changed_during_scan_withholds_counts(env,monkeypatch):
 from kestrel.services import data_tables as tables
 from kestrel.models import CleanTeamMembership
 from kestrel.services.auth import clock
 from sqlalchemy import select
 h,sessions,ids,_=env
 with sessions() as db:db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
 c=login(h).json()['csrf_token'];a=upload(h,c,ids['matter'],classification='clean_team',clean_team_scope='pricing').json();original=tables.collect
 def changed(db,actor,view,p):
  rows=original(db,actor,view,p)
  with sessions() as other:other.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;other.commit()
  return rows
 monkeypatch.setattr(tables,'collect',changed)
 r=post(h,T+'/inventory/query',c,{'matter_id':ids['matter']});assert r.status_code==409,r.text
 assert a['id'] not in r.text and 'recordsTotal' not in r.text

def test_unrelated_matter_wall_does_not_disclose_change_through_table_failure(env,monkeypatch):
 from kestrel.services import data_tables as tables
 from kestrel.models import EthicalWall
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];upload(h,c,ids['matter']);original=tables.collect
 def changed(db,actor,view,p):
  rows=original(db,actor,view,p)
  with sessions() as other:other.add(EthicalWall(account_id=ids['bank'],matter_id=ids['other'],active=True));other.commit()
  return rows
 monkeypatch.setattr(tables,'collect',changed)
 r=post(h,T+'/inventory/query',c,{'matter_id':ids['matter']});assert r.status_code==200,r.text;assert r.json()['recordsTotal']==1

def test_export_withholds_file_if_wall_changes_and_formula_looking_names_are_text(env,monkeypatch):
 from test_document_workflow import BASE
 from kestrel.services import data_tables as tables
 from kestrel.models import EthicalWall
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];a=upload(h,c,ids['matter'],file_name='=1+1.txt').json()
 assert post(h,BASE+'/documents/'+a['id']+'/confirm',c,{'snapshot_hash':a['snapshot_hash'],'rationale':'Confirm synthetic literal name before export safety checks'}).status_code==200
 p={'matter_id':ids['matter'],'ids':[a['id']],'format':'csv'}
 r=post(h,T+'/inventory/export',c,p);assert r.status_code==200 and "'=1+1.txt" in r.text
 original=tables.selected
 def changed(db,actor,view,p):
  rows=original(db,actor,view,p)
  with sessions() as other:other.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));other.commit()
  return rows
 monkeypatch.setattr(tables,'selected',changed)
 r=post(h,T+'/inventory/export',c,{**p,'format':'xlsx'});assert r.status_code in {403,409},r.text
 assert 'content-disposition' not in r.headers and a['id'] not in r.text
