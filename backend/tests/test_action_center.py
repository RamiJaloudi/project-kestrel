import json
from sqlalchemy import select,func,update
from sqlalchemy.exc import DBAPIError
import pytest
from test_auth_policy import env,login
from test_document_workflow import candidate,BASE
from test_observability_governance import post
from kestrel import models as m
from kestrel.services import jobs

AC='/api/v1/action-center'


def replacement(env,author='root',reviewer='sme'):
    http,sessions,ids,_=env
    source,finding,_=candidate(env)
    csrf=login(http,author).json()['csrf_token']
    old=http.get('/api/v1/policy-editor/'+finding['playbook_id']).json()
    definition=old['definition'];definition['rules'][0]['description']+=' Changed analysis guidance.'
    result=post(http,'/api/v1/policy-editor',csrf,{'matter_id':ids['matter'],'kind':'legal_playbook','name':'Explicit replacement','definition':definition,'base_playbook_id':old['id']})
    assert result.status_code==201,result.text
    target=result.json()['id'];path='/api/v1/policy-editor/'+target
    assert post(http,path+'/test',csrf,{}).status_code==200
    assert post(http,path+'/submit',csrf,{'expected_revision':1,'rationale':'Submit revised rule guidance'}).status_code==200
    csrf=login(http,reviewer).json()['csrf_token']
    assert post(http,path+'/approve',csrf,{'expected_revision':2,'rationale':'Independent revised playbook review'}).status_code==200
    csrf=login(http,'root').json()['csrf_token']
    assert post(http,path+'/publish',csrf,{'expected_revision':3,'rationale':'Publish replacement with impact assessment'}).status_code==200
    return source,finding,target


def task_for(env):
    source,finding,target=replacement(env)
    http,sessions,ids,_=env
    assert jobs.run_once(sessions) # durable publication event -> impact, never a rerun
    csrf=login(http,'sme').json()['csrf_token']
    tasks=http.get(AC+'/tasks').json()
    assert len(tasks)==1
    return source,finding,target,http.get(AC+'/tasks/'+tasks[0]['id']).json(),csrf


def test_publication_impact_notifications_and_explicit_rerun(env):
    http,sessions,ids,_=env
    source,old,target,task,csrf=task_for(env)
    assert task['diff'] and task['counts']['reviewed_findings']==1 and task['state']=='open'
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.AnalysisJob))==1
    notices=http.get(AC+'/notifications').json();assert len(notices)==1 and notices[0]['state']=='unread'
    assert post(http,AC+'/notifications/'+notices[0]['id']+'/acknowledge',csrf,{}).status_code==200
    assert http.get(AC+'/tasks/'+task['id']).json()['state']=='open'
    claimed=post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{});assert claimed.status_code==200,claimed.text
    body={'snapshot_hash':task['snapshot_hash'],'rationale':'Independently authorize only this document version','idempotency_key':'impact-approval-test-001','engine_name':'literal'}
    approved=post(http,AC+'/tasks/'+task['id']+'/approve',csrf,body)
    assert approved.status_code==200,approved.text
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,body).json()['job_id']==approved.json()['job_id']
    assert jobs.run_once(sessions)
    shown=http.get(AC+'/tasks/'+task['id']).json()
    assert shown['state']=='pending_attorney_review' and shown['comparisons']
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.AnalysisJob))==2
        assert db.get(m.SourceFinding,old['id']).summary==old['summary']
        assert db.get(m.DocumentPolicyVersion,db.get(m.SourceFinding,old['id']).policy_id).review_state=='reviewed'
        for f in db.scalars(select(m.SourceFinding).where(m.SourceFinding.playbook_id==target)):
            assert db.get(m.DocumentPolicyVersion,f.policy_id).review_state=='candidate'
        with pytest.raises(DBAPIError):
            db.execute(update(m.ImpactSnapshot).values(snapshot_hash='modified'));db.commit()
        db.rollback()
    assert post(http,AC+'/tasks/'+task['id']+'/close',csrf,{'rationale':'Premature closure should be denied','release_handling_rationale':''}).status_code==409
    for comparison in shown['comparisons']:
        if comparison['new']:
            assert post(http,BASE+'/findings/'+comparison['new']['id']+'/review',csrf,{'decision':'reviewed','rationale':'Lawyer checked the new exact evidence'}).status_code==200
        disposition='accept_reviewed_candidate' if comparison['new'] else 'not_redetected_reviewed'
        assert post(http,AC+'/comparisons/'+comparison['id']+'/disposition',csrf,{'disposition':disposition,'rationale':'Compared against preserved original findings'}).status_code==200
    assert post(http,AC+'/tasks/'+task['id']+'/close',csrf,{'rationale':'Lawyer review and comparison completed','release_handling_rationale':''}).status_code==200
    assert post(http,AC+'/notifications/'+notices[0]['id']+'/resolve',csrf,{}).status_code==200


