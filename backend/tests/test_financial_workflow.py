import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_observability_governance import post
from test_document_workflow import BASE
F='/api/v1/financial'
TEXT='Synthetic Vireo revenue FY2025 EUR units IFRS consolidated: 9007199254740993.125. Alternative revenue FY2025 EUR units IFRS consolidated: 9007199254740992.125.'

def source(env):
 h,_,ids,_=env;c=login(h).json()['csrf_token']
 r=h.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':'synthetic-financial.txt','logical_key':'FIN-001','classification':'ordinary','resource_type':'financial','language':'en','governing_law':'unconfirmed','wave':'wave2','synthetic':True},content=TEXT.encode(),headers={'origin':'https://firm.localhost','x-csrf-token':c,'content-type':'application/octet-stream'})
 assert r.status_code==201,r.text;s=r.json()
 assert post(h,BASE+'/documents/'+s['id']+'/confirm',c,{'snapshot_hash':s['snapshot_hash'],'rationale':'Confirmed synthetic financial source classification'}).status_code==200
 return s,c

def payload(rid,content=TEXT,kind='source',token='9007199254740993.125'):
 start=content.index(token)
 return {'reference_kind':kind,'reference_id':rid,'unit':1,'start':start,'end':start+len(token),'context_start':0,'context_end':len(content),'raw_number':token,'decimal_mark':'.','entity':'Vireo','metric':'revenue','period_label':'FY2025','period_start':'2025-01-01','period_end':'2025-12-31','currency':'EUR','scale':'1','scale_label':'units','accounting_basis':'IFRS','consolidation_scope':'consolidated'}

def decision(h,c,f,operation):return post(h,F+'/facts/'+f['id']+'/decisions',c,{'operation':operation,'content_hash':f['content_hash'],'rationale':'Independent confirmation of numeric evidence and every financial dimension'})

def enable_org(h,token):
 state=h.get(F+'/organization-gate').json()
 if not state['enabled']:
  result=post(h,F+'/organization-gate',token,{'expected_revision':state['revision'],'enabled':True,'rationale':'Explicit isolated test organization feature gate; no content grant'})
  assert result.status_code==200,result.text

def test_exact_numeric_duplicate_independent_review_and_reconciliation(env):
 h,sessions,ids,_=env;s,c=source(env);p=payload(s['id']);r=post(h,F+'/facts',c,p);assert r.status_code==201,r.text;f=r.json()
 assert f['amount_text']=='9007199254740993.125'
 assert post(h,F+'/facts',c,p).json()['id']==f['id']
 assert decision(h,c,f,'verify').status_code==403
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,f,'verify').status_code==200
 assert decision(h,token,f,'release').status_code==409
 c=login(h).json()['csrf_token'];g=post(h,F+'/facts',c,payload(s['id'],token='9007199254740992.125')).json()
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,g,'verify').status_code==200
 r=post(h,F+'/compare',token,{'left_id':f['id'],'right_id':g['id']});assert r.status_code==200,r.text
 assert r.json()['status']=='conflict_requires_review' and r.json()['calculation']['difference']=='1'
 # Repeated comparisons share one retained case; the detecting reviewer cannot self-resolve.
 case=r.json()['case']
 assert post(h,F+'/compare',token,{'left_id':g['id'],'right_id':f['id']}).json()['case']['id']==case['id']
 assert post(h,F+'/reconciliations/'+case['id']+'/resolve',token,{'operation':'use_left','content_hash':case['content_hash'],'rationale':'Self resolution must remain blocked'}).status_code==403
 r=post(h,F+'/query',token,{'matter_id':ids['matter'],'currency':'EUR','minimum':'9007199254740993.124'});assert r.status_code==200,r.text
 assert r.json()['authorized_count']==1 and r.json()['rows'][0]['id']==f['id']
 assert post(h,F+'/query',token,{'matter_id':ids['matter'],'minimum':'100'}).status_code==422
 with sessions() as db:
  from kestrel.models import FinancialFact
  assert str(db.get(FinancialFact,f['id']).amount).startswith('9007199254740993.125')
  with pytest.raises(DBAPIError):db.execute(text('DELETE FROM financial_facts'));db.commit()

