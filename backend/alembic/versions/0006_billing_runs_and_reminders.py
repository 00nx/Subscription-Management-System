"""billing run history and manual invoice reminders

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'billing_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('trigger', sa.String(length=20), nullable=False),
        sa.Column('triggered_by_id', sa.UUID(), nullable=True),
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('batches', sa.Integer(), nullable=False),
        sa.Column('examined', sa.Integer(), nullable=False),
        sa.Column('invoiced', sa.Integer(), nullable=False),
        sa.Column('recovered', sa.Integer(), nullable=False),
        sa.Column('skipped_locked', sa.Integer(), nullable=False),
        sa.Column('failed', sa.Integer(), nullable=False),
        sa.Column('renewed', sa.Integer(), nullable=False),
        sa.Column('expired', sa.Integer(), nullable=False),
        sa.Column('failures', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.ForeignKeyConstraint(['triggered_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_billing_runs_status', 'billing_runs', ['status'])
    op.create_index('ix_billing_runs_started_at', 'billing_runs', ['started_at'])
    op.add_column('invoices', sa.Column('reminder_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('invoices', sa.Column('last_reminded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('invoices', 'last_reminded_at')
    op.drop_column('invoices', 'reminder_count')
    op.drop_index('ix_billing_runs_started_at', table_name='billing_runs')
    op.drop_index('ix_billing_runs_status', table_name='billing_runs')
    op.drop_table('billing_runs')