def test_stale_snapshot_rejection_and_no_admin_override(env):
    http,sessions,ids,_=env
    source,old,target,task,csrf=task_for(env)
    post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{})
    with sessions() as db:
        db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id).review_state='rejected';db.commit()
    body={'snapshot_hash':task['snapshot_hash'],'rationale':'Changed state must require reassessment','idempotency_key':'stale-impact-test','engine_name':'literal'}
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,body).status_code==409
    refreshed=post(http,AC+'/tasks/'+task['id']+'/reassess',csrf,{})
    assert refreshed.status_code==200 and refreshed.json()['snapshot_hash']!=task['snapshot_hash']
    assert http.get(AC+'/tasks/'+task['id']).json()['state']=='superseded'
    csrf=login(http,'root').json()['csrf_token']
    assert http.get(AC+'/tasks').status_code==403
    assert http.get(AC+'/tasks/'+task['id']).status_code==403
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,body).status_code==403


def test_worker_rechecks_wall_after_rerun_approval(env):
    http,sessions,ids,_=env
    _,old,_,task,csrf=task_for(env)
    post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{})
    body={'snapshot_hash':task['snapshot_hash'],'rationale':'Authorize before subsequent wall change','idempotency_key':'wall-rerun-test','engine_name':'literal'}
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,body).status_code==200
    with sessions() as db:
        db.add(m.EthicalWall(account_id=ids['sme'],matter_id=ids['matter']));db.commit()
    assert jobs.run_once(sessions)
    with sessions() as db:
        task_row=db.get(m.GovernanceTask,task['id'])
        assert task_row.state=='failed'
        rerun=db.scalar(select(m.AnalysisJob).where(m.AnalysisJob.impact_task_id==task['id']))
        assert rerun.state=='denied'
        assert db.scalar(select(func.count()).select_from(m.SourceFinding).where(m.SourceFinding.job_id==rerun.id))==0


def test_no_redetection_preserves_reviewed_finding_and_requires_disposition(env,monkeypatch):
    from kestrel.services import workflow
    http,sessions,ids,_=env
    _,old,_,task,csrf=task_for(env)
    post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{})
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,{'snapshot_hash':task['snapshot_hash'],'rationale':'Explicitly assess possible nondetection during rerun','idempotency_key':'nondetection-rerun-test','engine_name':'literal'}).status_code==200
    monkeypatch.setattr(workflow,'analyze_source',lambda source,definition:{'findings':[],'source_hash':source.bytes_hash,'text_hash':source.text_hash,'model_config':'isolated-zero-hit-test','taxonomy_version':'test'})
    assert jobs.run_once(sessions)
    detail=http.get(AC+'/tasks/'+task['id']).json()
    assert detail['comparisons'] and all(c['change']=='not_redetected' and c['new'] is None for c in detail['comparisons'])
    assert post(http,AC+'/tasks/'+task['id']+'/close',csrf,{'rationale':'Cannot close before examining a missing match'}).status_code==409
    with sessions() as db:
        original=db.get(m.SourceFinding,old['id'])
        assert original.summary==old['summary'] and db.get(m.DocumentPolicyVersion,original.policy_id).review_state=='reviewed'


