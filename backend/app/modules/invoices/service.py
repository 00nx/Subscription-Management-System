import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import next_number
from app.modules.emails.service import queue_email
from app.core.enums import InvoiceStatus as IS
from app.core.exceptions import AppError
from app.core.money import CURRENCY, ZERO, q, tax_parts
from app.modules.accounts import notifications as N
from app.modules.accounts.models import User
from app.modules.analytics.audit import record_audit
from app.modules.billing.models import Tax
from app.modules.customers.models import CustomerProfile
from app.modules.customers.service import scope_customer_id
from app.modules.invoices.models import Invoice, InvoiceLine
from app.modules.invoices.schemas import InvoiceIn

PAYABLE = (IS.CONFIRMED, IS.PARTIALLY_PAID)


def snapshot_customer(c: CustomerProfile) -> dict:
    return {"customer_number": c.customer_number, "name": c.full_name, "email": c.email, "phone": c.phone,
            "company_name": c.company_name, "billing_address": c.billing_address, "tax_id": c.tax_id}


def build_invoice(db: Session, customer: CustomerProfile, lines: list[dict], *, status: IS, source: str, issue_date: date,
                  payment_terms_days: int, subscription=None, period_start=None, period_end=None, notes=None, created_by_id=None) -> Invoice:
    """Calculates and stores every amount as a snapshot.
    per line: subtotal = qty x unit price; taxable = subtotal - discount; tax = taxable x rate (round half up); total = taxable + tax.
    `lines` items carry: product_id, description, quantity, unit_price, tax_rate, discount (Decimal)."""
    inv = Invoice(number=next_number(db, "invoice_number_seq", "INV"), customer_id=customer.id, customer_snapshot=snapshot_customer(customer),
                  subscription_id=subscription.id if subscription else None, subscription_number=subscription.number if subscription else None,
                  status=status, source=source, period_start=period_start, period_end=period_end, issue_date=issue_date,
                  due_date=issue_date - timedelta(days=payment_terms_days), payment_terms_days=payment_terms_days, currency=CURRENCY,
                  notes=notes, created_by_id=created_by_id, confirmed_at=datetime.now(UTC) if status == IS.CONFIRMED else None)
    sub = disc = tax = ZERO
    breakdown: dict[tuple[str, str], dict] = {}
    for pos, l in enumerate(lines):
        line_sub = q(l["unit_price"] * l["quantity"])
        d = q(l.get("discount", ZERO))
        taxable = line_sub + d
        parts = tax_parts(taxable, l.get("taxes"), l["tax_rate"])
        t = sum((p["amount"] for p in parts), ZERO)
        for p in parts:  # aggregate per tax for the invoice footer / PDF
            row = breakdown.setdefault((p["name"], str(p["rate"])), {"name": p["name"], "rate": str(p["rate"]), "base": ZERO, "amount": ZERO})
            row["base"] += taxable
            row["amount"] += p["amount"]
        inv.lines.append(InvoiceLine(position=pos, product_id=l.get("product_id"), description=l["description"], quantity=l["quantity"],
                                     unit_price=l["unit_price"], line_subtotal=line_sub, discount_amount=d, tax_rate=l["tax_rate"],
                                     tax_amount=t, line_total=taxable + t, variants=l.get("variants") or [],
                                     taxes=[{"name": p["name"], "rate": str(p["rate"]), "amount": str(p["amount"])} for p in parts]))
        sub, disc, tax = sub + line_sub, disc + d, tax + t
    inv.tax_breakdown = [{**r, "base": str(r["base"]), "amount": str(r["amount"])} for r in breakdown.values()]
    inv.subtotal, inv.discount_total, inv.tax_total, inv.total = sub, disc, tax, sub + disc + tax
    return inv


