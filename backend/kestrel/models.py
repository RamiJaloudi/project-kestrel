"""S1 persistence; UUIDs and UTC epoch seconds are portable to PostgreSQL."""
from __future__ import annotations
from uuid import uuid4
from decimal import Decimal
from kestrel.financial_types import ExactFinancialDecimal
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Index, LargeBinary, CheckConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))


class Organization(Identity, Base):
    __tablename__ = "organizations"
    code: Mapped[str] = mapped_column(String(32), unique=True)


class Account(Identity, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("organization_id", "employee_id", name="uq_account_employer_employee"),)
    display_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    employee_id: Mapped[str] = mapped_column(String(40), default=lambda: "EMP-"+uuid4().hex[:16])
    profile_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    password_customized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    username: Mapped[str] = mapped_column(String(128), unique=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True, index=True)


class Role(Identity, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(64), unique=True)


class RoleGrant(Identity, Base):
    __tablename__ = "account_role_grants"
    __table_args__ = (UniqueConstraint("account_id", "role_id"),)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))


class Matter(Identity, Base):
    __tablename__ = "matters"
    name: Mapped[str] = mapped_column(String(128))


class MatterAssignment(Identity, Base):
    __tablename__ = "matter_assignments"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"))
    starts_at: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class EthicalWall(Identity, Base):
    __tablename__ = "ethical_walls"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CleanTeamMembership(Identity, Base):
    __tablename__ = "clean_team_memberships"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"))
    scope: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    starts_at: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class ServerSession(Identity, Base):
    __tablename__ = "server_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    host: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[int] = mapped_column(Integer)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    occurred_at: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32), default="administrative", server_default="administrative")
    matter_id: Mapped[str | None] = mapped_column(ForeignKey("matters.id"), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clean_team_scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Client(Identity, Base):
    __tablename__ = "clients"
    name: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    client_number: Mapped[str] = mapped_column(String(12),unique=True,default=lambda:str(uuid4().int%10**12).zfill(12))


class MatterValidation(Base):
    __tablename__ = "matter_validations"
    __table_args__=(UniqueConstraint('client_id','matter_number',name='uq_client_matter_number'),)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    matter_number: Mapped[str] = mapped_column(String(12),default=lambda:str(uuid4().int%10**12).zfill(12))


class AdministrationDecision(Identity, Base):
    __tablename__ = "administration_decisions"
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    target_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(String(1000))
    occurred_at: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)


class DocumentPolicyVersion(Identity, Base):
    __tablename__ = "document_policy_versions"
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"))
    document_id: Mapped[str] = mapped_column(String(128))
    source_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    classification: Mapped[str] = mapped_column(String(32), default="unclassified")
    classification_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_state: Mapped[str] = mapped_column(String(32), default="candidate")
    released: Mapped[bool] = mapped_column(Boolean, default=False)
    audience: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    signing_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    clean_team_scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sanitized: Mapped[bool] = mapped_column(Boolean, default=False)
    antitrust_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PolicySource(Identity, Base):
    __tablename__ = "policy_sources"
    artifact_id: Mapped[str] = mapped_column(ForeignKey("document_policy_versions.id"))
    source_id: Mapped[str] = mapped_column(ForeignKey("document_policy_versions.id"))
    __table_args__ = (UniqueConstraint("artifact_id", "source_id"),)