def test_reconciliation_union_of_sources_and_independent_resolution(env):
 h,sessions,ids,_=env;s,c=source(env)
 a=post(h,F+'/facts',c,payload(s['id'])).json();b=post(h,F+'/facts',c,payload(s['id'],token='9007199254740992.125')).json()
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,a,'verify').status_code==200;assert decision(h,token,b,'verify').status_code==200
 c=login(h).json()['csrf_token'];case=post(h,F+'/compare',c,{'left_id':a['id'],'right_id':b['id']}).json()['case']
 token=login(h,'sme').json()['csrf_token'];r=post(h,F+'/reconciliations/'+case['id']+'/resolve',token,{'operation':'unresolved','content_hash':case['content_hash'],'rationale':'Both original amounts are retained pending source clarification'});assert r.status_code==200,r.text
 assert r.json()['status']=='unresolved' and h.get(F+'/reconciliations?matter_id='+ids['matter']).json()[0]['status']=='unresolved'
 assert post(h,F+'/reconciliations/'+case['id']+'/resolve',token,{'operation':'use_left','content_hash':case['content_hash'],'rationale':'Cannot overwrite the retained resolution'}).status_code==409

def test_no_fabricated_dimensions_admin_override_or_denied_counts(env):
 from kestrel.models import EthicalWall
 h,sessions,ids,_=env;s,c=source(env)
 assert post(h,F+'/facts',c,{**payload(s['id']),'currency':'USD'}).status_code==422
 f=post(h,F+'/facts',c,payload(s['id'])).json()
 root=login(h,'root').json()['csrf_token'];assert post(h,F+'/query',root,{'matter_id':ids['matter']}).status_code==403
 assert decision(h,root,f,'verify').status_code==403
 with sessions() as db:
  from kestrel.models import AuditEvent
  denied=list(db.scalars(select(AuditEvent).where(AuditEvent.actor_id==ids['root'],AuditEvent.action=='financial.query.denied')))
  assert len(denied)==1 and denied[0].object_id is None and denied[0].matter_id is None
 c=login(h).json()['csrf_token']
 with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 assert post(h,F+'/query',c,{'matter_id':ids['matter']}).status_code==403
 assert decision(h,c,f,'verify').status_code==403

