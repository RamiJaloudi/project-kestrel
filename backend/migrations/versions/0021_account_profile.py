"""Account profile metadata; employee identifiers belong to an employer."""
from alembic import op
import sqlalchemy as sa

revision='0021'
down_revision='0020'
branch_labels=None
depends_on=None


def prepare():
    db=op.get_bind()
    views=[]
    if db.dialect.name=='sqlite':
        with op.get_context().autocommit_block():op.execute('PRAGMA foreign_keys=OFF')
        views=db.execute(sa.text("SELECT name,sql FROM sqlite_master WHERE type='view'")).all()
        for name,sql in views:op.execute('DROP VIEW "'+name+'"')
    return views


def finish(views):
    for name,sql in views:op.execute(sql)
    if op.get_bind().dialect.name=='sqlite':
        with op.get_context().autocommit_block():op.execute('PRAGMA foreign_keys=ON')
        if op.get_bind().exec_driver_sql('PRAGMA foreign_key_check').first():raise RuntimeError('Profile migration foreign key check failed')


def upgrade():
    views=prepare()
    op.add_column('accounts',sa.Column('display_name',sa.String(128),nullable=False,server_default=''))
    op.add_column('accounts',sa.Column('employee_id',sa.String(40),nullable=True))
    op.add_column('accounts',sa.Column('profile_revision',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('accounts',sa.Column('password_customized',sa.Boolean(),nullable=False,server_default=sa.false()))
    db=op.get_bind()
    counts={}
    for row in db.execute(sa.text('SELECT id, username, organization_id FROM accounts ORDER BY username')).mappings():
        counts[row['organization_id']]=counts.get(row['organization_id'],0)+1
        name=row['username'].split('@')[0].replace('.',' ').replace('_',' ').title()
        db.execute(sa.text('UPDATE accounts SET display_name=:name, employee_id=:employee WHERE id=:id'),{'name':name,'employee':f"EMP-{counts[row['organization_id']]:06d}",'id':row['id']})
    with op.batch_alter_table('accounts') as batch:
        batch.alter_column('employee_id',existing_type=sa.String(40),nullable=False)
        batch.create_unique_constraint('uq_account_employer_employee',['organization_id','employee_id'])
    finish(views)


def downgrade():
    views=prepare()
    with op.batch_alter_table('accounts') as batch:
        batch.drop_constraint('uq_account_employer_employee',type_='unique')
        for name in ['password_customized','profile_revision','employee_id','display_name']:
            batch.drop_column(name)

    finish(views)
