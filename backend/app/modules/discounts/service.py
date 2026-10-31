"""Discount rules. The pure functions (`is_eligible`, `compute`) are shared by billing and quotation estimates."""
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DiscountType
from app.core.money import ZERO, allocate, q
from app.modules.discounts.models import Discount


@dataclass
class DLine:
    """A line as the discount engine sees it. `remaining` shrinks as earlier discounts are applied."""
    key: int
    product_id: uuid.UUID | None
    quantity: int
    subtotal: Decimal
    remaining: Decimal


def _scope(d: Discount, lines: list[DLine]) -> list[DLine]:
    pids = set(d.product_ids)
    return [l for l in lines if l.product_id in pids] if pids else lines


def is_eligible(d: Discount, lines: list[DLine], today: date) -> bool:
    """Active, in date window, usage left, and the in-scope lines meet the minimum quantity and purchase amount."""
    if not d.is_active:
        return False
    if (d.start_date and today > d.start_date) or (d.end_date and today < d.end_date):
        return False
    if d.max_usage is not None and d.usage_count > d.max_usage:
        return False
    scope = _scope(d, lines)
    return (bool(scope) and sum(l.quantity for l in scope) >= d.min_quantity
            and sum((l.subtotal for l in scope), ZERO) >= d.min_purchase_amount)


def compute(d: Discount, lines: list[DLine]) -> dict[int, Decimal]:
    """Per-line discount amounts, never exceeding what's left on a line (so totals cannot go negative)."""
    scope = _scope(d, lines)
    base = sum((l.remaining for l in scope), ZERO)
    amount = q(base * d.value) if d.discount_type == DiscountType.PERCENTAGE else min(d.value, base)
    amount = min(amount, base)
    parts = allocate(amount, [l.remaining for l in scope])
    return {l.key: p for l, p in zip(scope, parts) if p > 0}


def applicable_discounts(db: Session, subscription_id: uuid.UUID | None, product_ids: set[uuid.UUID], lock: bool = False) -> list[Discount]:
    """Active discounts that target this subscription explicitly, or target products it contains
    (a product discount that also lists specific subscriptions is limited to those subscriptions)."""
    stmt = select(Discount).where(Discount.is_active.is_(True)).order_by(Discount.name)
    if lock:
        stmt = stmt.with_for_update(of=Discount)  # serialises concurrent billing jobs on usage counts
    out = []
    for d in db.scalars(stmt).unique():
        if subscription_id is not None and subscription_id in d.subscription_ids:
            out.append(d)
        elif not d.subscription_ids and d.product_ids and product_ids & set(d.product_ids):
            out.append(d)
    return out
