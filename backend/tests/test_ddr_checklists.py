import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_observability_governance import post
from test_document_workflow import upload,BASE

C='/api/v1/checklists'
ITEM='KESTREL-G-CONTRACTS-001'

def create(env,user='root',**changes):
    http,_,ids,_=env;csrf=login(http,user).json()['csrf_token']
    result=post(http,C,csrf,{'matter_id':ids['matter'],**changes})
    assert result.status_code==201,result.text
    return result.json(),csrf

def publish(env):
    http,_,_,_=env;row,csrf=create(env)
    body={'expected_revision':0,'content_hash':row['content_hash'],'rationale':'Submit original synthetic request scope for independent review'}
    assert post(http,C+'/'+row['id']+'/submit',csrf,body).status_code==200
    csrf=login(http,'sme').json()['csrf_token'];body['expected_revision']=1
    result=post(http,C+'/'+row['id']+'/approve',csrf,body);assert result.status_code==200,result.text
    csrf=login(http,'root').json()['csrf_token'];body['expected_revision']=2
    result=post(http,C+'/'+row['id']+'/publish',csrf,body);assert result.status_code==200,result.text
    return result.json()

def change(http,row,csrf,status,**extra):
    return post(http,C+'/'+row['id']+'/coverage/'+ITEM,csrf,{'expected_revision':0,'status':status,'rationale':'Synthetic inventory checked within this authorized scope',**extra})

def test_checklist_auth_template_and_source_provenance(env):
    http,_,ids,_=env
    assert http.get(C,params={'matter_id':ids['matter']}).status_code==401
    row,_=create(env)
    assert row['state']=='draft' and row['revision']==0
    assert [s['section_code'] for s in row['definition']['sections']]==list('ABCDEFGHIJKLMN')
    assert row['definition']['source']['pages']==21
    assert len(row['definition']['source']['sha256'])==64
    item=row['definition']['items'][0]
    assert item['item_id']==ITEM and item['section_code']=='G' and item['source_page']==10
    assert item['source_item_number'] is None and item['applicability']=='requires_legal_sme_review'
    assert item['authorship']=='original_kestrel_request_abstraction'

def test_legal_approval_independent_and_exact(env):
    http,_,_,_=env;row,csrf=create(env,'sme')
    body={'expected_revision':0,'content_hash':row['content_hash'],'rationale':'Submit for independent substantive legal review'}
    assert post(http,C+'/'+row['id']+'/submit',csrf,body).status_code==200
    body['expected_revision']=1
    assert post(http,C+'/'+row['id']+'/approve',csrf,body).status_code==403
    root=login(http,'root').json()['csrf_token']
    assert post(http,C+'/'+row['id']+'/approve',root,body).status_code==403
    assert post(http,C+'/'+row['id']+'/publish',root,body).status_code==409
    assert post(http,C+'/'+row['id']+'/submit',root,{**body,'content_hash':'0'*64}).status_code==409

def test_published_gap_not_legal_risk_or_automatic_na(env):
    http,_,ids,_=env;row=publish(env);csrf=login(http,'lawyer').json()['csrf_token']
    coverage=http.get(C+'/'+row['id']+'/coverage').json()
    assert coverage['items'][0]['status']=='GAP' and coverage['items'][0]['revision']==0
    assert 'not a legal finding' in coverage['scope_notice']
    assert change(http,row,csrf,'N_A_APPROVED_BY_HUMAN').status_code==422
    assert change(http,row,csrf,'RECEIVED').status_code==422
    assert change(http,row,csrf,'REQUESTED').status_code==201
    assert change(http,row,csrf,'GAP').status_code==409
    assert post(http,C+'/'+row['id']+'/coverage/'+ITEM,csrf,{'expected_revision':1,'status':'GAP','rationale':'No responsive evidence is linked in this permitted scope'}).status_code==201

