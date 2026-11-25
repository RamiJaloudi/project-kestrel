from alembic import op
import sqlalchemy as s
revision='0018'
down_revision='0017'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('source_access_grants',s.Column('revocation_rationale',s.String(1000),nullable=True))
    # Adding a nullable reference preserves old retained approvals.
    with op.batch_alter_table('source_access_grants') as batch:
        batch.add_column(s.Column('revoked_by',s.String(36),nullable=True))
        batch.create_foreign_key('fk_grant_revoked_by','accounts',['revoked_by'],['id'])
    op.add_column('source_access_grants',s.Column('revoked_at',s.Integer,nullable=True))
    fields=['source_id','account_id','snapshot_hash','expires_at','proposed_by','approved_by','rationale','decision_rationale','created_at']
    if op.get_bind().dialect.name=='sqlite':
        op.execute('DROP TRIGGER IF EXISTS source_grant_decided')
        condition=' OR '.join(f'NEW.{key} IS NOT OLD.{key}' for key in fields)
        op.execute(f"CREATE TRIGGER source_grant_decided BEFORE UPDATE ON source_access_grants WHEN OLD.state IN ('revoked','rejected') OR (OLD.state='approved' AND (NEW.state!='revoked' OR {condition})) BEGIN SELECT RAISE(ABORT,'Grant decision retained'); END")
        op.execute("CREATE TRIGGER IF NOT EXISTS source_grant_retained BEFORE DELETE ON source_access_grants BEGIN SELECT RAISE(ABORT,'Grant retained'); END")
    else:
        condition=' OR '.join(f'NEW.{key} IS DISTINCT FROM OLD.{key}' for key in fields)
        op.execute(f"CREATE OR REPLACE FUNCTION kestrel_grant_retained() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' OR OLD.state IN ('revoked','rejected') THEN RAISE EXCEPTION 'Grant retained'; END IF; IF OLD.state='approved' AND (NEW.state!='revoked' OR {condition}) THEN RAISE EXCEPTION 'Grant decision retained'; END IF; RETURN NEW; END $$")
def downgrade():
    retained=op.get_bind().scalar(s.text('SELECT count(*) FROM source_access_grants WHERE revocation_rationale IS NOT NULL OR revoked_by IS NOT NULL OR revoked_at IS NOT NULL'))
    if retained:raise RuntimeError('Retained grant revocation evidence must not be discarded by downgrade')
    with op.batch_alter_table('source_access_grants') as batch:
        batch.drop_constraint('fk_grant_revoked_by',type_='foreignkey')
        batch.drop_column('revoked_by');batch.drop_column('revoked_at');batch.drop_column('revocation_rationale')
    if op.get_bind().dialect.name=='sqlite':
        op.execute("CREATE TRIGGER IF NOT EXISTS source_grant_retained BEFORE DELETE ON source_access_grants BEGIN SELECT RAISE(ABORT,'Grant retained'); END")
        op.execute("CREATE TRIGGER IF NOT EXISTS source_grant_decided BEFORE UPDATE ON source_access_grants WHEN OLD.state IN ('revoked','rejected') OR (OLD.state='approved' AND (NEW.state!='revoked' OR NEW.source_id!=OLD.source_id OR NEW.account_id!=OLD.account_id OR NEW.snapshot_hash!=OLD.snapshot_hash OR NEW.expires_at!=OLD.expires_at OR NEW.proposed_by!=OLD.proposed_by OR NEW.approved_by!=OLD.approved_by)) BEGIN SELECT RAISE(ABORT,'Grant decision retained'); END")
