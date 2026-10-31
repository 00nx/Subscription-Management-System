"""Razorpay payment flow on top of the generic Payment model. See razorpay.py for the security model."""
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import PaymentMethod, PaymentStatus as PS
from app.core.exceptions import AppError
from app.core.money import q
from app.modules.accounts import notifications as N
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.customers.models import CustomerProfile
from app.modules.payments import razorpay as rz
from app.modules.payments.models import Payment, PaymentTransaction
from app.modules.payments.service import _check_amount, _existing_by_key, _log, _payable_invoice, apply_success, get_payment
from app.modules.customers.service import scope_customer_id

log = logging.getLogger(__name__)
PROVIDER = "RAZORPAY"
_METHODS = {"card": PaymentMethod.CARD, "upi": PaymentMethod.UPI}


def paise(amount) -> int:
    return int((q(amount) * 100).to_integral_value())


def create_order(db: Session, user: User, invoice_id: uuid.UUID, amount, key: str | None) -> Payment:
    """Creates our PENDING Payment and a Razorpay order for exactly that amount. The amount is validated against the invoice here,
    never trusted from the browser, and replaying the same idempotency key returns the same order."""
    rz.require_enabled()
    if prior := _existing_by_key(db, key):
        if scope_customer_id(db, user) not in (None, prior.customer_id) or prior.invoice_id != invoice_id or prior.provider != PROVIDER:
            raise AppError("Idempotency key already used", 409)
        return prior
    inv = _payable_invoice(db, user, invoice_id)
    amt = q(amount if amount is not None else inv.outstanding)
    if amt <= 0:
        raise AppError("Nothing to pay on this invoice", 409)
    _check_amount(inv, amt)
    p = Payment(invoice_id=inv.id, customer_id=inv.customer_id, method=PaymentMethod.OTHER, amount=amt, status=PS.PENDING, provider=PROVIDER,
                idempotency_key=key, recorded_by_id=user.id if user.role != UserRole.CUSTOMER else None)
    db.add(p)
    db.flush()
    order = rz.client().create_order(paise(amt), inv.currency, f"{inv.number}-{p.id.hex[:8]}", {"invoice": inv.number, "payment_id": str(p.id)})
    p.transaction_reference = order["id"]
    _log(db, p, "ORDER_CREATED", "PENDING", f"Razorpay order {order['id']} for {paise(amt)} paise", order["id"])
    return p


def _apply_captured(db: Session, p: Payment, rp_payment_id: str, method: str | None, source: str) -> None:
    """Settles a PENDING payment exactly once (callers hold the payment row lock)."""
    if p.status == PS.SUCCESS:
        _log(db, p, f"{source}_DUPLICATE", "SUCCESS", f"Already settled; ignoring repeat for {rp_payment_id}", rp_payment_id)
        return
    if p.status != PS.PENDING:
        _log(db, p, f"{source}_IGNORED", p.status.value, f"Payment is {p.status.value.lower()}; captured money for {rp_payment_id} may need a manual refund", rp_payment_id)
        return
    p.method = _METHODS.get((method or "").lower(), PaymentMethod.OTHER)
    _log(db, p, f"{source}_CAPTURED", "PENDING", f"Razorpay payment {rp_payment_id} captured", rp_payment_id)
    try:
        apply_success(db, p, None)
    except AppError as exc:  # the invoice was settled meanwhile: money was taken but cannot be applied -> visible FAILED row for refund
        _log(db, p, "CAPTURED_BUT_REJECTED", "FAILED", f"{exc.message}. Refund {rp_payment_id} in the Razorpay dashboard.", rp_payment_id)
        record_audit(db, None, "PAYMENT_NEEDS_REFUND", "payment", p.id, f"Razorpay {rp_payment_id} captured but invoice could not accept it")
        raise


def _capture(db: Session, p: Payment, rp_payment_id: str) -> dict | None:
    """Captures an authorized payment server-side. Returns Razorpay's payment, or None (and a log line) if that is not possible right now."""
    try:
        done = rz.client().capture_payment(rp_payment_id, paise(p.amount), p.invoice.currency)
    except AppError as exc:
        _log(db, p, "CAPTURE_FAILED", "PENDING", f"Authorized but could not be captured automatically ({exc.message}). Capture it in the Razorpay dashboard or retry.", rp_payment_id)
        return None
    _log(db, p, "CAPTURED_BY_SERVER", "PENDING", f"Authorized payment {rp_payment_id} captured by Brightloop", rp_payment_id)
    return done


