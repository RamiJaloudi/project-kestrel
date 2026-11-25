"""Prospective/historic workbook protection; all data is isolated synthetic evidence."""
import io,json,zipfile,uuid
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from test_auth_policy import env,login,PASSWORD
from test_document_workflow import BASE
from test_observability_governance import post
from test_financial_workflow import TEXT,F,payload,decision,enable_org
from kestrel import models as m
from kestrel.adapters.extraction import extract,canonical,digest,office_guard
from kestrel.adapters.spreadsheet_source import workbook
from kestrel.adapters import disclosure,workbook_safety

D='/api/v1/disclosures'
ROW_SECRET='HIDDEN_ROW_SECRET_784'
COL_SECRET='HIDDEN_COLUMN_SECRET_885'
COMMENT_SECRET='COMMENT_SECRET_982'
NAME_SECRET='NAME_SECRET_817'
OPAQUE_SECRET=b'OPAQUE_SECRET_781_NEVER_EXECUTE'
REMOVE='PRIVATE_REMOVE_772'

def book_data(mode='all'):
 from openpyxl import Workbook
 from openpyxl.comments import Comment
 from openpyxl.workbook.defined_name import DefinedName
 b=Workbook();s=b.active;s.title='Visible';s['A1']=TEXT;s['A2']=ROW_SECRET;s['A3']='Public commercial transaction summary '+REMOVE+' retained public terms.'
 if mode in {'all','row'}:s.row_dimensions[2].hidden=True
 if mode in {'all','column'}:s.column_dimensions['B'].hidden=True;s['B1']=COL_SECRET
 if mode in {'all','sheet'}:b.create_sheet('Restricted').sheet_state='veryHidden';b['Restricted']['A1']='HIDDEN_SHEET_SECRET_983'
 if mode in {'all','comment'}:s['A3'].comment=Comment(COMMENT_SECRET,'Private synthetic author')
 if mode in {'all','name'}:b.defined_names.add(DefinedName('PrivateNamedValue',attr_text='"'+NAME_SECRET+'"',hidden=True))
 if mode in {'all','formula'}:s['A4']='=1+2'
 if mode=='empty_hidden':s.row_dimensions[90].hidden=True;s.column_dimensions['AZ'].hidden=True
 stream=io.BytesIO();b.save(stream)
 out=io.BytesIO()
 with zipfile.ZipFile(stream) as source,zipfile.ZipFile(out,'w') as target:
  for item in source.infolist():
   value=source.read(item.filename)
   if item.filename=='xl/worksheets/sheet1.xml':value=value.replace(b'<f>1+2</f><v></v>',b'<f>1+2</f><v>771239005</v>')
   if mode in {'all','opaque'} and item.filename=='xl/_rels/workbook.xml.rels':value=value.replace(b'</Relationships>',b'<Relationship Id="opaque1" Type="urn:synthetic:opaque" Target="opaque/private.bin"/></Relationships>')
   target.writestr(item,value)
  if mode in {'all','opaque'}:target.writestr('xl/opaque/private.bin',OPAQUE_SECRET)
 return out.getvalue()

def historical(data):
 office_guard(data,'xl/workbook.xml');units=workbook(data,extended=False)
 return {'units':units,'media_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','extractor':'literal-workbook-xml-2','status':'ready','sensitive_hidden':False,'bytes_hash':digest(data),'text_hash':digest(canonical(units).encode())}

def source_like(data,old=False):
 parsed=historical(data) if old else extract('evidence.xlsx',data)
 return SimpleNamespace(file_name='evidence.xlsx',data=data,units_json=canonical(parsed['units'])),parsed

def upload(h,c,ids,data,classification='ordinary',key=None):
 return h.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':'evidence.xlsx','logical_key':key or 'XLSX-PARITY-'+uuid.uuid4().hex[:8],'classification':classification,'clean_team_scope':'pricing' if classification=='clean_team' else '', 'resource_type':'financial','synthetic':True},content=data,headers={'origin':'https://firm.localhost','x-csrf-token':c,'content-type':'application/octet-stream'})

