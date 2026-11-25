from alembic import op
import sqlalchemy as s
revision='0012'
down_revision='0011'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('ai_operations',s.Column('id',s.String(36),primary_key=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=False),s.Column('kind',s.String(32),nullable=False),s.Column('request_key',s.String(128),nullable=False),s.Column('input_hash',s.String(64),nullable=False),s.Column('state',s.String(32),nullable=False),s.Column('result_json',s.String,nullable=True),s.Column('created_at',s.Integer,nullable=False),s.UniqueConstraint('actor_id','request_key',name='uq_ai_operation_request'))
    op.create_table('operation_reservations',s.Column('operation_id',s.String(36),s.ForeignKey('ai_operations.id'),primary_key=True),s.Column('period',s.String(7),s.ForeignKey('ai_budget_periods.period'),nullable=False),s.Column('reserved_cents',s.Integer,nullable=False),s.Column('charged_cents',s.Integer,nullable=True),s.Column('state',s.String(32),nullable=False),s.Column('created_at',s.Integer,nullable=False))
    op.create_table('question_answers',s.Column('id',s.String(36),primary_key=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=False),s.Column('question',s.String(1000),nullable=False),s.Column('result_json',s.String,nullable=False),s.Column('created_at',s.Integer,nullable=False))
    if op.get_bind().dialect.name=='sqlite':
        for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER qa_no_{action.lower()} BEFORE {action} ON question_answers BEGIN SELECT RAISE(ABORT,'Q&A retained'); END")
        op.execute("CREATE TRIGGER ai_operation_terminal BEFORE UPDATE ON ai_operations WHEN OLD.state IN ('succeeded','failed') BEGIN SELECT RAISE(ABORT,'AI operation terminal'); END")
        op.execute("CREATE TRIGGER ai_operation_retained BEFORE DELETE ON ai_operations BEGIN SELECT RAISE(ABORT,'AI operation retained'); END")
    else:
        op.execute('CREATE TRIGGER qa_retained BEFORE UPDATE OR DELETE ON question_answers FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
        op.execute("CREATE FUNCTION kestrel_operation_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR OLD.state IN ('succeeded','failed') THEN RAISE EXCEPTION 'AI operation retained'; END IF; RETURN NEW; END $$")
        op.execute('CREATE TRIGGER ai_operation_retained BEFORE UPDATE OR DELETE ON ai_operations FOR EACH ROW EXECUTE FUNCTION kestrel_operation_retained()')

def downgrade():
    for table in ['question_answers','operation_reservations','ai_operations']:op.drop_table(table)
    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION kestrel_operation_retained()')
