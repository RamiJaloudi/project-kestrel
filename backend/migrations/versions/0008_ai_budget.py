"""Project-scoped conservative live AI reservations, two dollars/run, ten/month."""
from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('ai_budget_periods',sa.Column('period',sa.String(7),primary_key=True),
        sa.Column('spent_cents',sa.Integer,nullable=False),sa.Column('reserved_cents',sa.Integer,nullable=False))
    op.create_table('ai_reservations',sa.Column('job_id',sa.String(36),sa.ForeignKey('analysis_jobs.id'),primary_key=True),
        sa.Column('period',sa.String(7),sa.ForeignKey('ai_budget_periods.period'),nullable=False),
        sa.Column('reserved_cents',sa.Integer,nullable=False),sa.Column('charged_cents',sa.Integer,nullable=True),
        sa.Column('state',sa.String(32),nullable=False),sa.Column('created_at',sa.Integer,nullable=False))

def downgrade():
    op.drop_table('ai_reservations');op.drop_table('ai_budget_periods')
