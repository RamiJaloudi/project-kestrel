"""Synthetic paid-mode simulations only. The public create gate remains closed.

Fixtures enable the root integration constant only through monkeypatch and call
the real create/configuration services. No credential or actual provider is used.
"""
import json
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
pytest.importorskip('langgraph')
from test_auth_policy import env
from test_document_workflow import candidate
from test_ddr_runs import actor,payload
from kestrel import models as m
from kestrel.adapters import ddr_provider,provider_secrets
from kestrel.ddr.providers import FakeProvider
from kestrel.ddr.schemas import canonical,digest,Usage,ProviderResult
from kestrel.schemas.agent_registry import Create,Definition,Action
from kestrel.services import agent_registry,ddr_runs as commands,ddr_execution as worker,ai_budget
from kestrel.services.auth import clock
from kestrel.adapters.extraction import canonical as config_canonical


def prepared_live(env,monkeypatch,prompt=None,**limits):
    _,sessions,ids,_=env;source,finding,_=candidate(env,cloud_block=False);profile_ids=[]
    monkeypatch.setattr(provider_secrets,'configured',lambda:(True,'MOCK_PRIVATE_KEY'))
    monkeypatch.setattr(commands,'LIVE_GRAPH_READY',True)
    with sessions() as db:
        for role in ['contracts','drafter','quality']:
            version=agent_registry.create(db,actor(db,ids['root']),Create(matter_id=ids['matter'],name='Synthetic '+role,
                definition=Definition(agent_kind=role,provider='openai',model=ddr_provider.MODEL,
                    prompt=prompt or 'Use only supplied synthetic reviewed findings with exact source citations and preserve approved severity.',
                    tools=sorted(ddr_provider.REQUIRED[role]),**limits),rationale='Fixture independent stage configuration review',request_key=uuid.uuid4().hex))
            for operation,person in [('test','root'),('submit','root'),('approve','sme'),('publish','root')]:
                agent_registry.transition(db,actor(db,ids[person]),version['id'],Action(operation=operation,content_hash=version['content_hash'],rationale='Independently reviewed the exact synthetic stage definition',content_reviewed=operation=='approve'))
            profile_ids.append(version['id'])
    with sessions() as db:
        person=actor(db,ids['lawyer']);p=payload(ids,finding,engine='openai',agent_profile_ids=profile_ids)
        run=commands.create(db,person,p)
        return run.id,source,finding


class PaidFake(FakeProvider):
    live=True
    def invoke(self,*args):
        result=super().invoke(*args);usage=result.usage
        return ProviderResult(artifact=result.artifact,usage=Usage(input_tokens=usage.input_tokens,output_tokens=usage.output_tokens,cost_cents=ddr_provider.cost_cents(usage.input_tokens,usage.output_tokens)))


def test_live_simulation_one_aggregate_reservation_actual_usage_and_human_resume_no_charge(env,tmp_path,monkeypatch):
    from kestrel.schemas.ddr_runs import Review
    _,sessions,ids,_=env;rid,_,_=prepared_live(env,monkeypatch);provider=PaidFake()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='awaiting_attorney'
        operations=list(db.scalars(select(m.AIOperation).where(m.AIOperation.kind=='ddr_aggregate')));assert len(operations)==1
        group=operations[0];reservation=db.get(m.OperationReservation,group.id)
        assert reservation.reserved_cents==200 and reservation.state=='settled'
        usage=json.loads(group.result_json)['usage'];assert group.state=='succeeded' and usage['cost_cents']==reservation.charged_cents
        assert usage['cost_cents']==sum(db.scalars(select(m.DDRNodeResult.cost_cents)))>0
        assert db.scalar(select(func.count()).select_from(m.OperationReservation))==1
        month=db.get(m.AIBudgetPeriod,ai_budget.period());assert month.reserved_cents==0 and month.spent_cents==usage['cost_cents']
        task=db.scalar(select(m.DDRTask).where(m.DDRTask.run_id==rid));run=db.get(m.DDRRun,rid);draft=db.get(m.DDRArtifact,task.draft_id)
        _,release,_=commands.linked_report(db,task)
        commands.decide(db,actor(db,ids['sme']),task.id,Review(operation='approve',draft_hash=draft.content_hash,report_hash=release.content_hash,snapshot_hash=run.snapshot_hash,config_hash=run.config_hash,content_reviewed=True,rationale='Independently reviewed synthetic complete report package'))
        charged=month.spent_cents
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    assert provider.calls==['contracts','draft','quality']
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='complete'
        assert db.get(m.AIBudgetPeriod,ai_budget.period()).spent_cents==charged
        assert db.scalar(select(func.count()).select_from(m.OperationReservation))==1


