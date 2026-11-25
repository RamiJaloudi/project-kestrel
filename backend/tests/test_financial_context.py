"""Isolated source-bound sidecars/staging; no live records or provider calls."""
import io,json,uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_observability_governance import post
from test_document_workflow import BASE
from test_financial_workflow import F,payload,decision,TEXT
from kestrel import models as m
from kestrel.adapters.extraction import extract,canonical

C='/api/v1/financial-context'
EXTRA=' Source declarations: SYNTHETIC-ISIN-001 exact source declaration debit positive FY2025 annual report original.'
CONTENT=TEXT+EXTRA

@pytest.fixture
def ready(env):
 h,sessions,ids,app=env
 from kestrel.api.financial_context import router
 if not any(getattr(r,'path','')==C+'/compare' for r in app.routes):app.include_router(router)
 c=login(h).json()['csrf_token']
 src=upload(h,c,ids['matter'],'context-source.txt',CONTENT.encode(),'CTX-TXT')
 a=post(h,F+'/facts',c,payload(src['id'],CONTENT));assert a.status_code==201,a.text
 b=post(h,F+'/facts',c,payload(src['id'],CONTENT,token='9007199254740992.125'));assert b.status_code==201,b.text
 token=login(h,'sme').json()['csrf_token']
 for f in [a.json(),b.json()]:assert decision(h,token,f,'verify').status_code==200
 c=login(h).json()['csrf_token']
 return h,sessions,ids,app,c,src,a.json(),b.json()

def upload(h,c,matter,name,data,key):
 r=h.post(BASE+'/documents',params={'matter_id':matter,'file_name':name,'logical_key':key,'classification':'ordinary','resource_type':'financial','synthetic':True},content=data,headers={'origin':'https://firm.localhost','x-csrf-token':c,'content-type':'application/octet-stream'})
 assert r.status_code==201,r.text;src=r.json()
 r=post(h,BASE+'/documents/'+src['id']+'/confirm',c,{'snapshot_hash':src['snapshot_hash'],'rationale':'Confirm exact synthetic financial source classification'});assert r.status_code==200,r.text
 return src

def context_payload(**changes):
 start=CONTENT.index('Source declarations:');end=len(CONTENT)
 values={'instruments':{'status':'KNOWN','identifiers':[{'scheme':'ISIN','value':'SYNTHETIC-ISIN-001'}]},'precision':{'status':'KNOWN','kind':'exact','label':'exact source declaration'},
  'sign':{'status':'KNOWN','presentation':'unsigned','convention':'debit positive'},'calendar':{'status':'KNOWN','kind':'fiscal_year','label':'FY2025'},'period':{'status':'KNOWN','kind':'annual','label':'annual report'},'restatement':{'status':'KNOWN','kind':'original','label':'original'}}
 return {'dimensions':values,'evidence':[{'field':field,'unit':1,'start':start,'end':end} for field in values],'rationale':'Source declared dimensions; unknowns reviewed without inference','request_key':uuid.uuid4().hex,**changes}

def propose_context(h,c,f,p=None):
 r=post(h,C+'/facts/'+f['id']+'/versions',c,p or context_payload());assert r.status_code==201,r.text;return r.json()

def ctxdecision(h,c,ctx,operation='confirm',**extra):
 return post(h,C+'/versions/'+ctx['id']+'/decisions',c,{'operation':operation,'content_hash':ctx['content_hash'],'content_reviewed':True,'rationale':'Independent exact dimension and original evidence review',**extra})

def compare(h,c,ids,a,b,ca=None,cb=None):
 return post(h,C+'/compare',c,{'matter_id':ids['matter'],'left_id':a['id'],'right_id':b['id'],'left_context_hash':ca['content_hash'] if ca else None,'right_context_hash':cb['content_hash'] if cb else None})

