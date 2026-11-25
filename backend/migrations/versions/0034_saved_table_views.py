"""Add retained private configurations and independently reviewed named ACLs.

No existing content, release, source or signed manifest is rewritten.
"""
from alembic import op
import sqlalchemy as sa
revision='0034'
down_revision='0033'
branch_labels=None
depends_on=None
TABLES=['table_views','table_view_versions','table_view_evidence','table_view_shares','table_view_share_recipients','table_view_share_decisions']

def ident():return sa.Column('id',sa.String(36),primary_key=True)
def string(name,length=None,nullable=False):return sa.Column(name,sa.String(length),nullable=nullable)
def integer(name):return sa.Column(name,sa.Integer(),nullable=False)
def fk(name,target):return sa.Column(name,sa.String(36),sa.ForeignKey(target),nullable=False)
def matter():return fk('matter_id','matters.id')

def upgrade():
    op.create_table('table_views',ident(),matter(),string('dataset',16),fk('owner_id','accounts.id'),string('organization',32),integer('created_at'),
        sa.CheckConstraint("dataset IN ('inventory','financial')",name='ck_table_view_dataset'),sa.CheckConstraint("organization IN ('firm','castlegate')",name='ck_table_view_org'))
    op.create_table('table_view_versions',ident(),fk('view_id','table_views.id'),matter(),integer('revision'),string('previous_hash',64,True),string('name',96),string('query_json'),string('handling',32),string('rationale',1000),string('content_hash',64),fk('created_by','accounts.id'),integer('created_at'),string('request_key',128),string('input_hash',64),
        sa.UniqueConstraint('view_id','revision',name='uq_table_view_revision'),sa.UniqueConstraint('created_by','request_key',name='uq_table_view_request'),sa.CheckConstraint("handling IN ('private_unclassified','source_bound')",name='ck_table_view_handling'))
    op.create_table('table_view_evidence',ident(),matter(),fk('source_id','source_versions.id'),string('retained_classification',32),string('retained_scope',128,True),fk('version_id','table_view_versions.id'),string('kind',16),string('reference_id',36),string('reference_snapshot',64),
        sa.UniqueConstraint('version_id','kind','reference_id',name='uq_table_view_evidence'),sa.CheckConstraint("kind IN ('source','financial')",name='ck_table_view_evidence_kind'))
    op.create_table('table_view_shares',ident(),matter(),fk('version_id','table_view_versions.id'),string('version_hash',64),fk('requested_by','accounts.id'),integer('expires_at'),string('rationale',1000),string('content_hash',64),integer('created_at'),string('request_key',128),string('input_hash',64),sa.UniqueConstraint('requested_by','request_key',name='uq_table_share_request'))
    op.create_table('table_view_share_recipients',ident(),matter(),fk('share_id','table_view_shares.id'),fk('account_id','accounts.id'),sa.UniqueConstraint('share_id','account_id',name='uq_table_view_share_recipient'))
    op.create_table('table_view_share_decisions',ident(),matter(),fk('share_id','table_view_shares.id'),string('operation',16),string('content_hash',64),sa.Column('content_reviewed',sa.Boolean(),nullable=False),fk('actor_id','accounts.id'),string('rationale',1000),integer('occurred_at'),
        sa.UniqueConstraint('share_id','operation',name='uq_table_view_share_decision'),sa.CheckConstraint("operation IN ('approve','reject','revoke')",name='ck_table_view_share_decision'))
    for table in TABLES:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'saved table view records immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
    op.create_index('ix_table_view_matter_owner','table_views',['matter_id','dataset','owner_id'])
    op.create_index('ix_table_share_matter','table_view_shares',['matter_id','created_at'])

def downgrade():
    # Check the entire increment first: a failed downgrade cannot half-drop it.
    for table in TABLES:
        if op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')):raise RuntimeError('Retained saved table view records prevent destructive downgrade')
    for table in reversed(TABLES):op.drop_table(table)
