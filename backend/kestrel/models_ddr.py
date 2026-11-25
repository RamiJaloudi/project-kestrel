"""Durable graph records; imported by models only after base declarations."""
from sqlalchemy import ForeignKey,String,Integer,UniqueConstraint,Index,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from kestrel.models import Base,Identity,SourceWorkScope

class DDRRun(Identity,Base):
    __tablename__='ddr_runs'
    __table_args__=(UniqueConstraint('requested_by','request_key',name='uq_ddr_run_request'),CheckConstraint("engine IN ('offline','openai')",name='ck_ddr_engine'),CheckConstraint("audience IN ('halden','castlegate')",name='ck_ddr_audience'),)
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    requested_by:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key:Mapped[str]=mapped_column(String(128))
    input_hash:Mapped[str]=mapped_column(String(64))
    snapshot_json:Mapped[str]=mapped_column(String)
    snapshot_hash:Mapped[str]=mapped_column(String(64))
    config_json:Mapped[str]=mapped_column(String)
    config_hash:Mapped[str]=mapped_column(String(64))
    graph_version:Mapped[str]=mapped_column(String(96))
    playbook_id:Mapped[str]=mapped_column(ForeignKey('governance_versions.id'))
    title:Mapped[str]=mapped_column(String(160))
    audience:Mapped[str]=mapped_column(String(32))
    kind:Mapped[str]=mapped_column(String(32))
    engine:Mapped[str]=mapped_column(String(16))
    rationale:Mapped[str]=mapped_column(String(1000))
    created_at:Mapped[int]=mapped_column(Integer)
    deadline:Mapped[int]=mapped_column(Integer)

class DDREvidence(SourceWorkScope,Identity,Base):
    __tablename__='ddr_evidence'
    __table_args__=(UniqueConstraint('run_id','finding_id',name='uq_ddr_evidence_finding'),)
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'))
    finding_id:Mapped[str]=mapped_column(String(36))
    revision_id:Mapped[str]=mapped_column(String(36))
    descriptor_json:Mapped[str]=mapped_column(String)
    descriptor_hash:Mapped[str]=mapped_column(String(64))

class DDRExecution(Base):
    __tablename__='ddr_executions'
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'),primary_key=True)
    state:Mapped[str]=mapped_column(String(32),default='queued')
    phase:Mapped[str]=mapped_column(String(64),default='queued')
    lease_until:Mapped[int]=mapped_column(Integer,default=0)
    worker_token:Mapped[str|None]=mapped_column(String(64),nullable=True)
    attempts:Mapped[int]=mapped_column(Integer,default=0)
    error_code:Mapped[str|None]=mapped_column(String(64),nullable=True)
    updated_at:Mapped[int]=mapped_column(Integer)
    __table_args__=(Index('ix_ddr_execution_claim','state','lease_until','updated_at'),)

class DDRArtifact(Identity,Base):
    __tablename__='ddr_artifacts'
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'))
    kind:Mapped[str]=mapped_column(String(32))
    payload_json:Mapped[str]=mapped_column(String)
    content_hash:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[int]=mapped_column(Integer)

class DDRAttempt(Identity,Base):
    __tablename__='ddr_attempts'
    __table_args__=(UniqueConstraint('run_id','step_key',name='uq_ddr_attempt_step'),)
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'))
    step_key:Mapped[str]=mapped_column(String(128))
    input_hash:Mapped[str]=mapped_column(String(64))
    config_hash:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[int]=mapped_column(Integer)

class DDRNodeResult(Identity,Base):
    __tablename__='ddr_node_results'
    __table_args__=(UniqueConstraint('attempt_id',name='uq_ddr_node_result_attempt'),)
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    attempt_id:Mapped[str]=mapped_column(ForeignKey('ddr_attempts.id'))
    artifact_id:Mapped[str]=mapped_column(ForeignKey('ddr_artifacts.id'))
    input_tokens:Mapped[int]=mapped_column(Integer,default=0)
    output_tokens:Mapped[int]=mapped_column(Integer,default=0)
    cost_cents:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[int]=mapped_column(Integer)

class DDRTask(Identity,Base):
    __tablename__='ddr_tasks'
    __table_args__=(UniqueConstraint('run_id','draft_id',name='uq_ddr_task_draft'),)
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'))
    draft_id:Mapped[str]=mapped_column(ForeignKey('ddr_artifacts.id'))
    validation_id:Mapped[str]=mapped_column(ForeignKey('ddr_artifacts.id'))
    created_at:Mapped[int]=mapped_column(Integer)

class DDRDecision(Identity,Base):
    __tablename__='ddr_decisions'
    __table_args__=(UniqueConstraint('task_id','operation',name='uq_ddr_task_operation'),CheckConstraint("operation IN ('approve','reject','revoke')",name='ck_ddr_decision'),)
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    task_id:Mapped[str]=mapped_column(ForeignKey('ddr_tasks.id'))
    actor_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    operation:Mapped[str]=mapped_column(String(16))
    draft_hash:Mapped[str]=mapped_column(String(64))
    report_hash:Mapped[str]=mapped_column(String(64))
    snapshot_hash:Mapped[str]=mapped_column(String(64))
    config_hash:Mapped[str]=mapped_column(String(64))
    rationale:Mapped[str]=mapped_column(String(1000))
    created_at:Mapped[int]=mapped_column(Integer)

class DDREvent(Identity,Base):
    __tablename__='ddr_events'
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'))
    actor_id:Mapped[str|None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    kind:Mapped[str]=mapped_column(String(64))
    outcome:Mapped[str]=mapped_column(String(32))
    rationale:Mapped[str]=mapped_column(String(1000))
    created_at:Mapped[int]=mapped_column(Integer)

class DDRReportLink(Identity,Base):
    __tablename__='ddr_report_links'
    __table_args__=(UniqueConstraint('report_id',name='uq_ddr_report_link'),)
    matter_id:Mapped[str]=mapped_column(ForeignKey('matters.id'))
    run_id:Mapped[str]=mapped_column(ForeignKey('ddr_runs.id'))
    report_id:Mapped[str]=mapped_column(ForeignKey('report_versions.id'))
    task_id:Mapped[str]=mapped_column(ForeignKey('ddr_tasks.id'))
    draft_hash:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[int]=mapped_column(Integer)
