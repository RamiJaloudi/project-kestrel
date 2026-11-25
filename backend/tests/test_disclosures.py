import io,json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login,PASSWORD
from test_document_workflow import upload,BASE,TEXT
from test_observability_governance import post
from kestrel.services.auth import clock
D='/api/v1/disclosures'


def prepared(env,clean=False):
 http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
 if clean:
  from kestrel.models import CleanTeamMembership,MatterAssignment
  from kestrel.bootstrap import provision
  with sessions() as db:
   antitrust=provision(db,'antitrust','firm',['antitrust_counsel'],PASSWORD);db.flush();ids['antitrust']=antitrust.id
   db.add(MatterAssignment(account_id=antitrust.id,matter_id=ids['matter'],expires_at=clock()+3600))
   for uid in [ids['lawyer'],ids['sme'],antitrust.id]:db.add(CleanTeamMembership(account_id=uid,matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600))
   db.commit()
 src=upload(http,csrf,ids['matter'],classification='clean_team' if clean else 'ordinary',clean_team_scope='pricing' if clean else '').json()
 assert post(http,BASE+'/documents/'+src['id']+'/confirm',csrf,{'snapshot_hash':src['snapshot_hash'],'rationale':'Human confirmed exact synthetic source'}).status_code==200
 assert post(http,'/api/v1/diligence/documents/'+src['id']+'/reviews',csrf,{'expected_revision':0,'title':'Synthetic source review','counterparty':'Synthetic party','scope':'financial','coverage_state':'complete','rationale':'Reviewed all original passages before sanitization'}).status_code==201
 start=TEXT.index('prior written consent');end=start+len('prior written consent')
 p={'source_id':src['id'],'audience':'castlegate','title':'Sanitized contractual extract','purpose':'Synthetic commercial diligence','expires_in_days':7,'request_key':'disclosure-plan-001','spans':[{'unit':1,'start':start,'end':end}],'rationale':'Remove specified confidential wording from the disclosure transcript'}
 r=post(http,D+'/plans',csrf,p);assert r.status_code==201,r.text;plan=r.json()
 assert post(http,D+'/plans/'+plan['id']+'/review',csrf,{'operation':'approve','content_hash':plan['content_hash'],'rationale':'Cannot self approve redaction plan'}).status_code==403
 token=login(http,'sme').json()['csrf_token'];r=post(http,D+'/plans/'+plan['id']+'/review',token,{'operation':'approve','content_hash':plan['content_hash'],'rationale':'Independently checked all removal ranges against the original'});assert r.status_code==200,r.text
 csrf=login(http).json()['csrf_token'];r=post(http,D+'/plans/'+plan['id']+'/build',csrf,{});assert r.status_code==201,r.text
 return src,plan,r.json(),csrf


