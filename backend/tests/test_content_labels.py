import json
import pytest
from sqlalchemy import text,select
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_document_workflow import upload,candidate,BASE
from test_observability_governance import post
from kestrel.models import CleanTeamMembership,EthicalWall,Role,RoleGrant
from kestrel.services.auth import clock
B='/api/v1/content-labels'


def proposal(http,csrf,s,**extra):
 return post(http,B+'/sources/'+s['id'],csrf,{'expected_revision':0,'request_key':'segment-proposal-001','labels':['legal','financial'],'unit_number':1,'start':0,'end':18,'rationale':'Synthetic evidence classification only',**extra})


def test_provenance_exact_ranges_independent_confirmation_and_immutability(env):
 http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
 assert proposal(http,csrf,s,end=9999).status_code==422
 assert proposal(http,csrf,s,labels=['mystery']).status_code==422
 r=proposal(http,csrf,s);assert r.status_code==201,r.text;a=r.json();assert a['state']=='PROPOSED' and a['quote']=='Synthetic contract'
 assert post(http,B+'/assertions/'+a['id']+'/confirm',csrf,{'expected_revision':1,'rationale':'Cannot confirm my own attribute assertion'}).status_code==403
 csrf=login(http,'sme').json()['csrf_token'];r=post(http,B+'/assertions/'+a['id']+'/confirm',csrf,{'expected_revision':1,'rationale':'Independent source classification confirmation'});assert r.status_code==200,r.text
 assert r.json()['state']=='CONFIRMED'
 with sessions() as db:
  for table in ['content_label_assertions','content_label_decisions']:
   with pytest.raises(DBAPIError):db.execute(text('DELETE FROM '+table));db.commit()
   db.rollback()
 login(http,'root');assert http.get(B+'/sources/'+s['id']).status_code==403


def test_provisional_sensitive_labels_restrict_reader_and_analysis_and_cannot_relax(env):
 http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
 r=proposal(http,csrf,s,labels=['ai_restricted','personal_data']);assert r.status_code==201,r.text
 from kestrel.services.policy import evaluate
 from kestrel.repositories.identity import principal
 from kestrel.models import Account,DocumentPolicyVersion
 with sessions() as db:
  result=evaluate(db,principal(db,db.get(Account,ids['lawyer']),clock()),db.get(DocumentPolicyVersion,s['policy_id']) if 'policy_id' in s else db.scalar(select(DocumentPolicyVersion).where(DocumentPolicyVersion.document_id==s['logical_key'])),'analyze',clock())
  assert not result['allowed'] and result['reason_code']=='CONTENT_AI_RESTRICTED'
 a=r.json();assert post(http,B+'/assertions/'+a['id']+'/contest',csrf,{'expected_revision':1,'rationale':'Disputed label remains protective pending a governed relaxation'}).json()['state']=='CONTESTED'
 assert post(http,B+'/assertions/'+a['id']+'/remove',csrf,{'expected_revision':2,'rationale':'Removal cannot bypass controlled approval'}).status_code==422
 assert http.get(BASE+'/documents/'+s['id']+'/reader').status_code==200


def test_clean_team_labels_enforce_whole_original_and_wall_precedence(env):
 http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
 assert proposal(http,csrf,s,labels=['competitively_sensitive'],clean_team_scope='pricing').status_code==403
 with sessions() as db:
  db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
 r=proposal(http,csrf,s,labels=['competitively_sensitive'],clean_team_scope='pricing');assert r.status_code==201,r.text
 assert http.get(BASE+'/documents/'+s['id']+'/reader').status_code==200
 with sessions() as db:
  from kestrel.models import AuditEvent
  assert db.scalar(select(AuditEvent).where(AuditEvent.object_id==s['id'],AuditEvent.action=='source.reader',AuditEvent.category=='clean_team',AuditEvent.clean_team_scope=='pricing'))
 login(http,'sme');assert http.get(BASE+'/documents/'+s['id']+'/reader').status_code==403
 assert s['id'] not in {r['id'] for r in http.get(BASE+'/documents?matter_id='+ids['matter']).json()}
 login(http)
 with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 assert http.get(B+'/sources/'+s['id']).status_code==403