def confirm_review(h,c,src):
 assert post(h,BASE+'/documents/'+src['id']+'/confirm',c,{'snapshot_hash':src['snapshot_hash'],'rationale':'Confirm declared synthetic source handling without any access relaxation'}).status_code==200
 r=post(h,'/api/v1/diligence/documents/'+src['id']+'/reviews',c,{'expected_revision':0,'title':'Whole original workbook review','counterparty':'Synthetic Vireo','scope':'financial','coverage_state':'complete','rationale':'Review all original workbook rows and retained metadata'});assert r.status_code==201,r.text

def plan_payload(src,units):
 unit=next(u for u in units if REMOVE in u['text']);start=unit['text'].index(REMOVE)
 return {'source_id':src['id'],'audience':'castlegate','title':'Sanitized commercial evidence','purpose':'Synthetic exact output review only','expires_in_days':7,'request_key':uuid.uuid4().hex,'spans':[{'unit':unit['number'],'start':start,'end':start+len(REMOVE)}],'rationale':'Remove the selected confidential phrase; hidden and opaque material is never copied'}

@pytest.mark.parametrize('mode',['row','column','sheet','comment','name','opaque','empty_hidden'])
def test_xlsx_all_visibility_and_opaque_metadata_are_retained_and_protective(mode):
 data=book_data(mode);row,parsed=source_like(data);receipt=parsed['units'][0]['workbook_safety'];assert parsed['sensitive_hidden'] and receipt['sensitive_hidden']
 assert receipt['bytes_hash']==digest(data) and workbook_safety.scan(row)['complete']
 if mode=='row':assert next(u for u in parsed['units'] if u['locator']=='Visible, row 2')['cells'][0]['hidden']
 if mode=='column':assert next(u for u in parsed['units'] if u['locator']=='Visible, row 1')['cells'][1]['hidden']
 if mode=='comment':assert COMMENT_SECRET in canonical(parsed['units'])
 if mode=='name':assert NAME_SECRET in canonical(parsed['units'])
 if mode=='opaque':assert digest(OPAQUE_SECRET) in canonical(parsed['units']) and OPAQUE_SECRET.decode() not in canonical(parsed['units'])
 assert row.data==data

@pytest.mark.parametrize('old',[False,True])
def test_reconstruction_omits_hidden_cells_metadata_formula_and_cache_without_rewriting_offsets(old):
 data=book_data();source,parsed=source_like(data,old);before=source.units_json
 units,manifest,removed=disclosure.sanitize(source,plan_payload({'id':'source'},parsed['units'])['spans']);rendered=canonical(units)
 for secret in [ROW_SECRET,COL_SECRET,COMMENT_SECRET,NAME_SECRET,'HIDDEN_SHEET_SECRET_983','771239005','Formula =','Worksheet Visible',REMOVE]:assert secret not in rendered
 assert 'Public commercial transaction summary' in rendered and len(units)==1
 assert source.data==data and source.units_json==before
 original=next(u for u in parsed['units'] if REMOVE in u['text']);selected=manifest[0];assert original['text'][selected['start']:selected['end']]==REMOVE
 report=disclosure.validate(disclosure.render('Safe transcript',units),'Safe transcript',units,removed);assert report['passed']

def test_ordinary_workbook_is_still_allowed_and_unsupported_visibility_fails_closed():
 source,parsed=source_like(book_data('plain'));assert not parsed['sensitive_hidden'] and not parsed['units'][0]['workbook_safety']['has_formulas']
 units,_,_=disclosure.sanitize(source,[]);assert len(units)==3
 broken=SimpleNamespace(file_name='old.xlsx',data=b'not-a-workbook',units_json='[]')
 with pytest.raises(HTTPException) as denied:workbook_safety.scan(broken)
 assert denied.value.status_code==409
 old,parsed=source_like(book_data('row'),True);assert not workbook_safety.scan(old)['complete']
 with pytest.raises(HTTPException):workbook_safety.handling(old,SimpleNamespace(classification='ordinary',clean_team_scope=None,classification_confirmed=True))