def test_internal_context_confirmation_exact_comparison_and_legacy_contract(ready):
 h,sessions,ids,app,c,src,a,b=ready
 before=post(h,F+'/query',c,{'matter_id':ids['matter']}).json()
 assert compare(h,c,ids,a,b).json()['status']=='UNKNOWN'
 pa=context_payload();ca=propose_context(h,c,a,pa);cb=propose_context(h,c,b)
 assert propose_context(h,c,a,pa)['id']==ca['id']
 assert ctxdecision(h,c,ca).status_code==403
 token=login(h,'sme').json()['csrf_token']
 assert ctxdecision(h,token,ca,content_hash='0'*64).status_code==409
 assert ctxdecision(h,token,ca,content_reviewed=False).status_code==422
 for ctx in [ca,cb]:assert ctxdecision(h,token,ctx).status_code==200
 result=compare(h,token,ids,a,b,ca,cb);assert result.status_code==200,result.text
 assert result.json()['status']=='COMPATIBLE' and result.json()['calculation']['difference']=='1'
 c=login(h).json()['csrf_token'];assert post(h,F+'/query',c,{'matter_id':ids['matter']}).json()==before
 view=h.get(C+'/facts/'+a['id']).json();assert view['current']['state']=='CONFIRMED' and view['current']['provenance']['extractor_confidence']=={'status':'UNKNOWN'}
 assert view['current']['dimensions']['confidence']['status']=='UNKNOWN'
 assert len(view['current']['evidence'])==6
 from kestrel.services.financial_context import audit_records
 with sessions() as db:
  evidence=db.scalar(select(m.FinancialContextEvidence).where(m.FinancialContextEvidence.context_id==ca['id']))
  retained=audit_records(db,evidence.id);assert any(isinstance(row,m.FinancialFact) and row.id==a['id'] for row in retained)
  assert any(isinstance(row,m.FinancialContextDecision) for row in retained)
  for table in ['financial_fact_contexts','financial_context_evidence','financial_context_decisions']:
   with pytest.raises(DBAPIError):db.execute(text('DELETE FROM '+table));db.commit()
   db.rollback()

def test_unknown_mismatch_forged_evidence_and_version_concurrency(ready):
 h,_,ids,_,c,src,a,b=ready
 invalid=context_payload();invalid['dimensions']['calendar']['label']='Invented unsupported calendar';assert post(h,C+'/facts/'+a['id']+'/versions',c,invalid).status_code==422
 invalid=context_payload();invalid['dimensions']['sign']['presentation']='minus';assert post(h,C+'/facts/'+a['id']+'/versions',c,invalid).status_code==422
 invalid=context_payload();invalid['dimensions']['confidence']={'status':'ASSESSMENT','value':0.99,'basis':'reviewer_assessed','rationale':'Declared opinion only'};assert post(h,C+'/facts/'+a['id']+'/versions',c,invalid).status_code==422
 ca=propose_context(h,c,a);assert post(h,C+'/facts/'+a['id']+'/versions',c,context_payload()).status_code==409
 cb=propose_context(h,c,b,context_payload(dimensions={},evidence=[]))
 token=login(h,'sme').json()['csrf_token']
 for ctx in [ca,cb]:assert ctxdecision(h,token,ctx).status_code==200
 result=compare(h,token,ids,a,b,ca,cb).json();assert result['status']=='UNKNOWN' and result['calculation'] is None
 c=login(h).json()['csrf_token'];p=context_payload(expected_context_hash=cb['content_hash']);p['dimensions']['restatement']={'status':'KNOWN','kind':'restated','label':'original'}
 newer=propose_context(h,c,b,p);token=login(h,'sme').json()['csrf_token'];assert ctxdecision(h,token,newer).status_code==200
 assert compare(h,token,ids,a,b,ca,cb).status_code==409
 result=compare(h,token,ids,a,b,ca,newer).json();assert result['status']=='INCOMPATIBLE' and result['calculation'] is None

