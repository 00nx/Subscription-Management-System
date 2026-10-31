import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import InvoiceStatus as IS, PaymentMethod, PaymentStatus as PS
from app.core.exceptions import AppError
from app.core.money import q
from app.modules.accounts import notifications as N
from app.modules.emails.service import queue_email
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.customers.models import CustomerProfile
from app.modules.customers.service import scope_customer_id
from app.modules.invoices import service as invoices
from app.modules.invoices.models import Invoice
from app.modules.payments.models import Payment, PaymentTransaction
from app.modules.payments.providers import get_provider


def _log(db: Session, p: Payment, event: str, status: str, message: str = "", reference: str | None = None) -> None:
    p.transactions.append(PaymentTransaction(provider=p.provider, provider_reference=reference or p.transaction_reference, event=event, status=status, message=message))


def get_payment(db: Session, user: User, payment_id: uuid.UUID, lock: bool = False) -> Payment:
    stmt = select(Payment).where(Payment.id == payment_id)
    if lock:
        stmt = stmt.with_for_update(of=Payment).execution_options(populate_existing=True)
    p = db.scalars(stmt).unique().first()
    scope = scope_customer_id(db, user)
    if not p or (scope is not None and p.customer_id != scope):
        raise AppError("Payment not found", 404)
    return p


def _payable_invoice(db: Session, user: User, invoice_id: uuid.UUID) -> Invoice:
    inv = invoices.get_invoice(db, user, invoice_id)  # customers: own, non-draft only
    if inv.status not in invoices.PAYABLE:
        raise AppError(f"Invoice {inv.number} is {inv.status.value.lower().replace('_', ' ')} and cannot be paid", 409)
    return inv


def _check_amount(inv: Invoice, amount: Decimal) -> None:
    if not get_settings().allow_overpayment and amount > inv.outstanding:
        raise AppError(f"Amount exceeds the outstanding balance of {inv.outstanding}", 422)


def _existing_by_key(db: Session, key: str | None) -> Payment | None:
    return db.scalars(select(Payment).where(Payment.idempotency_key == key)).unique().first() if key else None


def apply_success(db: Session, p: Payment, actor: User | None) -> None:
    """Credits the invoice. Caller holds the payment row lock; the invoice row is locked here, so two payments cannot
    both pass the balance check."""
    inv = db.scalars(select(Invoice).where(Invoice.id == p.invoice_id).with_for_update(of=Invoice).execution_options(populate_existing=True)).unique().one()
    if inv.status not in invoices.PAYABLE or (not get_settings().allow_overpayment and p.amount > inv.outstanding):
        p.status = PS.FAILED
        _log(db, p, "REJECTED", "FAILED", "Invoice cannot accept this amount (already paid, cancelled or overpayment)")
        N.notify(db, db.get(CustomerProfile, p.customer_id).user_id, N.PAYMENT_FAILED, "Payment could not be applied", inv.number, "payment", p.id)
        raise AppError("Invoice cannot accept this payment (balance changed or invoice closed)", 409)
    inv.amount_paid = q(inv.amount_paid + p.amount)
    inv.status = IS.PAID if inv.amount_paid >= inv.total else IS.PARTIALLY_PAID
    p.status, p.payment_date = PS.SUCCESS, datetime.now(UTC)
    _log(db, p, "SUCCEEDED", "SUCCESS", "Payment applied to invoice")
    record_audit(db, actor, "PAYMENT_RECORDED", "payment", p.id, f"{p.method.value} payment {p.amount} on {inv.number}", {"invoice_status": inv.status.value})
    cust = db.get(CustomerProfile, p.customer_id)
    queue_email(db, cust.email, "payment_received", {"name": cust.full_name, "invoice": inv.number, "invoice_id": str(inv.id), "currency": inv.currency, "amount": str(p.amount),
                                                     "method": p.method.value.replace("_", " ").title(), "outstanding": str(inv.outstanding)}, "payment", p.id)
    N.notify(db, db.get(CustomerProfile, p.customer_id).user_id, N.PAYMENT_SUCCESS, f"Payment of {inv.currency} {p.amount} received", f"Invoice {inv.number}: {inv.status.value.replace('_', ' ').title()}", "payment", p.id)


def record_manual(db: Session, actor: User, invoice_id: uuid.UUID, method: PaymentMethod, amount: Decimal, reference: str | None,
                  notes: str | None, key: str | None) -> Payment:
    """Staff record money received outside the system. Succeeds immediately (the staff member is the confirmation)."""
    if prior := _existing_by_key(db, key):
        return prior  # idempotent replay
    inv = _payable_invoice(db, actor, invoice_id)
    amount = q(amount)
    _check_amount(inv, amount)
    p = Payment(invoice_id=inv.id, customer_id=inv.customer_id, method=method, amount=amount, status=PS.PENDING, provider="MANUAL",
                transaction_reference=reference, notes=notes, idempotency_key=key, recorded_by_id=actor.id)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("A payment with this reference or idempotency key already exists", 409)
    _log(db, p, "RECORDED", "PENDING", "Recorded by staff")
    apply_success(db, p, actor)
    return p


def initiate(db: Session, user: User, invoice_id: uuid.UUID, method: PaymentMethod, amount: Decimal | None, key: str | None) -> Payment:
    if prior := _existing_by_key(db, key):
        if scope_customer_id(db, user) not in (None, prior.customer_id) or prior.invoice_id != invoice_id:
            raise AppError("Idempotency key already used", 409)
        return prior
    inv = _payable_invoice(db, user, invoice_id)
    amount = q(amount if amount is not None else inv.outstanding)
    _check_amount(inv, amount)
    provider = get_provider("SIMULATED")
    p = Payment(invoice_id=inv.id, customer_id=inv.customer_id, method=method, amount=amount, status=PS.PENDING, provider=provider.name,
                idempotency_key=key, recorded_by_id=user.id if user.role != UserRole.CUSTOMER else None)
    db.add(p)
    db.flush()
    res = provider.initiate(p)
    p.transaction_reference = res.reference
    _log(db, p, "INITIATED", res.status, res.message, res.reference)
    return p


def complete(db: Session, user: User, payment_id: uuid.UUID, outcome: str) -> Payment:
    """Simulated-gateway callback. The payment row is locked, so a double submit cannot apply twice."""
    p = get_payment(db, user, payment_id, lock=True)
    if p.provider != "SIMULATED":
        raise AppError("Only simulated payments can be completed here", 400)
    if p.status != PS.PENDING:
        raise AppError(f"Payment is already {p.status.value.lower()}", 409)
    res = get_provider(p.provider).complete(p, outcome)
    if res.status == "SUCCESS":
        apply_success(db, p, user)
    else:
        p.status = PS(res.status)
        _log(db, p, res.status, res.status, res.message)
        if res.status == "FAILED":
            N.notify(db, db.get(CustomerProfile, p.customer_id).user_id, N.PAYMENT_FAILED, "Payment failed", f"Invoice {p.invoice.number}", "payment", p.id)
        record_audit(db, user, "PAYMENT_" + res.status, "payment", p.id, f"Simulated payment {res.status.lower()} on {p.invoice.number}")
    return p
