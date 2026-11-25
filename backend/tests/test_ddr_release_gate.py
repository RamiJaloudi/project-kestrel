"""Legacy release/export routes cannot bypass exact internal graph-report review."""
from test_auth_policy import env,login
from test_document_workflow import candidate,BASE
from test_observability_governance import post
from test_ddr_runs import payload
from kestrel.services.ddr_execution import run_once


def prepared(env,tmp_path):
    http,sessions,ids,_=env;source,finding,csrf=candidate(env)
    created=post(http,'/api/v1/ddr/matters/'+ids['matter']+'/runs',csrf,payload(ids,finding).model_dump())
    assert created.status_code==201,created.text
    run=created.json();assert run_once(sessions,checkpoint_root=tmp_path)
    run=http.get('/api/v1/ddr/runs/'+run['id']).json();assert run['state']=='awaiting_attorney',run
    report=next(r for r in http.get('/api/v1/reports',params={'matter_id':ids['matter']}).json() if r['id']==run['report_id'])
    return run,report,csrf


def review(task,operation='approve'):
    return {k:task[k] for k in ['draft_hash','report_hash','snapshot_hash','config_hash']}|{'operation':operation,'content_reviewed':True,'rationale':'Independent review of the complete report package and source citations'}


def test_old_release_routes_require_internal_approval_and_each_revision(env,tmp_path,monkeypatch):
    http,sessions,ids,_=env;run,report,csrf=prepared(env,tmp_path)
    monkeypatch.setattr('kestrel.adapters.report_export.export',lambda *args:b'synthetic artifact')
    assert http.get('/api/v1/reports/'+report['id']+'/download/docx').status_code==200
    assert http.get('/api/v1/reports/'+report['id']+'/download/pdf').status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    external={'content_hash':report['content_hash'],'snapshot_hash':report['snapshot_hash'],'rationale':'Independently reviewed audience package'}
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,external).status_code==403
    task=run['tasks'][0]
    assert post(http,'/api/v1/ddr/tasks/'+task['id']+'/decisions',csrf,review(task)).status_code==200
    assert run_once(sessions,checkpoint_root=tmp_path)
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,external).status_code==200
    csrf=login(http,'lawyer').json()['csrf_token']
    body=report['body'];edit={k:body[k] for k in ['title','overview','coverage']};edit['sections']=[{'heading':s['heading'],'text':'A lawyer edited this section; its complete new version requires independent review.'} for s in body['sections']]
    revised=post(http,'/api/v1/reports/'+report['id']+'/versions',csrf,edit)
    assert revised.status_code==201,revised.text
    new=revised.json();assert new['version']==2 and not new['released']
    csrf=login(http,'sme').json()['csrf_token']
    attempted={'content_hash':new['content_hash'],'snapshot_hash':new['snapshot_hash'],'rationale':'Attempt release before new internal approval'}
    assert post(http,BASE+'/releases/'+new['release_id']+'/approve',csrf,attempted).status_code==403
    current=http.get('/api/v1/ddr/runs/'+run['id']).json()
    new_task=next(t for t in current['tasks'] if t['report_id']==new['id'])
    assert post(http,'/api/v1/ddr/tasks/'+new_task['id']+'/decisions',csrf,review(new_task)).status_code==200
    assert post(http,BASE+'/releases/'+new['release_id']+'/approve',csrf,attempted).status_code==200
    # The immutable old approved package remains readable until explicitly revoked.
    from fastapi.testclient import TestClient
    with TestClient(env[3],base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get('/api/v1/reports/'+report['id']+'/download/pdf').status_code==200
        assert client.get('/api/v1/reports/'+new['id']+'/download/pdf').status_code==200


def test_pdf_is_withheld_when_internal_approval_revoked_during_render(env,tmp_path,monkeypatch):
    http,sessions,ids,_=env;run,report,_=prepared(env,tmp_path)
    csrf=login(http,'sme').json()['csrf_token'];task=run['tasks'][0]
    assert post(http,'/api/v1/ddr/tasks/'+task['id']+'/decisions',csrf,review(task)).status_code==200
    assert run_once(sessions,checkpoint_root=tmp_path)
    def renderer(*args):
        from kestrel.services import ddr_runs as commands
        from test_ddr_runs import actor
        from kestrel.schemas.ddr_runs import Review
        with sessions() as db:commands.decide(db,actor(db,ids['sme']),task['id'],Review(**review(task,'revoke')))
        return b'synthetic artifact must not escape'
    monkeypatch.setattr('kestrel.adapters.report_export.export',renderer)
    response=http.get('/api/v1/reports/'+report['id']+'/download/pdf')
    assert response.status_code==403 and b'must not escape' not in response.content
