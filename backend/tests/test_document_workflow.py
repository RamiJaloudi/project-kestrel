import json
import pytest
from sqlalchemy import select,update
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login,PASSWORD
from test_observability_governance import post
from test_runtime_queue import published
from kestrel.models import (SourceVersion,SourceFinding,Role,RoleGrant,Account,EthicalWall)
from kestrel.services import jobs

BASE='/api/v1/workflow'
TEXT='Synthetic contract. A change of control requires prior written consent. Governing law: England and Wales.'

def upload(http,csrf,matter,**changes):
    query={'matter_id':matter,'file_name':'synthetic-contract.txt','logical_key':'CONTRACT-001','classification':'ordinary',
        'resource_type':'contract','language':'en','governing_law':'England and Wales','wave':'wave1','synthetic':True,**changes}
    return http.post(BASE+'/documents',params=query,content=TEXT.encode(),headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})

def allow_processing(http,sessions,ids,cloud_block=True):
    csrf=login(http,'root').json()['csrf_token']
    row=post(http,'/api/v1/policy-editor',csrf,{'matter_id':ids['matter'],'name':'Local offline processing','kind':'environment_policy',
        'definition':{'block_ai':False,'block_cloud':cloud_block,'block_external':False,'allowed_regions':['OTHER']}}).json()
    path='/api/v1/policy-editor/'+row['id']
    post(http,path+'/submit',csrf,{'expected_revision':1,'rationale':'Security review requested'})
    with sessions() as db:
        role=Role(name='security_approver');db.add(role);db.flush();db.add(RoleGrant(account_id=ids['sme'],role_id=role.id));db.commit()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,path+'/approve',csrf,{'expected_revision':2,'rationale':'Independent local fixture processing review'}).status_code==200
    csrf=login(http,'root').json()['csrf_token']
    assert post(http,path+'/publish',csrf,{'expected_revision':3,'rationale':'Publish fixture processing policy'}).status_code==200

def candidate(env,classification='ordinary',*,cloud_block=True):
    http,sessions,ids,_=env
    version=published(http,ids);allow_processing(http,sessions,ids,cloud_block=cloud_block)
    csrf=login(http,'lawyer').json()['csrf_token']
    result=upload(http,csrf,ids['matter'],classification=classification,clean_team_scope='pricing' if classification=='clean_team' else '')
    assert result.status_code==201,result.text
    source=result.json()
    assert post(http,BASE+'/documents/'+source['id']+'/confirm',csrf,{'snapshot_hash':source['snapshot_hash'],'rationale':'Human confirmed intake handling and source'}).status_code==200
    csrf=login(http,'sme').json()['csrf_token']
    queued=post(http,'/api/v1/jobs',csrf,{'playbook_id':version,'document_version_id':source['id'],'idempotency_key':'document-analysis-001','rationale':'Authorize first analysis of this document version'})
    assert queued.status_code==201,queued.text
    assert jobs.run_once(sessions)
    csrf=login(http,'lawyer').json()['csrf_token']
    findings=http.get(BASE+'/findings',params={'matter_id':ids['matter']}).json()
    assert findings and findings[0]['evidence'][0]['quote'] in TEXT
    finding=findings[0]
    assert post(http,BASE+'/findings/'+finding['id']+'/review',csrf,{'decision':'reviewed','rationale':'Attorney checked exact original evidence'}).status_code==200
    return source,finding,csrf