def test_external_gate_does_not_grant_original_fact_access(env):
 h,_,ids,app=env;s,c=source(env);assert post(h,F+'/facts',c,payload(s['id'])).status_code==201
 with TestClient(app,base_url='https://bank.localhost') as bank:
  token=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  r=bank.post(F+'/query',json={'matter_id':ids['matter']},headers={'origin':'https://bank.localhost','x-csrf-token':token});assert r.status_code==403
  root=login(h,'root').json()['csrf_token'];r=post(h,F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Enable synthetic bank financial feature; no content grants'});assert r.status_code==200,r.text
  enable_org(h,root)
  r=bank.post(F+'/query',json={'matter_id':ids['matter']},headers={'origin':'https://bank.localhost','x-csrf-token':token});assert r.status_code==200 and r.json()['authorized_count']==0

def test_external_financial_fact_requires_derivative_and_fact_approvals(env,monkeypatch):
 import test_document_workflow as dw,test_disclosures as dis
 content=dw.TEXT+' '+TEXT
 monkeypatch.setattr(dw,'TEXT',content);monkeypatch.setattr(dis,'TEXT',content)
 h,sessions,ids,app=env;src,plan,a,c=dis.prepared(env)
 token=login(h,'sme').json()['csrf_token'];assert post(h,dis.D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':a['bundle_hash'],'rationale':'Approve exact sanitized financial transcript for synthetic bank review'}).status_code==200
 c=login(h).json()['csrf_token'];reader=h.get(dis.D+'/artifacts/'+a['id']+'/reader').json();t=reader['units'][0]['text']
 f=post(h,F+'/facts',c,payload(a['id'],t,'derivative')).json();assert 'id' in f,f
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,f,'verify').status_code==200
 root=login(h,'root').json()['csrf_token'];assert post(h,F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Enable synthetic financial views after individual row authorization'}).status_code==200
 enable_org(h,root)
 with TestClient(app,base_url='https://bank.localhost') as bank:
  b=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  def query():return bank.post(F+'/query',json={'matter_id':ids['matter']},headers={'origin':'https://bank.localhost','x-csrf-token':b})
  assert query().json()['authorized_count']==0
  token=login(h,'sme').json()['csrf_token'];r=decision(h,token,f,'release');assert r.status_code==200,r.text
  r=query();assert r.status_code==200,r.text;assert r.json()['authorized_count']==1
  assert src['id'] not in r.text and 'source_snapshot' not in r.text
  qa=bank.post('/api/v1/questions',json={'matter_id':ids['matter'],'question':'Show the released revenue evidence','mode':'financial','financial_filters':{'currency':'EUR'}},headers={'origin':'https://bank.localhost','x-csrf-token':b})
  assert qa.status_code==201,qa.text
  assert src['id'] not in qa.text and qa.json()['citations'][0]['reader']['kind']=='disclosure'
  assert bank.get(F+'/reconciliations?matter_id='+ids['matter']).status_code==403
  with TestClient(app,base_url='https://client.localhost') as client:
   ct=login(client,'client',origin='https://client.localhost').json()['csrf_token']
   r=client.post(F+'/query',json={'matter_id':ids['matter']},headers={'origin':'https://client.localhost','x-csrf-token':ct});assert r.status_code==200 and r.json()['authorized_count']==0
  assert decision(h,token,f,'revoke').status_code==200
  assert query().json()['authorized_count']==0
  assert bank.get('/api/v1/questions/'+qa.json()['id']).status_code==403

def test_signing_freezes_facts_but_retains_future_access_revocation(env):
 from test_lifecycle import propose,approve
 h,_,ids,_=env;s,c=source(env);f=post(h,F+'/facts',c,payload(s['id'])).json()
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,f,'verify').status_code==200
 root=login(h,'root').json()['csrf_token'];assert post(h,F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Enable feature before signing without any content grant'}).status_code==200
 enable_org(h,root)
 login(h);sign=propose(h,ids,'sign');r=approve(h,sign);assert r.status_code==200,r.text
 c=login(h).json()['csrf_token'];assert post(h,F+'/facts',c,payload(s['id'],token='9007199254740992.125')).status_code==409
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,f,'revoke').status_code==200
 root=login(h,'root').json()['csrf_token'];r=post(h,F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':1,'enabled':False,'rationale':'Disable future bank access after signing without modifying signed records'});assert r.status_code==200,r.text

def test_financial_question_uses_verified_typed_filters_and_rechecks_revocation(env):
 h,_,ids,_=env;s,c=source(env);f=post(h,F+'/facts',c,payload(s['id'])).json()
 p={'matter_id':ids['matter'],'question':'Show the declared revenue evidence','mode':'financial','financial_filters':{'currency':'EUR','minimum':'9007199254740993.124'}}
 r=post(h,'/api/v1/questions',c,p);assert r.status_code==201 and r.json()['status']=='insufficient_evidence'
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,f,'verify').status_code==200
 c=login(h).json()['csrf_token'];r=post(h,'/api/v1/questions',c,{**p,'mode':'automatic'});assert r.status_code==201,r.text
 answer=r.json();assert answer['retrieval']['route']=='typed_financial_sql' and '9007199254740993.125' in answer['answer'] and answer['citations'][0]['kind']=='financial'
 assert '_scope_refs' not in answer
 assert post(h,'/api/v1/questions',c,{**p,'mode':'hybrid'}).status_code==422
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,f,'revoke').status_code==200
 login(h);assert h.get('/api/v1/questions/'+answer['id']).status_code==403
