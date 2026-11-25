"""Bind optional discussion context to an immutable report section."""
from alembic import op
import sqlalchemy as sa
revision='0024'
down_revision='0023'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('collaboration_messages',sa.Column('section_index',sa.Integer(),nullable=True))

def downgrade():
    # Discussion context is a retained record. Do not silently discard it.
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM collaboration_messages WHERE section_index IS NOT NULL')):
        raise RuntimeError('Retained section discussions require an explicit archival rollback plan')
    op.drop_column('collaboration_messages','section_index')
