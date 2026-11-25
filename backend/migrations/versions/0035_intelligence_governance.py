"""Default-off organization gate and additive immutable intelligence governance."""
from alembic import op
import sqlalchemy as sa
revision='0035'
down_revision='0034'
branch_labels=None
depends_on=None
TABLES=['financial_organization_gates','intelligence_profiles','intelligence_profile_decisions','intelligence_overrides','intelligence_override_decisions','intelligence_alerts','intelligence_alert_recipients','intelligence_alert_dispositions','intelligence_alert_reads']
def ident():return sa.Column('id',sa.String(36),primary_key=True)
def string(name,length=None,nullable=False):return sa.Column(name,sa.String(length),nullable=nullable)
def integer(name):return sa.Column(name,sa.Integer(),nullable=False)
def fk(name,target):return sa.Column(name,sa.String(36),sa.ForeignKey(target),nullable=False)
def matter():return fk('matter_id','matters.id')
def scope():return [matter(),fk('source_id','source_versions.id'),string('retained_classification',32),string('retained_scope',128,True)]
def reason():return [fk('actor_id','accounts.id'),string('rationale',1000),integer('occurred_at')]
def upgrade():
    op.create_table('financial_organization_gates',ident(),fk('organization_id','organizations.id'),integer('revision'),sa.Column('enabled',sa.Boolean(),nullable=False),*reason(),sa.UniqueConstraint('organization_id','revision',name='uq_financial_org_revision'))
    op.create_table('intelligence_profiles',ident(),matter(),string('name',96),integer('version_number'),fk('author_id','accounts.id'),string('definition_json'),string('content_hash',64),string('rationale',1000),string('request_key',128),string('input_hash',64),integer('created_at'),sa.UniqueConstraint('matter_id','name','version_number',name='uq_intelligence_profile_version'),sa.UniqueConstraint('author_id','request_key',name='uq_intelligence_profile_request'))
    op.create_table('intelligence_profile_decisions',ident(),matter(),fk('profile_id','intelligence_profiles.id'),string('operation',16),string('content_hash',64),*reason(),sa.UniqueConstraint('profile_id','operation',name='uq_intelligence_profile_decision'),sa.CheckConstraint("operation IN ('approve','reject','publish','revoke')",name='ck_intelligence_profile_decision'))
    op.create_table('intelligence_overrides',ident(),*scope(),fk('profile_id','intelligence_profiles.id'),string('domain',16),integer('value'),string('base_hash',64),string('source_snapshot',64),integer('expires_at'),fk('created_by','accounts.id'),string('content_hash',64),string('rationale',1000),string('request_key',128),string('input_hash',64),integer('created_at'),sa.UniqueConstraint('created_by','request_key',name='uq_intelligence_override_request'),sa.CheckConstraint("domain IN ('delay','legal','financial')",name='ck_intelligence_override_domain'),sa.CheckConstraint('value >= 0 AND value <= 100',name='ck_intelligence_override_value'))
    op.create_table('intelligence_override_decisions',ident(),*scope(),fk('override_id','intelligence_overrides.id'),string('operation',16),string('content_hash',64),*reason(),sa.UniqueConstraint('override_id','operation',name='uq_intelligence_override_decision'),sa.CheckConstraint("operation IN ('approve','reject','revoke')",name='ck_intelligence_override_decision'))
    op.create_table('intelligence_alerts',ident(),*scope(),string('dedupe_key',64),fk('profile_id','intelligence_profiles.id'),string('source_snapshot',64),string('domain',16),string('signal_json'),fk('task_id','review_tasks.id'),fk('created_by','accounts.id'),integer('created_at'),sa.UniqueConstraint('dedupe_key'))
    op.create_table('intelligence_alert_recipients',ident(),*scope(),fk('alert_id','intelligence_alerts.id'),fk('account_id','accounts.id'),sa.UniqueConstraint('alert_id','account_id',name='uq_intelligence_alert_recipient'))
    op.create_table('intelligence_alert_dispositions',ident(),*scope(),fk('alert_id','intelligence_alerts.id'),integer('revision'),string('operation',16),*reason(),sa.UniqueConstraint('alert_id','revision',name='uq_intelligence_alert_revision'),sa.CheckConstraint("operation IN ('acknowledge','escalate','close')",name='ck_intelligence_alert_disposition'))
    op.create_table('intelligence_alert_reads',ident(),fk('alert_id','intelligence_alerts.id'),fk('account_id','accounts.id'),integer('occurred_at'),sa.UniqueConstraint('alert_id','account_id',name='uq_intelligence_alert_read'))
    for table in TABLES:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'intelligence governance immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
    op.create_index('ix_intelligence_alert_matter','intelligence_alerts',['matter_id','created_at'])
    op.create_index('ix_intelligence_profile_matter','intelligence_profiles',['matter_id','version_number'])
def downgrade():
    for table in TABLES:
        if op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')):raise RuntimeError('Retained intelligence records prevent destructive downgrade')
    for table in reversed(TABLES):op.drop_table(table)
