from sqlalchemy import select,func
from test_auth_policy import env,login
from test_review_clocks import create_sla,running
from test_observability_governance import post
from kestrel.models import MatterAssignment,EthicalWall
from kestrel.services.auth import clock

B='/api/v1/sla-alerts'

def prepared(env):
    http,sessions,ids,_=env;_,policy=create_sla(env);_,task,csrf=running(env)
    bound=post(http,'/api/v1/review-clocks/tasks/'+task['id']+'/sla',csrf,{'policy_id':policy['id'],'expected_revision':task['revision'],'request_key':'alert-sla-bind-001','rationale':'Explicit operational budget binding'}).json()
    p={'expected_revision':bound['revision'],'request_key':'escalation-plan-001','warning_percent':80,'recipient_ids':[ids['lawyer'],ids['sme']],'rationale':'Scoped in-app reminders only; no legal action'}
    r=post(http,B+'/tasks/'+task['id']+'/plans',csrf,p);assert r.status_code==201,r.text
    plan=r.json()
    assert post(http,B+'/plans/'+plan['id']+'/approve',csrf,{'content_hash':plan['content_hash'],'rationale':'Cannot self-approve escalation recipients'}).status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,B+'/plans/'+plan['id']+'/approve',csrf,{'content_hash':plan['content_hash'],'rationale':'Independent SME approves exact scoped escalation'}).status_code==200
    with sessions() as db:
        for a in db.scalars(select(MatterAssignment)):a.expires_at=clock()+60*86400
        db.commit()
    return task,plan

def test_worker_alerts_are_deduplicated_and_scoped(env,monkeypatch):
    from kestrel.services import sla_alerts as s,review_clocks as c
    from kestrel.models import ReviewSlaAlert
    http,sessions,ids,_=env;task,plan=prepared(env);future=clock()+14*86400
    monkeypatch.setattr(s,'clock',lambda:future);monkeypatch.setattr(c,'clock',lambda:future)
    s.scan_due(sessions);s.scan_due(sessions)
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ReviewSlaAlert))==1
    csrf=login(http).json()['csrf_token'];r=http.get(B+'?matter_id='+ids['matter']);assert r.status_code==200 and len(r.json())==1
    alert=r.json()[0];assert alert['level']=='breach'
    assert post(http,B+'/'+alert['id']+'/read',csrf,{}).status_code==200
    assert post(http,B+'/'+alert['id']+'/dispositions',csrf,{'expected_revision':0,'operation':'acknowledge','rationale':'Lawyer acknowledges operational follow-up'}).status_code==201
    login(http,'root');assert http.get(B+'?matter_id='+ids['matter']).status_code==403
    with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    login(http);assert http.get(B+'?matter_id='+ids['matter']).status_code==403

def test_unapproved_plan_and_stale_binding_never_emit_alert(env,monkeypatch):
    from kestrel.services import sla_alerts as s,review_clocks as c
    from kestrel.models import ReviewSlaAlert
    http,sessions,ids,_=env;task,plan=prepared(env)
    csrf=login(http).json()['csrf_token']
    now=http.get('/api/v1/review-work/tasks/'+task['id']).json()
    assert post(http,'/api/v1/review-work/tasks/'+task['id']+'/events',csrf,{'operation':'reassign','assignee_id':ids['sme'],'expected_revision':now['revision'],'request_key':'reassign-plan-001','rationale':'New assignment requires new explicit escalation binding'}).status_code==201
    future=clock()+14*86400;monkeypatch.setattr(s,'clock',lambda:future);monkeypatch.setattr(c,'clock',lambda:future)
    s.scan_due(sessions)
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ReviewSlaAlert))==0


def test_proposed_plan_never_emits_and_freeze_stops_approved_plan(env,monkeypatch):
    from kestrel.services import sla_alerts as s,review_clocks as c
    from kestrel.models import ReviewSlaAlert
    from test_lifecycle import propose,approve
    http,sessions,ids,_=env;_,policy=create_sla(env);_,task,csrf=running(env)
    task=post(http,'/api/v1/review-clocks/tasks/'+task['id']+'/sla',csrf,{'policy_id':policy['id'],'expected_revision':task['revision'],'request_key':'bind-unapproved-001','rationale':'Bind operational budget for isolation test'}).json()
    plan=post(http,B+'/tasks/'+task['id']+'/plans',csrf,{'expected_revision':task['revision'],'request_key':'proposed-only-001','warning_percent':80,'recipient_ids':[ids['lawyer']],'rationale':'Explicit proposal must remain inactive'}).json()
    future=clock()+14*86400;monkeypatch.setattr(s,'clock',lambda:future);monkeypatch.setattr(c,'clock',lambda:future)
    s.scan_due(sessions)
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ReviewSlaAlert))==0
    monkeypatch.setattr(s,'clock',clock);monkeypatch.setattr(c,'clock',clock)
    csrf=login(http,'sme').json()['csrf_token'];assert post(http,B+'/plans/'+plan['id']+'/approve',csrf,{'content_hash':plan['content_hash'],'rationale':'Independent exact scoped plan decision'}).status_code==200
    login(http);signing=propose(http,ids,'sign');assert approve(http,signing).status_code==200
    s.scan_due(sessions)
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ReviewSlaAlert))==0


def test_alert_read_is_not_ack_and_recipient_wall_revokes_delivery(env,monkeypatch):
    from kestrel.services import sla_alerts as s,review_clocks as c
    from kestrel.models import ReviewSlaAlertRecipient,ReviewSlaAlertDisposition
    http,sessions,ids,_=env;prepared(env)
    with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    future=clock()+14*86400;monkeypatch.setattr(s,'clock',lambda:future);monkeypatch.setattr(c,'clock',lambda:future);s.scan_due(sessions)
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(ReviewSlaAlertRecipient).where(ReviewSlaAlertRecipient.account_id==ids['lawyer']))==0
    csrf=login(http,'sme').json()['csrf_token'];alerts=http.get(B+'?matter_id='+ids['matter']).json();assert len(alerts)==1
    read=post(http,B+'/'+alerts[0]['id']+'/read',csrf,{}).json();assert read['read'] and read['state']=='open' and read['revision']==0
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ReviewSlaAlertDisposition))==0