def test_context_no_root_bank_client_or_cross_matter_override(ready):
 h,sessions,ids,app,c,src,a,b=ready;ctx=propose_context(h,c,a)
 root=login(h,'root').json()['csrf_token'];assert h.get(C+'/facts/'+a['id']).status_code==403
 assert ctxdecision(h,root,ctx).status_code==403
 c=login(h).json()['csrf_token'];bad={'matter_id':ids['other'],'left_id':a['id'],'right_id':b['id']}
 assert post(h,C+'/compare',c,bad).status_code==403
 for host,name in [('bank','bank'),('client','client')]:
  origin='https://'+host+'.localhost'
  with TestClient(app,base_url=origin) as external:
   csrf=login(external,name,origin=origin).json()['csrf_token']
   assert external.get(C+'/facts/'+a['id']).status_code==403
   r=external.post(C+'/sources/'+src['id']+'/scan',json={'extractor':'literal_rows_v1','limit':50,'request_key':uuid.uuid4().hex,'rationale':'External source metadata must stay unavailable'},headers={'origin':origin,'x-csrf-token':csrf});assert r.status_code==403
   assert a['amount_text'] not in r.text and 'SYNTHETIC-ISIN' not in r.text
 with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 assert h.get(C+'/facts/'+a['id']).status_code==403

@pytest.mark.parametrize('change',['wall','role','revocation'])
def test_context_compare_withholds_prepared_arithmetic_after_confirmation_changes(ready,monkeypatch,change):
 from kestrel.services import financial_context as service
 h,sessions,ids,_,c,src,a,b=ready;ca=propose_context(h,c,a);cb=propose_context(h,c,b)
 token=login(h,'sme').json()['csrf_token']
 for ctx in [ca,cb]:assert ctxdecision(h,token,ctx).status_code==200
 c=login(h).json()['csrf_token'];original=service.comparison;done=[]
 def changed(db,actor,p):
  value=original(db,actor,p)
  if not done:
   done.append(True)
   with sessions() as other:
    if change=='wall':other.add(m.EthicalWall(account_id=ids['sme'],matter_id=ids['matter'],active=True))
    elif change=='role':
     for grant in other.scalars(select(m.RoleGrant).where(m.RoleGrant.account_id==ids['sme'])):other.delete(grant)
    else:
     row=other.get(m.FinancialFactContext,ca['id']);capture={k:getattr(row,k) for k in ['matter_id','source_id','retained_classification','retained_scope']}
     from kestrel.services.auth import clock
     other.add(m.FinancialContextDecision(**capture,context_id=row.id,operation='revoke',content_hash=row.content_hash,actor_id=ids['sme'],content_reviewed=False,rationale='Independent concurrent revocation before response',occurred_at=clock()))
    other.commit()
  return value
 monkeypatch.setattr(service,'comparison',changed)
 r=compare(h,c,ids,a,b,ca,cb);assert r.status_code in {403,409},r.text
 assert 'calculation' not in r.text and '900719925474' not in r.text

def workbook_template(*,formula=False):
 from openpyxl import Workbook
 names=['amount','entity','metric','period_label','period_start','period_end','currency','scale','scale_label','accounting_basis','consolidation_scope','decimal_mark','numeric_notation','instrument_scheme','instrument_id','precision_kind','precision_label','sign_convention','calendar_kind','calendar_label','period_kind','restatement_kind','restatement_label']
 values=['-9007199254740993.125','Vireo','revenue','FY2025','2025-01-01','2025-12-31','EUR','1','units','IFRS','consolidated','.','decimal','ISIN','SYNTHETIC-ISIN-001','exact','exact source declaration','debit positive','fiscal_year','FY2025','annual','original','original']
 book=Workbook();book.active.title='Declared facts';book.active.append(names);book.active.append(values)
 if formula:book.active['A2']='=1+2'
 stream=io.BytesIO();book.save(stream);return stream.getvalue()

