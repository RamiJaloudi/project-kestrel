from alembic import op
import sqlalchemy as s
revision='0015'
down_revision='0014'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('client_submissions',s.Column('id',s.String(36),primary_key=True),s.Column('policy_id',s.String(36),s.ForeignKey('document_policy_versions.id'),nullable=False,unique=True),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=False),s.Column('uploaded_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('file_name',s.String(160),nullable=False),s.Column('bytes_hash',s.String(64),nullable=False),s.Column('data',s.LargeBinary,nullable=True),s.Column('parsed_json',s.String,nullable=True),s.Column('created_at',s.Integer,nullable=False),s.UniqueConstraint('matter_id','uploaded_by','bytes_hash',name='uq_client_submission_bytes'))
    op.create_table('submission_acceptances',s.Column('submission_id',s.String(36),s.ForeignKey('client_submissions.id'),primary_key=True),s.Column('source_id',s.String(36),s.ForeignKey('source_versions.id'),nullable=False,unique=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('created_at',s.Integer,nullable=False))
    if op.get_bind().dialect.name=='sqlite':
        for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER submission_acceptance_{action.lower()} BEFORE {action} ON submission_acceptances BEGIN SELECT RAISE(ABORT,'Acceptance retained'); END")
        op.execute("CREATE TRIGGER client_submission_retained BEFORE DELETE ON client_submissions BEGIN SELECT RAISE(ABORT,'Submission metadata retained'); END")
    else:
        op.execute('CREATE TRIGGER submission_acceptance_retained BEFORE UPDATE OR DELETE ON submission_acceptances FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
        op.execute('CREATE TRIGGER client_submission_retained BEFORE DELETE ON client_submissions FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
def downgrade():
    op.drop_table('submission_acceptances');op.drop_table('client_submissions')
