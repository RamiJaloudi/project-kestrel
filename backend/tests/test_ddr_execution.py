"""Actual durable graph bridge, private SQLite checkpoints and isolated matter DB."""
import json
import uuid
import pytest
from sqlalchemy import select,func
pytest.importorskip('langgraph')
from test_auth_policy import env
from test_document_workflow import candidate
from test_ddr_runs import actor,payload
from kestrel import models as m
from kestrel.services import ddr_runs as commands
from kestrel.services.auth import clock


def prepared(env):
    _,sessions,ids,_=env;source,finding,_=candidate(env)
    with sessions() as db:run=commands.create(db,actor(db,ids['lawyer']),payload(ids,finding));return run.id,source,finding


def test_actual_worker_checkpoint_pause_restart_and_independent_approval(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    from kestrel.schemas.ddr_runs import Review
    _,sessions,ids,_=env;rid,source,finding=prepared(env)
    assert run_once(sessions,checkpoint_root=tmp_path)
    with sessions() as db:
        execution=db.get(m.DDRExecution,rid);assert execution.state=='awaiting_attorney',execution.error_code
        task=db.scalar(select(m.DDRTask).where(m.DDRTask.run_id==rid));assert task
        report,release,link=commands.linked_report(db,task)
        assert not db.get(m.DocumentPolicyVersion,release.policy_id).released
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==4
        assert sum(db.scalars(select(m.DDRNodeResult.cost_cents)))==0
        run=db.get(m.DDRRun,rid);draft=db.get(m.DDRArtifact,task.draft_id)
        # Human acknowledgement begins a new bounded active cycle even when the
        # preceding cycle already consumed its safe crash-recovery allowance.
        execution.attempts=2;db.commit()
        commands.decide(db,actor(db,ids['sme']),task.id,Review(operation='approve',draft_hash=draft.content_hash,report_hash=release.content_hash,snapshot_hash=run.snapshot_hash,config_hash=run.config_hash,content_reviewed=True,rationale='Independently reviewed complete synthetic report and annex package'))
    assert run_once(sessions,checkpoint_root=tmp_path)
    assert not run_once(sessions,checkpoint_root=tmp_path)
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='complete'
        assert db.scalar(select(func.count()).select_from(m.DDRTask))==1
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==4
        assert not db.get(m.DocumentPolicyVersion,release.policy_id).released
    for path in tmp_path.rglob('opaque-checkpoints*'):
        if path.is_file():assert finding['summary'].encode() not in path.read_bytes()


def test_provider_unknown_completion_is_durable_and_never_retried(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    from kestrel.ddr.providers import FakeProvider
    _,sessions,_,_=env;rid,_,_=prepared(env);calls=[]
    class Broken(FakeProvider):
        def invoke(self,*args):calls.append('sent');raise TimeoutError('SYNTHETIC_SECRET_CANARY')
    assert run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:Broken())
    assert not run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:Broken())
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='paused_ambiguous'
        assert db.scalar(select(func.count()).select_from(m.DDRAttempt))==1
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==0
        assert db.scalar(select(m.OperationReservation)).state=='reserved'
    assert len(calls)==1
    for path in tmp_path.rglob('opaque-checkpoints*'):
        if path.is_file():assert b'SYNTHETIC_SECRET_CANARY' not in path.read_bytes()


def test_current_wall_after_provider_prevents_artifact_task_or_report(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    from kestrel.ddr.providers import FakeProvider
    _,sessions,ids,_=env;rid,_,_=prepared(env)
    class Revoke(FakeProvider):
        def invoke(self,*args):
            result=super().invoke(*args)
            with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
            return result
    assert run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:Revoke())
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state in {'failed','paused_ambiguous'}
        assert db.scalar(select(func.count()).select_from(m.DDRArtifact))==0
        assert db.scalar(select(func.count()).select_from(m.DDRTask))==0


def test_expired_worker_cannot_use_claimed_authority(env,tmp_path):
    from kestrel.services.ddr_execution import claim,DurableGraphPorts,make_spec
    from kestrel.ddr.graph import GraphFault
    _,sessions,_,_=env;rid,_,_=prepared(env);claimed=claim(sessions);assert claimed
    with sessions() as db:
        run=db.get(m.DDRRun,rid);spec=make_spec(run)
        execution=db.get(m.DDRExecution,rid);execution.worker_token='replacement-worker';db.commit()
    with pytest.raises(GraphFault):DurableGraphPorts(sessions,rid,claimed[1]).authorize(spec,'test')


def test_live_factory_is_not_allowed_to_sneak_paid_calls_into_offline_run(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    _,sessions,_,_=env;rid,_,_=prepared(env);calls=[]
    class Forbidden:
        live=True
        def invoke(self,*args):calls.append('network');raise AssertionError('must not call')
    assert run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:Forbidden())
    assert not calls
    with sessions() as db:assert db.get(m.DDRExecution,rid).state=='failed'