def test_deterministic_template_and_xbrl_missing_semantics_never_infer_or_execute():
 from kestrel.adapters.financial_candidates import extract as stage
 from test_financial_converters import xbrl,ixbrl
 rows=stage(extract('template.xlsx',workbook_template())['units'],'literal_rows_v1',50)
 assert len(rows)==1 and rows[0]['state']=='READY_FOR_REVIEW'
 assert rows[0]['amount_text']=='-9007199254740993.125' and rows[0]['normalized']['approval']=='UNAPPROVED'
 assert rows[0]['dimensions']['sign']['presentation']=='minus'
 assert rows[0]['dimensions']['confidence']['status']=='UNKNOWN'
 formula=stage(extract('template.xlsx',workbook_template(formula=True))['units'],'literal_rows_v1',50)[0]
 assert formula['amount_text'] is None and formula['state']=='INCOMPLETE' and formula['normalized'] is None
 units=extract('source.xbrl',xbrl())['units'];first=stage(units,'xbrl_v1',50)[0]
 assert first['amount_text']=='9007199254740993.125' and first['currency']=='EUR' and first['state']=='INCOMPLETE'
 assert first['dimensions']['precision']['value']=='3'
 assert {'instruments','calendar','period','restatement','accounting_basis','consolidation_scope'}<=set(first['missing'])
 assert first['normalized'] is None and first['dimensions']['instruments']['identifiers']==[]
 inline=stage(extract('source.ixbrl',ixbrl())['units'],'xbrl_v1',50)[0]
 assert inline['amount_text']=='-9007199254740993125' and inline['dimensions']['sign']['status']=='UNKNOWN'
 with pytest.raises(HTTPException) as denied:stage(units,'xbrl_v1',1)
 assert denied.value.status_code==413

def test_candidate_stage_idempotency_bounds_retained_evidence_and_no_fact_promotion(ready):
 h,sessions,ids,_,c,_,a,b=ready;src=upload(h,c,ids['matter'],'template.xlsx',workbook_template(),'CTX-XLSX')
 p={'request_key':uuid.uuid4().hex,'extractor':'literal_rows_v1','limit':50,'rationale':'Explicit deterministic staging only; no fact or release creation'}
 with sessions() as db:before=db.scalar(select(func.count()).select_from(m.FinancialFact))
 r=post(h,C+'/sources/'+src['id']+'/scan',c,p);assert r.status_code==201,r.text
 staged=r.json();assert len(staged)==1 and staged[0]['state']=='READY_FOR_REVIEW' and staged[0]['approval']=='UNAPPROVED'
 assert post(h,C+'/sources/'+src['id']+'/scan',c,p).json()==staged
 assert post(h,C+'/sources/'+src['id']+'/scan',c,{**p,'limit':1}).status_code==409
 assert h.get(C+'/sources/'+src['id']+'/candidates').json()==staged
 for ref in staged[0]['evidence']:assert ref['quote'] and ref['reader']['id']==src['id']
 with sessions() as db:
  assert db.scalar(select(func.count()).select_from(m.FinancialFact))==before
  from decimal import Decimal
  row=db.get(m.FinancialExtractionCandidate,staged[0]['id']);assert row.amount==Decimal('-9007199254740993.125')
  with pytest.raises(DBAPIError):db.execute(text('UPDATE financial_extraction_candidates SET state=\'INCOMPLETE\''));db.commit()
  db.rollback();db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 r=h.get(C+'/sources/'+src['id']+'/candidates');assert r.status_code==403 and '900719925474' not in r.text

def test_signing_retains_contexts_and_candidates_blocks_new_work_allows_bodyless_revoke(ready):
 from test_lifecycle import propose,approve
 h,sessions,ids,_,c,_,a,b=ready;ctx=propose_context(h,c,a)
 src=upload(h,c,ids['matter'],'template.xlsx',workbook_template(),'CTX-SIGN-XLSX')
 p={'request_key':uuid.uuid4().hex,'extractor':'literal_rows_v1','rationale':'Retained unapproved staging for signing manifest coverage'}
 assert post(h,C+'/sources/'+src['id']+'/scan',c,p).status_code==201
 token=login(h,'sme').json()['csrf_token'];assert ctxdecision(h,token,ctx).status_code==200
 login(h);sign=propose(h,ids,'sign');r=approve(h,sign);assert r.status_code==200,r.text
 with sessions() as db:
  manifest=json.loads(db.get(m.LifecycleDecision,sign['id']).payload_json)
  for name in ['financial_fact_contexts','financial_context_evidence','financial_context_decisions','financial_extraction_candidates']:assert manifest[name],name
 c=login(h).json()['csrf_token'];assert post(h,C+'/facts/'+b['id']+'/versions',c,context_payload()).status_code==409
 assert post(h,C+'/sources/'+src['id']+'/scan',c,{**p,'request_key':uuid.uuid4().hex}).status_code==409
 r=ctxdecision(h,c,ctx,'revoke');assert r.status_code==200,r.text
 assert set(r.json())=={'id','content_hash','state','audience'} and r.json()['state']=='REVOKED'
 assert h.get(C+'/facts/'+a['id']).json()['current']['state']=='REVOKED'

