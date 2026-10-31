"""multi-variant and multi-tax snapshots, tax applicability, invoice breakdowns, template default discount

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

_JSON = postgresql.JSONB(astext_type=sa.Text())


def _json(name):
    return sa.Column(name, _JSON, server_default=sa.text("'[]'"), nullable=False)


def upgrade() -> None:
    for table, cols in {
        'subscription_lines': ('variants', 'taxes'), 'quotation_lines': ('variants', 'taxes'), 'invoice_lines': ('variants', 'taxes'),
        'quotation_template_lines': ('variant_ids',), 'invoices': ('tax_breakdown', 'discount_breakdown'), 'products': ('extra_tax_ids',),
    }.items():
        for c in cols:
            op.add_column(table, _json(c))
    op.add_column('taxes', sa.Column('applies_to', sa.String(length=20), server_default='PRODUCTS', nullable=False))
    op.add_column('quotation_templates', sa.Column('discount_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_quotation_templates_discount', 'quotation_templates', 'discounts', ['discount_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_quotation_templates_discount', 'quotation_templates', type_='foreignkey')
    op.drop_column('quotation_templates', 'discount_id')
    op.drop_column('taxes', 'applies_to')
    for table, cols in {
        'subscription_lines': ('variants', 'taxes'), 'quotation_lines': ('variants', 'taxes'), 'invoice_lines': ('variants', 'taxes'),
        'quotation_template_lines': ('variant_ids',), 'invoices': ('tax_breakdown', 'discount_breakdown'), 'products': ('extra_tax_ids',),
    }.items():
        for c in cols:
            op.drop_column(table, c)