def verify_checkout(db: Session, user: User, payment_id: uuid.UUID, order_id: str, rp_payment_id: str, signature: str) -> Payment:
    """Browser hand-off: validates the signature, then CONFIRMS with Razorpay server-to-server before crediting anything."""
    p = get_payment(db, user, payment_id, lock=True)
    if p.provider != PROVIDER or p.transaction_reference != order_id:
        raise AppError("This payment does not match the Razorpay order", 400)
    if p.status == PS.SUCCESS:
        return p
    if p.status != PS.PENDING:
        raise AppError(f"Payment is already {p.status.value.lower()}", 409)
    if not rz.verify_payment_signature(order_id, rp_payment_id, signature):
        _log(db, p, "SIGNATURE_INVALID", "PENDING", "Checkout signature did not verify", rp_payment_id)
        db.commit()
        raise AppError("Payment signature verification failed", 400)
    _log(db, p, "SIGNATURE_VERIFIED", "PENDING", "Checkout signature verified", rp_payment_id)
    try:
        remote = rz.client().fetch_payment(rp_payment_id)
    except AppError as exc:
        _log(db, p, "CONFIRMATION_PENDING", "PENDING", f"Could not confirm with Razorpay ({exc.message}); the webhook will settle it", rp_payment_id)
        return p
    if remote.get("order_id") != order_id or int(remote.get("amount", -1)) != paise(p.amount):
        _log(db, p, "CONFIRMATION_MISMATCH", "PENDING", "Razorpay payment does not match this order/amount; not credited", rp_payment_id)
        db.commit()
        raise AppError("Razorpay payment does not match this order", 400)
    if remote.get("status") == "authorized" and (done := _capture(db, p, rp_payment_id)):
        remote = {**remote, **done}
    if remote.get("status") == "captured":
        try:
            _apply_captured(db, p, rp_payment_id, remote.get("method"), "CHECKOUT")
        except AppError:
            db.commit()  # keep the FAILED / needs-refund trail even though the request answers with an error
            raise
    elif remote.get("status") == "failed":
        p.status = PS.FAILED
        _log(db, p, "FAILED", "FAILED", remote.get("error_description") or "Razorpay reports the payment failed", rp_payment_id)
        N.notify(db, db.get(CustomerProfile, p.customer_id).user_id, N.PAYMENT_FAILED, "Payment failed", f"Invoice {p.invoice.number}", "payment", p.id)
    else:
        _log(db, p, "CONFIRMATION_PENDING", "PENDING", f"Razorpay status is '{remote.get('status')}'; waiting for capture", rp_payment_id)
    return p


def handle_webhook(db: Session, raw_body: bytes, signature: str | None, event_id: str | None) -> str:
    """Signed, idempotent webhook. Returns a short outcome string; raises AppError(400) only for a bad signature or body."""
    if not get_settings().razorpay_webhook_secret:  # the webhook needs only its own secret; API key validity is irrelevant to verifying a signature
        raise AppError("Webhook secret not configured: set RAZORPAY_WEBHOOK_SECRET in backend/.env and restart", 503)
    if not rz.verify_webhook_signature(raw_body, signature):
        raise AppError("Invalid webhook signature", 400)
    try:
        event = json.loads(raw_body)
        etype = event["event"]
        entity = event.get("payload", {}).get("payment", {}).get("entity") or {}
    except (ValueError, KeyError, TypeError):
        raise AppError("Malformed webhook body", 400)
    order_id, rp_id = entity.get("order_id"), entity.get("id")
    if etype == "order.paid":  # carries the payment under payload.payment too; the order id may also sit under payload.order
        order_id = order_id or event.get("payload", {}).get("order", {}).get("entity", {}).get("id")
    if not order_id:
        return "ignored: no order"
    p = db.scalars(select(Payment).where(Payment.transaction_reference == order_id, Payment.provider == PROVIDER)
                   .with_for_update(of=Payment).execution_options(populate_existing=True)).unique().first()
    if p is None:
        return "ignored: unknown order"
    if event_id and db.scalar(select(PaymentTransaction.id).where(PaymentTransaction.payment_id == p.id, PaymentTransaction.provider_reference == event_id,
                                                                 PaymentTransaction.event.like("WEBHOOK%"))):
        return "duplicate event"
    _log(db, p, f"WEBHOOK_{etype}", p.status.value, f"Webhook {etype} received", event_id or rp_id)
    if etype in ("payment.captured", "order.paid"):
        if int(entity.get("amount", -1)) != paise(p.amount):
            _log(db, p, "AMOUNT_MISMATCH", p.status.value, f"Webhook amount {entity.get('amount')} != expected {paise(p.amount)}; not credited", rp_id)
            return "amount mismatch"
        was_settled = p.status == PS.SUCCESS
        try:
            _apply_captured(db, p, rp_id or "", entity.get("method"), "WEBHOOK")
        except AppError:
            return "captured but rejected"
        return "already settled" if was_settled else "applied"
    if etype == "payment.authorized" and p.status == PS.PENDING:
        if int(entity.get("amount", -1)) != paise(p.amount):
            _log(db, p, "AMOUNT_MISMATCH", p.status.value, f"Webhook amount {entity.get('amount')} != expected {paise(p.amount)}; not captured", rp_id)
            return "amount mismatch"
        if _capture(db, p, rp_id or "") is None:
            return "authorized, capture failed"
        try:
            _apply_captured(db, p, rp_id or "", entity.get("method"), "WEBHOOK")
        except AppError:
            return "captured but rejected"
        return "captured and applied"
    if etype == "payment.failed" and p.status == PS.PENDING:
        p.status = PS.FAILED
        _log(db, p, "FAILED", "FAILED", entity.get("error_description") or "Razorpay reports the payment failed", rp_id)
        N.notify(db, db.get(CustomerProfile, p.customer_id).user_id, N.PAYMENT_FAILED, "Payment failed", f"Invoice {p.invoice.number}", "payment", p.id)
        return "failed"
    return "noted"