def test_known_completed_artifact_survives_crash_without_provider_replay(env,tmp_path,monkeypatch):
    from kestrel.services import ddr_execution as worker
    from kestrel.ddr.providers import FakeProvider
    _,sessions,_,_=env;rid,_,_=prepared(env);first=FakeProvider();original=worker.DurableGraphPorts.execute_once;crashed=[False]
    def crash_after_commit(self,spec,step,input_hash,producer):
        value=original(self,spec,step,input_hash,producer)
        if step=='contracts' and not crashed[0]:crashed[0]=True;raise SystemExit('SYNTHETIC_PROCESS_CRASH')
        return value
    monkeypatch.setattr(worker.DurableGraphPorts,'execute_once',crash_after_commit)
    with pytest.raises(SystemExit):worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:first)
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==1
        db.get(m.DDRExecution,rid).lease_until=0;db.commit()
    monkeypatch.setattr(worker.DurableGraphPorts,'execute_once',original);fresh=FakeProvider()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:fresh)
    assert first.calls==['contracts'] and fresh.calls==['draft','quality']
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='awaiting_attorney'
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==4


def test_failed_quality_creates_durable_followup_without_report_or_approval(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    from kestrel.ddr.providers import FakeProvider
    _,sessions,_,_=env;rid,source,_=prepared(env)
    assert run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:FakeProvider(quality_passed=False))
    with sessions() as db:
        execution=db.get(m.DDRExecution,rid);assert execution.state=='failed' and execution.phase=='blocked_validation'
        assert db.scalar(select(func.count()).select_from(m.DDRTask))==0
        followup=db.scalar(select(m.ReviewTask).where(m.ReviewTask.source_id==source['id'],m.ReviewTask.request_key.like('ddr-validation-%')))
        assert followup


def test_offline_execution_does_not_spend_or_reserve_monthly_paid_allowance(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    from kestrel.services import ai_budget
    _,sessions,_,_=env;rid,_,_=prepared(env)
    with sessions() as db:db.add(m.AIBudgetPeriod(period=ai_budget.period(),spent_cents=1000,reserved_cents=0));db.commit()
    assert run_once(sessions,checkpoint_root=tmp_path)
    with sessions() as db:
        period=db.get(m.AIBudgetPeriod,ai_budget.period());assert period.spent_cents==1000 and period.reserved_cents==0
        assert all(r.reserved_cents==0 and r.charged_cents==0 and r.state=='settled' for r in db.scalars(select(m.OperationReservation)))
        operations=list(db.scalars(select(m.AIOperation).where(m.AIOperation.kind=='ddr_node')))
        assert len(operations)==3
        used=sum(json.loads(op.result_json)['usage']['input_tokens']+json.loads(op.result_json)['usage']['output_tokens'] for op in operations)
        assert used==sum(r.input_tokens+r.output_tokens for r in db.scalars(select(m.DDRNodeResult)))


def test_pinned_profile_limits_are_minimum_bounds():
    from types import SimpleNamespace
    from kestrel.services.ddr_execution import make_spec
    config={'max_concurrency':2,'max_model_calls':3,'total_tokens':12000,'max_output_tokens':1200,'max_cost_cents':200,'agent_profiles':[{'definition':{'max_concurrency':1,'total_tokens':9000,'max_output_tokens':900,'max_cost_cents':50}},{'definition':{'total_tokens':8000,'max_cost_cents':0}}]}
    run=SimpleNamespace(id=str(uuid.uuid4()),requested_by=str(uuid.uuid4()),matter_id=str(uuid.uuid4()),graph_version='ddr-graph-1',snapshot_hash='a'*64,config_hash='b'*64,config_json=json.dumps(config),snapshot_json=json.dumps({'items':[{'finding_id':str(uuid.uuid4())}]}),deadline=clock()+60)
    limits=make_spec(run).limits
    assert limits.max_concurrency==1 and limits.total_tokens==8000 and limits.max_output_tokens==900 and limits.max_cost_cents==0


def test_third_claim_is_failed_closed_before_any_node_or_provider(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    _,sessions,_,_=env;rid,_,_=prepared(env)
    with sessions() as db:db.get(m.DDRExecution,rid).attempts=2;db.commit()
    assert run_once(sessions,checkpoint_root=tmp_path) is False
    with sessions() as db:
        execution=db.get(m.DDRExecution,rid)
        assert execution.state=='failed' and execution.error_code=='WORKER_RETRY_LIMIT'
        assert db.scalar(select(func.count()).select_from(m.DDRAttempt))==0
        assert db.scalar(select(m.AuditEvent).where(m.AuditEvent.object_id==rid,m.AuditEvent.action=='ddr.worker_retry_limit',m.AuditEvent.outcome=='denied'))


def test_freeze_during_provider_stops_operational_lease_without_new_retained_content(env,tmp_path):
    from kestrel.services.ddr_execution import run_once
    from kestrel.ddr.providers import FakeProvider
    _,sessions,ids,_=env;rid,_,_=prepared(env)
    class Freeze(FakeProvider):
        def invoke(self,*args):
            result=super().invoke(*args)
            with sessions() as db:db.add(m.MatterLifecycle(matter_id=ids['matter'],frozen=True));db.commit()
            return result
    assert run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:Freeze())
    with sessions() as db:
        execution=db.get(m.DDRExecution,rid)
        assert execution.state=='paused_ambiguous' and execution.worker_token is None and execution.lease_until==0
        assert db.get(m.MatterLifecycle,ids['matter']).frozen
        assert db.scalar(select(func.count()).select_from(m.DDRArtifact))==0
        assert not db.scalar(select(m.DDREvent).where(m.DDREvent.run_id==rid,m.DDREvent.kind=='worker_stop'))
        assert db.scalar(select(m.AuditEvent).where(m.AuditEvent.object_id==rid,m.AuditEvent.action=='ddr.worker_stop'))
