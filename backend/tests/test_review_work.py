import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_document_workflow import upload
from test_observability_governance import post
from kestrel.models import EthicalWall,CleanTeamMembership,MatterLifecycle
from kestrel.services.auth import clock

B='/api/v1/review-work'


def source(env,**kw):
    http,_,ids,_=env;csrf=login(http).json()['csrf_token']
    return upload(http,csrf,ids['matter'],**kw).json(),csrf


def task(env,stage='review',**kw):
    http,_,ids,_=env;s,csrf=source(env)
    r=post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':stage,'assignee_id':ids['lawyer'],'request_key':'create-task-001','rationale':'Assign synthetic document review',**kw})
    assert r.status_code==201,r.text
    return s,r.json(),csrf


def change(http,t,csrf,operation,**kw):
    return post(http,B+'/tasks/'+t['id']+'/events',csrf,{'operation':operation,'expected_revision':t['revision'],
        'request_key':operation+'-task-event-001','rationale':'Synthetic workflow decision with source checked',**kw})


def test_parallel_tasks_separate_histories_and_idempotency(env):
    http,_,ids,_=env;s,t,csrf=task(env)
    qc=post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'qc','assignee_id':ids['sme'],'request_key':'create-qc-task-002','rationale':'Independent quality control stage'}).json()
    assert qc['id']!=t['id'] and qc['state']=='assigned'
    retry=post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'review','assignee_id':ids['lawyer'],'request_key':'create-task-001','rationale':'Assign synthetic document review'})
    assert retry.json()['id']==t['id']
    a=change(http,t,csrf,'accept');assert a.status_code==201,a.text
    accepted=a.json();assert accepted['state']=='accepted' and accepted['revision']==2
    assert change(http,t,csrf,'accept').json()['revision']==2
    assert change(http,t,csrf,'start').status_code==409
    running=change(http,accepted,csrf,'start').json();assert running['state']=='in_progress'
    paused=change(http,running,csrf,'pause').json();assert paused['state']=='paused'
    resumed=change(http,paused,csrf,'resume').json()
    completed=change(http,resumed,csrf,'complete').json();assert completed['state']=='completed'
    assert completed['timing']['active_seconds'] is None
    assert completed['timestamps']['completed_at']>=completed['timestamps']['assigned_at']
    assert http.get(B+'/tasks/'+qc['id']).json()['revision']==1
    reopened=change(http,completed,csrf,'reopen').json();assert reopened['state']=='assigned'
    assert len(reopened['events'])==7


def test_assignment_roles_reassignment_and_notification_scope(env):
    http,_,ids,_=env;s,t,csrf=task(env)
    changed=change(http,t,csrf,'reassign',assignee_id=ids['sme']);assert changed.status_code==201,changed.text
    assigned=changed.json();assert assigned['assignee']['id']==ids['sme']
    assert change(http,assigned,csrf,'accept').status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    inbox=http.get(B+'/notifications?matter_id='+ids['matter']);assert inbox.status_code==200
    n=next(n for n in inbox.json() if n['task_id']==t['id']);assert not n['read']
    assert post(http,B+'/notifications/'+n['id']+'/read',csrf,{}).status_code==200
    assert post(http,B+'/notifications/'+n['id']+'/read',csrf,{}).status_code==200
    assert change(http,assigned,csrf,'accept').status_code==201
    csrf=login(http,'root').json()['csrf_token']
    assert http.get(B+'/sources/'+s['id']).status_code==403
    assert post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'review','assignee_id':ids['root'],'request_key':'root-task-attempt','rationale':'Root has no legal document override'}).status_code==403
    csrf=login(http).json()['csrf_token']
    assert post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'review','assignee_id':ids['bank'],'request_key':'bank-task-attempt','rationale':'Cannot give bank internal reviewer access'}).status_code==403


def test_custodians_are_many_to_many_and_distinct_from_parties(env):
    http,_,ids,_=env;s,csrf=source(env)
    payload={'display_name':'Synthetic seller mailbox','custodian_type':'shared_mailbox','custody_role':'origin','provenance':'Synthetic vendor inventory','request_key':'custodian-mailbox-001'}
    one=post(http,B+'/sources/'+s['id']+'/custodians',csrf,payload);assert one.status_code==201,one.text
    assert post(http,B+'/sources/'+s['id']+'/custodians',csrf,payload).json()['id']==one.json()['id']
    second=post(http,B+'/sources/'+s['id']+'/custodians',csrf,{**payload,'display_name':'Synthetic legal department','custodian_type':'department','request_key':'custodian-dept-002'})
    assert second.status_code==201
    party=post(http,B+'/sources/'+s['id']+'/parties',csrf,{'name':'Synthetic Supplier Ltd','party_role':'supplier','provenance':'Instrument heading checked','request_key':'party-supplier-001'})
    assert party.status_code==201,party.text
    values=http.get(B+'/sources/'+s['id']).json();assert len(values['custodians'])==2 and len(values['parties'])==1
    assert values['tasks']==[]
    other=upload(http,csrf,ids['matter'],logical_key='SECOND-DOC').json()
    reused=post(http,B+'/sources/'+other['id']+'/custodians',csrf,{'custodian_id':one.json()['custodian']['id'],'custody_role':'copy_holder','provenance':'Second source inventory','request_key':'reuse-custodian-003'})
    assert reused.status_code==201,reused.text
    retired=post(http,B+'/custodian-links/'+one.json()['id']+'/retire',csrf,{'rationale':'Superseded custody attribution retained in history'})
    assert retired.status_code==201
    assert len(http.get(B+'/sources/'+s['id']).json()['custodians'])==2
    assert next(c for c in http.get(B+'/sources/'+s['id']).json()['custodians'] if c['id']==one.json()['id'])['retired']


