import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env, login
from test_observability_governance import post
from kestrel.models import EthicalWall, AnalysisJob
from kestrel.services import jobs
from kestrel.redirect import app as redirect


def test_redirect_preserves_local_links_and_denies_untrusted_targets():
    with TestClient(redirect, base_url='http://firm.localhost:8000', follow_redirects=False) as http:
        r=http.get('/portal?view=Resources')
        assert r.status_code==308
        assert r.headers['location']=='https://firm.localhost:8443/portal?view=Resources'
        assert http.post('/api/v1/auth/login',json={'password':'never-forward'}).status_code==400
        assert http.get('/',headers={'host':'evil.example'}).status_code==403
        assert http.get('/',headers={'host':'localhost:8000','x-forwarded-host':'evil.example'}).headers['location']=='https://localhost:8443/'


def published(http,ids):
    csrf=login(http,'root').json()['csrf_token']
    definition=json.loads((Path(__file__).resolve().parents[2]/'data/playbooks/PB-STARTER-GOVERNED-DRAFT.json').read_text())
    v=post(http,'/api/v1/policy-editor',csrf,{'matter_id':ids['matter'],'kind':'legal_playbook','name':'Queue test','definition':definition}).json()['id']
    path='/api/v1/policy-editor/'+v
    post(http,path+'/test',csrf)
    post(http,path+'/submit',csrf,{'expected_revision':1,'rationale':'Review exact version'})
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,path+'/approve',csrf,{'expected_revision':2,'rationale':'Independent synthetic review'}).status_code==200
    csrf=login(http,'root').json()['csrf_token']
    assert post(http,path+'/publish',csrf,{'expected_revision':3,'rationale':'Publish exact approved version'}).status_code==200
    return v


def enqueue(http,version,key='queue-test-1'):
    csrf=login(http,'sme').json()['csrf_token']
    return post(http,'/api/v1/jobs',csrf,{'playbook_id':version,'idempotency_key':key,'rationale':'Authorize synthetic example analysis'})


def test_durable_queue_idempotence_evidence_and_scope(env):
    http,sessions,ids,_=env
    version=published(http,ids)
    created=enqueue(http,version)
    assert created.status_code==201
    job=created.json()['id']
    assert enqueue(http,version).json()['id']==job
    assert jobs.run_once(sessions)
    result=http.get('/api/v1/jobs/'+job).json()
    assert result['state']=='succeeded' and result['attempts']==1
    assert result['result']['status']=='candidate_only'
    assert result['result']['playbook_hash']==result['playbook_hash']
    assert any(c['evidence'] for c in result['result']['cases'])
    assert not jobs.run_once(sessions)
    csrf=login(http,'root').json()['csrf_token']
    assert post(http,'/api/v1/jobs',csrf,{'playbook_id':version,'idempotency_key':'root-denied','rationale':'Root is not Legal SME'}).status_code==403
    with TestClient(env[3],base_url='https://bank.localhost') as bank:
        assert login(bank,'bank',origin='https://bank.localhost').status_code==200
        assert bank.get('/api/v1/jobs/'+job).status_code==403


def test_worker_rechecks_wall_and_denies_stale_results(env):
    http,sessions,ids,_=env
    version=published(http,ids)
    job=enqueue(http,version).json()['id']
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['sme'],matter_id=ids['matter']));db.commit()
    assert jobs.run_once(sessions)
    with sessions() as db:
        row=db.get(AnalysisJob,job)
        assert row.state=='denied' and row.result_json is None
    assert http.get('/api/v1/jobs/'+job).status_code==403


def test_claim_fencing_and_explicit_expired_retry(env):
    http,sessions,ids,_=env
    job=enqueue(http,published(http,ids)).json()['id']
    now=int(time.time())
    lease=jobs.claim(sessions,now=now)
    assert lease and jobs.claim(sessions,now=now+1) is None
    assert not jobs.finish(sessions,job,'wrong-token',{'test':'unsafe'},now=now+2)
    assert not jobs.finish(sessions,job,lease[1],{'test':'expired'},now=now+1000)
    with sessions() as db:
        db.get(AnalysisJob,job).lease_until=now-1;db.commit()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,'/api/v1/jobs/'+job+'/retry',csrf,{'rationale':'Manual recovery after expired lease'}).status_code==200
    assert jobs.run_once(sessions)
    with sessions() as db:
        assert db.get(AnalysisJob,job).attempts==2


def test_transient_retry_is_bounded_and_redacted(env,monkeypatch,tmp_path):
    http,sessions,ids,_=env
    job=enqueue(http,published(http,ids)).json()['id']
    monkeypatch.setenv('KESTREL_LOG_DIR',str(tmp_path/'logs'))
    def fail(_):raise RuntimeError('SECRET document passage')
    monkeypatch.setattr(jobs,'analyze',fail)
    assert jobs.run_once(sessions)
    with sessions() as db:
        row=db.get(AnalysisJob,job);assert row.state=='queued';row.available_at=0;db.commit()
    assert jobs.run_once(sessions)
    with sessions() as db:assert db.get(AnalysisJob,job).state=='failed'
    assert 'SECRET' not in (tmp_path/'logs'/'worker.jsonl').read_text()


def test_terminal_candidate_result_is_immutable(env):
    http,sessions,ids,_=env
    job=enqueue(http,published(http,ids)).json()['id']
    assert jobs.run_once(sessions)
    with sessions() as db:
        with pytest.raises(DBAPIError):
            db.execute(update(AnalysisJob).where(AnalysisJob.id==job).values(result_json='{}'));db.commit()
        db.rollback()


def test_postgres_concurrent_workers_claim_once(env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    http,sessions,ids,_=env
    if sessions.kw['bind'].dialect.name!='postgresql':pytest.skip('PostgreSQL concurrency test')
    job=enqueue(http,published(http,ids)).json()['id']
    barrier=Barrier(2)
    def attempt():
        barrier.wait(timeout=5)
        return jobs.claim(sessions)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(attempt) for _ in range(2)]
        claims=[future.result(timeout=10) for future in futures]
    assert len([c for c in claims if c])==1
    assert next(c for c in claims if c)[0]==job


def test_console_messages_exclude_unrecognized_content(capsys,tmp_path,monkeypatch):
    import logging
    from kestrel.diagnostics import SafeConsoleHandler
    monkeypatch.setenv('KESTREL_LOG_DIR',str(tmp_path/'logs'))
    handler=SafeConsoleHandler()
    handler.emit(logging.LogRecord('provider',logging.ERROR,'fake.py',1,'PASSWORD: %s',('secret doc text',),None))
    output=capsys.readouterr().out
    assert 'PASSWORD' not in output and 'secret doc text' not in output
    assert 'Runtime error' in output
