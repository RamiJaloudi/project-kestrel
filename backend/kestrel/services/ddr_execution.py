"""Offline-first durable LangGraph bridge. No release or permission-management tool."""
import ctypes
import json
import os
import re
import sqlite3
import subprocess
import uuid
from functools import wraps
from pathlib import Path
from sqlalchemy import select,update,text,func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from pydantic import TypeAdapter
from kestrel import models as m
from kestrel.services import ddr_runs as commands,ai_budget
from kestrel.services.auth import clock
from kestrel.adapters import ddr_provider
from kestrel.ddr.graph import DdrEngine,GraphFault
from kestrel.ddr.providers import FakeProvider
from kestrel.ddr.schemas import (RunSpec,Limits,EvidenceBundle,EvidenceItem,Citation,Artifact,ArtifactRef,Usage,canonical,digest)

LEASE_SECONDS=180
ROOT=Path(__file__).resolve().parents[3]
ARTIFACT=TypeAdapter(Artifact)


def make_spec(run):
    config=json.loads(run.config_json);values={key:config[key] for key in Limits.model_fields if key in config}
    for profile in config.get('agent_profiles',[]):
        for key in Limits.model_fields:
            if key in profile['definition']:values[key]=min(values.get(key,Limits().model_dump()[key]),profile['definition'][key])
    snapshot=json.loads(run.snapshot_json)
    return RunSpec(run_id=run.id,requester_id=run.requested_by,matter_id=run.matter_id,graph_version=run.graph_version,
        snapshot_hash=run.snapshot_hash,config_hash=run.config_hash,finding_refs=tuple(item['finding_id'] for item in snapshot['items']),deadline_epoch=run.deadline,limits=Limits(**values))


