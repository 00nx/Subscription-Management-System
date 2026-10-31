"""account lockout counters and staff discount permission

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('can_manage_discounts', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'can_manage_discounts')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