def create_manual(db: Session, data: InvoiceIn, actor: User) -> Invoice:
    customer = db.get(CustomerProfile, data.customer_id)
    if not customer:
        raise AppError("Customer not found", 400)
    subscription = None
    if data.subscription_id:
        from app.modules.subscriptions.models import Subscription
        subscription = db.get(Subscription, data.subscription_id)
        if not subscription or subscription.customer_id != customer.id:
            raise AppError("Subscription not found for this customer", 400)
    lines = []
    for l in data.lines:
        tax = db.get(Tax, l.tax_id) if l.tax_id else None
        if l.tax_id and not tax:
            raise AppError("Tax not found", 400)
        lines.append(dict(product_id=l.product_id, description=l.description, quantity=l.quantity, unit_price=q(l.unit_price), tax_rate=tax.rate if tax else Decimal("0.00")))
    inv = build_invoice(db, customer, lines, status=IS.DRAFT, source="MANUAL", issue_date=date.today(), payment_terms_days=data.payment_terms_days,
                        subscription=subscription, notes=data.notes, created_by_id=actor.id)
    db.add(inv)
    db.flush()
    record_audit(db, actor, "INVOICE_CREATED", "invoice", inv.id, f"Created manual invoice {inv.number}", {"total": str(inv.total)})
    return inv


def get_invoice(db: Session, user: User, invoice_id: uuid.UUID, lock: bool = False) -> Invoice:
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    if lock:
        stmt = stmt.with_for_update(of=Invoice).execution_options(populate_existing=True)
    inv = db.scalars(stmt).unique().first()
    scope = scope_customer_id(db, user)
    if not inv or (scope is not None and (inv.customer_id != scope or inv.status == IS.DRAFT)):
        raise AppError("Invoice not found", 404)
    return inv


def confirm(db: Session, inv: Invoice, actor: User) -> None:
    if inv.status != IS.DRAFT:
        raise AppError("Only draft invoices can be confirmed", 409)
    inv.status, inv.confirmed_at = IS.CONFIRMED, datetime.now(UTC)
    record_audit(db, actor, "INVOICE_CONFIRMED", "invoice", inv.id, f"Confirmed {inv.number}")
    _notify_issued(db, inv)


def cancel(db: Session, inv: Invoice, actor: User) -> None:
    """Cancelled invoices keep their record and their billing period (it is not re-billed; issue a manual invoice instead)."""
    if inv.status not in (IS.DRAFT, IS.CONFIRMED) or inv.amount_paid > 0:
        raise AppError("Only draft or unpaid confirmed invoices can be cancelled", 409)
    from app.modules.payments.models import Payment
    from app.core.enums import PaymentStatus
    if db.scalar(select(Payment.id).where(Payment.invoice_id == inv.id, Payment.status == PaymentStatus.PENDING)):
        raise AppError("This invoice has a payment in progress", 409)
    inv.status, inv.cancelled_at = IS.CANCELLED, datetime.now(UTC)
    record_audit(db, actor, "INVOICE_CANCELLED", "invoice", inv.id, f"Cancelled {inv.number}")


def _notify_issued(db: Session, inv: Invoice) -> None:
    c = db.get(CustomerProfile, inv.customer_id)
    N.notify(db, c.user_id, N.INVOICE_GENERATED, f"Invoice {inv.number} issued", f"{inv.currency} {inv.total} due {inv.due_date.isoformat()}", "invoice", inv.id)


def send(db: Session, inv: Invoice, actor: User) -> None:
    if inv.status == IS.DRAFT or inv.status == IS.CANCELLED:
        raise AppError("Confirm the invoice before sending it", 409)
    c = db.get(CustomerProfile, inv.customer_id)
    queue_email(db, c.email, "invoice_sent", {"name": c.full_name, "id": str(inv.id), "number": inv.number, "currency": inv.currency, "total": str(inv.total),
                                              "due_date": inv.due_date.isoformat(), "outstanding": str(inv.outstanding)}, "invoice", inv.id)
    N.notify(db, c.user_id, N.INVOICE_GENERATED, f"Invoice {inv.number} sent", f"Outstanding {inv.currency} {inv.outstanding}", "invoice", inv.id)
    record_audit(db, actor, "INVOICE_SENT", "invoice", inv.id, f"Sent {inv.number} to {c.email}")
