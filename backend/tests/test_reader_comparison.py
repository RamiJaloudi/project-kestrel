from test_auth_policy import env,login
from test_document_workflow import upload
from test_observability_governance import post

def test_comparison_candidates_paginate_only_permitted_sources_and_keep_exact_anchors(env):
 h,_,ids,_=env;c=login(h).json()['csrf_token']
 a=upload(h,c,ids['matter'],logical_key='COMPARE-001').json();b=upload(h,c,ids['matter'],logical_key='COMPARE-002').json()
 path='/api/v1/readers/candidates?matter_id='+ids['matter']+'&kind=source&limit=1'
 r=h.get(path);assert r.status_code==200,r.text;assert len(r.json()['rows'])==1 and r.json()['has_more']
 next_page=h.get(path+'&after='+r.json()['next_after']);assert next_page.status_code==200 and not next_page.json()['has_more']
 assert r.json()['rows'][0]['id']!=next_page.json()['rows'][0]['id']
 result=post(h,'/api/v1/readers/compare',c,{'matter_id':ids['matter'],'targets':[{'kind':'source','id':a['id']},{'kind':'source','id':b['id']}]})
 assert result.status_code==200,result.text;assert all(p['allowed'] for p in result.json()['panes'])
 for p in result.json()['panes']:
  assert p['citation_anchors'][0]['document_version_id']==p['target']['id'] and p['citation_anchors'][0]['bounding_box'] is None
 assert post(h,'/api/v1/readers/compare',c,{'matter_id':ids['matter'],'targets':[{'kind':'source','id':a['id']}]*5}).status_code==422
 assert h.get(path+'&after=not-an-authorized-version').status_code==404

def test_bank_can_compare_released_derivative_without_obtaining_its_original(env):
 from test_disclosures import prepared,D
 from fastapi.testclient import TestClient
 h,_,ids,app=env;src,p,a,c=prepared(env)
 token=login(h,'sme').json()['csrf_token'];assert post(h,D+'/artifacts/'+a['id']+'/decisions',token,{'operation':'legal_approve','bundle_hash':a['bundle_hash'],'rationale':'Release exact sanitized transcript for independent comparison test'}).status_code==200
 with TestClient(app,base_url='https://bank.localhost') as bank:
  b=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
  assert bank.get('/api/v1/readers/candidates',params={'matter_id':ids['matter'],'kind':'source'}).json()['rows']==[]
  r=bank.get('/api/v1/readers/candidates',params={'matter_id':ids['matter'],'kind':'derivative'});assert r.status_code==200,r.text
  assert len(r.json()['rows'])==1 and src['id'] not in r.text
  r=bank.post('/api/v1/readers/compare',json={'matter_id':ids['matter'],'targets':[{'kind':'source','id':src['id']},{'kind':'derivative','id':a['id']}]},headers={'origin':'https://bank.localhost','x-csrf-token':b})
  assert r.status_code==200,r.text;panes=r.json()['panes'];assert not panes[0]['allowed'] and panes[1]['allowed']
  assert src['id'] not in r.text and panes[1]['citation_anchors'][0]['artifact_id']==a['id']
  assert panes[1]['citation_anchors'][0]['document_version_id'] is None
  assert bank.get('/api/v1/workflow/documents/'+src['id']+'/reader').status_code==403

def test_revoking_one_pane_does_not_grant_or_hide_the_other_and_walls_override_all(env):
 from kestrel.models import CleanTeamMembership,EthicalWall
 from kestrel.services.auth import clock
 from sqlalchemy import select
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];a=upload(h,c,ids['matter'],logical_key='COMPARE-ORDINARY').json()
 with sessions() as db:db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
 b=upload(h,c,ids['matter'],logical_key='COMPARE-PRICING',classification='clean_team',clean_team_scope='pricing').json()
 with sessions() as db:db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;db.commit()
 p={'matter_id':ids['matter'],'targets':[{'kind':'source','id':a['id'],'unit':1,'start':0,'end':9},{'kind':'source','id':b['id']}]}
 r=post(h,'/api/v1/readers/compare',c,p);assert r.status_code==200,r.text
 assert r.json()['panes'][0]['target']['end']==9 and not r.json()['panes'][1]['allowed'] and b['id'] not in r.text
 with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 assert post(h,'/api/v1/readers/compare',c,p).status_code==403
 root=login(h,'root').json()['csrf_token'];assert post(h,'/api/v1/readers/compare',root,p).status_code==403
