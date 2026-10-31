"""email delivery log

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'email_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('to_email', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('template', sa.String(length=50), nullable=False),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column('text_body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_logs_to_email', 'email_logs', ['to_email'])
    op.create_index('ix_email_logs_template', 'email_logs', ['template'])
    op.create_index('ix_email_logs_created_at', 'email_logs', ['created_at'])
    op.create_index('ix_email_logs_status_created', 'email_logs', ['status', 'created_at'])


def downgrade() -> None:
    op.drop_table('email_logs')