def test_context_schema_metadata_and_populated_destructive_downgrade_are_guarded(ready):
 from pathlib import Path
 from alembic import command
 from alembic.config import Config
 h,sessions,ids,_,c,src,a,b=ready;ctx=propose_context(h,c,a)
 cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
 command.check(cfg)
 with pytest.raises(RuntimeError,match='Retained financial context'):command.downgrade(cfg,'0037')
 with sessions() as db:
  assert db.get(m.FinancialFactContext,ctx['id']).content_hash==ctx['content_hash']
  assert db.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0038'

def test_candidate_response_rechecks_source_clearance_and_audits_without_body(ready,monkeypatch):
 from kestrel.services import financial_context as service
 h,sessions,ids,_,c,_,a,b=ready;src=upload(h,c,ids['matter'],'template.xlsx',workbook_template(),'CTX-RACE-XLSX')
 p={'request_key':uuid.uuid4().hex,'extractor':'literal_rows_v1','rationale':'Retained candidate metadata needs current source clearance'}
 assert post(h,C+'/sources/'+src['id']+'/scan',c,p).status_code==201
 original=service.candidate_output;done=[]
 def changed(db,actor,cid):
  value=original(db,actor,cid)
  if not done:
   done.append(True)
   with sessions() as other:other.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));other.commit()
  return value
 monkeypatch.setattr(service,'candidate_output',changed)
 r=h.get(C+'/sources/'+src['id']+'/candidates');assert r.status_code in {403,409},r.text
 assert 'SYNTHETIC-ISIN' not in r.text and '900719925474' not in r.text
 with sessions() as db:
  event=db.scalar(select(m.AuditEvent).where(m.AuditEvent.action=='financial_context.candidates.denied'));assert event and event.object_id is None and event.matter_id is None

def test_changed_source_policy_denies_retained_context_body_and_candidate_metadata(ready):
 h,sessions,ids,_,c,src,a,b=ready;propose_context(h,c,a)
 workbook=upload(h,c,ids['matter'],'template.xlsx',workbook_template(),'CTX-CHANGE-XLSX')
 p={'request_key':uuid.uuid4().hex,'extractor':'literal_rows_v1','rationale':'Explicit source-bound staging before quarantine changes'}
 assert post(h,C+'/sources/'+workbook['id']+'/scan',c,p).status_code==201
 with sessions() as db:
  for sid in [src['id'],workbook['id']]:db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,sid).policy_id).quarantined=True
  db.commit()
 for path in ['/facts/'+a['id'],'/sources/'+workbook['id']+'/candidates']:
  r=h.get(C+path);assert r.status_code==403 and 'SYNTHETIC-ISIN' not in r.text and '900719925474' not in r.text

