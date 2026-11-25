"""Durable leased queue for synthetic examples; retained terminal results."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('analysis_jobs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('playbook_id',sa.String(36),sa.ForeignKey('governance_versions.id'),nullable=False),
        sa.Column('playbook_hash',sa.String(64),nullable=False),
        sa.Column('requested_by',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('idempotency_key',sa.String(128),nullable=False),
        sa.Column('rationale',sa.String(1000),nullable=False),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('attempts',sa.Integer,nullable=False),
        sa.Column('created_at',sa.Integer,nullable=False),
        sa.Column('available_at',sa.Integer,nullable=False),
        sa.Column('lease_until',sa.Integer,nullable=True),
        sa.Column('lease_token',sa.String(36),nullable=True),
        sa.Column('finished_at',sa.Integer,nullable=True),
        sa.Column('result_json',sa.String,nullable=True),
        sa.Column('error_code',sa.String(64),nullable=True),
        sa.UniqueConstraint('requested_by','idempotency_key',name='uq_job_request_key'))
    op.create_index('ix_analysis_jobs_claim','analysis_jobs',['state','available_at','created_at'])
    if op.get_bind().dialect.name=='sqlite':
        op.execute("CREATE TRIGGER job_result_immutable BEFORE UPDATE ON analysis_jobs WHEN OLD.state IN ('succeeded','denied') BEGIN SELECT RAISE(ABORT, 'terminal job immutable'); END")
        op.execute("CREATE TRIGGER job_no_delete BEFORE DELETE ON analysis_jobs BEGIN SELECT RAISE(ABORT, 'job retained'); END")
    else:
        op.execute("CREATE FUNCTION kestrel_job_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR OLD.state IN ('succeeded','denied') THEN RAISE EXCEPTION 'job retained'; END IF; RETURN NEW; END $$")
        op.execute("CREATE TRIGGER job_retained BEFORE UPDATE OR DELETE ON analysis_jobs FOR EACH ROW EXECUTE FUNCTION kestrel_job_retained()")

def downgrade():
    op.drop_table('analysis_jobs')
    if op.get_bind().dialect.name!='sqlite':op.execute('DROP FUNCTION kestrel_job_retained()')