def test_live_unknown_completion_retains_whole_reservation_and_known_node_usage(env,tmp_path,monkeypatch):
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch)
    class Broken(PaidFake):
        def invoke(self,spec,stage,*args):
            if stage=='draft':self.calls.append(stage);raise TimeoutError('SYNTHETIC_UNKNOWN_COMPLETION')
            return super().invoke(spec,stage,*args)
    provider=Broken()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    assert not worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='paused_ambiguous'
        group=db.scalar(select(m.AIOperation).where(m.AIOperation.kind=='ddr_aggregate'))
        assert group.state=='pending' and db.get(m.OperationReservation,group.id).state=='reserved'
        month=db.get(m.AIBudgetPeriod,ai_budget.period());assert month.spent_cents==0 and month.reserved_cents==200
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==1
        assert db.scalar(select(func.count()).select_from(m.DDRTask))==0
    assert provider.calls==['contracts','draft']
    for path in tmp_path.rglob('opaque-checkpoints*'):
        if path.is_file():assert b'SYNTHETIC_UNKNOWN_COMPLETION' not in path.read_bytes()


def test_shared_monthly_cap_is_reserved_before_first_mock_paid_send(env,tmp_path,monkeypatch):
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch);provider=PaidFake()
    with sessions() as db:db.add(m.AIBudgetPeriod(period=ai_budget.period(),spent_cents=900,reserved_cents=0));db.commit()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    assert provider.calls==[]
    with sessions() as db:
        month=db.get(m.AIBudgetPeriod,ai_budget.period());assert month.spent_cents==900 and month.reserved_cents==0
        assert db.scalar(select(func.count()).select_from(m.OperationReservation))==0
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==0


def test_live_crash_reuses_completed_node_and_same_aggregate_reservation(env,tmp_path,monkeypatch):
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch);first=PaidFake();original=worker.DurableGraphPorts.execute_once;crashed=[]
    def crash(self,spec,step,input_hash,producer):
        reference=original(self,spec,step,input_hash,producer)
        if step=='contracts' and not crashed:crashed.append(True);raise SystemExit('SYNTHETIC_PROCESS_CRASH')
        return reference
    monkeypatch.setattr(worker.DurableGraphPorts,'execute_once',crash)
    with pytest.raises(SystemExit):worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:first)
    with sessions() as db:
        db.get(m.DDRExecution,rid).lease_until=0;db.commit()
        assert db.get(m.AIBudgetPeriod,ai_budget.period()).reserved_cents==200
    monkeypatch.setattr(worker.DurableGraphPorts,'execute_once',original);fresh=PaidFake()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:fresh)
    assert first.calls==['contracts'] and fresh.calls==['draft','quality']
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='awaiting_attorney'
        assert db.scalar(select(func.count()).select_from(m.OperationReservation))==1
        assert db.get(m.AIBudgetPeriod,ai_budget.period()).reserved_cents==0


def test_private_provider_disabled_after_send_denies_output_and_holds_reservation(env,tmp_path,monkeypatch):
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch);enabled=[True]
    monkeypatch.setattr(provider_secrets,'configured',lambda:(enabled[0],'MOCK_PRIVATE_KEY'))
    class Disable(PaidFake):
        def invoke(self,*args):
            result=super().invoke(*args);enabled[0]=False;return result
    provider=Disable()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='paused_ambiguous'
        assert db.scalar(select(func.count()).select_from(m.DDRArtifact))==0
        assert db.get(m.AIBudgetPeriod,ai_budget.period()).reserved_cents==200
    assert provider.calls==['contracts']


def test_live_usage_cost_is_recomputed_and_underreported_cost_never_settles(env,tmp_path,monkeypatch):
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch)
    class WrongCost(PaidFake):
        def invoke(self,*args):
            value=super().invoke(*args)
            return value.model_copy(update={'usage':value.usage.model_copy(update={'cost_cents':0})})
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:WrongCost())
    with sessions() as db:
        assert db.get(m.DDRExecution,rid).state=='paused_ambiguous'
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==0
        assert db.get(m.AIBudgetPeriod,ai_budget.period()).reserved_cents==200


