from alembic import op
import sqlalchemy as s
revision='0013'
down_revision='0012'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('collaboration_messages',s.Column('id',s.String(36),primary_key=True),s.Column('release_id',s.String(36),s.ForeignKey('release_packages.id'),nullable=False),s.Column('parent_id',s.String(36),s.ForeignKey('collaboration_messages.id'),nullable=True),s.Column('author_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('kind',s.String(32),nullable=False),s.Column('body',s.String(4000),nullable=False),s.Column('body_hash',s.String(64),nullable=False),s.Column('internal_draft',s.Boolean,nullable=False),s.Column('created_at',s.Integer,nullable=False))
    op.create_table('collaboration_approvals',s.Column('message_id',s.String(36),s.ForeignKey('collaboration_messages.id'),primary_key=True),s.Column('kind',s.String(32),primary_key=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('body_hash',s.String(64),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('created_at',s.Integer,nullable=False))
    for table in ['collaboration_messages','collaboration_approvals']:
        if op.get_bind().dialect.name=='sqlite':
            for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Collaboration record retained'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')

def downgrade():
    op.drop_table('collaboration_approvals');op.drop_table('collaboration_messages')