def test_author_cannot_claim_or_approve_own_change(env):
    from kestrel.bootstrap import provision
    from test_auth_policy import PASSWORD
    from kestrel.services.auth import clock
    http,sessions,ids,_=env
    with sessions() as db:
        reviewer=provision(db,'reviewer','firm',['legal_sme'],PASSWORD)
        reviewer_id=reviewer.id
        db.add(m.MatterAssignment(account_id=reviewer.id,matter_id=ids['matter'],expires_at=clock()+3600));db.commit()
    replacement(env,author='sme',reviewer='reviewer')
    assert jobs.run_once(sessions)
    csrf=login(http,'sme').json()['csrf_token'];task=http.get(AC+'/tasks').json()[0]
    assert not task['independent'] and not task['assigned_to_me']
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{}).status_code==403
    csrf=login(http,'reviewer').json()['csrf_token']
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{}).status_code==200


def test_clean_team_tasks_and_notifications_disappear_when_membership_ends(env):
    http,sessions,ids,_=env
    source,old,target,task,csrf=task_for(env)
    # Tightening source handling must also hide descendants and prior impact metadata.
    with sessions() as db:
        from kestrel.services.auth import clock
        policy=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id)
        policy.classification='clean_team';policy.clean_team_scope='pricing'
        membership=m.CleanTeamMembership(account_id=ids['sme'],matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600)
        db.add(membership);db.commit();membership_id=membership.id
    assert len(http.get(AC+'/tasks').json())==1
    with sessions() as db:
        db.get(m.CleanTeamMembership,membership_id).revoked=True;db.commit()
    assert http.get(AC+'/tasks').json()==[]
    assert http.get(AC+'/notifications').json()==[]
    assert http.get(AC+'/tasks/'+task['id']).status_code==403


def test_overdue_escalation_is_persistent_once_and_never_authorizes_a_rerun(env):
    from kestrel.services.auth import clock
    http,sessions,ids,_=env
    _,_,_,task,csrf=task_for(env)
    notice=http.get(AC+'/notifications').json()[0]
    post(http,AC+'/notifications/'+notice['id']+'/acknowledge',csrf,{})
    with sessions() as db:
        db.get(m.GovernanceTask,task['id']).due_at=clock()-1;db.commit()
    assert jobs.run_once(sessions)
    assert not jobs.run_once(sessions)
    assert http.get(AC+'/notifications').json()[0]['state']=='unread'
    assert http.get(AC+'/tasks/'+task['id']).json()['priority']=='critical'
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.AnalysisJob))==1
        assert db.scalar(select(func.count()).select_from(m.AuditEvent).where(m.AuditEvent.action=='impact.escalate'))==1


def test_return_claim_and_processing_restriction_do_not_create_bypass(env):
    http,sessions,ids,_=env
    source,_,_,task,csrf=task_for(env)
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{}).status_code==200
    assert post(http,AC+'/tasks/'+task['id']+'/return-claim',csrf,{'rationale':'Return this undecided task for independent allocation'}).json()['state']=='open'
    with sessions() as db:
        db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id).ai_restricted=True;db.commit()
    current=post(http,AC+'/tasks/'+task['id']+'/reassess',csrf,{}).json()
    assert post(http,AC+'/tasks/'+current['id']+'/claim',csrf,{}).status_code==200
    body={'snapshot_hash':current['snapshot_hash'],'rationale':'Document processing restriction remains authoritative','idempotency_key':'ai-restriction-rerun-test','engine_name':'literal'}
    assert post(http,AC+'/tasks/'+current['id']+'/approve',csrf,body).status_code==403
    assert post(http,AC+'/tasks/'+current['id']+'/reject',csrf,body).status_code==200


def test_only_eligible_assignee_can_recover_an_abandoned_claim(env):
    from kestrel.bootstrap import provision
    from kestrel.services.auth import clock
    from test_auth_policy import PASSWORD
    http,sessions,ids,_=env
    _,_,_,task,csrf=task_for(env)
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{}).status_code==200
    with sessions() as db:
        reviewer=provision(db,'claim_reviewer','firm',['legal_sme'],PASSWORD);reviewer_id=reviewer.id
        db.add(m.MatterAssignment(account_id=reviewer_id,matter_id=ids['matter'],expires_at=clock()+3600));db.commit()
    csrf=login(http,'claim_reviewer').json()['csrf_token']
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{'rationale':'Attempt to take an active claim'}).status_code==403
    assert post(http,AC+'/tasks/'+task['id']+'/reassess',csrf,{}).status_code==200
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{'rationale':'Attempt to take an active claim'}).status_code==409
    with sessions() as db:
        db.get(m.Account,ids['sme']).active=False;db.commit()
    recovered=post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{'rationale':'Recover the disabled original claimant task'})
    assert recovered.status_code==200 and recovered.json()['claimed_by']==reviewer_id