@pytest.mark.parametrize('limits',[{'max_cost_cents':0},{'total_tokens':100},{'max_model_calls':2}])
def test_published_profile_lower_bounds_deny_before_paid_send(env,tmp_path,monkeypatch,limits):
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch,**limits);provider=PaidFake()
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:provider)
    assert not provider.calls
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.OperationReservation))==0
        assert db.scalar(select(func.count()).select_from(m.DDRArtifact))==0


def test_aggregate_budget_cannot_exceed_month_or_settle_twice(env):
    _,sessions,ids,_=env
    with sessions() as db:
        db.add(m.AIBudgetPeriod(period=ai_budget.period(),spent_cents=800,reserved_cents=0))
        first=m.AIOperation(actor_id=ids['lawyer'],matter_id=ids['matter'],kind='ddr_aggregate',request_key='aggregate-helper-first',input_hash='a'*64,created_at=clock());db.add(first);db.flush()
        ai_budget.reserve_aggregate(db,first,200);db.commit();oid=first.id
    with sessions() as db:
        second=m.AIOperation(actor_id=ids['lawyer'],matter_id=ids['matter'],kind='ddr_aggregate',request_key='aggregate-helper-second',input_hash='b'*64,created_at=clock());db.add(second);db.flush()
        with pytest.raises(HTTPException) as error:ai_budget.reserve_aggregate(db,second,200)
        assert error.value.status_code==429;db.rollback()
    with sessions() as db:
        first=db.get(m.AIOperation,oid)
        with pytest.raises(HTTPException):ai_budget.settle_aggregate(db,first,201)
        assert db.get(m.OperationReservation,oid).state=='reserved'
        ai_budget.settle_aggregate(db,first,3);ai_budget.settle_aggregate(db,first,3);db.commit()
        month=db.get(m.AIBudgetPeriod,ai_budget.period());assert month.spent_cents==803 and month.reserved_cents==0
        with pytest.raises(HTTPException):ai_budget.reserve_aggregate(db,first,200)


def test_published_german_stage_prompts_keep_registry_and_runtime_hashes_identical(env,tmp_path,monkeypatch):
    _,sessions,_,_=env
    rid,_,_=prepared_live(env,monkeypatch,prompt='Prüfe ausschließlich bestätigte synthetische Befunde; erhalte Kündigungsfristen, ursprüngliche Zitate und die genehmigte Bewertung.')
    with sessions() as db:
        run=db.get(m.DDRRun,rid);config=json.loads(run.config_json)
        assert config['agent_profiles_hash']==digest(config_canonical(config['agent_profiles']))
        assert ddr_provider.factory(config)._config_hash==run.config_hash
        assert ddr_provider.validate_config(config)
    assert worker.run_once(sessions,checkpoint_root=tmp_path,provider_factory=lambda config:PaidFake())
    with sessions() as db:
        execution=db.get(m.DDRExecution,rid);assert execution.state=='awaiting_attorney',execution.error_code


def test_default_live_factory_actual_three_stage_sdk_bridge_uses_mock_transport_only(env,tmp_path,monkeypatch):
    import httpx
    _,sessions,_,_=env;rid,_,_=prepared_live(env,monkeypatch);sent=[];fake=FakeProvider()
    def handle(self,request):
        body=json.loads(request.content);name=body['response_format']['json_schema']['name']
        stage={'SpecialistResult':'contracts','DraftReport':'draft','QualityReview':'quality'}[name]
        artifact=fake.invoke(None,stage,json.loads(body['messages'][-1]['content']),body['max_completion_tokens']).artifact
        sent.append({'stage':stage,'store':body['store'],'model':body['model'],'prompt':body['messages'][1]['content']})
        return httpx.Response(200,json={'id':'synthetic-'+stage,'object':'chat.completion','created':1,'model':ddr_provider.MODEL,
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':canonical(artifact)}}],
            'usage':{'prompt_tokens':100,'completion_tokens':100,'total_tokens':200}},request=request)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',handle)
    assert worker.run_once(sessions,checkpoint_root=tmp_path)
    assert [item['stage'] for item in sent]==['contracts','draft','quality']
    assert all(item['store'] is False and item['model']==ddr_provider.MODEL for item in sent)
    with sessions() as db:
        execution=db.get(m.DDRExecution,rid);assert execution.state=='awaiting_attorney',execution.error_code
        group=db.scalar(select(m.AIOperation).where(m.AIOperation.kind=='ddr_aggregate'))
        assert json.loads(group.result_json)['usage']=={'input_tokens':300,'output_tokens':300,'cost_cents':3}
        assert db.get(m.OperationReservation,group.id).charged_cents==3
        assert db.scalar(select(func.count()).select_from(m.DDRNodeResult))==4
