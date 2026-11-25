"""Append-only lawyer finding revisions and explicit whole-document review."""
from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('legal_finding_revisions',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('record_key',sa.String(36),nullable=False),
        sa.Column('version_number',sa.Integer,nullable=False),
        sa.Column('previous_id',sa.String(36),sa.ForeignKey('legal_finding_revisions.id'),nullable=True,unique=True),
        sa.Column('candidate_id',sa.String(36),sa.ForeignKey('source_findings.id'),nullable=True),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('policy_id',sa.String(36),sa.ForeignKey('document_policy_versions.id'),nullable=False,unique=True),
        sa.Column('summary',sa.String(2000),nullable=False),sa.Column('topic',sa.String(32),nullable=False),
        sa.Column('severity',sa.String(32),nullable=False),sa.Column('materiality',sa.String(32),nullable=False),
        sa.Column('exposure',sa.String(32),nullable=False),sa.Column('workflow_status',sa.String(32),nullable=False),
        sa.Column('action',sa.String(2000),nullable=False),
        sa.Column('owner_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=True),
        sa.Column('due_on',sa.String(10),nullable=True),sa.Column('evidence_json',sa.String,nullable=False),
        sa.Column('decision',sa.String(32),nullable=False),
        sa.Column('reviewer_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('rationale',sa.String(1000),nullable=False),sa.Column('created_at',sa.Integer,nullable=False),
        sa.UniqueConstraint('record_key','version_number',name='uq_legal_record_version'))
    op.create_table('document_review_versions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('version_number',sa.Integer,nullable=False),
        sa.Column('previous_id',sa.String(36),sa.ForeignKey('document_review_versions.id'),nullable=True,unique=True),
        sa.Column('title',sa.String(160),nullable=False),sa.Column('counterparty',sa.String(160),nullable=False),
        sa.Column('scope',sa.String(32),nullable=False),sa.Column('coverage_state',sa.String(32),nullable=False),
        sa.Column('reviewer_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('rationale',sa.String(1000),nullable=False),sa.Column('created_at',sa.Integer,nullable=False),
        sa.UniqueConstraint('source_id','version_number',name='uq_document_review_version'))
    for table in ['legal_finding_revisions','document_review_versions']:
        if op.get_bind().dialect.name=='sqlite':
            for action in ['UPDATE','DELETE']:
                op.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'review version immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')

def downgrade():
    op.drop_table('document_review_versions');op.drop_table('legal_finding_revisions')