class ServiceClient(Identity, Base):
    __tablename__ = "service_clients"
    client_name: Mapped[str] = mapped_column(String(128), unique=True)
    secret_hash: Mapped[str] = mapped_column(String(512))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    scopes: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ServiceToken(Identity, Base):
    __tablename__ = "service_tokens"
    client_id: Mapped[str] = mapped_column(ForeignKey("service_clients.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[int] = mapped_column(Integer)


class GovernanceVersion(Identity, Base):
    __tablename__ = "governance_versions"
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    definition_json: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="draft")
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"),nullable=True)
    review_rationale: Mapped[str | None] = mapped_column(String(1000),nullable=True)
    approved_hash: Mapped[str | None] = mapped_column(String(64),nullable=True)
    revision: Mapped[int] = mapped_column(Integer,default=1)
    tested_hash: Mapped[str | None] = mapped_column(String(64),nullable=True)
    base_playbook_id: Mapped[str | None] = mapped_column(ForeignKey("governance_versions.id",name="fk_playbook_base"),nullable=True)


class AnalysisJob(Identity, Base):
    __tablename__='analysis_jobs'
    __table_args__=(UniqueConstraint('requested_by','idempotency_key',name='uq_job_request_key'),
        Index('uq_job_source_first_analysis','document_version_id',unique=True,postgresql_where=text('impact_task_id IS NULL'),sqlite_where=text('impact_task_id IS NULL')),
        UniqueConstraint('impact_task_id',name='uq_job_impact_task'),
        Index('ix_analysis_jobs_claim','state','available_at','created_at'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    playbook_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'))
    playbook_hash: Mapped[str]=mapped_column(String(64))
    requested_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    idempotency_key: Mapped[str]=mapped_column(String(128))
    rationale: Mapped[str]=mapped_column(String(1000))
    state: Mapped[str]=mapped_column(String(32),default='queued')
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[int]=mapped_column(Integer)
    available_at: Mapped[int]=mapped_column(Integer)
    lease_until: Mapped[int | None]=mapped_column(Integer,nullable=True)
    lease_token: Mapped[str | None]=mapped_column(String(36),nullable=True)
    finished_at: Mapped[int | None]=mapped_column(Integer,nullable=True)
    result_json: Mapped[str | None]=mapped_column(String,nullable=True)
    error_code: Mapped[str | None]=mapped_column(String(64),nullable=True)
    document_version_id: Mapped[str | None]=mapped_column(ForeignKey('source_versions.id',name='fk_job_document_version'),nullable=True)
    engine_name: Mapped[str]=mapped_column(String(32),default='literal',server_default='literal')
    impact_task_id: Mapped[str | None]=mapped_column(ForeignKey('governance_tasks.id',name='fk_job_impact_task'),nullable=True)


class SourceVersion(Identity,Base):
    __tablename__='source_versions'
    __table_args__=(UniqueConstraint('matter_id','logical_key','version_number',name='uq_source_version'),)
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'),unique=True)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    logical_key: Mapped[str]=mapped_column(String(96))
    version_number: Mapped[int]=mapped_column(Integer)
    previous_id: Mapped[str | None]=mapped_column(ForeignKey('source_versions.id'),nullable=True)
    file_name: Mapped[str]=mapped_column(String(160))
    media_type: Mapped[str]=mapped_column(String(96))
    data: Mapped[bytes]=mapped_column(LargeBinary)
    bytes_hash: Mapped[str]=mapped_column(String(64))
    text_hash: Mapped[str]=mapped_column(String(64))
    units_json: Mapped[str]=mapped_column(String)
    language: Mapped[str]=mapped_column(String(12))
    governing_law: Mapped[str]=mapped_column(String(80))
    extraction_status: Mapped[str]=mapped_column(String(32))
    extractor_version: Mapped[str]=mapped_column(String(96))
    uploaded_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)
    wave: Mapped[str]=mapped_column(String(32))


class LogicalDocument(Identity,Base):
    __tablename__='documents'
    __table_args__=(UniqueConstraint('matter_id','logical_key',name='uq_document_matter_key'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    logical_key: Mapped[str]=mapped_column(String(96))
    created_at: Mapped[int]=mapped_column(Integer)


class DocumentVersionLink(Base):
    """Additive projection: never rewrite an immutable source version to attach identity."""
    __tablename__='document_version_links'
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'),primary_key=True)
    document_id: Mapped[str]=mapped_column(ForeignKey('documents.id'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    bytes_hash: Mapped[str]=mapped_column(String(64))


class VdrMappingProfile(Identity,Base):
    __tablename__='vdr_mapping_profiles'
    __table_args__=(UniqueConstraint('matter_id','name','version_number',name='uq_vdr_mapping_version'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    name: Mapped[str]=mapped_column(String(96))
    source_system: Mapped[str]=mapped_column(String(96))
    version_number: Mapped[int]=mapped_column(Integer)
    mapping_json: Mapped[str]=mapped_column(String())
    delimiter: Mapped[str]=mapped_column(String(1))
    author_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class VdrImportBatch(Identity,Base):
    __tablename__='vdr_import_batches'
    __table_args__=(UniqueConstraint('actor_id','request_key',name='uq_vdr_batch_request'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    profile_id: Mapped[str]=mapped_column(ForeignKey('vdr_mapping_profiles.id'))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    csv_hash: Mapped[str]=mapped_column(String(64))
    raw_csv: Mapped[str]=mapped_column(String())
    file_name: Mapped[str]=mapped_column(String(160))
    wave: Mapped[str]=mapped_column(String(32))
    created_at: Mapped[int]=mapped_column(Integer)


class VdrImportRow(Identity,Base):
    __tablename__='vdr_import_rows'
    __table_args__=(UniqueConstraint('batch_id','row_number',name='uq_vdr_batch_row'),)
    batch_id: Mapped[str]=mapped_column(ForeignKey('vdr_import_batches.id'))
    row_number: Mapped[int]=mapped_column(Integer)
    raw_json: Mapped[str]=mapped_column(String())
    mapped_json: Mapped[str]=mapped_column(String())
    errors_json: Mapped[str]=mapped_column(String())
    row_hash: Mapped[str]=mapped_column(String(64))


class DocumentSource(Identity,Base):
    __tablename__='document_sources'
    __table_args__=(UniqueConstraint('import_row_id','source_id',name='uq_vdr_row_source'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    document_id: Mapped[str]=mapped_column(ForeignKey('documents.id'))
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    import_row_id: Mapped[str]=mapped_column(ForeignKey('vdr_import_rows.id'))
    source_system: Mapped[str]=mapped_column(String(96))
    source_external_id: Mapped[str]=mapped_column(String(160))
    vdr_index_number: Mapped[str]=mapped_column(String(160))
    folder_path: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class ClassificationRequest(Identity,Base):
    __tablename__='classification_requests'
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    proposed_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    classification: Mapped[str]=mapped_column(String(32))
    resource_type: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    state: Mapped[str]=mapped_column(String(32),default='pending')
    reviewer_id: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    decision_rationale: Mapped[str | None]=mapped_column(String(1000),nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class SourceFinding(Identity,Base):
    __tablename__='source_findings'
    __table_args__=(UniqueConstraint('job_id','rule_id',name='uq_job_rule'),)
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'),unique=True)
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    job_id: Mapped[str]=mapped_column(ForeignKey('analysis_jobs.id'))
    rule_id: Mapped[str]=mapped_column(String(96))
    summary: Mapped[str]=mapped_column(String(2000))
    evidence_json: Mapped[str]=mapped_column(String)
    playbook_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'))
    playbook_hash: Mapped[str]=mapped_column(String(64))
    model_config: Mapped[str]=mapped_column(String(256))
    taxonomy_version: Mapped[str]=mapped_column(String(96))
    created_at: Mapped[int]=mapped_column(Integer)


class FindingReview(Identity,Base):
    __tablename__='finding_reviews'
    finding_id: Mapped[str]=mapped_column(ForeignKey('source_findings.id'),unique=True)
    reviewer_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    decision: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class ReleasePackage(Identity,Base):
    __tablename__='release_packages'
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'),unique=True)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    title: Mapped[str]=mapped_column(String(160))
    summary: Mapped[str]=mapped_column(String(6000))
    references_json: Mapped[str]=mapped_column(String)
    content_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ReleaseApproval(Identity,Base):
    __tablename__='release_approvals'
    __table_args__=(UniqueConstraint('release_id','kind',name='uq_release_decision'),)
    release_id: Mapped[str]=mapped_column(ForeignKey('release_packages.id'))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    kind: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    content_hash: Mapped[str]=mapped_column(String(64))
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class AIBudgetPeriod(Base):
    __tablename__='ai_budget_periods'
    period: Mapped[str]=mapped_column(String(7),primary_key=True)
    spent_cents: Mapped[int]=mapped_column(Integer,default=0)
    reserved_cents: Mapped[int]=mapped_column(Integer,default=0)


class AIReservation(Base):
    __tablename__='ai_reservations'
    job_id: Mapped[str]=mapped_column(ForeignKey('analysis_jobs.id'),primary_key=True)
    period: Mapped[str]=mapped_column(ForeignKey('ai_budget_periods.period'))
    reserved_cents: Mapped[int]=mapped_column(Integer)
    charged_cents: Mapped[int | None]=mapped_column(Integer,nullable=True)
    state: Mapped[str]=mapped_column(String(32),default='reserved')
    created_at: Mapped[int]=mapped_column(Integer)


class LegalFindingRevision(Identity,Base):
    __tablename__='legal_finding_revisions'
    __table_args__=(UniqueConstraint('record_key','version_number',name='uq_legal_record_version'),)
    record_key: Mapped[str]=mapped_column(String(36))
    version_number: Mapped[int]=mapped_column(Integer)
    previous_id: Mapped[str | None]=mapped_column(ForeignKey('legal_finding_revisions.id'),nullable=True,unique=True)
    candidate_id: Mapped[str | None]=mapped_column(ForeignKey('source_findings.id'),nullable=True)
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'),unique=True)
    summary: Mapped[str]=mapped_column(String(2000))
    topic: Mapped[str]=mapped_column(String(32))
    severity: Mapped[str]=mapped_column(String(32))
    materiality: Mapped[str]=mapped_column(String(32))
    exposure: Mapped[str]=mapped_column(String(32))
    workflow_status: Mapped[str]=mapped_column(String(32))
    action: Mapped[str]=mapped_column(String(2000))
    owner_id: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    due_on: Mapped[str | None]=mapped_column(String(10),nullable=True)
    evidence_json: Mapped[str]=mapped_column(String)
    decision: Mapped[str]=mapped_column(String(32))
    reviewer_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class DocumentReviewVersion(Identity,Base):
    __tablename__='document_review_versions'
    __table_args__=(UniqueConstraint('source_id','version_number',name='uq_document_review_version'),)
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    version_number: Mapped[int]=mapped_column(Integer)
    previous_id: Mapped[str | None]=mapped_column(ForeignKey('document_review_versions.id'),nullable=True,unique=True)
    title: Mapped[str]=mapped_column(String(160))
    counterparty: Mapped[str]=mapped_column(String(160))
    scope: Mapped[str]=mapped_column(String(32))
    coverage_state: Mapped[str]=mapped_column(String(32))
    reviewer_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class ReportVersion(Identity,Base):
    __tablename__='report_versions'
    __table_args__=(UniqueConstraint('report_key','version_number',name='uq_report_version'),)
    report_key: Mapped[str]=mapped_column(String(36))
    version_number: Mapped[int]=mapped_column(Integer)
    previous_id: Mapped[str | None]=mapped_column(ForeignKey('report_versions.id'),nullable=True,unique=True)
    release_id: Mapped[str]=mapped_column(ForeignKey('release_packages.id'),unique=True)
    kind: Mapped[str]=mapped_column(String(32))
    body_json: Mapped[str]=mapped_column(String)
    created_at: Mapped[int]=mapped_column(Integer)


class OCRJob(Identity,Base):
    __tablename__='ocr_jobs'
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'),unique=True)
    requested_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    state: Mapped[str]=mapped_column(String(32),default='queued')
    created_at: Mapped[int]=mapped_column(Integer)
    lease_until: Mapped[int | None]=mapped_column(Integer,nullable=True)
    result_source_id: Mapped[str | None]=mapped_column(ForeignKey('source_versions.id'),nullable=True)
    error_code: Mapped[str | None]=mapped_column(String(64),nullable=True)

class OCRVerification(Base):
    __tablename__='ocr_verifications'
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'),primary_key=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    text_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)

class ProcessingReplacement(Identity,Base):
    __tablename__='processing_replacements'
    old_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'),unique=True)
    new_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'))
    proposed_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    approved_by: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    state: Mapped[str]=mapped_column(String(32),default='pending')
    rationale: Mapped[str]=mapped_column(String(1000))
    decision_rationale: Mapped[str | None]=mapped_column(String(1000),nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class AIOperation(Identity,Base):
    __tablename__='ai_operations'
    __table_args__=(UniqueConstraint('actor_id','request_key',name='uq_ai_operation_request'),)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    kind: Mapped[str]=mapped_column(String(32))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    state: Mapped[str]=mapped_column(String(32),default='pending')
    result_json: Mapped[str | None]=mapped_column(String,nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class OperationReservation(Base):
    __tablename__='operation_reservations'
    operation_id: Mapped[str]=mapped_column(ForeignKey('ai_operations.id'),primary_key=True)
    period: Mapped[str]=mapped_column(ForeignKey('ai_budget_periods.period'))
    reserved_cents: Mapped[int]=mapped_column(Integer)
    charged_cents: Mapped[int | None]=mapped_column(Integer,nullable=True)
    state: Mapped[str]=mapped_column(String(32),default='reserved')
    created_at: Mapped[int]=mapped_column(Integer)


class QuestionAnswer(Identity,Base):
    __tablename__='question_answers'
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    question: Mapped[str]=mapped_column(String(1000))
    result_json: Mapped[str]=mapped_column(String)
    created_at: Mapped[int]=mapped_column(Integer)


class CollaborationMessage(Identity,Base):
    __tablename__='collaboration_messages'
    section_index: Mapped[int | None]=mapped_column(Integer,nullable=True)
    release_id: Mapped[str]=mapped_column(ForeignKey('release_packages.id'))
    parent_id: Mapped[str | None]=mapped_column(ForeignKey('collaboration_messages.id'),nullable=True)
    author_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    kind: Mapped[str]=mapped_column(String(32))
    body: Mapped[str]=mapped_column(String(4000))
    body_hash: Mapped[str]=mapped_column(String(64))
    internal_draft: Mapped[bool]=mapped_column(Boolean)
    created_at: Mapped[int]=mapped_column(Integer)


class CollaborationApproval(Base):
    __tablename__='collaboration_approvals'
    message_id: Mapped[str]=mapped_column(ForeignKey('collaboration_messages.id'),primary_key=True)
    kind: Mapped[str]=mapped_column(String(32),primary_key=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    body_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class SourceAccessGrant(Identity,Base):
    __tablename__='source_access_grants'
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    proposed_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    approved_by: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    decision_rationale: Mapped[str | None]=mapped_column(String(1000),nullable=True)
    revocation_rationale: Mapped[str | None]=mapped_column(String(1000),nullable=True)
    revoked_by: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    revoked_at: Mapped[int | None]=mapped_column(Integer,nullable=True)
    state: Mapped[str]=mapped_column(String(32),default='pending')
    expires_at: Mapped[int]=mapped_column(Integer)
    created_at: Mapped[int]=mapped_column(Integer)


class ClientSubmission(Identity,Base):
    __tablename__='client_submissions'
    __table_args__=(UniqueConstraint('matter_id','uploaded_by','bytes_hash',name='uq_client_submission_bytes'),)
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'),unique=True)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    uploaded_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    file_name: Mapped[str]=mapped_column(String(160))
    bytes_hash: Mapped[str]=mapped_column(String(64))
    data: Mapped[bytes | None]=mapped_column(LargeBinary,nullable=True)
    parsed_json: Mapped[str | None]=mapped_column(String,nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class SubmissionAcceptance(Base):
    __tablename__='submission_acceptances'
    submission_id: Mapped[str]=mapped_column(ForeignKey('client_submissions.id'),primary_key=True)
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class MatterLifecycle(Base):
    __tablename__='matter_lifecycle'
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'),primary_key=True)
    frozen: Mapped[bool]=mapped_column(Boolean,default=False)
    external_closed: Mapped[bool]=mapped_column(Boolean,default=False)
    legal_hold: Mapped[bool]=mapped_column(Boolean,default=False)
    firm_retention: Mapped[str]=mapped_column(String(96),default='indefinite_pending_approved_retention_schedule')


class LifecycleDecision(Identity,Base):
    __tablename__='lifecycle_decisions'
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    kind: Mapped[str]=mapped_column(String(32))
    proposed_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    approved_by: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    state: Mapped[str]=mapped_column(String(32),default='pending')
    payload_json: Mapped[str]=mapped_column(String)
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    decision_rationale: Mapped[str | None]=mapped_column(String(1000),nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class SourceArchive(Identity,Base):
    __tablename__='source_archives'
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    storage_key: Mapped[str]=mapped_column(String(36),unique=True)
    protected_hash: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str]=mapped_column(String(64))
    manifest_json: Mapped[str]=mapped_column(String)
    created_at: Mapped[int]=mapped_column(Integer)


class WallControl(Identity,Base):
    __tablename__='wall_controls'
    __table_args__=(Index('ix_wall_controls_scope','client_id','matter_id'),Index('ix_wall_controls_account','account_id'),CheckConstraint("entry_type IN ('restriction','relationship','retirement')",name='ck_wall_control_type'),CheckConstraint('expires_at IS NULL OR expires_at>starts_at',name='ck_wall_control_term'))
    client_id: Mapped[str]=mapped_column(ForeignKey('clients.id'))
    matter_id: Mapped[str | None]=mapped_column(ForeignKey('matters.id'),nullable=True)
    entry_type: Mapped[str]=mapped_column(String(32))
    account_id: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    role_name: Mapped[str | None]=mapped_column(String(64),nullable=True)
    relationship_kind: Mapped[str | None]=mapped_column(String(64),nullable=True)
    starts_at: Mapped[int]=mapped_column(Integer)
    expires_at: Mapped[int | None]=mapped_column(Integer,nullable=True)
    proposed_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    retire_id: Mapped[str | None]=mapped_column(ForeignKey('wall_controls.id'),nullable=True)
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class WallControlDecision(Base):
    __tablename__='wall_control_decisions'
    control_id: Mapped[str]=mapped_column(ForeignKey('wall_controls.id'),primary_key=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    decision: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class WallCheckRecord(Identity,Base):
    __tablename__='wall_check_records'
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    subject_id: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    client_id: Mapped[str]=mapped_column(ForeignKey('clients.id'))
    matter_id: Mapped[str | None]=mapped_column(ForeignKey('matters.id'),nullable=True)
    result_json: Mapped[str]=mapped_column(String)
    created_at: Mapped[int]=mapped_column(Integer)


class ImpactPublication(Identity,Base):
    __tablename__='impact_publications'
    target_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'),unique=True)
    base_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'))
    state: Mapped[str]=mapped_column(String(32),default='pending')
    created_at: Mapped[int]=mapped_column(Integer)
    processed_at: Mapped[int | None]=mapped_column(Integer,nullable=True)


class ImpactSnapshot(Identity,Base):
    __tablename__='impact_snapshots'
    __table_args__=(UniqueConstraint('target_id','source_id','snapshot_hash',name='uq_impact_snapshot'),)
    target_id: Mapped[str]=mapped_column(ForeignKey('governance_versions.id'))
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    baseline_job_id: Mapped[str]=mapped_column(ForeignKey('analysis_jobs.id',use_alter=True,name='fk_impact_baseline'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    snapshot_json: Mapped[str]=mapped_column(String)
    diff_json: Mapped[str]=mapped_column(String)
    created_at: Mapped[int]=mapped_column(Integer)


class GovernanceTask(Identity,Base):
    __tablename__='governance_tasks'
    impact_id: Mapped[str]=mapped_column(ForeignKey('impact_snapshots.id'),unique=True)
    assigned_json: Mapped[str]=mapped_column(String)
    claimed_by: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    state: Mapped[str]=mapped_column(String(32),default='open')
    priority: Mapped[str]=mapped_column(String(32))
    created_at: Mapped[int]=mapped_column(Integer)
    due_at: Mapped[int]=mapped_column(Integer)


class ImpactDecision(Identity,Base):
    __tablename__='impact_decisions'
    task_id: Mapped[str]=mapped_column(ForeignKey('governance_tasks.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    operation: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    idempotency_key: Mapped[str]=mapped_column(String(128))
    engine_name: Mapped[str]=mapped_column(String(32))
    created_at: Mapped[int]=mapped_column(Integer)


class TaskNotification(Identity,Base):
    __tablename__='task_notifications'
    __table_args__=(UniqueConstraint('task_id','account_id',name='uq_task_recipient'),)
    task_id: Mapped[str]=mapped_column(ForeignKey('governance_tasks.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    state: Mapped[str]=mapped_column(String(32),default='unread')
    escalated_at: Mapped[int | None]=mapped_column(Integer,nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class FindingReconciliation(Identity,Base):
    __tablename__='finding_reconciliations'
    task_id: Mapped[str]=mapped_column(ForeignKey('governance_tasks.id'))
    old_finding_id: Mapped[str | None]=mapped_column(ForeignKey('source_findings.id'),nullable=True)
    new_finding_id: Mapped[str | None]=mapped_column(ForeignKey('source_findings.id'),nullable=True)
    rule_id: Mapped[str]=mapped_column(String(96))
    change: Mapped[str]=mapped_column(String(32))
    created_at: Mapped[int]=mapped_column(Integer)


class ReconciliationDecision(Identity,Base):
    __tablename__='reconciliation_decisions'
    comparison_id: Mapped[str]=mapped_column(ForeignKey('finding_reconciliations.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    disposition: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class TaskClosure(Identity,Base):
    __tablename__='task_closures'
    task_id: Mapped[str]=mapped_column(ForeignKey('governance_tasks.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    release_handling_rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class PolicyRecipient(Identity,Base):
    __tablename__='policy_recipients'
    __table_args__=(UniqueConstraint('policy_id','account_id',name='uq_policy_recipient'),)
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))


class TrackerImport(Identity,Base):
    __tablename__='tracker_imports'
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    uploaded_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    register: Mapped[str]=mapped_column(String(32))
    file_name: Mapped[str]=mapped_column(String(160))
    file_hash: Mapped[str]=mapped_column(String(64))
    data: Mapped[bytes]=mapped_column(LargeBinary)
    proposals_json: Mapped[str]=mapped_column(String)
    created_at: Mapped[int]=mapped_column(Integer)


class TrackerImportApplication(Identity,Base):
    __tablename__='tracker_import_applications'
    import_id: Mapped[str]=mapped_column(ForeignKey('tracker_imports.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    selection_json: Mapped[str]=mapped_column(String)
    result_json: Mapped[str]=mapped_column(String)
    rationale: Mapped[str]=mapped_column(String(1000))
    idempotency_key: Mapped[str]=mapped_column(String(128))
    created_at: Mapped[int]=mapped_column(Integer)


class TrackerExport(Identity,Base):
    __tablename__='tracker_exports'
    release_id: Mapped[str]=mapped_column(ForeignKey('release_packages.id'),unique=True)
    register: Mapped[str]=mapped_column(String(32))
    body_json: Mapped[str]=mapped_column(String)
    data: Mapped[bytes]=mapped_column(LargeBinary)
    bytes_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ChecklistVersion(Identity,Base):
    __tablename__='checklist_versions'
    __table_args__=(UniqueConstraint('matter_id','version_number',name='uq_checklist_version'),UniqueConstraint('author_id','request_key',name='uq_checklist_request'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    version_number: Mapped[int]=mapped_column(Integer)
    previous_id: Mapped[str | None]=mapped_column(ForeignKey('checklist_versions.id'),nullable=True)
    author_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    definition_json: Mapped[str]=mapped_column(String)
    content_hash: Mapped[str]=mapped_column(String(64))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ChecklistVersionDecision(Identity,Base):
    __tablename__='checklist_version_decisions'
    __table_args__=(UniqueConstraint('version_id','revision',name='uq_checklist_decision'),)
    version_id: Mapped[str]=mapped_column(ForeignKey('checklist_versions.id'))
    revision: Mapped[int]=mapped_column(Integer)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    state: Mapped[str]=mapped_column(String(32))
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class ChecklistCoverageDecision(Identity,Base):
    __tablename__='checklist_coverage_decisions'
    __table_args__=(UniqueConstraint('version_id','item_id','revision',name='uq_checklist_coverage'),UniqueConstraint('request_id',name='uq_checklist_na_decision'))
    version_id: Mapped[str]=mapped_column(ForeignKey('checklist_versions.id'))
    item_id: Mapped[str]=mapped_column(String(96))
    revision: Mapped[int]=mapped_column(Integer)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    owner_id: Mapped[str | None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    kind: Mapped[str]=mapped_column(String(32))
    status: Mapped[str]=mapped_column(String(40))
    source_ids_json: Mapped[str]=mapped_column(String)
    finding_ids_json: Mapped[str]=mapped_column(String)
    source_snapshots_json: Mapped[str]=mapped_column(String)
    missing_information: Mapped[str]=mapped_column(String(1000))
    rationale: Mapped[str]=mapped_column(String(1000))
    request_id: Mapped[str | None]=mapped_column(ForeignKey('checklist_coverage_decisions.id'),nullable=True)
    created_at: Mapped[int]=mapped_column(Integer)


class SourceWorkScope:
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    retained_classification: Mapped[str]=mapped_column(String(32))
    retained_scope: Mapped[str | None]=mapped_column(String(128),nullable=True)


class RecordCustodian(Identity,SourceWorkScope,Base):
    __tablename__='record_custodians'
    __table_args__=(Index('ix_custodian_source','source_id'),)
    display_name: Mapped[str]=mapped_column(String(160))
    custodian_type: Mapped[str]=mapped_column(String(32))
    upn: Mapped[str | None]=mapped_column(String(254),nullable=True)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class DocumentCustodian(Identity,SourceWorkScope,Base):
    __tablename__='document_custodians'
    __table_args__=(UniqueConstraint('created_by','request_key',name='uq_custodian_request'),Index('ix_document_custodian_source','source_id'),)
    document_id: Mapped[str]=mapped_column(ForeignKey('documents.id'))
    custodian_id: Mapped[str]=mapped_column(ForeignKey('record_custodians.id'))
    custody_role: Mapped[str]=mapped_column(String(40))
    provenance: Mapped[str]=mapped_column(String(1000))
    effective_from: Mapped[int | None]=mapped_column(Integer,nullable=True)
    effective_until: Mapped[int | None]=mapped_column(Integer,nullable=True)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class CustodianLinkRetirement(Identity,SourceWorkScope,Base):
    __tablename__='custodian_link_retirements'
    link_id: Mapped[str]=mapped_column(ForeignKey('document_custodians.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class DocumentParty(Identity,SourceWorkScope,Base):
    __tablename__='document_parties'
    __table_args__=(UniqueConstraint('created_by','request_key',name='uq_party_request'),Index('ix_doc_party_source','source_id'),)
    document_id: Mapped[str]=mapped_column(ForeignKey('documents.id'))
    name: Mapped[str]=mapped_column(String(160))
    party_role: Mapped[str]=mapped_column(String(64))
    provenance: Mapped[str]=mapped_column(String(1000))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewTask(Identity,SourceWorkScope,Base):
    __tablename__='review_tasks'
    __table_args__=(UniqueConstraint('created_by','request_key',name='uq_review_task_request'),Index('ix_review_task_source','source_id'),)
    document_id: Mapped[str]=mapped_column(ForeignKey('documents.id'))
    stage: Mapped[str]=mapped_column(String(32))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    source_snapshot_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewTaskEvent(Identity,SourceWorkScope,Base):
    __tablename__='review_task_events'
    __table_args__=(UniqueConstraint('task_id','revision',name='uq_review_task_revision'),UniqueConstraint('task_id','actor_id','request_key',name='uq_review_event_request'),)
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    revision: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(32))
    from_state: Mapped[str | None]=mapped_column(String(32),nullable=True)
    to_state: Mapped[str]=mapped_column(String(32))
    assignee_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    due_at: Mapped[int | None]=mapped_column(Integer,nullable=True)
    rationale: Mapped[str]=mapped_column(String(1000))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    occurred_at: Mapped[int]=mapped_column(Integer)


class ReviewTaskNotification(Identity,Base):
    __tablename__='review_task_notifications'
    __table_args__=(UniqueConstraint('event_id','account_id',name='uq_review_task_notification'),Index('ix_review_notification_inbox','account_id','matter_id','created_at'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    event_id: Mapped[str]=mapped_column(ForeignKey('review_task_events.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewNotificationRead(Identity,Base):
    __tablename__='review_notification_reads'
    notification_id: Mapped[str]=mapped_column(ForeignKey('review_task_notifications.id'),unique=True)
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    occurred_at: Mapped[int]=mapped_column(Integer)


class SlaCalendarVersion(Identity,Base):
    __tablename__='sla_calendars'
    __table_args__=(UniqueConstraint('matter_id','name','version_number',name='uq_sla_calendar_version'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    name: Mapped[str]=mapped_column(String(96))
    version_number: Mapped[int]=mapped_column(Integer)
    timezone: Mapped[str]=mapped_column(String(96))
    tzdata_version: Mapped[str]=mapped_column(String(32))
    weekdays_json: Mapped[str]=mapped_column(String())
    holidays_json: Mapped[str]=mapped_column(String())
    start_minute: Mapped[int]=mapped_column(Integer)
    end_minute: Mapped[int]=mapped_column(Integer)
    author_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewSlaVersion(Identity,Base):
    __tablename__='review_sla_policies'
    __table_args__=(UniqueConstraint('matter_id','name','version_number',name='uq_review_sla_version'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    calendar_id: Mapped[str]=mapped_column(ForeignKey('sla_calendars.id'))
    name: Mapped[str]=mapped_column(String(96))
    version_number: Mapped[int]=mapped_column(Integer)
    stage: Mapped[str]=mapped_column(String(32))
    max_business_seconds: Mapped[int]=mapped_column(Integer)
    exclude_paused: Mapped[bool]=mapped_column(Boolean)
    idle_timeout_seconds: Mapped[int]=mapped_column(Integer)
    author_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewSlaDecision(Identity,Base):
    __tablename__='review_sla_decisions'
    __table_args__=(UniqueConstraint('policy_id','revision',name='uq_review_sla_decision'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    policy_id: Mapped[str]=mapped_column(ForeignKey('review_sla_policies.id'))
    revision: Mapped[int]=mapped_column(Integer)
    state: Mapped[str]=mapped_column(String(32))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewSlaBinding(Identity,SourceWorkScope,Base):
    __tablename__='review_sla_bindings'
    __table_args__=(UniqueConstraint('event_id',name='uq_review_sla_binding_event'),)
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    assignment_event_id: Mapped[str]=mapped_column(ForeignKey('review_task_events.id'))
    policy_id: Mapped[str]=mapped_column(ForeignKey('review_sla_policies.id'))
    event_id: Mapped[str]=mapped_column(ForeignKey('review_task_events.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class ReviewSession(Identity,SourceWorkScope,Base):
    __tablename__='review_sessions'
    __table_args__=(UniqueConstraint('account_id','request_key',name='uq_review_session_request'),Index('ix_review_session_task','task_id'),)
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    assignment_event_id: Mapped[str]=mapped_column(ForeignKey('review_task_events.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    idle_timeout_seconds: Mapped[int]=mapped_column(Integer)
    started_at: Mapped[int]=mapped_column(Integer)


class ReviewSessionReceipt(Identity,SourceWorkScope,Base):
    __tablename__='review_session_receipts'
    __table_args__=(UniqueConstraint('session_id','sequence',name='uq_review_receipt_sequence'),UniqueConstraint('session_id','request_key',name='uq_review_receipt_request'),)
    session_id: Mapped[str]=mapped_column(ForeignKey('review_sessions.id'))
    sequence: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(24))
    mode: Mapped[str]=mapped_column(String(24))
    interaction: Mapped[bool]=mapped_column(Boolean)
    interval_start_at: Mapped[int]=mapped_column(Integer)
    interval_end_at: Mapped[int]=mapped_column(Integer)
    last_interaction_at: Mapped[int]=mapped_column(Integer)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    occurred_at: Mapped[int]=mapped_column(Integer)


class ReviewSessionLease(Base):
    """Mutable technical pointer; evidence is retained in immutable roots/receipts."""
    __tablename__='review_session_leases'
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'),primary_key=True)
    session_id: Mapped[str]=mapped_column(ForeignKey('review_sessions.id'),unique=True)
    lease_until: Mapped[int]=mapped_column(Integer)


class ChecklistSectionRecord(Identity,Base):
    __tablename__='checklist_sections'
    __table_args__=(UniqueConstraint('version_id','section_code',name='uq_checklist_section_record'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    version_id: Mapped[str]=mapped_column(ForeignKey('checklist_versions.id'))
    section_code: Mapped[str]=mapped_column(String(1))
    title: Mapped[str]=mapped_column(String(400))
    page_start: Mapped[int]=mapped_column(Integer)
    page_end: Mapped[int]=mapped_column(Integer)

class ChecklistItemRecord(Identity,Base):
    __tablename__='checklist_items'
    __table_args__=(UniqueConstraint('version_id','item_code',name='uq_checklist_item_record'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    version_id: Mapped[str]=mapped_column(ForeignKey('checklist_versions.id'))
    section_id: Mapped[str]=mapped_column(ForeignKey('checklist_sections.id'))
    item_code: Mapped[str]=mapped_column(String(96))
    short_abstract: Mapped[str]=mapped_column(String(400))
    source_page: Mapped[int]=mapped_column(Integer)
    definition_hash: Mapped[str]=mapped_column(String(64))

class ChecklistCoverageProjection(Identity,Base):
    __tablename__='checklist_coverage_versions'
    coverage_event_id: Mapped[str]=mapped_column(ForeignKey('checklist_coverage_decisions.id'),unique=True)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    item_id: Mapped[str]=mapped_column(ForeignKey('checklist_items.id'))
    revision: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(40))
    kind: Mapped[str]=mapped_column(String(32))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)

class DocumentChecklistLink(Identity,Base):
    __tablename__='document_checklist_links'
    __table_args__=(UniqueConstraint('coverage_event_id','source_id',name='uq_document_checklist_link'),Index('ix_doc_checklist_source','source_id'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    coverage_event_id: Mapped[str]=mapped_column(ForeignKey('checklist_coverage_decisions.id'))
    item_id: Mapped[str]=mapped_column(ForeignKey('checklist_items.id'))
    source_id: Mapped[str]=mapped_column(ForeignKey('source_versions.id'))
    bytes_hash: Mapped[str]=mapped_column(String(64))

class ChecklistFindingLink(Identity,Base):
    __tablename__='checklist_finding_links'
    __table_args__=(UniqueConstraint('coverage_event_id','finding_reference',name='uq_checklist_finding_link'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    coverage_event_id: Mapped[str]=mapped_column(ForeignKey('checklist_coverage_decisions.id'))
    item_id: Mapped[str]=mapped_column(ForeignKey('checklist_items.id'))
    finding_reference: Mapped[str]=mapped_column(String(36))
    candidate_id: Mapped[str | None]=mapped_column(ForeignKey('source_findings.id'),nullable=True)
    revision_id: Mapped[str | None]=mapped_column(ForeignKey('legal_finding_revisions.id'),nullable=True)

class ChecklistRequestEvent(Identity,Base):
    __tablename__='checklist_request_events'
    __table_args__=(UniqueConstraint('item_id','revision',name='uq_checklist_request_revision'),UniqueConstraint('actor_id','request_key',name='uq_checklist_request_event'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    item_id: Mapped[str]=mapped_column(ForeignKey('checklist_items.id'))
    revision: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(32))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    due_date: Mapped[str | None]=mapped_column(String(10),nullable=True)
    wave: Mapped[str]=mapped_column(String(32))
    workstream: Mapped[str]=mapped_column(String(96))
    jurisdiction: Mapped[str]=mapped_column(String(160))
    notes: Mapped[str]=mapped_column(String(2000))
    request_reference: Mapped[str]=mapped_column(String(160))
    disclosure_reference: Mapped[str]=mapped_column(String(160))
    import_row_id: Mapped[str | None]=mapped_column(ForeignKey('vdr_import_rows.id'),nullable=True)
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)

class ChecklistRequestEvidence(Identity,SourceWorkScope,Base):
    __tablename__='checklist_request_evidence'
    __table_args__=(UniqueConstraint('request_event_id','source_id',name='uq_checklist_request_evidence'),)
    request_event_id: Mapped[str]=mapped_column(ForeignKey('checklist_request_events.id'))

class ReportChecklistSnapshot(Identity,Base):
    __tablename__='report_checklist_snapshots'
    __table_args__=(UniqueConstraint('report_id','coverage_event_id',name='uq_report_checklist_snapshot'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    report_id: Mapped[str]=mapped_column(ForeignKey('report_versions.id'))
    coverage_event_id: Mapped[str]=mapped_column(ForeignKey('checklist_coverage_decisions.id'))

class ReviewSlaEscalationPlan(Identity,SourceWorkScope,Base):
    __tablename__='review_sla_escalation_plans'
    __table_args__=(UniqueConstraint('task_id','version_number',name='uq_sla_escalation_version'),UniqueConstraint('created_by','request_key',name='uq_sla_escalation_request'),)
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    sla_binding_id: Mapped[str]=mapped_column(ForeignKey('review_sla_bindings.id'))
    version_number: Mapped[int]=mapped_column(Integer)
    warning_percent: Mapped[int]=mapped_column(Integer)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    source_snapshot_hash: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str]=mapped_column(String(64))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)

class ReviewSlaPlanRecipient(Identity,Base):
    __tablename__='review_sla_plan_recipients'
    __table_args__=(UniqueConstraint('plan_id','account_id',name='uq_sla_plan_recipient'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    plan_id: Mapped[str]=mapped_column(ForeignKey('review_sla_escalation_plans.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))

class ReviewSlaPlanDecision(Identity,SourceWorkScope,Base):
    __tablename__='review_sla_plan_decisions'
    plan_id: Mapped[str]=mapped_column(ForeignKey('review_sla_escalation_plans.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)

class ReviewSlaAlert(Identity,SourceWorkScope,Base):
    __tablename__='review_sla_alerts'
    __table_args__=(UniqueConstraint('plan_id','level',name='uq_review_sla_alert'),)
    plan_id: Mapped[str]=mapped_column(ForeignKey('review_sla_escalation_plans.id'))
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    level: Mapped[str]=mapped_column(String(16))
    business_elapsed_seconds: Mapped[int]=mapped_column(Integer)
    budget_seconds: Mapped[int]=mapped_column(Integer)
    created_at: Mapped[int]=mapped_column(Integer)

class ReviewSlaAlertRecipient(Identity,Base):
    __tablename__='review_sla_alert_recipients'
    __table_args__=(UniqueConstraint('alert_id','account_id',name='uq_sla_alert_recipient'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    alert_id: Mapped[str]=mapped_column(ForeignKey('review_sla_alerts.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))

class ReviewSlaAlertRead(Identity,Base):
    __tablename__='review_sla_alert_reads'
    recipient_id: Mapped[str]=mapped_column(ForeignKey('review_sla_alert_recipients.id'),unique=True)
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    occurred_at: Mapped[int]=mapped_column(Integer)

class ReviewSlaAlertDisposition(Identity,SourceWorkScope,Base):
    __tablename__='review_sla_alert_dispositions'
    __table_args__=(UniqueConstraint('alert_id','revision',name='uq_sla_alert_disposition'),)
    alert_id: Mapped[str]=mapped_column(ForeignKey('review_sla_alerts.id'))
    revision: Mapped[int]=mapped_column(Integer)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    operation: Mapped[str]=mapped_column(String(16))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)

class ReviewSlaAlertCursor(Base):
    __tablename__='review_sla_alert_cursor'
    id: Mapped[str]=mapped_column(String(32),primary_key=True)
    last_plan_id: Mapped[str | None]=mapped_column(String(36),nullable=True)


class ContentLabelAssertion(Identity,SourceWorkScope,Base):
    __tablename__='content_label_assertions'
    __table_args__=(UniqueConstraint('source_id','version_number',name='uq_content_label_version'),UniqueConstraint('created_by','request_key',name='uq_content_label_request'),)
    version_number: Mapped[int]=mapped_column(Integer)
    labels_json: Mapped[str]=mapped_column(String)
    label_scope: Mapped[str | None]=mapped_column(String(128),nullable=True)
    unit_number: Mapped[int | None]=mapped_column(Integer,nullable=True)
    start_offset: Mapped[int | None]=mapped_column(Integer,nullable=True)
    end_offset: Mapped[int | None]=mapped_column(Integer,nullable=True)
    evidence_hash: Mapped[str]=mapped_column(String(64))
    source_bytes_hash: Mapped[str]=mapped_column(String(64))
    source_text_hash: Mapped[str]=mapped_column(String(64))
    provenance_kind: Mapped[str]=mapped_column(String(24))
    classifier_version: Mapped[str]=mapped_column(String(64))
    confidence: Mapped[str | None]=mapped_column(String(16),nullable=True)
    rationale: Mapped[str]=mapped_column(String(1000))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)

class ContentLabelDecision(Identity,SourceWorkScope,Base):
    __tablename__='content_label_decisions'
    __table_args__=(UniqueConstraint('assertion_id','sequence',name='uq_content_label_decision'),)
    assertion_id: Mapped[str]=mapped_column(ForeignKey('content_label_assertions.id'))
    sequence: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(24))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)

class ContentLabelImpact(Identity,SourceWorkScope,Base):
    __tablename__='content_label_impacts'
    __table_args__=(UniqueConstraint('assertion_id','policy_id',name='uq_content_label_impact'),)
    assertion_id: Mapped[str]=mapped_column(ForeignKey('content_label_assertions.id'))
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'))
    kind: Mapped[str]=mapped_column(String(48))
    created_at: Mapped[int]=mapped_column(Integer)


class DisclosurePlan(Identity,SourceWorkScope,Base):
    __tablename__='disclosure_plans'
    __table_args__=(UniqueConstraint('created_by','request_key',name='uq_disclosure_plan_request'),)
    audience: Mapped[str]=mapped_column(String(32))
    title: Mapped[str]=mapped_column(String(160))
    purpose: Mapped[str]=mapped_column(String(500))
    expires_at: Mapped[int]=mapped_column(Integer)
    spans_json: Mapped[str]=mapped_column(String)
    source_snapshot: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    created_at: Mapped[int]=mapped_column(Integer)

class DisclosurePlanReview(Identity,SourceWorkScope,Base):
    __tablename__='disclosure_plan_reviews'
    plan_id: Mapped[str]=mapped_column(ForeignKey('disclosure_plans.id'),unique=True)
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)

class DisclosureArtifact(Identity,SourceWorkScope,Base):
    __tablename__='disclosure_artifacts'
    plan_id: Mapped[str]=mapped_column(ForeignKey('disclosure_plans.id'),unique=True)
    policy_id: Mapped[str]=mapped_column(ForeignKey('document_policy_versions.id'),unique=True)
    data: Mapped[bytes]=mapped_column(LargeBinary)
    units_json: Mapped[str]=mapped_column(String)
    manifest_json: Mapped[str]=mapped_column(String)
    manifest_hash: Mapped[str]=mapped_column(String(64))
    bytes_hash: Mapped[str]=mapped_column(String(64))
    text_hash: Mapped[str]=mapped_column(String(64))
    bundle_hash: Mapped[str]=mapped_column(String(64))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)

class DisclosureValidation(Identity,SourceWorkScope,Base):
    __tablename__='disclosure_validations'
    artifact_id: Mapped[str]=mapped_column(ForeignKey('disclosure_artifacts.id'),unique=True)
    bytes_hash: Mapped[str]=mapped_column(String(64))
    manifest_hash: Mapped[str]=mapped_column(String(64))
    report_json: Mapped[str]=mapped_column(String)
    validator_version: Mapped[str]=mapped_column(String(64))
    occurred_at: Mapped[int]=mapped_column(Integer)

class DisclosureDecision(Identity,SourceWorkScope,Base):
    __tablename__='disclosure_decisions'
    __table_args__=(UniqueConstraint('artifact_id','operation',name='uq_disclosure_decision'),)
    artifact_id: Mapped[str]=mapped_column(ForeignKey('disclosure_artifacts.id'))
    operation: Mapped[str]=mapped_column(String(24))
    bundle_hash: Mapped[str]=mapped_column(String(64))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class ContentImpactTask(Identity,SourceWorkScope,Base):
    __tablename__='content_impact_tasks'
    impact_id: Mapped[str]=mapped_column(ForeignKey('content_label_impacts.id'),unique=True)
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'),unique=True)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class SourceEmbedding(Identity,SourceWorkScope,Base):
    __tablename__='source_embeddings'
    __table_args__=(UniqueConstraint('source_id','source_snapshot','unit_number','start_offset','end_offset','model_version',name='uq_source_embedding'),)
    source_snapshot: Mapped[str]=mapped_column(String(64))
    unit_number: Mapped[int]=mapped_column(Integer)
    start_offset: Mapped[int]=mapped_column(Integer)
    end_offset: Mapped[int]=mapped_column(Integer)
    text_hash: Mapped[str]=mapped_column(String(64))
    model_version: Mapped[str]=mapped_column(String(96))
    vector_json: Mapped[str]=mapped_column(String)
    vector_hash: Mapped[str]=mapped_column(String(64))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    operation_id: Mapped[str]=mapped_column(ForeignKey('ai_operations.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class FinancialFact(Identity,SourceWorkScope,Base):
    __tablename__='financial_facts'
    __table_args__=(UniqueConstraint('evidence_key',name='uq_financial_evidence'),)
    evidence_key: Mapped[str]=mapped_column(String(64))
    reference_kind: Mapped[str]=mapped_column(String(16))
    reference_id: Mapped[str]=mapped_column(String(36))
    reference_snapshot: Mapped[str]=mapped_column(String(64))
    entity: Mapped[str]=mapped_column(String(160))
    metric: Mapped[str]=mapped_column(String(128))
    period_start: Mapped[str]=mapped_column(String(10))
    period_end: Mapped[str]=mapped_column(String(10))
    currency: Mapped[str]=mapped_column(String(3))
    scale: Mapped[str]=mapped_column(String(16))
    accounting_basis: Mapped[str]=mapped_column(String(128))
    consolidation_scope: Mapped[str]=mapped_column(String(128))
    amount_text: Mapped[str]=mapped_column(String(64))
    amount: Mapped[Decimal]=mapped_column(ExactFinancialDecimal())
    evidence_json: Mapped[str]=mapped_column(String)
    content_hash: Mapped[str]=mapped_column(String(64))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class FinancialFactDecision(Identity,SourceWorkScope,Base):
    __tablename__='financial_fact_decisions'
    __table_args__=(UniqueConstraint('fact_id','operation',name='uq_financial_decision'),)
    fact_id: Mapped[str]=mapped_column(ForeignKey('financial_facts.id'))
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class FinancialAccessGate(Identity,Base):
    __tablename__='financial_access_gates'
    __table_args__=(UniqueConstraint('matter_id','revision',name='uq_financial_gate_revision'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    revision: Mapped[int]=mapped_column(Integer)
    enabled: Mapped[bool]=mapped_column(Boolean)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class FinancialReconciliation(Identity,Base):
    __tablename__='financial_reconciliations'
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    left_id: Mapped[str]=mapped_column(ForeignKey('financial_facts.id'))
    right_id: Mapped[str]=mapped_column(ForeignKey('financial_facts.id'))
    content_hash: Mapped[str]=mapped_column(String(64),unique=True)
    calculation_json: Mapped[str]=mapped_column(String)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class FinancialResolution(Identity,Base):
    __tablename__='financial_resolutions'
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    reconciliation_id: Mapped[str]=mapped_column(ForeignKey('financial_reconciliations.id'),unique=True)
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class TableView(Identity,Base):
    __tablename__='table_views'
    __table_args__=(CheckConstraint("dataset IN ('inventory','financial')",name='ck_table_view_dataset'),CheckConstraint("organization IN ('firm','castlegate')",name='ck_table_view_org'),Index('ix_table_view_matter_owner','matter_id','dataset','owner_id'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    dataset: Mapped[str]=mapped_column(String(16))
    owner_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    organization: Mapped[str]=mapped_column(String(32))
    created_at: Mapped[int]=mapped_column(Integer)


class TableViewVersion(Identity,Base):
    __tablename__='table_view_versions'
    __table_args__=(UniqueConstraint('view_id','revision',name='uq_table_view_revision'),UniqueConstraint('created_by','request_key',name='uq_table_view_request'),CheckConstraint("handling IN ('private_unclassified','source_bound')",name='ck_table_view_handling'),)
    view_id: Mapped[str]=mapped_column(ForeignKey('table_views.id'))
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    revision: Mapped[int]=mapped_column(Integer)
    previous_hash: Mapped[str|None]=mapped_column(String(64),nullable=True)
    name: Mapped[str]=mapped_column(String(96))
    query_json: Mapped[str]=mapped_column(String)
    handling: Mapped[str]=mapped_column(String(32))
    rationale: Mapped[str]=mapped_column(String(1000))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))


class TableViewEvidence(Identity,SourceWorkScope,Base):
    __tablename__='table_view_evidence'
    __table_args__=(UniqueConstraint('version_id','kind','reference_id',name='uq_table_view_evidence'),CheckConstraint("kind IN ('source','financial')",name='ck_table_view_evidence_kind'),)
    version_id: Mapped[str]=mapped_column(ForeignKey('table_view_versions.id'))
    kind: Mapped[str]=mapped_column(String(16))
    reference_id: Mapped[str]=mapped_column(String(36))
    reference_snapshot: Mapped[str]=mapped_column(String(64))


class TableViewShare(Identity,Base):
    __tablename__='table_view_shares'
    __table_args__=(UniqueConstraint('requested_by','request_key',name='uq_table_share_request'),Index('ix_table_share_matter','matter_id','created_at'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    version_id: Mapped[str]=mapped_column(ForeignKey('table_view_versions.id'))
    version_hash: Mapped[str]=mapped_column(String(64))
    requested_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    expires_at: Mapped[int]=mapped_column(Integer)
    rationale: Mapped[str]=mapped_column(String(1000))
    content_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))


class TableViewShareRecipient(Identity,Base):
    __tablename__='table_view_share_recipients'
    __table_args__=(UniqueConstraint('share_id','account_id',name='uq_table_view_share_recipient'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    share_id: Mapped[str]=mapped_column(ForeignKey('table_view_shares.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))


class TableViewShareDecision(Identity,Base):
    __tablename__='table_view_share_decisions'
    __table_args__=(UniqueConstraint('share_id','operation',name='uq_table_view_share_decision'),CheckConstraint("operation IN ('approve','reject','revoke')",name='ck_table_view_share_decision'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    share_id: Mapped[str]=mapped_column(ForeignKey('table_view_shares.id'))
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    content_reviewed: Mapped[bool]=mapped_column(Boolean)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class FinancialOrganizationGate(Identity,Base):
    __tablename__='financial_organization_gates'
    __table_args__=(UniqueConstraint('organization_id','revision',name='uq_financial_org_revision'),)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'))
    revision: Mapped[int]=mapped_column(Integer)
    enabled: Mapped[bool]=mapped_column(Boolean)
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class IntelligenceProfile(Identity,Base):
    __tablename__='intelligence_profiles'
    __table_args__=(UniqueConstraint('matter_id','name','version_number',name='uq_intelligence_profile_version'),UniqueConstraint('author_id','request_key',name='uq_intelligence_profile_request'),Index('ix_intelligence_profile_matter','matter_id','version_number'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    name: Mapped[str]=mapped_column(String(96))
    version_number: Mapped[int]=mapped_column(Integer)
    author_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    definition_json: Mapped[str]=mapped_column(String)
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class IntelligenceProfileDecision(Identity,Base):
    __tablename__='intelligence_profile_decisions'
    __table_args__=(UniqueConstraint('profile_id','operation',name='uq_intelligence_profile_decision'),CheckConstraint("operation IN ('approve','reject','publish','revoke')",name='ck_intelligence_profile_decision'),)
    matter_id: Mapped[str]=mapped_column(ForeignKey('matters.id'))
    profile_id: Mapped[str]=mapped_column(ForeignKey('intelligence_profiles.id'))
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class IntelligenceOverride(Identity,SourceWorkScope,Base):
    __tablename__='intelligence_overrides'
    __table_args__=(UniqueConstraint('created_by','request_key',name='uq_intelligence_override_request'),CheckConstraint("domain IN ('delay','legal','financial')",name='ck_intelligence_override_domain'),CheckConstraint('value >= 0 AND value <= 100',name='ck_intelligence_override_value'),)
    profile_id: Mapped[str]=mapped_column(ForeignKey('intelligence_profiles.id'))
    domain: Mapped[str]=mapped_column(String(16))
    value: Mapped[int]=mapped_column(Integer)
    base_hash: Mapped[str]=mapped_column(String(64))
    source_snapshot: Mapped[str]=mapped_column(String(64))
    expires_at: Mapped[int]=mapped_column(Integer)
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_hash: Mapped[str]=mapped_column(String(64))
    rationale: Mapped[str]=mapped_column(String(1000))
    request_key: Mapped[str]=mapped_column(String(128))
    input_hash: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[int]=mapped_column(Integer)


class IntelligenceOverrideDecision(Identity,SourceWorkScope,Base):
    __tablename__='intelligence_override_decisions'
    __table_args__=(UniqueConstraint('override_id','operation',name='uq_intelligence_override_decision'),CheckConstraint("operation IN ('approve','reject','revoke')",name='ck_intelligence_override_decision'),)
    override_id: Mapped[str]=mapped_column(ForeignKey('intelligence_overrides.id'))
    operation: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class IntelligenceAlert(Identity,SourceWorkScope,Base):
    __tablename__='intelligence_alerts'
    __table_args__=(Index('ix_intelligence_alert_matter','matter_id','created_at'),)
    dedupe_key: Mapped[str]=mapped_column(String(64),unique=True)
    profile_id: Mapped[str]=mapped_column(ForeignKey('intelligence_profiles.id'))
    source_snapshot: Mapped[str]=mapped_column(String(64))
    domain: Mapped[str]=mapped_column(String(16))
    signal_json: Mapped[str]=mapped_column(String)
    task_id: Mapped[str]=mapped_column(ForeignKey('review_tasks.id'))
    created_by: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at: Mapped[int]=mapped_column(Integer)


class IntelligenceAlertRecipient(Identity,SourceWorkScope,Base):
    __tablename__='intelligence_alert_recipients'
    __table_args__=(UniqueConstraint('alert_id','account_id',name='uq_intelligence_alert_recipient'),)
    alert_id: Mapped[str]=mapped_column(ForeignKey('intelligence_alerts.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))


class IntelligenceAlertDisposition(Identity,SourceWorkScope,Base):
    __tablename__='intelligence_alert_dispositions'
    __table_args__=(UniqueConstraint('alert_id','revision',name='uq_intelligence_alert_revision'),CheckConstraint("operation IN ('acknowledge','escalate','close')",name='ck_intelligence_alert_disposition'),)
    alert_id: Mapped[str]=mapped_column(ForeignKey('intelligence_alerts.id'))
    revision: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(16))
    actor_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    rationale: Mapped[str]=mapped_column(String(1000))
    occurred_at: Mapped[int]=mapped_column(Integer)


class IntelligenceAlertRead(Identity,Base):
    __tablename__='intelligence_alert_reads'
    __table_args__=(UniqueConstraint('alert_id','account_id',name='uq_intelligence_alert_read'),)
    alert_id: Mapped[str]=mapped_column(ForeignKey('intelligence_alerts.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    occurred_at: Mapped[int]=mapped_column(Integer)


# Durable graph models are declared separately after shared source-scope mixins.
from kestrel.models_ddr import (DDRRun,DDREvidence,DDRExecution,DDRArtifact,DDRAttempt,DDRNodeResult,DDRTask,DDRDecision,DDREvent,DDRReportLink)

# Agent definitions and impact decisions retain their own immutable history.
from kestrel.models_agents import (AgentProfile,AgentProfileVersion,AgentProfileEvent,AgentProfileReplacement,
    AgentProfileImpact,AgentProfileImpactItem,AgentProfileImpactTask,AgentProfileImpactDecision,AgentProfileImpactNotification)

# Internal context sidecars never mutate or extend released FinancialFact JSON.
from kestrel.models_financial_context import (FinancialFactContext,FinancialContextEvidence,FinancialContextDecision,FinancialExtractionCandidate)