def safe_callback(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        try:return fn(*args,**kwargs)
        except GraphFault as error:
            code=str(error)
            raise GraphFault(code if re.fullmatch(r'[A-Z_]{3,64}',code) else 'PORT_FAILURE') from None
        except HTTPException as error:raise GraphFault('AUTHORITY_DENIED' if error.status_code in {401,403,409} else 'PORT_FAILURE') from None
        except Exception:raise GraphFault('PORT_FAILURE') from None
    return call


class DurableGraphPorts:
    def __init__(self,sessions,run_id,worker_token,heartbeat=None):
        self.sessions,self.run_id,self.worker_token=sessions,run_id,worker_token
        self.heartbeat=heartbeat

    def _authority(self,db,spec,lock=False):
        if self.heartbeat:self.heartbeat()
        if db.new or db.dirty:db.flush()
        db.expire_all()
        execution=db.scalar(select(m.DDRExecution).where(m.DDRExecution.run_id==self.run_id).with_for_update() if lock else select(m.DDRExecution).where(m.DDRExecution.run_id==self.run_id))
        if not execution or execution.state!='running' or execution.worker_token!=self.worker_token or execution.lease_until<=clock():raise GraphFault('WORKER_AUTHORITY_LOST')
        run,actor,bundle=commands.execution_authority(db,self.run_id)
        if make_spec(run)!=spec:raise GraphFault('RUN_SCOPE_CHANGED')
        if run.engine=='openai':
            ddr_provider.validate_config(json.loads(run.config_json))
            if bundle['snapshot'].get('external_processing') is not True or not ddr_provider.availability()['enabled']:raise GraphFault('LIVE_PROVIDER_DISABLED')
        elif run.engine!='offline':raise GraphFault('LIVE_PROVIDER_DISABLED')
        return run,actor,bundle

    @safe_callback
    def authorize(self,spec,stage):
        with self.sessions() as db:self._authority(db,spec)

    @safe_callback
    def evidence(self,spec):
        with self.sessions() as db:
            run,actor,bundle=self._authority(db,spec);items=[]
            rows={r.finding_id:r for r in commands.evidence_rows(db,run)}
            contents={item['finding_id']:item for item in bundle['content']}
            for descriptor in bundle['snapshot']['items']:
                retained=rows[descriptor['finding_id']];source=db.get(m.SourceVersion,retained.source_id)
                units={u['number']:u for u in json.loads(source.units_json)};content=contents[descriptor['finding_id']]
                severity=content['severity']
                if severity in {'unassessed','uncertain','information'}:severity='unrated'  # Explicit root-approved legacy mapping; no rating inferred.
                if severity not in {'low','medium','high','critical','unrated'}:raise GraphFault('UNSUPPORTED_REVIEWED_SEVERITY')
                for index,span in enumerate(content['evidence']):
                    eid=retained.id+':'+str(index);unit=units[span['unit']]
                    citation=Citation(evidence_id=eid,finding_ref=retained.finding_id,source_version_id=source.id,source_bytes_hash=source.bytes_hash,source_text_hash=source.text_hash,
                        unit=span['unit'],start=span['start'],end=span['end'],quote=span['quote'])
                    items.append(EvidenceItem(id=eid,finding_ref=retained.finding_id,severity=severity,summary=content['summary'],citation=citation,unit_text=unit['text'],unit_text_hash=digest(unit['text']),quote_hash=digest(span['quote'])))
            value=EvidenceBundle(snapshot_hash=run.snapshot_hash,config_hash=run.config_hash,items=tuple(items))
            self._authority(db,spec);return value

    def _operation_key(self,spec,step):return 'ddr:'+spec.run_id+':'+step

    def _aggregate(self,db,run,spec,create=False):
        key='ddr-budget:'+run.id;fingerprint=digest(canonical({'config':spec.config_hash,'snapshot':spec.snapshot_hash}))
        operation=db.scalar(select(m.AIOperation).where(m.AIOperation.actor_id==run.requested_by,m.AIOperation.request_key==key))
        if not operation and create:
            operation=m.AIOperation(actor_id=run.requested_by,matter_id=run.matter_id,kind='ddr_aggregate',request_key=key,input_hash=fingerprint,created_at=clock())
            db.add(operation);db.flush()
        if not operation or operation.kind!='ddr_aggregate' or operation.matter_id!=run.matter_id or operation.input_hash!=fingerprint:raise GraphFault('AGGREGATE_RESERVATION_SCOPE')
        if create:ai_budget.reserve_aggregate(db,operation,min(ai_budget.RUN_CENTS,spec.limits.max_cost_cents))
        return operation

    def _node_operations(self,db,run):
        return list(db.scalars(select(m.AIOperation).where(m.AIOperation.actor_id==run.requested_by,m.AIOperation.kind=='ddr_node',m.AIOperation.request_key.like('ddr:'+run.id+':%'))))

    def _reference(self,run,artifact):return ArtifactRef(id=artifact.id,kind=artifact.kind,content_hash=artifact.content_hash,creator_id=run.requested_by)

    @safe_callback
    def execute_once(self,spec,step,input_hash,producer):
        if step not in {'contracts','draft','quality','citations'}:raise GraphFault('UNKNOWN_GRAPH_STEP')
        with self.sessions() as db:
            run,actor,_=self._authority(db,spec,True)
            attempt=db.scalar(select(m.DDRAttempt).where(m.DDRAttempt.run_id==run.id,m.DDRAttempt.step_key==step))
            if attempt:
                if attempt.input_hash!=input_hash or attempt.config_hash!=spec.config_hash:raise GraphFault('ATTEMPT_INPUT_CHANGED')
                result=db.scalar(select(m.DDRNodeResult).where(m.DDRNodeResult.attempt_id==attempt.id))
                if not result:raise GraphFault('ATTEMPT_UNCERTAIN')
                artifact=db.get(m.DDRArtifact,result.artifact_id)
                if not artifact or artifact.run_id!=run.id or digest(artifact.payload_json)!=artifact.content_hash:raise GraphFault('ARTIFACT_INTEGRITY')
                self._authority(db,spec);return self._reference(run,artifact)
            attempt=m.DDRAttempt(matter_id=run.matter_id,run_id=run.id,step_key=step,input_hash=input_hash,config_hash=spec.config_hash,created_at=clock())
            db.add(attempt)
            try:db.commit()
            except IntegrityError:raise GraphFault('ATTEMPT_UNCERTAIN') from None
            attempt_id=attempt.id
        # No DB session or lock survives a provider callback. A committed incomplete
        # attempt is deliberately ambiguous after a crash; it is never resent.
        value=ARTIFACT.validate_python(producer())
        encoded=canonical(value)
        if len(encoded.encode())>512000:raise GraphFault('ARTIFACT_BOUND')
        with self.sessions() as db:
            run,actor,_=self._authority(db,spec,True)
            operation=db.scalar(select(m.AIOperation).where(m.AIOperation.actor_id==run.requested_by,m.AIOperation.request_key==self._operation_key(spec,step)))
            usage=Usage(input_tokens=0,output_tokens=0,cost_cents=0)
            if step!='citations':
                if not operation or operation.state!='succeeded':raise GraphFault('USAGE_UNCERTAIN')
                usage=Usage.model_validate(json.loads(operation.result_json)['usage'])
            artifact=m.DDRArtifact(matter_id=run.matter_id,run_id=run.id,kind=value.kind,payload_json=encoded,content_hash=digest(encoded),created_at=clock());db.add(artifact);db.flush()
            db.add(m.DDRNodeResult(matter_id=run.matter_id,attempt_id=attempt_id,artifact_id=artifact.id,**usage.model_dump(),created_at=clock()))
            self._authority(db,spec);commands.record(db,run,actor.id,'node_'+step,'completed');db.commit();return self._reference(run,artifact)

    @safe_callback
    def artifact(self,spec,reference):
        with self.sessions() as db:
            run,_,_=self._authority(db,spec)
            value=commands.artifact(db,run,reference,reference.kind)
            result=ARTIFACT.validate_python(value);self._authority(db,spec);return result

    @safe_callback
    def reserve(self,spec,step,estimated_input_tokens,max_output_tokens,live):
        if step not in {'contracts','draft','quality'} or type(estimated_input_tokens) is not int or estimated_input_tokens<0 or max_output_tokens!=spec.limits.max_output_tokens:raise GraphFault('INVALID_TOKEN_ESTIMATE')
        with self.sessions() as db:
            run,actor,_=self._authority(db,spec,True)
            if type(live) is not bool or live!=(run.engine=='openai'):raise GraphFault('PROVIDER_ENGINE_MISMATCH')
            ops=self._node_operations(db,run)
            if len(ops)>=spec.limits.max_model_calls:raise GraphFault('MODEL_CALL_BUDGET')
            used_tokens=0;used_cost=0
            for operation in ops:
                retained=json.loads(operation.result_json)
                if operation.state=='succeeded':used_tokens+=retained['usage']['input_tokens']+retained['usage']['output_tokens'];used_cost+=retained['usage']['cost_cents']
                else:used_tokens+=retained['reserved_tokens'];used_cost+=retained.get('reserved_cost_cents',0)
            estimated_cost=ddr_provider.cost_cents(estimated_input_tokens,max_output_tokens) if live else 0
            if used_tokens+estimated_input_tokens+max_output_tokens>spec.limits.total_tokens or used_cost+estimated_cost>min(200,spec.limits.max_cost_cents):raise GraphFault('AGGREGATE_BUDGET')
            key=self._operation_key(spec,step)
            if any(op.request_key==key for op in ops):raise GraphFault('PROVIDER_RETRY_PROHIBITED')
            if live:self._aggregate(db,run,spec,create=True)
            operation=m.AIOperation(actor_id=actor.id,matter_id=run.matter_id,kind='ddr_node',request_key=key,input_hash=digest(spec.config_hash+':'+step),result_json=json.dumps({'reserved_tokens':estimated_input_tokens+max_output_tokens,'input_bound':estimated_input_tokens,'reserved_cost_cents':estimated_cost,'live':live}),created_at=clock())
            db.add(operation);db.flush()
            if not live:
                period=ai_budget.period()
                db.execute(text('INSERT INTO ai_budget_periods(period,spent_cents,reserved_cents) VALUES (:period,0,0) ON CONFLICT(period) DO NOTHING'),{'period':period})
                db.add(m.OperationReservation(operation_id=operation.id,period=period,reserved_cents=0,created_at=clock()))
            self._authority(db,spec);db.commit();return operation.id

    @safe_callback
    def settle(self,spec,reservation,usage,uncertain):
        with self.sessions() as db:
            run,_,_=self._authority(db,spec,True)
            operation=db.get(m.AIOperation,reservation);budget=db.get(m.OperationReservation,reservation)
            if not operation or operation.matter_id!=run.matter_id or operation.actor_id!=run.requested_by or operation.state!='pending' or operation.kind!='ddr_node' or not operation.request_key.startswith('ddr:'+run.id+':'):raise GraphFault('RESERVATION_SCOPE')
            value=json.loads(operation.result_json);live=run.engine=='openai'
            if value['live']!=live:raise GraphFault('RESERVATION_SCOPE')
            if live:
                aggregate=self._aggregate(db,run,spec);group_budget=db.get(m.OperationReservation,aggregate.id)
                if not group_budget or group_budget.state!='reserved':raise GraphFault('AGGREGATE_RESERVATION_SCOPE')
            elif not budget or budget.state!='reserved':raise GraphFault('RESERVATION_SCOPE')
            if uncertain or usage is None:
                self._authority(db,spec);db.commit();raise GraphFault('PROVIDER_UNCERTAIN')
            usage=Usage.model_validate(usage)
            if usage.cost_cents!=(ddr_provider.cost_cents(usage.input_tokens,usage.output_tokens) if live else 0):raise GraphFault('PROVIDER_COST_INVALID')
            if live and usage.input_tokens>value['input_bound']:raise GraphFault('INPUT_TOKEN_BUDGET')
            if usage.output_tokens>spec.limits.max_output_tokens:raise GraphFault('OUTPUT_TOKEN_BUDGET')
            others=list(db.scalars(select(m.AIOperation).where(m.AIOperation.actor_id==run.requested_by,m.AIOperation.kind=='ddr_node',m.AIOperation.request_key.like('ddr:'+run.id+':%'),m.AIOperation.id!=operation.id)))
            total=usage.input_tokens+usage.output_tokens;cost=usage.cost_cents
            for other in others:
                retained=json.loads(other.result_json);total+=retained['usage']['input_tokens']+retained['usage']['output_tokens'] if other.state=='succeeded' else retained['reserved_tokens']
                cost+=retained['usage']['cost_cents'] if other.state=='succeeded' else retained.get('reserved_cost_cents',0)
            if total>spec.limits.total_tokens:raise GraphFault('AGGREGATE_TOKEN_BUDGET')
            if cost>min(200,spec.limits.max_cost_cents):raise GraphFault('AGGREGATE_COST_BUDGET')
            value['usage']=usage.model_dump();operation.result_json=json.dumps(value);operation.state='succeeded'
            if not live:budget.state='settled';budget.charged_cents=0
            self._authority(db,spec);db.commit()

    def finish_budget(self,db,run,spec):
        if run.engine!='openai':return
        operation=self._aggregate(db,run,spec);ops=self._node_operations(db,run)
        if len(ops)!=3 or any(op.state!='succeeded' for op in ops):raise GraphFault('AGGREGATE_USAGE_UNCERTAIN')
        results=list(db.scalars(select(m.DDRNodeResult).join(m.DDRAttempt,m.DDRAttempt.id==m.DDRNodeResult.attempt_id).where(m.DDRAttempt.run_id==run.id,m.DDRAttempt.step_key.in_(['contracts','draft','quality']))))
        if len(results)!=3:raise GraphFault('AGGREGATE_USAGE_UNCERTAIN')
        usage={key:sum(getattr(row,key) for row in results) for key in ['input_tokens','output_tokens','cost_cents']}
        ledger={key:sum(json.loads(op.result_json)['usage'][key] for op in ops) for key in usage}
        if ledger!=usage or usage['input_tokens']+usage['output_tokens']>spec.limits.total_tokens or usage['cost_cents']>spec.limits.max_cost_cents:raise GraphFault('AGGREGATE_USAGE_INTEGRITY')
        ai_budget.settle_aggregate(db,operation,usage['cost_cents'])
        encoded=canonical({'usage':usage,'node_result_ids':sorted(row.id for row in results),'pricing':ddr_provider.pricing_manifest()})
        if operation.state=='succeeded' and operation.result_json!=encoded:raise GraphFault('AGGREGATE_USAGE_INTEGRITY')
        operation.state='succeeded';operation.result_json=encoded

    @safe_callback
    def review_task(self,spec,draft,validation,key):
        with self.sessions() as db:
            run,actor,_=self._authority(db,spec,True)
            task=commands.review_task(db,actor,run,draft,validation,key)
            self._authority(db,spec);db.commit();return task.id

    @safe_callback
    def approval(self,spec,draft,validation):
        with self.sessions() as db:
            run,actor,_=self._authority(db,spec)
            receipt=commands.approval(db,actor,run,draft,validation)
            self._authority(db,spec);return receipt


def claim(sessions):
    now=clock();token=uuid.uuid4().hex
    with sessions() as db:
        row=db.scalar(select(m.DDRExecution).where((m.DDRExecution.state=='queued')|((m.DDRExecution.state=='running')&(m.DDRExecution.lease_until<=now))).order_by(m.DDRExecution.updated_at,m.DDRExecution.run_id).with_for_update(skip_locked=True).limit(1))
        if not row:return None
        human_cycle=row.state=='queued' and row.phase=='human_decision_recorded'
        if row.attempts>=2 and not human_cycle:
            row.state='failed';row.phase='failed';row.error_code='WORKER_RETRY_LIMIT';row.worker_token=None;row.lease_until=0;row.updated_at=now
            from kestrel.services.auth import audit
            run=db.get(m.DDRRun,row.run_id)
            audit(db,'ddr.worker_retry_limit','denied',category='legal_sme',matter_id=run.matter_id,object_id=run.id)
            db.commit();return None
        changed=db.execute(update(m.DDRExecution).where(m.DDRExecution.run_id==row.run_id,m.DDRExecution.state==row.state,m.DDRExecution.lease_until==row.lease_until).values(state='running',worker_token=token,lease_until=now+LEASE_SECONDS,attempts=1 if human_cycle else row.attempts+1,updated_at=now))
        if changed.rowcount!=1:db.rollback();return None
        db.commit();return row.run_id,token


def private_checkpoint(root,run_id):
    """Protect the per-run directory before SQLite creates DB/WAL files."""
    run_uuid=str(uuid.UUID(run_id))
    base=Path(root).resolve();folder=base/run_uuid;folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    if folder.resolve().parent!=base:raise GraphFault('CHECKPOINT_PATH')
    path=folder/'opaque-checkpoints.sqlite3'
    if not path.exists():
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    if os.name=='nt':
        import csv,io
        result=subprocess.run(['whoami.exe','/user','/fo','csv','/nh'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        sid=next(csv.reader(io.StringIO(result.stdout.decode(errors='replace'))))[1]
        if result.returncode or not re.fullmatch(r'S-1-[0-9-]+',sid):raise GraphFault('CHECKPOINT_ACL')
        descriptor=ctypes.c_void_p();advapi=ctypes.windll.advapi32
        advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p]
        advapi.SetFileSecurityW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p]
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;OICI;FA;;;'+sid+')(A;OICI;FA;;;SY)',1,ctypes.byref(descriptor),None):raise GraphFault('CHECKPOINT_ACL')
        try:
            for target in [folder,path,*[Path(str(path)+suffix) for suffix in ['-wal','-shm','-journal'] if Path(str(path)+suffix).exists()]]:
                if not advapi.SetFileSecurityW(str(target),0x80000004,descriptor):raise GraphFault('CHECKPOINT_ACL')
        finally:
            free=ctypes.windll.kernel32.LocalFree;free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p;free(descriptor)
    else:os.chmod(folder,0o700)
    if os.name!='nt':os.chmod(path,0o600)
    return path