def test_na_is_separate_independent_human_decision(env):
    http,_,_,_=env;row=publish(env);csrf=login(http,'sme').json()['csrf_token']
    response=post(http,C+'/'+row['id']+'/coverage/'+ITEM+'/na-requests',csrf,{'expected_revision':0,'rationale':'Applicability requires a separate human assessment of transaction facts'})
    assert response.status_code==201,response.text
    pending=response.json();assert pending['status']=='GAP' and pending['pending_na_id']
    payload={'expected_revision':1,'rationale':'Independent applicability decision based on recorded facts'}
    path=C+'/'+row['id']+'/na-requests/'+pending['pending_na_id']+'/approve'
    assert post(http,path,csrf,payload).status_code==403
    assert post(http,path,login(http,'root').json()['csrf_token'],payload).status_code==403
    # A normal lawyer's request can be approved by an independent Legal SME.
    csrf=login(http,'lawyer').json()['csrf_token']
    request=post(http,C+'/'+row['id']+'/coverage/'+ITEM+'/na-requests',csrf,{'expected_revision':1,'rationale':'Revised request for independent SME applicability review'}).json()
    csrf=login(http,'sme').json()['csrf_token']
    path=C+'/'+row['id']+'/na-requests/'+request['pending_na_id']+'/approve'
    approved=post(http,path,csrf,{'expected_revision':2,'rationale':'Independent SME has reviewed the stated synthetic applicability facts'})
    assert approved.status_code==200,approved.text
    assert approved.json()['status']=='N_A_APPROVED_BY_HUMAN'

def test_evidence_confirmation_scope_and_immutability(env):
    http,sessions,ids,_=env;row=publish(env);csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter']).json()
    response=change(http,row,csrf,'RECEIVED',source_ids=[source['id']])
    assert response.status_code==201,response.text
    assert post(http,C+'/'+row['id']+'/coverage/'+ITEM,csrf,{'expected_revision':1,'status':'VERIFIED','source_ids':[source['id']],'rationale':'Cannot verify before whole-document review'}).status_code==409
    root=login(http,'root').json()['csrf_token'];assert http.get(C+'/'+row['id']+'/coverage').status_code==403
    with sessions() as db:
        for table,column,value in [('checklist_versions','definition_json','{}'),('checklist_version_decisions','rationale','altered'),('checklist_coverage_decisions','status','VERIFIED')]:
            with pytest.raises(DBAPIError):db.execute(text(f'UPDATE {table} SET {column}=:value'),{'value':value});db.commit()
            db.rollback()
    # No new published definition bypasses the unimplemented material-change impact gate.
    draft=post(http,C,root,{'matter_id':ids['matter'],'base_version_id':row['id']}).json()
    body={'expected_revision':0,'content_hash':draft['content_hash'],'rationale':'Proposed replacement requires governed impact handling'}
    assert post(http,C+'/'+draft['id']+'/submit',root,body).status_code==200
    sme=login(http,'sme').json()['csrf_token'];body['expected_revision']=1
    assert post(http,C+'/'+draft['id']+'/approve',sme,body).status_code==200
    body['expected_revision']=2
    assert post(http,C+'/'+draft['id']+'/publish',login(http,'root').json()['csrf_token'],body).status_code==409

def test_wall_external_and_wrong_matter_denials(env):
    from kestrel.models import EthicalWall
    http,sessions,ids,app=env;row=publish(env)
    assert http.get(C,params={'matter_id':ids['other']}).status_code==403
    with TestClient(app,base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get(C+'/'+row['id']).status_code==403
        assert client.get(C+'/'+row['id']+'/coverage').status_code==403
    with sessions() as db:db.add(EthicalWall(account_id=ids['root'],matter_id=ids['matter']));db.commit()
    assert http.get(C+'/'+row['id']).status_code==403

def test_draft_idempotency_and_identity_fields_cannot_be_forged(env):
    http,_,ids,_=env;row,csrf=create(env,request_key='checklist-request-01')
    repeat=post(http,C,csrf,{'matter_id':ids['matter'],'request_key':'checklist-request-01'})
    assert repeat.status_code==201 and repeat.json()['id']==row['id']
    assert post(http,C,csrf,{'matter_id':ids['matter'],'base_version_id':row['id'],'request_key':'checklist-request-01'}).status_code==409
    assert post(http,C,csrf,{'matter_id':ids['matter'],'actor_id':ids['sme']}).status_code==422
    assert post(http,C,csrf,{'matter_id':ids['matter'],'items':[{**row['definition']['items'][0],'source_page':1}]}).status_code==422


def test_clean_team_receipts_reauthorize_and_cannot_drop_source_restrictions(env):
    from kestrel.models import CleanTeamMembership
    from kestrel.services.auth import clock
    http,sessions,ids,_=env;row=publish(env)
    with sessions() as db:
        member=CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600)
        db.add(member);db.commit();member_id=member.id
    csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter'],classification='clean_team',clean_team_scope='pricing').json()
    response=change(http,row,csrf,'RECEIVED',source_ids=[source['id']]);assert response.status_code==201,response.text
    # A later ordinary status with no submitted IDs cannot strip the earlier source policy.
    response=post(http,C+'/'+row['id']+'/coverage/'+ITEM,csrf,{'expected_revision':1,'status':'NEEDS_CLARIFICATION','rationale':'Retain original restrictions while clarifying this inventory response'})
    assert response.status_code==201 and response.json()['source_ids']==[source['id']]
    from kestrel.models import Account
    from kestrel.repositories.identity import principal
    from kestrel.services.auditing import selected
    with sessions() as db:
        events=selected(db,principal(db,db.get(Account,ids['lawyer']),clock()),'clean_team',ids['matter'])
        assert any(e['object_id']==response.json()['id'] for e in events)
    from kestrel.models import DocumentPolicyVersion,SourceVersion
    with sessions() as db:
        # A later source relaxation must not automatically declassify retained coverage.
        db.get(DocumentPolicyVersion,db.get(SourceVersion,source['id']).policy_id).classification='ordinary'
        db.get(CleanTeamMembership,member_id).revoked=True;db.commit()
    response=http.get(C+'/'+row['id']+'/coverage')
    assert response.status_code==200 and response.json()['items']==[] and source['id'] not in response.text
    assert post(http,C+'/'+row['id']+'/coverage/'+ITEM,csrf,{'expected_revision':2,'status':'GAP','rationale':'Attempt to overwrite a restricted response after losing clearance'}).status_code==403


