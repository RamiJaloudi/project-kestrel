from alembic import op
import sqlalchemy as s
revision='0017'
down_revision='0016'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('source_archives',s.Column('id',s.String(36),primary_key=True),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=False),s.Column('created_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('storage_key',s.String(36),nullable=False,unique=True),s.Column('protected_hash',s.String(64),nullable=False),s.Column('content_hash',s.String(64),nullable=False),s.Column('manifest_json',s.String,nullable=False),s.Column('created_at',s.Integer,nullable=False))
    if op.get_bind().dialect.name=='sqlite':
        for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER source_archive_{action.lower()} BEFORE {action} ON source_archives BEGIN SELECT RAISE(ABORT,'Archive record retained'); END")
    else:op.execute('CREATE TRIGGER source_archive_retained BEFORE UPDATE OR DELETE ON source_archives FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
def downgrade():op.drop_table('source_archives')