def test_signing_freeze_blocks_tasks_new_legal_versions_and_escalation(env):
    from kestrel.services.auth import clock
    http,sessions,ids,_=env
    _,_,target,task,csrf=task_for(env)
    with sessions() as db:
        db.add(m.MatterLifecycle(matter_id=ids['matter'],frozen=True))
        db.get(m.GovernanceTask,task['id']).due_at=clock()-1;db.commit()
    assert post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{}).status_code==409
    assert not jobs.run_once(sessions)
    csrf=login(http,'root').json()['csrf_token']
    prior=http.get('/api/v1/policy-editor/'+target).json()
    assert post(http,'/api/v1/policy-editor',csrf,{'matter_id':ids['matter'],'kind':'legal_playbook','name':'Frozen edit attempt','definition':prior['definition'],'base_playbook_id':target}).status_code==409


def test_released_impact_requires_explicit_followup_and_preserves_package(env):
    http,sessions,ids,_=env
    source,old,target=replacement(env)
    # Create an audience-approved historical package before assessment runs.
    csrf=login(http,'lawyer').json()['csrf_token']
    release=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Historical synthetic note','summary':'Consent issue retained for explicit review','references':[{'finding_id':old['id'],'public_reference':'Synthetic clause'}]}).json()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Independent historical synthetic package approval'}).status_code==200
    assert jobs.run_once(sessions)
    task=http.get(AC+'/tasks').json()[0]
    assert task['priority']=='urgent' and task['counts']['released_packages_visible']==1
    post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{})
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,{'snapshot_hash':task['snapshot_hash'],'rationale':'Explicitly compare historical released evidence','idempotency_key':'released-impact-rerun','engine_name':'literal'}).status_code==200
    assert jobs.run_once(sessions)
    task=http.get(AC+'/tasks/'+task['id']).json()
    for comparison in task['comparisons']:
        if comparison['new']:
            post(http,BASE+'/findings/'+comparison['new']['id']+'/review',csrf,{'decision':'reviewed','rationale':'Lawyer checked the new source evidence'})
        post(http,AC+'/comparisons/'+comparison['id']+'/disposition',csrf,{'disposition':'accept_reviewed_candidate' if comparison['new'] else 'not_redetected_reviewed','rationale':'Explicit historical comparison disposition'})
    assert post(http,AC+'/tasks/'+task['id']+'/close',csrf,{'rationale':'All findings independently checked','release_handling_rationale':''}).status_code==409
    assert post(http,AC+'/tasks/'+task['id']+'/close',csrf,{'rationale':'All findings checked and separately handled','release_handling_rationale':'Justified retention of the existing synthetic package; any new publication requires separate approval'}).status_code==200
    assert http.get(BASE+'/releases/'+release['id']).json()['released']


def test_rejection_wall_and_tampered_scope(env):
    http,sessions,ids,_=env
    _,_,_,task,csrf=task_for(env)
    post(http,AC+'/tasks/'+task['id']+'/claim',csrf,{})
    body={'snapshot_hash':task['snapshot_hash'],'rationale':'Do not rerun under this proposed change','idempotency_key':'reject-impact-test','engine_name':'literal'}
    assert post(http,AC+'/tasks/'+task['id']+'/approve',csrf,{**body,'document_ids':['unapproved']}).status_code==422
    assert post(http,AC+'/tasks/'+task['id']+'/reject',csrf,body).status_code==200
    assert not jobs.run_once(sessions)
    with sessions() as db:
        db.add(m.EthicalWall(account_id=ids['sme'],matter_id=ids['matter']));db.commit()
    assert http.get(AC+'/tasks').json()==[]
    assert http.get(AC+'/notifications').json()==[]
    assert http.get(AC+'/tasks/'+task['id']).status_code==403
