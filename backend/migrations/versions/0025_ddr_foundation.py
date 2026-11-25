"""Immutable, matter-scoped checklist definitions and human decisions."""
from alembic import op
import sqlalchemy as sa
revision='0025'
down_revision='0024'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('checklist_versions',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('version_number',sa.Integer(),nullable=False),sa.Column('previous_id',sa.String(36),sa.ForeignKey('checklist_versions.id')),
        sa.Column('author_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),sa.Column('definition_json',sa.String(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False),
        sa.UniqueConstraint('matter_id','version_number',name='uq_checklist_version'),sa.UniqueConstraint('author_id','request_key',name='uq_checklist_request'))
    op.create_table('checklist_version_decisions',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('version_id',sa.String(36),sa.ForeignKey('checklist_versions.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('state',sa.String(32),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('rationale',sa.String(1000),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),sa.UniqueConstraint('version_id','revision',name='uq_checklist_decision'))
    op.create_table('checklist_coverage_decisions',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('version_id',sa.String(36),sa.ForeignKey('checklist_versions.id'),nullable=False),
        sa.Column('item_id',sa.String(96),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),sa.Column('owner_id',sa.String(36),sa.ForeignKey('accounts.id')),
        sa.Column('kind',sa.String(32),nullable=False),sa.Column('status',sa.String(40),nullable=False),
        sa.Column('source_ids_json',sa.String(),nullable=False),sa.Column('finding_ids_json',sa.String(),nullable=False),sa.Column('source_snapshots_json',sa.String(),nullable=False),
        sa.Column('missing_information',sa.String(1000),nullable=False),sa.Column('rationale',sa.String(1000),nullable=False),
        sa.Column('request_id',sa.String(36),sa.ForeignKey('checklist_coverage_decisions.id')),sa.Column('created_at',sa.Integer(),nullable=False),
        sa.UniqueConstraint('version_id','item_id','revision',name='uq_checklist_coverage'),sa.UniqueConstraint('request_id',name='uq_checklist_na_decision'))
    for table in ['checklist_versions','checklist_version_decisions','checklist_coverage_decisions']:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'checklist record immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM checklist_versions')):raise RuntimeError('Retained checklist records prevent destructive downgrade')
    op.drop_table('checklist_coverage_decisions')
    op.drop_table('checklist_version_decisions')
    op.drop_table('checklist_versions')