def test_verified_coverage_requires_whole_review_and_tracks_finding_revision(env):
    from test_document_workflow import candidate
    from test_diligence import assessment
    http,_,ids,_=env;row=publish(env);source,finding,csrf=candidate(env)
    assert change(http,row,csrf,'VERIFIED',source_ids=[source['id']],finding_ids=[finding['id']]).status_code==409
    profile={'expected_revision':0,'title':'Synthetic customer agreement review','counterparty':'Fictional customer','scope':'customer','coverage_state':'complete','rationale':'Read all original text and decided the source-bound candidates'}
    assert post(http,'/api/v1/diligence/documents/'+source['id']+'/reviews',csrf,profile).status_code==201
    verified=change(http,row,csrf,'VERIFIED',source_ids=[source['id']],finding_ids=[finding['id']])
    assert verified.status_code==201,verified.text
    assert verified.json()['status']=='VERIFIED'
    corrected=post(http,'/api/v1/diligence/findings/'+finding['id']+'/revisions',csrf,assessment(source))
    assert corrected.status_code==201,corrected.text
    coverage=http.get(C+'/'+row['id']+'/coverage').json()['items'][0]
    assert coverage['status']=='NEEDS_CLARIFICATION' and coverage['recorded_status']=='VERIFIED' and coverage['stale']


def test_withdrawn_reviewer_cannot_publish_and_no_draft_coverage(env):
    from kestrel.models import EthicalWall
    http,sessions,ids,_=env;row,root=create(env)
    assert http.get(C+'/'+row['id']+'/coverage').status_code==403
    payload={'expected_revision':0,'content_hash':row['content_hash'],'rationale':'Independent scope approval is required before use'}
    assert post(http,C+'/'+row['id']+'/submit',root,payload).status_code==200
    sme=login(http,'sme').json()['csrf_token']
    assert http.get(C+'/'+row['id']+'/coverage').status_code==409
    payload['expected_revision']=1
    assert post(http,C+'/'+row['id']+'/approve',sme,payload).status_code==200
    with sessions() as db:db.add(EthicalWall(account_id=ids['sme'],matter_id=ids['matter']));db.commit()
    payload['expected_revision']=2
    assert post(http,C+'/'+row['id']+'/publish',login(http,'root').json()['csrf_token'],payload).status_code==403


def test_signing_manifest_includes_checklist_decisions_and_blocks_later_changes(env):
    from test_lifecycle import propose,approve
    http,_,ids,_=env;row=publish(env)
    signing=propose(http,ids,'sign')
    csrf=login(http,'lawyer').json()['csrf_token']
    assert change(http,row,csrf,'REQUESTED').status_code==201
    assert approve(http,signing).status_code==409
    signing=propose(http,ids,'sign')
    assert approve(http,signing).status_code==200
    csrf=login(http,'lawyer').json()['csrf_token']
    assert post(http,C+'/'+row['id']+'/coverage/'+ITEM,csrf,{'expected_revision':1,'status':'GAP','rationale':'Cannot change the frozen checklist after signing'}).status_code==409
    assert http.get(C+'/'+row['id']+'/coverage').status_code==200
