"""Stable display numbers and client+matter composite uniqueness."""
from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

OLD_VIEW='''CREATE VIEW vw_client_matter_validation AS
SELECT m.id AS matter_id,m.name AS matter_name,c.id AS client_id,c.name AS client_name,
v.status AS validation_status,v.revision
FROM matters m JOIN matter_validations v ON v.matter_id=m.id JOIN clients c ON c.id=v.client_id'''
NEW_VIEW='''CREATE VIEW vw_client_matter_validation AS
SELECT m.id AS matter_id,m.name AS matter_name,c.id AS client_id,c.name AS client_name,
c.client_number,v.matter_number,c.client_number || '-' || v.matter_number AS client_matter_number,
v.status AS validation_status,v.revision
FROM matters m JOIN matter_validations v ON v.matter_id=m.id JOIN clients c ON c.id=v.client_id'''

def upgrade():
    sqlite_foreign_keys(False)
    op.execute('DROP VIEW vw_client_matter_validation')
    op.add_column('clients',sa.Column('client_number',sa.String(12),nullable=True))
    op.add_column('matter_validations',sa.Column('matter_number',sa.String(12),nullable=True))
    connection=op.get_bind()
    # The existing store is a synthetic demo; retain UUIDs and allocate numbers.
    for index,row in enumerate(connection.execute(sa.text('SELECT id FROM clients ORDER BY id')).all()):
        connection.execute(sa.text('UPDATE clients SET client_number=:number WHERE id=:id'),{'number':str(900000+index),'id':row[0]})
    for index,row in enumerate(connection.execute(sa.text('SELECT matter_id FROM matter_validations ORDER BY client_id,matter_id')).all()):
        connection.execute(sa.text('UPDATE matter_validations SET matter_number=:number WHERE matter_id=:id'),{'number':str(900000+index),'id':row[0]})
    with op.batch_alter_table('clients') as batch:
        batch.alter_column('client_number',existing_type=sa.String(12),nullable=False)
        batch.create_unique_constraint('uq_client_number',['client_number'])
    with op.batch_alter_table('matter_validations') as batch:
        batch.alter_column('matter_number',existing_type=sa.String(12),nullable=False)
        batch.create_unique_constraint('uq_client_matter_number',['client_id','matter_number'])
    op.execute(NEW_VIEW)
    sqlite_foreign_keys(True)

def downgrade():
    sqlite_foreign_keys(False)
    op.execute('DROP VIEW vw_client_matter_validation')
    with op.batch_alter_table('matter_validations') as batch:
        batch.drop_constraint('uq_client_matter_number',type_='unique');batch.drop_column('matter_number')
    with op.batch_alter_table('clients') as batch:
        batch.drop_constraint('uq_client_number',type_='unique');batch.drop_column('client_number')
    op.execute(OLD_VIEW)
    sqlite_foreign_keys(True)

def sqlite_foreign_keys(enabled):
    if op.get_bind().dialect.name=='sqlite':
        # SQLite table-copy DDL must release incoming FK enforcement outside a
        # transaction. Only used by isolated/local SQLite migration fallback.
        with op.get_context().autocommit_block():
            op.execute('PRAGMA foreign_keys='+('ON' if enabled else 'OFF'))
        if enabled and op.get_bind().exec_driver_sql('PRAGMA foreign_key_check').first():
            raise RuntimeError('Registry migration foreign-key check failed')
