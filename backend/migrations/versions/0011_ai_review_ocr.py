from alembic import op
import sqlalchemy as s
revision='0011'
down_revision='0010'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('ocr_jobs',s.Column('id',s.String(36),primary_key=True),s.Column('source_id',s.String(36),s.ForeignKey('source_versions.id'),unique=True,nullable=False),s.Column('requested_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('state',s.String(32),nullable=False),s.Column('created_at',s.Integer,nullable=False),s.Column('lease_until',s.Integer,nullable=True),s.Column('result_source_id',s.String(36),s.ForeignKey('source_versions.id'),nullable=True),s.Column('error_code',s.String(64),nullable=True))
    op.create_table('ocr_verifications',s.Column('source_id',s.String(36),s.ForeignKey('source_versions.id'),primary_key=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('text_hash',s.String(64),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('created_at',s.Integer,nullable=False))
    op.create_table('processing_replacements',s.Column('id',s.String(36),primary_key=True),s.Column('old_id',s.String(36),s.ForeignKey('governance_versions.id'),unique=True,nullable=False),s.Column('new_id',s.String(36),s.ForeignKey('governance_versions.id'),nullable=False),s.Column('proposed_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('approved_by',s.String(36),s.ForeignKey('accounts.id'),nullable=True),s.Column('state',s.String(32),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('decision_rationale',s.String(1000),nullable=True),s.Column('created_at',s.Integer,nullable=False))
    if op.get_bind().dialect.name=='sqlite':
        for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER ocr_verified_no_{action.lower()} BEFORE {action} ON ocr_verifications BEGIN SELECT RAISE(ABORT,'OCR verification immutable'); END")
        op.execute("CREATE TRIGGER processing_decision_immutable BEFORE UPDATE ON processing_replacements WHEN OLD.state IN ('approved','rejected') BEGIN SELECT RAISE(ABORT,'processing decision immutable'); END")
        op.execute("CREATE TRIGGER processing_decision_retained BEFORE DELETE ON processing_replacements BEGIN SELECT RAISE(ABORT,'processing decision retained'); END")
    else:
        op.execute('CREATE TRIGGER ocr_verified_retained BEFORE UPDATE OR DELETE ON ocr_verifications FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
        op.execute("CREATE FUNCTION kestrel_processing_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR OLD.state IN ('approved','rejected') THEN RAISE EXCEPTION 'processing decision retained'; END IF; RETURN NEW; END $$")
        op.execute('CREATE TRIGGER processing_decision_retained BEFORE UPDATE OR DELETE ON processing_replacements FOR EACH ROW EXECUTE FUNCTION kestrel_processing_retained()')
def downgrade():
    op.drop_table('processing_replacements');op.drop_table('ocr_verifications');op.drop_table('ocr_jobs')
    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION kestrel_processing_retained()')
