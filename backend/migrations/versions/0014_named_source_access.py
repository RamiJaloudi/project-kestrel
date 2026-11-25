from alembic import op
import sqlalchemy as s
revision='0014'
down_revision='0013'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('source_access_grants',s.Column('id',s.String(36),primary_key=True),s.Column('source_id',s.String(36),s.ForeignKey('source_versions.id'),nullable=False),s.Column('account_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('proposed_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('approved_by',s.String(36),s.ForeignKey('accounts.id'),nullable=True),s.Column('snapshot_hash',s.String(64),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('decision_rationale',s.String(1000),nullable=True),s.Column('state',s.String(32),nullable=False),s.Column('expires_at',s.Integer,nullable=False),s.Column('created_at',s.Integer,nullable=False))
    # Decision identity/content cannot be overwritten; an approved grant can only be revoked.
    if op.get_bind().dialect.name=='sqlite':
        op.execute("CREATE TRIGGER source_grant_retained BEFORE DELETE ON source_access_grants BEGIN SELECT RAISE(ABORT,'Grant retained'); END")
        op.execute("CREATE TRIGGER source_grant_decided BEFORE UPDATE ON source_access_grants WHEN OLD.state IN ('revoked','rejected') OR (OLD.state='approved' AND (NEW.state!='revoked' OR NEW.source_id!=OLD.source_id OR NEW.account_id!=OLD.account_id OR NEW.snapshot_hash!=OLD.snapshot_hash OR NEW.expires_at!=OLD.expires_at OR NEW.proposed_by!=OLD.proposed_by OR NEW.approved_by!=OLD.approved_by)) BEGIN SELECT RAISE(ABORT,'Grant decision retained'); END")
    else:
        op.execute("CREATE FUNCTION kestrel_grant_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR OLD.state IN ('revoked','rejected') THEN RAISE EXCEPTION 'Grant retained'; END IF; IF OLD.state='approved' AND (NEW.state!='revoked' OR NEW.source_id!=OLD.source_id OR NEW.account_id!=OLD.account_id OR NEW.snapshot_hash!=OLD.snapshot_hash OR NEW.expires_at!=OLD.expires_at OR NEW.proposed_by!=OLD.proposed_by OR NEW.approved_by!=OLD.approved_by) THEN RAISE EXCEPTION 'Grant decision retained'; END IF; RETURN NEW; END $$")
        op.execute('CREATE TRIGGER source_grant_retained BEFORE UPDATE OR DELETE ON source_access_grants FOR EACH ROW EXECUTE FUNCTION kestrel_grant_retained()')
def downgrade():
    op.drop_table('source_access_grants')
    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION kestrel_grant_retained()')
