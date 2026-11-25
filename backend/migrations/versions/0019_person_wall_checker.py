from alembic import op
import sqlalchemy as s
revision='0019'
down_revision='0018'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('wall_controls',s.Column('id',s.String(36),primary_key=True),s.Column('client_id',s.String(36),s.ForeignKey('clients.id'),nullable=False),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=True),s.Column('entry_type',s.String(32),nullable=False),s.Column('account_id',s.String(36),s.ForeignKey('accounts.id'),nullable=True),s.Column('role_name',s.String(64),nullable=True),s.Column('relationship_kind',s.String(64),nullable=True),s.Column('starts_at',s.Integer,nullable=False),s.Column('expires_at',s.Integer,nullable=True),s.Column('proposed_by',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('retire_id',s.String(36),s.ForeignKey('wall_controls.id'),nullable=True),s.Column('rationale',s.String(1000),nullable=False),s.Column('created_at',s.Integer,nullable=False),s.CheckConstraint("entry_type IN ('restriction','relationship','retirement')",name='ck_wall_control_type'),s.CheckConstraint('expires_at IS NULL OR expires_at>starts_at',name='ck_wall_control_term'))
    op.create_index('ix_wall_controls_scope','wall_controls',['client_id','matter_id'])
    op.create_index('ix_wall_controls_account','wall_controls',['account_id'])
    op.create_table('wall_control_decisions',s.Column('control_id',s.String(36),s.ForeignKey('wall_controls.id'),primary_key=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('decision',s.String(32),nullable=False),s.Column('rationale',s.String(1000),nullable=False),s.Column('created_at',s.Integer,nullable=False))
    op.create_table('wall_check_records',s.Column('id',s.String(36),primary_key=True),s.Column('actor_id',s.String(36),s.ForeignKey('accounts.id'),nullable=False),s.Column('subject_id',s.String(36),s.ForeignKey('accounts.id'),nullable=True),s.Column('client_id',s.String(36),s.ForeignKey('clients.id'),nullable=False),s.Column('matter_id',s.String(36),s.ForeignKey('matters.id'),nullable=True),s.Column('result_json',s.String,nullable=False),s.Column('created_at',s.Integer,nullable=False))
    op.execute("CREATE VIEW vw_person_wall_entries AS SELECT c.* FROM wall_controls c JOIN wall_control_decisions d ON d.control_id=c.id AND d.decision='approve' WHERE c.entry_type!='retirement' AND NOT EXISTS (SELECT 1 FROM wall_controls r JOIN wall_control_decisions rd ON rd.control_id=r.id AND rd.decision='approve' WHERE r.retire_id=c.id AND r.entry_type='retirement')")
    op.execute("CREATE VIEW vw_person_relationships AS SELECT * FROM vw_person_wall_entries WHERE entry_type='relationship'")
    op.execute("CREATE VIEW vw_person_wall_rules AS SELECT * FROM vw_person_wall_entries WHERE entry_type='restriction'")
    op.execute('CREATE VIEW vw_wall_document_references AS SELECT p.id AS policy_id,p.matter_id,s.id AS source_version_id,s.version_number FROM document_policy_versions p LEFT JOIN source_versions s ON s.policy_id=p.id')
    for table in ['wall_controls','wall_control_decisions','wall_check_records']:
        if op.get_bind().dialect.name=='sqlite':
            for action in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Wall governance evidence retained'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')
def downgrade():
    for table in ['wall_controls','wall_control_decisions','wall_check_records']:
        if op.get_bind().scalar(s.text('SELECT count(*) FROM '+table)):raise RuntimeError('Retained wall governance evidence must not be discarded by downgrade')
    for view in ['vw_wall_document_references','vw_person_wall_rules','vw_person_relationships','vw_person_wall_entries']:op.execute('DROP VIEW '+view)
    for table in ['wall_check_records','wall_control_decisions','wall_controls']:op.drop_table(table)