@pytest.mark.parametrize('secret',[ROW_SECRET,COL_SECRET,COMMENT_SECRET,NAME_SECRET,'771239005'])
def test_removed_hidden_cell_name_comment_or_cache_cannot_reappear_in_title(secret):
 source,parsed=source_like(book_data());units,_,removed=disclosure.sanitize(source,plan_payload({'id':'source'},parsed['units'])['spans'])
 title='Proposed disclosure '+secret
 with pytest.raises(HTTPException) as denied:disclosure.validate(disclosure.render(title,units),title,units,removed)
 assert denied.value.status_code==422

def test_current_intake_requires_named_scope_and_client_ordinary_upload_cannot_bypass_it(env):
 from test_financial_converters import memberships
 h,sessions,ids,app=env;c=login(h).json()['csrf_token'];data=book_data()
 assert upload(h,c,ids,data).status_code==422
 assert upload(h,c,ids,data,'clean_team').status_code==403
 memberships(sessions,ids,[ids['lawyer']]);r=upload(h,c,ids,data,'clean_team');assert r.status_code==201,r.text;src=r.json()
 reader=h.get(BASE+'/documents/'+src['id']+'/reader');assert reader.status_code==200 and reader.json()['units'][0]['workbook_safety']['sensitive_hidden']
 with TestClient(app,base_url='https://client.localhost') as client:
  token=login(client,'client',origin='https://client.localhost').json()['csrf_token'];headers={'origin':'https://client.localhost','x-csrf-token':token,'content-type':'application/octet-stream'}
  denied=client.post('/api/v1/client-uploads',params={'matter_id':ids['matter'],'file_name':'private.xlsx','synthetic':True,'handling':'ordinary'},content=data,headers=headers);assert denied.status_code==422
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');denied=bank.get(BASE+'/documents/'+src['id']+'/reader');assert denied.status_code==403 and COL_SECRET not in denied.text

def test_legacy_unscanned_ordinary_source_cannot_obtain_a_new_disclosure_plan(env,monkeypatch):
 from kestrel.services import workflow
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];data=book_data()
 with monkeypatch.context() as old:old.setattr(workflow,'extract',lambda name,raw:historical(raw));r=upload(h,c,ids,data)
 assert r.status_code==201,r.text;src=r.json();confirm_review(h,c,src);units=h.get(BASE+'/documents/'+src['id']+'/reader').json()['units']
 r=post(h,D+'/plans',c,plan_payload(src,units));assert r.status_code==409,r.text
 with sessions() as db:
  source=db.get(m.SourceVersion,src['id']);policy=db.get(m.DocumentPolicyVersion,source.policy_id)
  assert source.data==data and source.extractor_version=='literal-workbook-xml-2' and policy.classification=='ordinary'
  assert db.scalar(select(func.count()).select_from(m.DisclosurePlan))==0

