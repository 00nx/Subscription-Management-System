import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.enums import PaymentMethod, PaymentStatus
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.customers.service import scope_customer_id
from app.modules.payments import razorpay as rz
from app.modules.payments import razorpay_service as rzs
from app.modules.payments import service
from app.modules.payments.models import Payment
from app.modules.payments.schemas import (InitiatePaymentIn, PaymentOut, PaymentStatusOut, RazorpayConfigOut, RazorpayOrderIn, RazorpayOrderOut,
                                          RazorpayVerifyIn, RecordPaymentIn, SimulateIn)
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/payments", tags=["payments"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
_SORTS = {"created_at": Payment.created_at, "amount": Payment.amount, "payment_date": Payment.payment_date}


@router.get("/", response_model=ApiResponse[Page[PaymentOut]], responses=_errors)
def list_payments(page: PageParams = Depends(), status: PaymentStatus | None = None, method: PaymentMethod | None = None,
                  invoice_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Payment)
    scope = scope_customer_id(db, user)
    if scope is not None:
        stmt = stmt.where(Payment.customer_id == scope)
    elif customer_id:
        stmt = stmt.where(Payment.customer_id == customer_id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if method:
        stmt = stmt.where(Payment.method == method)
    if invoice_id:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    if date_from:
        stmt = stmt.where(func_date(Payment) >= date_from)
    if date_to:
        stmt = stmt.where(func_date(Payment) <= date_to)
    return ApiResponse(data=paginate(db, stmt, page, PaymentOut, _SORTS, "-created_at"))


def func_date(model):
    from sqlalchemy import func
    return func.date(func.coalesce(model.payment_date, model.created_at))


@router.post("/", status_code=201, response_model=ApiResponse[PaymentOut], responses=_errors)
def record_payment(body: RecordPaymentIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    """Staff record an external payment against an outstanding invoice."""
    p = service.record_manual(db, actor, body.invoice_id, body.method, body.amount, body.transaction_reference, body.notes, body.idempotency_key)
    db.commit()
    return ApiResponse(message="Payment recorded", data=PaymentOut.model_validate(p))


@router.post("/initiate/", status_code=201, response_model=ApiResponse[PaymentOut], responses=_errors)
def initiate_payment(body: InitiatePaymentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Customer (own invoices) or staff starts an online payment through the provider. Returns a PENDING payment."""
    p = service.initiate(db, user, body.invoice_id, body.method, body.amount, body.idempotency_key)
    db.commit()
    return ApiResponse(message="Payment initiated", data=PaymentOut.model_validate(p))


@router.get("/razorpay/config/", response_model=ApiResponse[RazorpayConfigOut], responses=_errors)
def razorpay_config(_: User = Depends(get_current_user)):
    """Whether Razorpay Test Mode is usable, plus the public key id for Checkout. The secret never leaves the server."""
    c = rz.config()
    return ApiResponse(data=RazorpayConfigOut(enabled=c.enabled, key_id=c.key_id or None, reason=c.reason or None))


@router.post("/razorpay/orders/", status_code=201, response_model=ApiResponse[RazorpayOrderOut], responses=_errors)
def razorpay_create_order(body: RazorpayOrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Server-side order creation: the amount comes from the invoice, not the browser."""
    p = rzs.create_order(db, user, body.invoice_id, body.amount, body.idempotency_key)
    db.commit()
    return ApiResponse(message="Order created", data=RazorpayOrderOut(payment_id=p.id, order_id=p.transaction_reference, amount=rzs.paise(p.amount), currency=p.invoice.currency,
                                                                      key_id=rz.config().key_id, invoice_number=p.invoice.number, description=f"Invoice {p.invoice.number}"))


@router.post("/razorpay/verify/", response_model=ApiResponse[PaymentOut], responses=_errors)
def razorpay_verify(body: RazorpayVerifyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Checkout hand-off. Verifies the signature and confirms with Razorpay server-side; if confirmation is not possible yet
    the payment stays PENDING and the signed webhook settles it."""
    p = rzs.verify_checkout(db, user, body.payment_id, body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature)
    db.commit()
    return ApiResponse(message=f"Payment {p.status.value.lower()}", data=PaymentOut.model_validate(p))


@router.post("/{payment_id}/simulate/", response_model=ApiResponse[PaymentOut], responses=_errors)
def simulate_gateway(payment_id: uuid.UUID, body: SimulateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Simulated gateway: choose the test outcome. Success is decided and recorded here on the backend."""
    try:
        p = service.complete(db, user, payment_id, body.outcome)
        db.commit()
    except AppError as e:
        if e.status_code == 409 and "cannot accept" in e.message:
            db.commit()  # keep the FAILED record written by apply_success
        raise
    return ApiResponse(message=f"Payment {p.status.value.lower()}", data=PaymentOut.model_validate(p))


@router.get("/{payment_id}/", response_model=ApiResponse[PaymentOut], responses=_errors)
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ApiResponse(data=PaymentOut.model_validate(service.get_payment(db, user, payment_id)))


@router.get("/{payment_id}/status/", response_model=ApiResponse[PaymentStatusOut], responses=_errors)
def payment_status(payment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = service.get_payment(db, user, payment_id)
    return ApiResponse(data=PaymentStatusOut(id=p.id, status=p.status, invoice_status=p.invoice.status.value, invoice_outstanding=p.invoice.outstanding))


webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhook_router.post("/razorpay/", responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay -> us. Authenticated only by the HMAC over the raw body (X-Razorpay-Signature). Idempotent per event id."""
    raw = await request.body()
    outcome = rzs.handle_webhook(db, raw, request.headers.get("X-Razorpay-Signature"), request.headers.get("X-Razorpay-Event-Id"))
    db.commit()
    return {"success": True, "message": outcome, "data": None}
