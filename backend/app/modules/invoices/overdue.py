"""Overdue tracking: who owes what, since when, what they already paid, and a (throttled) reminder action."""
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.modules.emails.service import queue_email
from app.core.enums import InvoiceStatus, PaymentStatus
from app.core.exceptions import AppError
from app.modules.accounts import notifications as N
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.customers.models import CustomerProfile
from app.modules.invoices import service
from app.modules.invoices.models import Invoice
from app.modules.payments.models import Payment
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/overdue-invoices", tags=["invoices"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
REMINDER_COOLDOWN = timedelta(hours=24)


class PaymentBrief(BaseModel):
    id: uuid.UUID
    amount: Decimal
    method: str
    payment_date: datetime | None


class OverdueOut(BaseModel):
    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    customer_name: str
    customer_email: str
    status: InvoiceStatus
    issue_date: date
    due_date: date
    days_overdue: int
    currency: str
    total: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    reminder_count: int
    last_reminded_at: datetime | None
    payments: list[PaymentBrief]  # successful payments so far, newest first (max 5)


class RemindIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class RemindOut(BaseModel):
    reminded: int
    skipped: list[dict]


def remind(db: Session, inv: Invoice, actor: User, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if inv.status not in service.PAYABLE or inv.outstanding <= 0:
        raise AppError(f"Invoice {inv.number} has nothing outstanding", 409)
    if inv.last_reminded_at and now - inv.last_reminded_at < REMINDER_COOLDOWN:
        raise AppError(f"Invoice {inv.number} was already reminded in the last 24 hours", 409)
    c = db.get(CustomerProfile, inv.customer_id)
    days = (date.today() - inv.due_date).days
    queue_email(db, c.email, "payment_reminder", {"name": c.full_name, "id": str(inv.id), "number": inv.number, "currency": inv.currency, "outstanding": str(inv.outstanding),
                                                  "due_date": inv.due_date.isoformat(), "days_overdue": max(days, 0)}, "invoice", inv.id)
    N.notify(db, c.user_id, N.INVOICE_OVERDUE if days > 0 else N.INVOICE_DUE, f"Reminder: invoice {inv.number}", f"Outstanding {inv.currency} {inv.outstanding}", "invoice", inv.id)
    inv.reminder_count, inv.last_reminded_at = (inv.reminder_count or 0) + 1, now
    record_audit(db, actor, "INVOICE_REMINDER", "invoice", inv.id, f"Reminder sent for {inv.number} to {c.email}")


@router.get("/", response_model=ApiResponse[Page[OverdueOut]], responses=_errors)
def list_overdue(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), customer_id: uuid.UUID | None = None,
                 status: InvoiceStatus | None = None, due_from: date | None = None, due_to: date | None = None,
                 min_amount: Decimal | None = Query(None, ge=0), max_amount: Decimal | None = Query(None, ge=0),
                 min_days: int | None = Query(None, ge=1), db: Session = Depends(get_db), _: User = Depends(_staff)):
    """Payable invoices past their due date with a balance. Oldest due first by default."""
    today = date.today()
    outstanding = Invoice.total - Invoice.amount_paid
    stmt = (select(Invoice).join(CustomerProfile, CustomerProfile.id == Invoice.customer_id).join(User, User.id == CustomerProfile.user_id)
            .where(Invoice.status.in_(service.PAYABLE), Invoice.due_date < today, outstanding > 0))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Invoice.number).like(like), func.lower(User.full_name).like(like), func.lower(User.email).like(like)))
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if due_from:
        stmt = stmt.where(Invoice.due_date >= due_from)
    if due_to:
        stmt = stmt.where(Invoice.due_date <= due_to)
    if min_amount is not None:
        stmt = stmt.where(outstanding >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(outstanding <= max_amount)
    if min_days:
        stmt = stmt.where(Invoice.due_date <= today - timedelta(days=min_days))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    order = {"outstanding": outstanding, "due_date": Invoice.due_date, "number": Invoice.number}.get((page.sort or "due_date").lstrip("-"), Invoice.due_date)
    desc = (page.sort or "").startswith("-")
    rows = db.scalars(stmt.order_by(order.desc() if desc else order.asc()).offset(page.offset).limit(page.page_size)).unique().all()
    pays: dict[uuid.UUID, list[Payment]] = {}
    if rows:
        for p in db.scalars(select(Payment).where(Payment.invoice_id.in_([r.id for r in rows]), Payment.status == PaymentStatus.SUCCESS)
                            .order_by(Payment.payment_date.desc())).unique():
            pays.setdefault(p.invoice_id, []).append(p)
    items = []
    for inv in rows:
        c = db.get(CustomerProfile, inv.customer_id)
        items.append(OverdueOut(
            id=inv.id, number=inv.number, customer_id=inv.customer_id, customer_name=c.full_name, customer_email=c.email, status=inv.status,
            issue_date=inv.issue_date, due_date=inv.due_date, days_overdue=(today - inv.due_date).days, currency=inv.currency, total=inv.total,
            amount_paid=inv.amount_paid, outstanding=inv.outstanding, reminder_count=inv.reminder_count or 0, last_reminded_at=inv.last_reminded_at,
            payments=[PaymentBrief(id=p.id, amount=p.amount, method=p.method.value, payment_date=p.payment_date) for p in pays.get(inv.id, [])[:5]]))
    return ApiResponse(data=Page(items=items, total=total, page=page.page, page_size=page.page_size))


@router.post("/remind/", response_model=ApiResponse[RemindOut], responses=_errors)
def remind_many(body: RemindIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    """Sends a reminder for each invoice; an invoice reminded in the last 24 h (or already settled) is skipped, not an error."""
    done, skipped = 0, []
    for iid in dict.fromkeys(body.ids):
        try:
            inv = service.get_invoice(db, actor, iid, lock=True)
            remind(db, inv, actor)
            db.commit()
            done += 1
        except AppError as e:
            db.rollback()
            skipped.append({"id": str(iid), "reason": e.message})
    return ApiResponse(message=f"{done} reminder(s) sent", data=RemindOut(reminded=done, skipped=skipped))
