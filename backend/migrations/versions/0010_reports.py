from alembic import op
import sqlalchemy as sa
revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('report_versions',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('report_key',sa.String(36),nullable=False),sa.Column('version_number',sa.Integer,nullable=False),
        sa.Column('previous_id',sa.String(36),sa.ForeignKey('report_versions.id'),unique=True,nullable=True),
        sa.Column('release_id',sa.String(36),sa.ForeignKey('release_packages.id'),unique=True,nullable=False),
        sa.Column('kind',sa.String(32),nullable=False),sa.Column('body_json',sa.String,nullable=False),sa.Column('created_at',sa.Integer,nullable=False),
        sa.UniqueConstraint('report_key','version_number',name='uq_report_version'))
    if op.get_bind().dialect.name=='sqlite':
        for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER report_versions_no_{action.lower()} BEFORE {action} ON report_versions BEGIN SELECT RAISE(ABORT,'report version immutable'); END")
    else:op.execute('CREATE TRIGGER report_versions_retained BEFORE UPDATE OR DELETE ON report_versions FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
def downgrade():op.drop_table('report_versions')