def test_released_bank_fact_json_does_not_inherit_internal_context_or_candidates(env,monkeypatch):
 import test_document_workflow as dw,test_disclosures as dis
 from test_financial_workflow import enable_org
 from kestrel.api.financial_context import router
 h,sessions,ids,app=env
 if not any(getattr(r,'path','')==C+'/compare' for r in app.routes):app.include_router(router)
 content=dw.TEXT+' '+CONTENT;monkeypatch.setattr(dw,'TEXT',content);monkeypatch.setattr(dis,'TEXT',content)
 src,plan,artifact,c=dis.prepared(env);token=login(h,'sme').json()['csrf_token']
 r=post(h,dis.D+'/artifacts/'+artifact['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Independent exact financial transcript approval for isolated bank boundary'});assert r.status_code==200,r.text
 c=login(h).json()['csrf_token'];body=h.get(dis.D+'/artifacts/'+artifact['id']+'/reader').json()['units'][0]['text'];r=post(h,F+'/facts',c,payload(artifact['id'],body,'derivative'));assert r.status_code==201,r.text;fact=r.json()
 token=login(h,'sme').json()['csrf_token'];assert decision(h,token,fact,'verify').status_code==200;assert decision(h,token,fact,'release').status_code==200
 root=login(h,'root').json()['csrf_token'];assert post(h,F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Explicit isolated bank gate; no source content override'}).status_code==200;enable_org(h,root)
 with TestClient(app,base_url='https://bank.localhost') as bank:
  csrf=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  def query():return bank.post(F+'/query',json={'matter_id':ids['matter']},headers={'origin':'https://bank.localhost','x-csrf-token':csrf})
  before=query();assert before.status_code==200 and before.json()['authorized_count']==1
  c=login(h).json()['csrf_token'];context=propose_context(h,c,fact,context_payload(dimensions={},evidence=[]));token=login(h,'sme').json()['csrf_token'];assert ctxdecision(h,token,context).status_code==200
  after=query();assert after.json()==before.json() and 'context' not in set(after.json()['rows'][0]) and context['id'] not in after.text
  denied=bank.get(C+'/facts/'+fact['id']);assert denied.status_code==403 and context['content_hash'] not in denied.text

def test_context_audit_and_signing_inherit_a_different_historic_fact_restriction(ready):
 """Seed a retained historic fact, not a downgrade of any existing record.

 The current source and new context are ordinary, but an older fact retains
 another partition. Audit authorization must not infer safety from the context.
 """
 from kestrel.services.auth import clock,audit
 from kestrel.adapters.extraction import digest
 from kestrel.services.financial_context import audit_records
 h,sessions,ids,_,c,src,a,b=ready
 with sessions() as db:
  db.add(m.CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='historic-financial-partition',approved_by=ids['sme'],expires_at=clock()+3600))
  old=db.get(m.FinancialFact,a['id']);values={col.name:getattr(old,col.name) for col in m.FinancialFact.__table__.columns if col.name not in {'id','evidence_key','retained_classification','retained_scope'}}
  historic=m.FinancialFact(**values,evidence_key=digest(uuid.uuid4().hex.encode()),retained_classification='clean_team',retained_scope='historic-financial-partition');db.add(historic);db.commit();fid=historic.id
 context=propose_context(h,c,{'id':fid},context_payload(dimensions={},evidence=[]))
 with sessions() as db:
  row=db.get(m.FinancialFactContext,context['id']);assert row.retained_classification=='ordinary'
  assert any(isinstance(record,m.FinancialFact) and record.retained_scope=='historic-financial-partition' for record in audit_records(db,row.id))
  audit(db,'financial_context.fixture_access','allowed',ids['lawyer'],category='access',matter_id=ids['matter'],object_id=row.id);db.commit()
 before=h.get('/api/v1/audit/events?category=access&matter_id='+ids['matter']);assert before.status_code==200 and context['id'] in before.text
 with sessions() as db:
  membership=db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'],m.CleanTeamMembership.scope=='historic-financial-partition'));membership.revoked=True;db.commit()
 assert h.get(BASE+'/documents/'+src['id']+'/reader').status_code==200
 denied=h.get(C+'/facts/'+fid);assert denied.status_code==403 and context['content_hash'] not in denied.text
 after=h.get('/api/v1/audit/events?category=access&matter_id='+ids['matter']);assert after.status_code==200 and context['id'] not in after.text
 assert post(h,'/api/v1/lifecycle',c,{'matter_id':ids['matter'],'kind':'sign','rationale':'Current source access cannot erase the retained fact partition'}).status_code==403
