"""Retained internal financial context and unapproved literal proposal staging."""
from alembic import op
import sqlalchemy as sa
revision='0038'
down_revision='0037'
branch_labels=None
depends_on=None
TABLES=['financial_fact_contexts','financial_context_evidence','financial_context_decisions','financial_extraction_candidates']

def ident():return sa.Column('id',sa.String(36),primary_key=True)
def string(name,length=None,nullable=False):return sa.Column(name,sa.String(length),nullable=nullable)
def integer(name):return sa.Column(name,sa.Integer(),nullable=False)
def fk(name,target):return sa.Column(name,sa.String(36),sa.ForeignKey(target),nullable=False)
def scoped():return [fk('matter_id','matters.id'),fk('source_id','source_versions.id'),string('retained_classification',32),string('retained_scope',128,True)]

def upgrade():
    op.create_table('financial_fact_contexts',ident(),*scoped(),fk('fact_id','financial_facts.id'),integer('revision'),string('previous_hash',64,True),string('fact_hash',64),string('reference_kind',16),string('reference_id',36),string('reference_snapshot',64),string('dimensions_json'),string('provenance_json'),string('content_hash',64),string('rationale',1000),fk('created_by','accounts.id'),integer('created_at'),string('request_key',128),string('input_hash',64),
        sa.UniqueConstraint('fact_id','revision',name='uq_financial_context_revision'),sa.UniqueConstraint('created_by','request_key',name='uq_financial_context_request'))
    op.create_table('financial_context_evidence',ident(),*scoped(),fk('context_id','financial_fact_contexts.id'),string('field',32),integer('unit_number'),integer('start_offset'),integer('end_offset'),string('quote',2000),string('quote_hash',64),
        sa.UniqueConstraint('context_id','field','unit_number','start_offset','end_offset',name='uq_financial_context_evidence'))
    op.create_table('financial_context_decisions',ident(),*scoped(),fk('context_id','financial_fact_contexts.id'),string('operation',16),string('content_hash',64),fk('actor_id','accounts.id'),sa.Column('content_reviewed',sa.Boolean(),nullable=False),string('rationale',1000),integer('occurred_at'),
        sa.UniqueConstraint('context_id','operation',name='uq_financial_context_decision'),sa.CheckConstraint("operation IN ('confirm','reject','revoke')",name='ck_financial_context_decision'))
    amount_type=sa.String(64) if op.get_bind().dialect.name=='sqlite' else sa.Numeric(38,12)
    op.create_table('financial_extraction_candidates',ident(),*scoped(),string('source_snapshot',64),string('extractor_version',96),string('anchor_key',256),string('candidate_key',64),string('raw_number',128,True),sa.Column('amount',amount_type,nullable=True),string('amount_text',64,True),string('entity',160,True),string('metric',128,True),string('period_start',10,True),string('period_end',10,True),string('currency',3,True),string('scale',16,True),string('accounting_basis',128,True),string('consolidation_scope',128,True),string('state',32),string('dimensions_json'),string('missing_json'),string('evidence_json'),string('provenance_json'),string('normalized_json',None,True),string('content_hash',64),fk('created_by','accounts.id'),integer('created_at'),string('request_key',128),string('input_hash',64),
        sa.UniqueConstraint('candidate_key',name='uq_financial_extraction_candidate'),sa.CheckConstraint("state IN ('INCOMPLETE','READY_FOR_REVIEW')",name='ck_financial_candidate_state'))
    op.create_index('ix_financial_context_fact','financial_fact_contexts',['matter_id','fact_id','revision'])
    op.create_index('ix_financial_candidate_source','financial_extraction_candidates',['matter_id','source_id','created_at'])
    for table in TABLES:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'financial context records immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')

def downgrade():
    for table in TABLES:
        if op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')):raise RuntimeError('Retained financial context records prevent destructive downgrade')
    for table in reversed(TABLES):op.drop_table(table)
