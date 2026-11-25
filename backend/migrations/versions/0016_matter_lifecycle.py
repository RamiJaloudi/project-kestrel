from alembic import op
import sqlalchemy as s
revision='0016'
down_revision='0015'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('matter_lifecycle',s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),primary_key=True),s.Column('frozen',s.Boolean,nullable=False),s.Column('external_closed',s.Boolean,nullable=False),s.Column('legal_hold',s.Boolean,nullable=False),s.Column('firm_retention',s.String(96),nullable=False))
    op.create_table('lifecycle_decisions',s.Column('id',s.String(36),primary_key=True),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=False),s.Column('kind',s.String(32),nullable=False),s.Column('proposed_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('approved_by',s.String(36),s.ForeignKey('accounts.id'),nullable=True),s.Column('state',s.String(32),nullable=False),s.Column('payload_json',s.String,nullable=False),s.Column('content_hash',s.String(64),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('decision_rationale',s.String(1000),nullable=True),s.Column('created_at',s.Integer,nullable=False))
    if op.get_bind().dialect.name=='sqlite':
        op.execute("CREATE TRIGGER lifecycle_decision_no_delete BEFORE DELETE ON lifecycle_decisions BEGIN SELECT RAISE(ABORT,'Decision retained'); END")
        op.execute("CREATE TRIGGER lifecycle_decision_terminal BEFORE UPDATE ON lifecycle_decisions WHEN OLD.state IN ('approved','rejected') BEGIN SELECT RAISE(ABORT,'Decision immutable'); END")
        op.execute("CREATE TRIGGER lifecycle_frozen_retained BEFORE UPDATE ON matter_lifecycle WHEN (OLD.frozen=1 AND NEW.frozen!=1) OR (OLD.external_closed=1 AND NEW.external_closed!=1) BEGIN SELECT RAISE(ABORT,'No thaw or external reopening'); END")
        op.execute("CREATE TRIGGER lifecycle_no_delete BEFORE DELETE ON matter_lifecycle BEGIN SELECT RAISE(ABORT,'Lifecycle retained'); END")
    else:
        op.execute("CREATE FUNCTION kestrel_lifecycle_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR OLD.state IN ('approved','rejected') THEN RAISE EXCEPTION 'Decision retained'; END IF; RETURN NEW; END $$")
        op.execute('CREATE TRIGGER lifecycle_decision_retained BEFORE UPDATE OR DELETE ON lifecycle_decisions FOR EACH ROW EXECUTE FUNCTION kestrel_lifecycle_retained()')
        op.execute("CREATE FUNCTION kestrel_freeze_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR (OLD.frozen AND NOT NEW.frozen) OR (OLD.external_closed AND NOT NEW.external_closed) THEN RAISE EXCEPTION 'Lifecycle retained; no reopening'; END IF; RETURN NEW; END $$")
        op.execute('CREATE TRIGGER lifecycle_frozen_retained BEFORE UPDATE OR DELETE ON matter_lifecycle FOR EACH ROW EXECUTE FUNCTION kestrel_freeze_retained()')
def downgrade():
    op.drop_table('lifecycle_decisions');op.drop_table('matter_lifecycle')
    if op.get_bind().dialect.name=='postgresql':
        op.execute('DROP FUNCTION kestrel_lifecycle_retained()');op.execute('DROP FUNCTION kestrel_freeze_retained()')
