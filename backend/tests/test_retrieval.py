import pytest
from test_auth_policy import env,login
from test_document_workflow import upload,BASE
from test_observability_governance import post


def test_bm25_exact_symbols_numbers_and_deterministic_ranking():
 from kestrel.adapters.retrieval import bm25,cosine,rrf
 docs=['ISIN GB0001234567 revenue EUR 125000 FY2025','ISIN GB0001234567 revenue EUR 125 FY2024','Unrelated assignment clause']
 ranked=bm25('gb0001234567 125000',docs)
 assert ranked[0][0]==0 and ranked[0][1]>0 and 2 not in [i for i,_ in ranked]
 assert bm25('gb0001234567 125000',docs)==ranked
 assert cosine([1,0],[1,0])==1 and cosine([1,0],[0,1])==0
 with pytest.raises(ValueError):cosine([float('nan')],[1])
 assert rrf([[0,1],[1,0]])[0][0]==0


def test_lexical_mode_preserves_citations_and_records_route(env):
 http,_,ids,_=env;csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
 assert post(http,BASE+'/documents/'+s['id']+'/confirm',csrf,{'snapshot_hash':s['snapshot_hash'],'rationale':'Confirmed exact source for retrieval tests'}).status_code==200
 r=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which contracts have change of control consent?','mode':'lexical'});assert r.status_code==201,r.text
 assert r.json()['retrieval']['route']=='lexical_bm25' and r.json()['citations']
 assert r.json()['citations'][0]['reader']['id']==s['id']
 assert all(c['score']>0 for c in r.json()['citations'])


def test_retrieval_scores_and_counts_never_include_denied_clean_team(env):
 from sqlalchemy import select
 from kestrel.models import CleanTeamMembership
 from kestrel.services.auth import clock
 http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
 ordinary=upload(http,csrf,ids['matter']).json()
 assert post(http,BASE+'/documents/'+ordinary['id']+'/confirm',csrf,{'snapshot_hash':ordinary['snapshot_hash'],'rationale':'Confirmed ordinary retrieval source'}).status_code==200
 with sessions() as db:db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
 secret=upload(http,csrf,ids['matter'],logical_key='RESTRICTED-002',classification='clean_team',clean_team_scope='pricing').json()
 assert post(http,BASE+'/documents/'+secret['id']+'/confirm',csrf,{'snapshot_hash':secret['snapshot_hash'],'rationale':'Confirmed named clean-team source'}).status_code==200
 with sessions() as db:
  member=db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer']));member.revoked=True;db.commit()
 r=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'What requires change of control consent?','mode':'automatic'});assert r.status_code==201,r.text
 assert len(r.json()['citations'])==1 and r.json()['citations'][0]['object_id']==ordinary['id']
 assert r.json()['retrieval']['authorized_chunks']==1


def test_semantic_uses_shared_budget_exact_source_cache_and_idempotency(env,monkeypatch):
 from test_document_workflow import candidate
 from kestrel.adapters import embeddings as e
 from kestrel.models import SourceEmbedding,OperationReservation
 from sqlalchemy import select,func
 http,sessions,ids,_=env;src,f,csrf=candidate(env,cloud_block=False);calls=[]
 monkeypatch.setattr(e,'configuration',lambda:(True,'synthetic-test-key'))
 def send(texts):calls.append(texts);return [[1.0]+[0.0]*255 for _ in texts],100
 monkeypatch.setattr(e,'send',send)
 p={'matter_id':ids['matter'],'question':'Which agreement needs consent?','mode':'semantic','request_key':'semantic-test-001'}
 r=post(http,'/api/v1/questions',csrf,p);assert r.status_code==201,r.text
 assert r.json()['retrieval']['route']=='semantic_embeddings' and r.json()['citations'][0]['object_id']==src['id'] and '_scope_refs' not in r.json()
 assert post(http,'/api/v1/questions',csrf,p).json()['id']==r.json()['id'] and len(calls)==1
 p['request_key']='semantic-test-002';r=post(http,'/api/v1/questions',csrf,p);assert r.status_code==201,r.text
 assert len(calls[-1])==1 and r.json()['retrieval']['cache_hits']>=1
 with sessions() as db:
  assert db.scalar(select(func.count()).select_from(SourceEmbedding))>=1
  assert all(row.charged_cents==1 for row in db.scalars(select(OperationReservation)))


def test_semantic_processing_denial_never_calls_provider(env,monkeypatch):
 from test_document_workflow import candidate
 from kestrel.adapters import embeddings as e
 http,_,ids,_=env;_,_,csrf=candidate(env,cloud_block=True)
 monkeypatch.setattr(e,'configuration',lambda:(True,'synthetic-test-key'))
 def denied(*args):raise AssertionError('Provider must not be called')
 monkeypatch.setattr(e,'send',denied)
 r=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which agreement needs consent?','mode':'semantic','request_key':'semantic-blocked-001'})
 assert r.status_code==409,r.text


def test_semantic_rechecks_wall_after_provider_and_saves_no_index(env,monkeypatch):
 from test_document_workflow import candidate
 from kestrel.adapters import embeddings as e
 from kestrel.models import EthicalWall,SourceEmbedding
 from sqlalchemy import select,func
 http,sessions,ids,_=env;_,_,csrf=candidate(env,cloud_block=False)
 monkeypatch.setattr(e,'configuration',lambda:(True,'synthetic-test-key'))
 def changed(texts):
  with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
  return [[1.0]+[0.0]*255 for _ in texts],100
 monkeypatch.setattr(e,'send',changed)
 r=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which agreement needs consent?','mode':'hybrid','request_key':'semantic-wall-001'});assert r.status_code==403,r.text
 with sessions() as db:assert db.scalar(select(func.count()).select_from(SourceEmbedding))==0


def test_saved_scope_counts_reauthorize_non_cited_sources(env):
 http,_,ids,_=env;csrf=login(http).json()['csrf_token'];sources=[]
 for key in ['CONTRACT-011','CONTRACT-012']:
  s=upload(http,csrf,ids['matter'],logical_key=key).json();sources.append(s)
  assert post(http,BASE+'/documents/'+s['id']+'/confirm',csrf,{'snapshot_hash':s['snapshot_hash'],'rationale':'Confirm scoped retrieval source'}).status_code==200
 answer=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Change of control consent?','mode':'lexical','top_k':1}).json()
 assert answer['retrieval']['authorized_chunks']==2 and '_scope_refs' not in answer
 other=next(s for s in sources if s['id']!=answer['citations'][0]['object_id'])
 assert post(http,'/api/v1/content-labels/sources/'+other['id'],csrf,{'expected_revision':0,'request_key':'scope-count-change-001','labels':['financial'],'rationale':'Changed non-cited corpus attributes must invalidate stored ranking counts'}).status_code==201
 assert http.get('/api/v1/questions/'+answer['id']).status_code==403