def test_attribute_changes_revoke_released_lineage_and_create_counsel_impacts(env):
 http,sessions,ids,app=env;s,f,csrf=candidate(env)
 release=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Synthetic cited note','summary':'Consent requires further transaction-specific investigation.','references':[{'finding_id':f['id'],'public_reference':'Contract A, consent clause'}]}).json()
 csrf=login(http,'sme').json()['csrf_token'];approved=post(http,BASE+'/releases/'+release['id']+'/approve',csrf,{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Approve exact cited synthetic package'});assert approved.status_code==200,approved.text
 csrf=login(http).json()['csrf_token'];assert proposal(http,csrf,s,labels=['financial']).status_code==201
 with sessions() as db:
  from kestrel.models import ContentLabelImpact,ReleasePackage
  assert db.scalar(select(ContentLabelImpact).where(ContentLabelImpact.policy_id==db.get(ReleasePackage,release['id']).policy_id))
 from fastapi.testclient import TestClient
 with TestClient(app,base_url='https://client.localhost') as client:
  login(client,'client',origin='https://client.localhost')
  rows=client.get(BASE+'/releases?matter_id='+ids['matter']).json();assert not rows


def test_freeze_and_unknown_attribute_state_fail_closed(env,monkeypatch):
 from test_lifecycle import propose,approve
 from kestrel.services import content_labels as labels
 from kestrel.services.policy import evaluate
 from kestrel.repositories.identity import principal
 from kestrel.models import Account,SourceVersion,DocumentPolicyVersion
 http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
 a=proposal(http,csrf,s,labels=['bank_eligible']).json()
 assert proposal(http,csrf,s,labels=['bank_eligible']).json()['id']==a['id']
 with sessions() as db:
  actor=principal(db,db.get(Account,ids['lawyer']),clock());policy=db.get(DocumentPolicyVersion,db.get(SourceVersion,s['id']).policy_id)
  def corrupt(*args):raise ValueError('Unknown attribute state')
  with monkeypatch.context() as patch:
   patch.setattr(labels,'policy_records',corrupt);decision=evaluate(db,actor,policy,'read',clock());assert not decision['allowed'] and decision['reason_code']=='CONTENT_ATTRIBUTES_INDETERMINATE'
 signing=propose(http,ids,'sign');assert approve(http,signing).status_code==200
 csrf=login(http).json()['csrf_token']
 assert proposal(http,csrf,s,expected_revision=1,request_key='frozen-label-002',labels=['financial']).status_code==409
 assert post(http,B+'/assertions/'+a['id']+'/contest',csrf,{'expected_revision':1,'rationale':'Frozen content cannot be changed'}).status_code==409


def test_counsel_routing_is_scoped_idempotent_and_excludes_admin(env):
    http,sessions,ids,_=env;s,f,csrf=candidate(env)
    release=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Routing test disclosure','summary':'Synthetic counsel follow-up routing fixture.','references':[{'finding_id':f['id'],'public_reference':'Synthetic evidence only'}]}).json()
    token=login(http,'sme').json()['csrf_token'];assert post(http,BASE+'/releases/'+release['id']+'/approve',token,{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Independent fixture approval before classification change'}).status_code==200
    csrf=login(http).json()['csrf_token'];assert proposal(http,csrf,s,labels=['financial']).status_code==201
    impacts=http.get(B+'/impacts?matter_id='+ids['matter']).json();assert impacts and not impacts[0]['task_id'];impact=impacts[0]['id']
    people=http.get(B+'/impacts/'+impact+'/eligible-counsel');assert people.status_code==200
    assert ids['sme'] in {p['id'] for p in people.json()} and ids['root'] not in {p['id'] for p in people.json()}
    route=post(http,B+'/impacts/'+impact+'/assign',csrf,{'assignee_id':ids['sme']});assert route.status_code==201,route.text
    assert post(http,B+'/impacts/'+impact+'/assign',csrf,{'assignee_id':ids['sme']}).json()['task_id']==route.json()['task_id']
    login(http,'root');assert http.get(B+'/impacts/'+impact+'/eligible-counsel').status_code==403