def test_upload_triage_format_limits_and_no_admin_override(env):
    http,sessions,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    assert upload(http,csrf,ids['matter']).status_code==403
    csrf=login(http,'lawyer').json()['csrf_token']
    result=upload(http,csrf,ids['matter']);assert result.status_code==201
    source=result.json()
    assert not source['classification_confirmed']
    shown=http.get(BASE+'/documents/'+source['id']).json()
    assert shown['units'][0]['text']==TEXT and shown['governing_law']=='England and Wales'
    # Including history must not hide current unconfirmed intake/OCR work.
    assert http.get(BASE+'/documents/'+source['id'],params={'historical':True}).status_code==200
    assert source['id'] in {r['id'] for r in http.get(BASE+'/documents',params={'matter_id':ids['matter'],'historical':True}).json()}
    assert upload(http,csrf,ids['other']).status_code==403
    assert upload(http,csrf,ids['matter'],file_name='../escape.txt').status_code==422
    assert upload(http,csrf,ids['matter'],file_name='macro.docm').status_code==415
    login(http,'root')
    assert http.get(BASE+'/documents/'+source['id']).status_code==403
    assert http.get(BASE+'/documents',params={'matter_id':ids['matter']}).json()==[]

def test_end_to_end_review_and_independent_audience_release(env):
    http,sessions,ids,_=env
    source,finding,csrf=candidate(env)
    created=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Synthetic board risk note',
        'summary':'Consent should be checked before completing the transaction.','references':[{'finding_id':finding['id'],'public_reference':'Contract A, consent clause'}]})
    assert created.status_code==201,created.text
    release=created.json()
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Attempting self approval'}).status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Independent audience release review'}).status_code==200
    from fastapi.testclient import TestClient
    with TestClient(env[3],base_url='https://client.localhost') as external:
        login(external,'client',origin='https://client.localhost')
        output=external.get(BASE+'/releases/'+release['id'])
        assert output.status_code==200 and output.json()['summary'].startswith('Consent')
        assert 'units' not in output.json() and 'evidence' not in output.json()
        assert external.get(BASE+'/documents/'+source['id']).status_code==403
    # New version retains bytes/history and makes the old source superseded.
    csrf=login(http,'lawyer').json()['csrf_token']
    newer=upload(http,csrf,ids['matter'],previous_id=source['id'],wave='wave2')
    assert newer.status_code==201 and newer.json()['version_number']==2
    with TestClient(env[3],base_url='https://client.localhost') as external:
        login(external,'client',origin='https://client.localhost')
        assert external.get(BASE+'/releases/'+release['id']).status_code==403
    assert http.get(BASE+'/documents/'+source['id'],params={'historical':True}).status_code==200
    with sessions() as db:
        job_id=db.get(SourceFinding,finding['id']).job_id
    assert http.get('/api/v1/jobs/'+job_id).status_code==403
    assert http.get('/api/v1/jobs/'+job_id,params={'historical':True}).status_code==200
    with sessions() as db:
        with pytest.raises(DBAPIError):
            db.execute(update(SourceVersion).where(SourceVersion.id==source['id']).values(data=b'changed'));db.commit()
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(update(SourceFinding).where(SourceFinding.id==finding['id']).values(summary='silent replacement'));db.commit()
        db.rollback()

def test_privileged_bank_release_and_unreviewed_finding_denied(env):
    http,_,ids,_=env
    _,finding,csrf=candidate(env,'privileged')
    body={'matter_id':ids['matter'],'audience':'castlegate','title':'Not allowed','summary':'Do not release privileged source advice.',
        'references':[{'finding_id':finding['id'],'public_reference':'Internal note'}]}
    assert post(http,BASE+'/releases',csrf,body).status_code==403

def test_classification_relaxation_requires_independent_approver(env):
    http,sessions,ids,_=env
    csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter'],classification='privileged').json()
    proposal=post(http,BASE+'/documents/'+source['id']+'/classification-requests',csrf,{
        'classification':'ordinary','resource_type':'contract','snapshot_hash':source['snapshot_hash'],'rationale':'Request independent review of mistaken intake label'})
    assert proposal.status_code==201
    path=BASE+'/classification-requests/'+proposal.json()['id']+'/approve'
    assert post(http,path,csrf,{'rationale':'Self approval attempt'}).status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,path,csrf,{'rationale':'Independent SME confirms this synthetic note is a contract'}).status_code==200
    assert http.get(BASE+'/documents/'+source['id']).json()['classification']=='ordinary'

