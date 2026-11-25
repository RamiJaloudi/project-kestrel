"""Immutable reader observations and approved operational SLA; mutable technical lease only."""
from alembic import op
import sqlalchemy as sa
revision='0028'
down_revision='0027'
branch_labels=None
depends_on=None
TABLES=['sla_calendars', 'review_sla_policies', 'review_sla_decisions', 'review_sla_bindings', 'review_sessions', 'review_session_receipts', 'review_session_leases']


def upgrade():
    op.create_table('sla_calendars',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('name',sa.String(96),nullable=False),
        sa.Column('version_number',sa.Integer(),nullable=False),
        sa.Column('timezone',sa.String(96),nullable=False),
        sa.Column('tzdata_version',sa.String(32),nullable=False),
        sa.Column('weekdays_json',sa.String(),nullable=False),
        sa.Column('holidays_json',sa.String(),nullable=False),
        sa.Column('start_minute',sa.Integer(),nullable=False),
        sa.Column('end_minute',sa.Integer(),nullable=False),
        sa.Column('author_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('matter_id','name','version_number',name='uq_sla_calendar_version'))
    op.create_table('review_sla_policies',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('calendar_id',sa.String(36),sa.ForeignKey('sla_calendars.id'),nullable=False),
        sa.Column('name',sa.String(96),nullable=False),
        sa.Column('version_number',sa.Integer(),nullable=False),
        sa.Column('stage',sa.String(32),nullable=False),
        sa.Column('max_business_seconds',sa.Integer(),nullable=False),
        sa.Column('exclude_paused',sa.Boolean(),nullable=False),
        sa.Column('idle_timeout_seconds',sa.Integer(),nullable=False),
        sa.Column('author_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('matter_id','name','version_number',name='uq_review_sla_version'))
    op.create_table('review_sla_decisions',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('policy_id',sa.String(36),sa.ForeignKey('review_sla_policies.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('rationale',sa.String(1000),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('policy_id','revision',name='uq_review_sla_decision'))
    op.create_table('review_sla_bindings',
        sa.Column('task_id',sa.String(36),sa.ForeignKey('review_tasks.id'),nullable=False),
        sa.Column('assignment_event_id',sa.String(36),sa.ForeignKey('review_task_events.id'),nullable=False),
        sa.Column('policy_id',sa.String(36),sa.ForeignKey('review_sla_policies.id'),nullable=False),
        sa.Column('event_id',sa.String(36),sa.ForeignKey('review_task_events.id'),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('event_id',name='uq_review_sla_binding_event'))
    op.create_table('review_sessions',
        sa.Column('task_id',sa.String(36),sa.ForeignKey('review_tasks.id'),nullable=False),
        sa.Column('assignment_event_id',sa.String(36),sa.ForeignKey('review_task_events.id'),nullable=False),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('idle_timeout_seconds',sa.Integer(),nullable=False),
        sa.Column('started_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('account_id','request_key',name='uq_review_session_request'))
    op.create_index('ix_review_session_task','review_sessions',['task_id'],unique=False)
    op.create_table('review_session_receipts',
        sa.Column('session_id',sa.String(36),sa.ForeignKey('review_sessions.id'),nullable=False),
        sa.Column('sequence',sa.Integer(),nullable=False),
        sa.Column('operation',sa.String(24),nullable=False),
        sa.Column('mode',sa.String(24),nullable=False),
        sa.Column('interaction',sa.Boolean(),nullable=False),
        sa.Column('interval_start_at',sa.Integer(),nullable=False),
        sa.Column('interval_end_at',sa.Integer(),nullable=False),
        sa.Column('last_interaction_at',sa.Integer(),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('occurred_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('session_id','request_key',name='uq_review_receipt_request'),
        sa.UniqueConstraint('session_id','sequence',name='uq_review_receipt_sequence'))
    op.create_table('review_session_leases',
        sa.Column('account_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False,primary_key=True),
        sa.Column('session_id',sa.String(36),sa.ForeignKey('review_sessions.id'),nullable=False),
        sa.Column('lease_until',sa.Integer(),nullable=False),
        sa.UniqueConstraint('session_id',name=None))
    for table in TABLES[:-1]:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'review timing/SLA record immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')


def downgrade():
    if any(op.get_bind().scalar(sa.text('SELECT count(*) FROM '+t)) for t in TABLES):raise RuntimeError('Retained review timing evidence prevents destructive downgrade; archival rollback required')
    for table in reversed(TABLES):op.drop_table(table)
