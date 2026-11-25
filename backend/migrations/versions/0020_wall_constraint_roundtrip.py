"""Keep the wall-type whitelist stable through PostgreSQL dump/restore parsing.

PostgreSQL reparses IN/varchar-array casts into equivalent element casts during
restore. Scalar text comparisons retain the same whitelist and stable metadata.
SQLite keeps the existing equivalent IN constraint; its dump format is not used.
"""
from alembic import op
revision='0020'
down_revision='0019'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.drop_constraint('ck_wall_control_type','wall_controls',type_='check')
        op.create_check_constraint('ck_wall_control_type','wall_controls',"entry_type::text = 'restriction'::text OR entry_type::text = 'relationship'::text OR entry_type::text = 'retirement'::text")

def downgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.drop_constraint('ck_wall_control_type','wall_controls',type_='check')
        op.create_check_constraint('ck_wall_control_type','wall_controls',"entry_type IN ('restriction','relationship','retirement')")