def test_walls_clean_team_and_retained_restrictions(env):
    http,sessions,ids,_=env
    with sessions() as db:
        for aid in [ids['lawyer'],ids['sme']]:db.add(CleanTeamMembership(account_id=aid,matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600))
        db.commit()
    s,csrf=source(env,classification='clean_team',clean_team_scope='pricing')
    t=post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'qc','assignee_id':ids['sme'],'request_key':'restricted-task-001','rationale':'Review protected pricing source'}).json()
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['sme'],matter_id=ids['matter'],active=True));db.commit()
    csrf=login(http,'sme').json()['csrf_token']
    assert http.get(B+'/tasks/'+t['id']).status_code==403
    assert http.get(B+'/notifications?matter_id='+ids['matter']).status_code==403
    csrf=login(http).json()['csrf_token']
    with sessions() as db:
        membership=db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer']));membership.revoked=True;db.commit()
    assert http.get(B+'/sources/'+s['id']).status_code==403


def test_immutable_events_and_signing_freeze(env):
    http,sessions,ids,_=env;s,t,csrf=task(env)
    with sessions() as db:
        for table in ['review_tasks','review_task_events','review_task_notifications']:
            with pytest.raises(DBAPIError):db.execute(text('DELETE FROM '+table));db.commit()
            db.rollback()
        db.add(MatterLifecycle(matter_id=ids['matter'],frozen=True));db.commit()
    assert change(http,t,csrf,'accept').status_code==409
    assert post(http,B+'/sources/'+s['id']+'/parties',csrf,{'name':'Synthetic frozen party','party_role':'buyer','provenance':'Frozen instrument','request_key':'frozen-party-001'}).status_code==409
    assert http.get(B+'/tasks/'+t['id']).status_code==200


def test_task_metadata_does_not_declassify_with_its_source(env):
    from kestrel.models import SourceVersion,DocumentPolicyVersion
    http,sessions,ids,_=env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
    s,csrf=source(env,classification='clean_team',clean_team_scope='pricing')
    t=post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'review','assignee_id':ids['lawyer'],'request_key':'retained-task-001','rationale':'Record restricted source review assignment'}).json()
    # Fixture models an authorized source relaxation; retained workflow history is separate.
    with sessions() as db:
        row=db.get(SourceVersion,s['id']);policy=db.get(DocumentPolicyVersion,row.policy_id);policy.classification='ordinary';policy.clean_team_scope=None
        db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;db.commit()
    assert http.get('/api/v1/workflow/documents/'+s['id']).status_code==200
    assert http.get(B+'/tasks/'+t['id']).status_code==403
    assert http.get(B+'/sources/'+s['id']).json()['tasks']==[]
    assert http.get(B+'/notifications?matter_id='+ids['matter']).json()==[]


def test_clean_team_task_events_remain_exportable_only_with_scope(env):
    http,sessions,ids,_=env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
    s,csrf=source(env,classification='clean_team',clean_team_scope='pricing')
    t=post(http,B+'/sources/'+s['id']+'/tasks',csrf,{'stage':'review','assignee_id':ids['lawyer'],'request_key':'audit-task-001','rationale':'Restricted review coordination'}).json()
    assert 'id' in t
    rows=http.get('/api/v1/audit/events?category=clean_team').json()
    assert any(r['action']=='review.task.assign' and r['object_id']==t['events'][0]['id'] for r in rows)
    assert 'Restricted review coordination' not in str(rows)


def test_signing_snapshot_changes_with_task_events_and_keeps_receipts_operational(env):
    from test_lifecycle import propose,approve
    http,_,ids,_=env;s,t,csrf=task(env)
    snapshot=propose(http,ids,'sign')
    csrf=login(http).json()['csrf_token'];accepted=change(http,t,csrf,'accept');assert accepted.status_code==201
    assert approve(http,snapshot).status_code==409
    fresh=propose(http,ids,'sign');assert approve(http,fresh).status_code==200
    csrf=login(http).json()['csrf_token']
    assert change(http,accepted.json(),csrf,'start').status_code==409
    notes=http.get(B+'/notifications?matter_id='+ids['matter']).json();assert notes
    assert post(http,B+'/notifications/'+notes[0]['id']+'/read',csrf,{}).status_code==200


def test_task_manager_cannot_assign_a_walled_recipient_and_identity_is_not_a_role_grant(env):
    from kestrel.models import SourceFinding,RoleGrant
    http,sessions,ids,_=env;s,t,csrf=task(env)
    with sessions() as db:
        grants=db.scalar(select(func.count()).select_from(RoleGrant))
        db.add(EthicalWall(account_id=ids['sme'],matter_id=ids['matter'],active=True));db.commit()
    assert change(http,t,csrf,'reassign',assignee_id=ids['sme']).status_code==403
    assert http.get(B+'/tasks/'+t['id']).json()['assignee']['id']==ids['lawyer']
    assert post(http,B+'/tasks/'+t['id']+'/events',csrf,{'operation':'complete','expected_revision':1,'request_key':'forged-time-test','rationale':'Cannot forge an event time','occurred_at':0}).status_code==422
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(RoleGrant))==grants
        assert db.scalar(select(func.count()).select_from(SourceFinding))==0
