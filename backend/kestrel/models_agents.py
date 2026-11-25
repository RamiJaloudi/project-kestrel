"""Retained agent definitions and source-bound, human-governed impact requests."""
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from kestrel.models import Base, Identity, SourceWorkScope


class AgentProfile(Identity, Base):
    __tablename__ = 'agent_profiles'
    __table_args__ = (UniqueConstraint('matter_id', 'name', name='uq_agent_profile_name'),Index('ix_agent_profile_matter','matter_id'),)
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    name: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileVersion(Identity, Base):
    __tablename__ = 'agent_profile_versions'
    __table_args__ = (UniqueConstraint('profile_id', 'revision', name='uq_agent_profile_revision'), UniqueConstraint('created_by', 'request_key', name='uq_agent_version_request'))
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    profile_id: Mapped[str] = mapped_column(ForeignKey('agent_profiles.id'))
    revision: Mapped[int] = mapped_column(Integer)
    previous_id: Mapped[str | None] = mapped_column(ForeignKey('agent_profile_versions.id'), nullable=True)
    base_published_id: Mapped[str | None] = mapped_column(ForeignKey('agent_profile_versions.id'), nullable=True)
    definition_json: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str] = mapped_column(String(128))
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileEvent(Identity, Base):
    __tablename__ = 'agent_profile_events'
    __table_args__ = (UniqueConstraint('version_id', 'operation', name='uq_agent_version_operation'), CheckConstraint("operation IN ('test','submit','approve','reject','publish','archive')", name='ck_agent_version_event'))
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    version_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_versions.id'))
    operation: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(String(1000))
    report_json: Mapped[str] = mapped_column(String, default='{}')
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileReplacement(Identity, Base):
    __tablename__ = 'agent_profile_replacements'
    __table_args__ = (UniqueConstraint('old_version_id', name='uq_agent_replacement_old'), UniqueConstraint('new_version_id', name='uq_agent_replacement_new'))
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    old_version_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_versions.id'))
    new_version_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_versions.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileImpact(Identity, Base):
    __tablename__ = 'agent_profile_impacts'
    __table_args__ = (UniqueConstraint('replacement_id', 'run_id', name='uq_agent_impact_run'),)
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    replacement_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_replacements.id'))
    run_id: Mapped[str] = mapped_column(ForeignKey('ddr_runs.id'))
    snapshot_json: Mapped[str] = mapped_column(String)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    diff_json: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileImpactItem(Identity, SourceWorkScope, Base):
    __tablename__ = 'agent_profile_impact_items'
    __table_args__ = (UniqueConstraint('impact_id', 'source_id', name='uq_agent_impact_source'),)
    impact_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_impacts.id'))
    run_id: Mapped[str] = mapped_column(ForeignKey('ddr_runs.id'))
    source_snapshot: Mapped[str] = mapped_column(String(64))


class AgentProfileImpactTask(Identity, Base):
    __tablename__ = 'agent_profile_impact_tasks'
    __table_args__ = (UniqueConstraint('impact_id', name='uq_agent_impact_task'),Index('ix_agent_impact_task_matter','matter_id','created_at'),)
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    impact_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_impacts.id'))
    assigned_json: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String(16))
    due_at: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileImpactDecision(Identity, Base):
    __tablename__ = 'agent_profile_impact_decisions'
    __table_args__ = (UniqueConstraint('task_id', 'operation', name='uq_agent_impact_operation'), CheckConstraint("operation IN ('approve','reject','revoke')", name='ck_agent_impact_decision'))
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    task_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_impact_tasks.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    operation: Mapped[str] = mapped_column(String(16))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    target_hash: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[int] = mapped_column(Integer)


class AgentProfileImpactNotification(Identity, Base):
    __tablename__ = 'agent_profile_impact_notifications'
    __table_args__ = (UniqueConstraint('task_id', 'account_id', name='uq_agent_impact_notification'),)
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id'))
    task_id: Mapped[str] = mapped_column(ForeignKey('agent_profile_impact_tasks.id'))
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int] = mapped_column(Integer)
    read_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acknowledged_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