def test_source_confirmation_rationale_is_not_exposed_in_admin_history(env):
    http,_,ids,_=env
    csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter'],classification='privileged').json()
    assert post(http,BASE+'/documents/'+source['id']+'/confirm',csrf,{'snapshot_hash':source['snapshot_hash'],'rationale':'PRIVATE LEGAL SOURCE RATIONALE'}).status_code==200
    login(http,'root')
    history=http.get('/api/v1/validation/matters/'+ids['matter']+'/history')
    assert history.status_code==200 and 'PRIVATE LEGAL SOURCE RATIONALE' not in history.text

def test_clean_team_requires_named_access_and_separate_antitrust_release(env):
    from kestrel.bootstrap import provision
    from kestrel.models import CleanTeamMembership,MatterAssignment
    from kestrel.services.auth import clock
    http,sessions,ids,_=env
    with sessions() as db:
        antitrust=provision(db,'antitrust','firm',['antitrust_counsel'],PASSWORD)
        anti_id=antitrust.id
        db.add(MatterAssignment(account_id=anti_id,matter_id=ids['matter'],expires_at=clock()+1000))
        for user in [ids['lawyer'],ids['sme'],anti_id]:
            db.add(CleanTeamMembership(account_id=user,matter_id=ids['matter'],scope='pricing',approved_by=anti_id,expires_at=clock()+1000))
        db.commit()
    source,finding,csrf=candidate(env,'clean_team')
    created=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'castlegate','title':'Sanitized commercial issue',
        'summary':'A customer consent item requires follow-up. No prices are included.',
        'references':[{'finding_id':finding['id'],'public_reference':'Sanitized customer contract reference'}]})
    assert created.status_code==201
    release=created.json()
    def decision(data):return {'content_hash':data['content_hash'],'snapshot_hash':data['snapshot_hash'],'rationale':'Independent audience and sanitization review'}
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,decision(release)).status_code==409
    csrf=login(http,'antitrust').json()['csrf_token']
    anti=post(http,BASE+'/releases/'+release['id']+'/antitrust',csrf,decision(release))
    assert anti.status_code==200,anti.text
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,decision(anti.json())).status_code==409
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,decision(anti.json())).status_code==200
    from fastapi.testclient import TestClient
    with TestClient(env[3],base_url='https://bank.localhost') as bank:
        login(bank,'bank',origin='https://bank.localhost')
        assert bank.get(BASE+'/releases/'+release['id']).status_code==200
        assert bank.get(BASE+'/documents/'+source['id']).status_code==403
    # Removing named clearance blocks source, finding and stored job-result access immediately.
    with sessions() as db:
        for grant in db.scalars(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['sme'])):grant.revoked=True
        job=db.get(SourceFinding,finding['id']).job_id;db.commit()
    assert http.get('/api/v1/jobs/'+job).status_code==403
    assert http.get(BASE+'/findings',params={'matter_id':ids['matter']}).json()==[]

def test_unreviewed_release_and_document_rerun_are_denied(env):
    http,sessions,ids,_=env
    source,finding,csrf=candidate(env)
    with sessions() as db:
        from kestrel.models import AnalysisJob,DocumentPolicyVersion
        job=db.get(SourceFinding,finding['id']).job_id
        db.get(DocumentPolicyVersion,db.get(SourceFinding,finding['id']).policy_id).review_state='candidate';db.commit()
    assert post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Unreviewed package',
        'summary':'This package must not be released yet.','references':[{'finding_id':finding['id'],'public_reference':'Contract A'}]}).status_code==409
    csrf=login(http,'sme').json()['csrf_token']
    with sessions() as db:
        from kestrel.models import AnalysisJob
        book=db.get(AnalysisJob,job).playbook_id
    assert post(http,'/api/v1/jobs',csrf,{'playbook_id':book,'document_version_id':source['id'],'idempotency_key':'second-document-analysis','rationale':'Attempt to bypass the impact authorization workflow'}).status_code==409