def test_scanned_scoped_workbook_can_release_only_rebuilt_visible_evidence_after_separate_counsel(env):
 from kestrel.bootstrap import provision
 from kestrel.services.auth import clock
 h,sessions,ids,app=env;c=login(h).json()['csrf_token'];data=book_data()
 with sessions() as db:
  counsel=provision(db,'counsel','firm',['antitrust_counsel'],PASSWORD);db.flush();db.add(m.MatterAssignment(account_id=counsel.id,matter_id=ids['matter'],expires_at=clock()+3600))
  for uid in [ids['lawyer'],ids['sme'],counsel.id]:db.add(m.CleanTeamMembership(account_id=uid,matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600))
  db.commit()
 r=upload(h,c,ids,data,'clean_team');assert r.status_code==201,r.text;src=r.json();confirm_review(h,c,src)
 original=h.get(BASE+'/documents/'+src['id']+'/reader').json()['units'];r=post(h,D+'/plans',c,plan_payload(src,original));assert r.status_code==201,r.text;plan=r.json()
 token=login(h,'sme').json()['csrf_token'];assert post(h,D+'/plans/'+plan['id']+'/review',token,{'operation':'approve','content_hash':plan['content_hash'],'rationale':'Review exact removal range and protected workbook visibility'}).status_code==200
 c=login(h).json()['csrf_token'];r=post(h,D+'/plans/'+plan['id']+'/build',c,{});assert r.status_code==201,r.text;artifact=r.json()
 assert artifact['requires_antitrust'] and artifact['manifest']['workbook_visibility']==original[0]['workbook_safety']
 token=login(h,'sme').json()['csrf_token'];assert post(h,D+'/artifacts/'+artifact['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Independent senior review of exact rebuilt visible transcript'}).status_code==200
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');assert bank.get(D+'/artifacts/'+artifact['id']+'/reader').status_code==403
  token=login(h,'counsel').json()['csrf_token'];assert post(h,D+'/artifacts/'+artifact['id']+'/decisions',token,{'operation':'antitrust_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Separate independent counsel approves only the exact rebuilt transcript'}).status_code==200
  reader=bank.get(D+'/artifacts/'+artifact['id']+'/reader');assert reader.status_code==200,reader.text
  from pypdf import PdfReader
  binary=bank.get(D+'/artifacts/'+artifact['id']+'/download');assert binary.status_code==200,binary.text
  text=''.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(binary.content)).pages)
  for secret in [ROW_SECRET,COL_SECRET,COMMENT_SECRET,NAME_SECRET,'HIDDEN_SHEET_SECRET_983','771239005',REMOVE,src['id'],'Private synthetic author']:
   assert secret not in reader.text and secret not in text
  assert 'Public commercial transaction summary' in text and 'workbook_visibility' not in reader.text
  assert bank.get(BASE+'/documents/'+src['id']+'/reader').status_code==403
 with sessions() as db:assert db.get(m.SourceVersion,src['id']).data==data and db.get(m.SourceVersion,src['id']).units_json==canonical(original)

