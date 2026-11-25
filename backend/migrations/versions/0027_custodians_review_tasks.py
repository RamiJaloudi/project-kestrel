"""Retained source-bound custody, parties and independent parallel task events."""
from alembic import op
import sqlalchemy as sa
revision='0027'
down_revision='0026'
branch_labels=None
depends_on=None
TABLES=['record_custodians', 'document_custodians', 'custodian_link_retirements', 'document_parties', 'review_tasks', 'review_task_events', 'review_task_notifications', 'review_notification_reads']


def upgrade():
    op.create_table('record_custodians',
        sa.Column('display_name',sa.String(160),nullable=False),
        sa.Column('custodian_type',sa.String(32),nullable=False),
        sa.Column('upn',sa.String(254),nullable=True),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True))
    op.create_table('document_custodians',
        sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),
        sa.Column('custodian_id',sa.String(36),sa.ForeignKey('record_custodians.id'),nullable=False),
        sa.Column('custody_role',sa.String(40),nullable=False),
        sa.Column('provenance',sa.String(1000),nullable=False),
        sa.Column('effective_from',sa.Integer(),nullable=True),
        sa.Column('effective_until',sa.Integer(),nullable=True),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('created_by','request_key',name='uq_custodian_request'))
    op.create_table('custodian_link_retirements',
        sa.Column('link_id',sa.String(36),sa.ForeignKey('document_custodians.id'),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('rationale',sa.String(1000),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('link_id',name=None))
    op.create_table('document_parties',
        sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),
        sa.Column('name',sa.String(160),nullable=False),
        sa.Column('party_role',sa.String(64),nullable=False),
        sa.Column('provenance',sa.String(1000),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('created_by','request_key',name='uq_party_request'))
    op.create_table('review_tasks',
        sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),
        sa.Column('stage',sa.String(32),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('source_snapshot_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('created_by','request_key',name='uq_review_task_request'))
    op.create_table('review_task_events',
        sa.Column('task_id',sa.String(36),sa.ForeignKey('review_tasks.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('operation',sa.String(32),nullable=False),
        sa.Column('from_state',sa.String(32),nullable=True),
        sa.Column('to_state',sa.String(32),nullable=False),
        sa.Column('assignee_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('due_at',sa.Integer(),nullable=True),
        sa.Column('rationale',sa.String(1000),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('occurred_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('retained_classification',sa.String(32),nullable=False),
        sa.Column('retained_scope',sa.String(128),nullable=True),
        sa.UniqueConstraint('task_id','revision',name='uq_review_task_revision'),
        sa.UniqueConstraint('task_id','actor_id','request_key',name='uq_review_event_request'))
    op.create_table('review_task_notifications',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('task_id',sa.String(36),sa.ForeignKey('review_tasks.id'),nullable=False),
        sa.Column('event_id',sa.String(36),sa.ForeignKey('review_task_events.id'),nullable=False),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('event_id','account_id',name='uq_review_task_notification'))
    op.create_table('review_notification_reads',
        sa.Column('notification_id',sa.String(36),sa.ForeignKey('review_task_notifications.id'),nullable=False),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('occurred_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('notification_id',name=None))
    op.create_index('ix_custodian_source','record_custodians',['source_id'])
    op.create_index('ix_document_custodian_source','document_custodians',['source_id'])
    op.create_index('ix_doc_party_source','document_parties',['source_id'])
    op.create_index('ix_review_task_source','review_tasks',['source_id'])
    op.create_index('ix_review_notification_inbox','review_task_notifications',['account_id','matter_id','created_at'])
    for table in TABLES:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'source work record immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')


def downgrade():
    if any(op.get_bind().scalar(sa.text('SELECT count(*) FROM '+t)) for t in TABLES):raise RuntimeError('Retained review/custody evidence prevents destructive downgrade; archival rollback required')
    for table in reversed(TABLES):op.drop_table(table)