def test_sanitized_bytes_review_gate_original_denial_and_audience_isolation(env):
 http,sessions,ids,app=env;src,plan,artifact,csrf=prepared(env)
 assert post(http,D+'/artifacts/'+artifact['id']+'/decisions',csrf,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Cannot approve my own generated disclosure'}).status_code==403
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');assert bank.get(D+'/artifacts/'+artifact['id']+'/reader').status_code==403
  token=login(http,'sme').json()['csrf_token'];r=post(http,D+'/artifacts/'+artifact['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Senior lawyer approves exact validated audience transcript'});assert r.status_code==200,r.text
  v=bank.get(D+'/artifacts/'+artifact['id']+'/reader');assert v.status_code==200,v.text
  assert 'prior written consent' not in v.text and src['id'] not in v.text and 'source_snapshot' not in v.text
  assert bank.get(BASE+'/documents/'+src['id']+'/reader').status_code==403
  data=bank.get(D+'/artifacts/'+artifact['id']+'/download').content
  from pypdf import PdfReader
  pdf=PdfReader(io.BytesIO(data));extracted=''.join(p.extract_text() for p in pdf.pages)
  assert 'prior written consent' not in extracted and 'Synthetic contract' in extracted
  assert '/Names' not in pdf.trailer['/Root'] and not pdf.get_fields() and all(not p.get('/Annots') for p in pdf.pages)
 with TestClient(app,base_url='https://client.localhost') as client:
  login(client,'client',origin='https://client.localhost');assert client.get(D+'/artifacts/'+artifact['id']+'/reader').status_code==403
 with sessions() as db:
  from kestrel.models import SourceVersion
  assert db.get(SourceVersion,src['id']).data==TEXT.encode()
  with pytest.raises(DBAPIError):db.execute(text('DELETE FROM disclosure_artifacts'));db.commit()


def test_clean_team_needs_separate_independent_antitrust_and_current_authority(env):
 http,sessions,ids,app=env;src,plan,a,csrf=prepared(env,True)
 token=login(http,'sme').json()['csrf_token'];assert post(http,D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':a['bundle_hash'],'rationale':'Senior review of clean-team sanitization'}).status_code==200
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');assert bank.get(D+'/artifacts/'+a['id']+'/reader').status_code==403
  token=login(http,'antitrust').json()['csrf_token'];r=post(http,D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'antitrust_approve','bundle_hash':a['bundle_hash'],'rationale':'Independent counsel approves declassification of exact output'});assert r.status_code==200,r.text
  assert bank.get(D+'/artifacts/'+a['id']+'/reader').status_code==200
  from kestrel.models import EthicalWall
  with sessions() as db:db.add(EthicalWall(account_id=ids['antitrust'],matter_id=ids['matter'],active=True));db.commit()
  assert bank.get(D+'/artifacts/'+a['id']+'/reader').status_code==403


def test_reclassification_and_revocation_remove_external_retrieval(env):
 http,sessions,ids,app=env;src,plan,a,csrf=prepared(env)
 token=login(http,'sme').json()['csrf_token'];assert post(http,D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':a['bundle_hash'],'rationale':'Independent audience disclosure approval'}).status_code==200
 with TestClient(app,base_url='https://bank.localhost') as bank:
  token_bank=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  q=bank.post('/api/v1/questions',json={'matter_id':ids['matter'],'question':'What happens on a change of control?'},headers={'origin':'https://bank.localhost','x-csrf-token':token_bank});assert q.status_code==201,q.text
  assert any(c['kind']=='derivative' for c in q.json()['citations'])
  assert all('prior written consent' not in c['text'] and c['object_id']==a['id'] for c in q.json()['citations'])
  csrf=login(http).json()['csrf_token'];assert post(http,'/api/v1/content-labels/sources/'+src['id'],csrf,{'expected_revision':0,'request_key':'reclassify-output-001','labels':['financial'],'rationale':'New content assertion requires new derivative approval'}).status_code==201
  assert bank.get(D+'/artifacts/'+a['id']+'/reader').status_code==403
  assert bank.get(D+'?matter_id='+ids['matter']).json()==[]
  from kestrel.models import ContentImpactTask
  with sessions() as db:assert db.scalar(select(ContentImpactTask)) is not None
  assert bank.get('/api/v1/questions/'+q.json()['id']).status_code==403


def test_native_containers_are_not_reused_hidden_sheets_and_repeated_tokens_fail_closed():
 from types import SimpleNamespace
 from openpyxl import Workbook
 from kestrel.adapters.extraction import extract,canonical
 from kestrel.adapters import disclosure as d
 from fastapi import HTTPException
 book=Workbook();book.active.title='Public';book.active['A1']='Public commercial information'
 hidden=book.create_sheet('Hidden');hidden.sheet_state='veryHidden';hidden['A1']='HIDDEN_SECRET_913'
 from openpyxl.comments import Comment
 book.active['A1'].comment=Comment('COMMENT_SECRET_926','Private author')
 payload=io.BytesIO();book.save(payload);data=payload.getvalue();parsed=extract('synthetic.xlsx',data)
 row=SimpleNamespace(file_name='synthetic.xlsx',data=data,units_json=canonical(parsed['units']))
 units,manifest,removed=d.sanitize(row,[{'unit':1,'start':0,'end':6}])
 assert len(units)==1 and 'HIDDEN_SECRET_913' not in canonical(units)
 binary=d.render('Sanitized synthetic workbook',units);report=d.validate(binary,'Sanitized synthetic workbook',units,removed)
 assert report['passed'] and not binary.startswith(b'PK')
 from pypdf import PdfReader
 text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(binary)).pages)
 assert 'COMMENT_SECRET_926' not in text and 'HIDDEN_SECRET_913' not in text and 'Private author' not in text
 duplicate=SimpleNamespace(file_name='synthetic.txt',data=b'',units_json=canonical([{'number':1,'locator':'Original location','text':'SECRET_TOKEN_123 public SECRET_TOKEN_123'}]))
 units,_,removed=d.sanitize(duplicate,[{'unit':1,'start':0,'end':16}])
 with pytest.raises(HTTPException) as e:d.validate(d.render('Safe transcript',units),'Safe transcript',units,removed)
 assert e.value.status_code==422


def test_plan_staleness_coverage_expiry_and_revocation_after_signing(env,monkeypatch):
 from kestrel.services import disclosures as d
 from test_lifecycle import propose,approve
 http,sessions,ids,app=env;src,p,a,csrf=prepared(env)
 # A root administrator cannot read or approve any source-bound derivative.
 root=login(http,'root').json()['csrf_token'];assert http.get(D+'/artifacts/'+a['id']).status_code==403
 assert post(http,D+'/artifacts/'+a['id']+'/decisions',root,{'operation':'legal_approve','bundle_hash':a['bundle_hash'],'rationale':'Root must never override source-content controls'}).status_code==403
 token=login(http,'sme').json()['csrf_token'];assert post(http,D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':a['bundle_hash'],'rationale':'Independent exact transcript release approval'}).status_code==200
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');assert bank.get(D+'/artifacts/'+a['id']+'/reader').status_code==200
  # Expiry is checked by the canonical policy using current time.
  from kestrel.services.policy import evaluate
  from kestrel.repositories.identity import principal
  from kestrel.models import Account,DisclosureArtifact,DocumentPolicyVersion
  with sessions() as db:
   actor=principal(db,db.get(Account,ids['bank']),clock());policy=db.get(DocumentPolicyVersion,db.get(DisclosureArtifact,a['id']).policy_id)
   assert not evaluate(db,actor,policy,'read',clock()+31*86400)['allowed']
  login(http);signing=propose(http,ids,'sign');assert approve(http,signing).status_code==200
  token=login(http,'sme').json()['csrf_token'];r=post(http,D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'revoke','bundle_hash':a['bundle_hash'],'rationale':'Revoke future disclosure after signing without changing the signed record'});assert r.status_code==200,r.text
  assert bank.get(D+'/artifacts/'+a['id']+'/reader').status_code==403