def test_already_approved_legacy_artifact_fact_and_cached_citation_are_withheld_without_mutation(env,monkeypatch):
 """Create historical records with the old omissions, then restore current guards."""
 from kestrel.services import workflow
 h,sessions,ids,app=env;c=login(h).json()['csrf_token'];data=book_data()
 with TestClient(app,base_url='https://bank.localhost') as bank:
  bank_token=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  def bpost(path,body):return bank.post(path,json=body,headers={'origin':'https://bank.localhost','x-csrf-token':bank_token})
  with monkeypatch.context() as old:
   old.setattr(workflow,'extract',lambda name,raw:historical(raw));old.setattr(workbook_safety,'handling',lambda source,policy:None);old.setattr(workbook_safety,'excluded',lambda source,units:set());old.setattr(workbook_safety,'secrets',lambda source:[]);old.setattr(disclosure,'VERSION','flattened-text-pdf-v1')
   r=upload(h,c,ids,data);assert r.status_code==201,r.text;src=r.json();confirm_review(h,c,src)
   units=h.get(BASE+'/documents/'+src['id']+'/reader').json()['units'];r=post(h,D+'/plans',c,plan_payload(src,units));assert r.status_code==201,r.text;plan=r.json()
   token=login(h,'sme').json()['csrf_token'];assert post(h,D+'/plans/'+plan['id']+'/review',token,{'operation':'approve','content_hash':plan['content_hash'],'rationale':'Historical exact plan approval before safety parity scan'}).status_code==200
   c=login(h).json()['csrf_token'];r=post(h,D+'/plans/'+plan['id']+'/build',c,{});assert r.status_code==201,r.text;artifact=r.json()
   token=login(h,'sme').json()['csrf_token'];assert post(h,D+'/artifacts/'+artifact['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Historical independent exact artifact release before parity fix'}).status_code==200
   assert COL_SECRET in bank.get(D+'/artifacts/'+artifact['id']+'/reader').text
   c=login(h).json()['csrf_token'];body=h.get(D+'/artifacts/'+artifact['id']+'/reader').json()['units'][0]['text'];r=post(h,F+'/facts',c,payload(artifact['id'],body,'derivative'));assert r.status_code==201,r.text;fact=r.json()
   token=login(h,'sme').json()['csrf_token'];assert decision(h,token,fact,'verify').status_code==200;assert decision(h,token,fact,'release').status_code==200
   root=login(h,'root').json()['csrf_token'];assert post(h,F+'/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Isolated bank gate for a retained legacy artifact boundary'}).status_code==200;enable_org(h,root)
   assert bpost(F+'/query',{'matter_id':ids['matter']}).json()['authorized_count']==1
   cached=bpost('/api/v1/questions',{'matter_id':ids['matter'],'question':'Show verified revenue evidence','mode':'financial','financial_filters':{'currency':'EUR'}});assert cached.status_code==201,cached.text;answer=cached.json()
  def retained():
   with sessions() as db:
    source=db.get(m.SourceVersion,src['id']);a=db.get(m.DisclosureArtifact,artifact['id']);f=db.get(m.FinancialFact,fact['id']);policy=db.get(m.DocumentPolicyVersion,source.policy_id)
    return (source.data,source.units_json,source.bytes_hash,source.text_hash,a.data,a.units_json,a.manifest_json,a.bundle_hash,f.content_hash,policy.classification,db.scalar(select(func.count()).select_from(m.DisclosureDecision)),db.scalar(select(func.count()).select_from(m.FinancialFactDecision)))
  before=retained()
  from kestrel.repositories.identity import principal
  from kestrel.services.auth import clock
  with sessions() as db:
   derived=db.get(m.DocumentPolicyVersion,db.get(m.DisclosureArtifact,artifact['id']).policy_id)
   actor=principal(db,db.get(m.Account,ids['lawyer']),clock())
   with pytest.raises(HTTPException):workflow.require_policy(db,actor,derived,'analyze')
   with pytest.raises(HTTPException):workflow.processing_allowed(db,derived,external=True)
  for suffix in ['/reader','/download']:
   denied=bank.get(D+'/artifacts/'+artifact['id']+suffix);assert denied.status_code==403 and COL_SECRET not in denied.text and 'content-disposition' not in denied.headers
  result=bpost(F+'/query',{'matter_id':ids['matter']});assert result.status_code==200 and result.json()['authorized_count']==0
  table=bpost('/api/v1/tables/financial/query',{'matter_id':ids['matter']});assert table.status_code==200 and table.json()['recordsTotal']==0
  denied=bank.get('/api/v1/questions/'+answer['id']);assert denied.status_code==403 and fact['amount_text'] not in denied.text
  assert retained()==before