def run_once(sessions,heartbeat=None,checkpoint_root=None,provider_factory=None):
    claimed=claim(sessions)
    if not claimed:return False
    rid,token=claimed
    try:
        if heartbeat:heartbeat()
        with sessions() as db:
            run=db.get(m.DDRRun,rid);spec=make_spec(run);config=json.loads(run.config_json);previous_phase=db.get(m.DDRExecution,rid).phase
        ports=DurableGraphPorts(sessions,rid,token,heartbeat);ports.authorize(spec,'worker.start')
        provider=provider_factory(config) if provider_factory else ddr_provider.factory(config) if config['engine']=='openai' else FakeProvider()
        if type(provider.live) is not bool or provider.live!=(config['engine']=='openai'):raise GraphFault('PROVIDER_ENGINE_MISMATCH')
        from langgraph.checkpoint.sqlite import SqliteSaver
        path=private_checkpoint(checkpoint_root or ROOT/'.runtime/ddr-checkpoints',rid)
        with SqliteSaver.from_conn_string(str(path)) as saver:
            engine=DdrEngine(ports,provider,saver)
            state=engine.status(spec)
            result=engine.resume(spec) if previous_phase=='human_decision_recorded' and state.get('phase')=='awaiting_attorney' else engine.continue_run(spec)
        phase=result.get('phase','failed')
        state={'awaiting_attorney':'awaiting_attorney','internally_approved':'complete','rejected':'rejected','blocked_validation':'failed'}.get(phase,'failed')
        with sessions() as db:
            run,actor,_=ports._authority(db,spec,True)
            ports.finish_budget(db,run,spec)
            if phase=='blocked_validation':
                from kestrel.schemas.review_work import TaskCreate
                from kestrel.services import review_work as rw
                for source_id in sorted({row.source_id for row in commands.evidence_rows(db,run)}):
                    rw.create_task(db,actor,source_id,TaskCreate(stage='ai_coordination',assignee_id=run.requested_by,request_key='ddr-validation-'+run.id+'-'+digest(source_id+run.snapshot_hash)[:32],rationale='DDR quality or citation validation failed. Lawyer follow-up is required; no finding or report approval was created.'),commit=False)
                ports._authority(db,spec)
            execution=db.get(m.DDRExecution,rid);execution.state=state;execution.phase=phase;execution.lease_until=0;execution.worker_token=None;execution.updated_at=clock();execution.error_code=None if state!='failed' else 'VALIDATION_BLOCKED'
            commands.record(db,run,actor.id,'worker_pause' if state=='awaiting_attorney' else 'worker_finish',state);db.commit()
    except Exception as error:
        with sessions() as db:
            execution=db.get(m.DDRExecution,rid)
            if execution and execution.state=='running' and execution.worker_token==token:
                incomplete=db.scalar(select(m.DDRAttempt.id).outerjoin(m.DDRNodeResult,m.DDRNodeResult.attempt_id==m.DDRAttempt.id).where(m.DDRAttempt.run_id==rid,m.DDRNodeResult.id.is_(None)).limit(1))
                code=str(error) if isinstance(error,GraphFault) and re.fullmatch(r'[A-Z_]{3,64}',str(error)) else 'EXECUTION_FAILED'
                execution.state='paused_ambiguous' if incomplete else 'failed';execution.phase=execution.state;execution.error_code=code;execution.lease_until=0;execution.worker_token=None;execution.updated_at=clock()
                run=db.get(m.DDRRun,rid);lifecycle=db.get(m.MatterLifecycle,run.matter_id)
                if lifecycle and lifecycle.frozen:
                    # Freeze closes retained graph content, not operational lease
                    # cleanup. Record sanitized audit metadata without a new DDREvent.
                    from kestrel.services.auth import audit
                    audit(db,'ddr.worker_stop',execution.state,category='legal_sme',matter_id=run.matter_id,object_id=run.id)
                else:commands.record(db,run,None,'worker_stop',execution.state,'Fixed error code: '+code)
                db.commit()
    finally:
        if heartbeat:heartbeat()
    return True
