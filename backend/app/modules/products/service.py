import uuid
from decimal import Decimal

from sqlalchemy import literal, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.enums import RecordStatus
from app.core.exceptions import AppError
from app.core.money import q
from app.modules.billing.models import Tax
from app.modules.products.models import Product, ProductVariant

_REFERENCING = ("subscription_lines", "quotation_lines", "invoice_lines", "plan_products", "subscription_plans",
                "quotation_template_lines", "discount_products")


def get_product(db: Session, product_id: uuid.UUID) -> Product:
    p = db.get(Product, product_id)
    if not p:
        raise AppError("Product not found", 404)
    return p


def get_variant(db: Session, product: Product, variant_id: uuid.UUID) -> ProductVariant:
    v = db.get(ProductVariant, variant_id)
    if not v or v.product_id != product.id:
        raise AppError("Variant does not belong to this product", 400)
    return v


def references_exist(db: Session, tables: tuple[str, ...], column: str, value: uuid.UUID) -> bool:
    """True if any row in the named tables points at `value` (looked up through the mapped tables, so UUIDs bind correctly)."""
    return any(db.scalar(select(literal(1)).select_from(Base.metadata.tables[t]).where(Base.metadata.tables[t].c[column] == value).limit(1)) for t in tables)


def is_referenced(db: Session, product_id: uuid.UUID) -> bool:
    return references_exist(db, _REFERENCING, "product_id", product_id)


def check_tax(db: Session, tax_id: uuid.UUID | None) -> None:
    if tax_id and not db.get(Tax, tax_id):
        raise AppError("Tax not found", 400)


def check_extra_taxes(db: Session, ids: list[uuid.UUID]) -> list[str]:
    out = list(dict.fromkeys(str(i) for i in ids))
    for i in out:
        check_tax(db, uuid.UUID(i))
    return out


def variant_price(product: Product, variant: ProductVariant | None) -> Decimal:
    """Variant pricing: base sales price + the variant's configurable additional amount (e.g. 'Odoo brand' = +560)."""
    return q(product.sales_price + (variant.additional_price if variant else 0))


def taxes_for(db: Session, product: Product) -> list[dict]:
    """Active taxes that apply to a product line, as snapshots: its own (primary + extra) plus every tax that applies to all lines."""
    ids = [i for i in [product.tax_id, *(product.extra_tax_ids or [])] if i]
    cond = Tax.applies_to == "ALL"
    if ids:
        cond = cond | Tax.id.in_([uuid.UUID(str(i)) for i in ids])
    found = db.scalars(select(Tax).where(cond, Tax.status == RecordStatus.ACTIVE).order_by(Tax.created_at, Tax.name)).all()
    return [{"id": str(t.id), "name": t.name, "rate": str(t.rate)} for t in found]


def tax_rate_for(db: Session, product: Product, tax_id: uuid.UUID | None = None) -> tuple[uuid.UUID | None, Decimal]:
    """Returns (tax_id, rate snapshot). Inactive/archived taxes contribute 0%."""
    tid = tax_id or product.tax_id
    tax = db.get(Tax, tid) if tid else None
    return (tid, tax.rate if tax and tax.status == RecordStatus.ACTIVE else Decimal("0.00"))