@pytest.mark.parametrize('legacy',[False,True])
def test_named_halden_grant_never_treats_missing_workbook_scan_as_cleared(legacy,env,monkeypatch):
 from kestrel.services import workflow
 from kestrel.services.auth import clock
 from kestrel.bootstrap import provision
 h,sessions,ids,app=env;c=login(h).json()['csrf_token'];data=book_data('row')
 with sessions() as db:
  counsel=provision(db,'counsel','firm',['antitrust_counsel'],PASSWORD);db.flush();db.add(m.MatterAssignment(account_id=counsel.id,matter_id=ids['matter'],expires_at=clock()+3600))
  for uid in [ids['lawyer'],ids['sme'],counsel.id]:db.add(m.CleanTeamMembership(account_id=uid,matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600))
  db.commit()
 if legacy:
  with monkeypatch.context() as old:old.setattr(workflow,'extract',lambda name,raw:historical(raw));r=upload(h,c,ids,data,'clean_team')
 else:r=upload(h,c,ids,data,'clean_team')
 assert r.status_code==201,r.text;src=r.json();confirm_review(h,c,src)
 grant=post(h,'/api/v1/source-access',c,{'source_id':src['id'],'username':'client','outside_business':True,'expires_in_days':7,'rationale':'Explicit fictional named outside-business original source access'});assert grant.status_code==201,grant.text
 token=login(h,'counsel').json()['csrf_token'];r=post(h,'/api/v1/source-access/'+grant.json()['id']+'/approve',token,{'rationale':'Independent counsel reviews exact original and named recipient'});assert r.status_code==200,r.text
 with TestClient(app,base_url='https://client.localhost') as client:
  login(client,'client',origin='https://client.localhost')
  for suffix in ['/reader','/download']:
   response=client.get(BASE+'/documents/'+src['id']+suffix);assert response.status_code==(403 if legacy else 200),response.text
   if legacy:assert ROW_SECRET not in response.text and 'content-disposition' not in response.headers
 with sessions() as db:
  source=db.get(m.SourceVersion,src['id']);assert source.data==data and (source.extractor_version=='literal-workbook-xml-2')==legacy
  assert db.get(m.SourceAccessGrant,grant.json()['id']).state=='approved'

@pytest.mark.parametrize('legacy_sensitive',[True,False])
def test_paid_semantic_service_checks_workbook_processing_before_provider_send(legacy_sensitive,env,monkeypatch):
 from test_document_workflow import allow_processing
 from kestrel.services import workflow
 from kestrel.adapters import embeddings
 from kestrel.repositories.identity import principal
 from kestrel.services.auth import clock
 h,sessions,ids,_=env;allow_processing(h,sessions,ids,cloud_block=False);c=login(h).json()['csrf_token'];data=book_data('row' if legacy_sensitive else 'plain')
 if legacy_sensitive:
  with monkeypatch.context() as old:old.setattr(workflow,'extract',lambda name,raw:historical(raw));r=upload(h,c,ids,data)
 else:r=upload(h,c,ids,data)
 assert r.status_code==201,r.text;src=r.json();confirm_review(h,c,src)
 # Inspection/triage stays available; this is a processing containment decision.
 assert h.get(BASE+'/documents/'+src['id']+'/reader').status_code==200
 monkeypatch.setattr(embeddings,'configuration',lambda:(True,'synthetic-test-key'));calls=[]
 def send(texts):calls.append(texts);return [[1.0]+[0.0]*255 for _ in texts],100
 monkeypatch.setattr(embeddings,'send',send)
 response=post(h,'/api/v1/questions',c,{'matter_id':ids['matter'],'question':'Which Vireo revenue evidence is available?','mode':'semantic','request_key':uuid.uuid4().hex})
 if legacy_sensitive:
  assert response.status_code==409,f'Expected protective processing refusal; status={response.status_code}, provider_calls={len(calls)}'
  assert not calls and ROW_SECRET not in response.text and 'citations' not in response.text
 else:
  assert response.status_code==201,response.text;assert len(calls)==1 and response.json()['retrieval']['route']=='semantic_embeddings'
 with sessions() as db:
  source=db.get(m.SourceVersion,src['id']);policy=db.get(m.DocumentPolicyVersion,source.policy_id);actor=principal(db,db.get(m.Account,ids['lawyer']),clock())
  assert source.data==data and policy.classification=='ordinary'
  workflow.require_policy(db,actor,policy,'read');workflow.require_policy(db,actor,policy,'triage')
  if legacy_sensitive:
   with pytest.raises(HTTPException):workflow.require_policy(db,actor,policy,'analyze')
   with pytest.raises(HTTPException):workflow.processing_allowed(db,policy,external=True)
  else:workflow.require_policy(db,actor,policy,'analyze');workflow.processing_allowed(db,policy,external=True)
