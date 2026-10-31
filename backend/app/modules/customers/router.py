import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.enums import InvoiceStatus, SubscriptionStatus
from app.core.exceptions import AppError
from app.core.money import q
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.customers import service
from app.modules.customers.models import CustomerProfile
from app.modules.customers.schemas import CustomerOut, CustomerUpdateIn
from app.modules.invoices.schemas import InvoiceOut
from app.modules.payments.schemas import PaymentOut
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/customers", tags=["customers"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)

_SORTS = {"created_at": CustomerProfile.created_at, "customer_number": CustomerProfile.customer_number, "company_name": CustomerProfile.company_name}


def _apply(profile: CustomerProfile, body: CustomerUpdateIn, allow_status: bool) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if "is_active" in changes and not allow_status:
        raise AppError("Insufficient permissions", 403)
    if "full_name" in changes:
        profile.user.full_name = changes.pop("full_name")
    if "is_active" in changes:
        profile.user.is_active = changes.pop("is_active")
    for k, v in changes.items():
        setattr(profile, k, v)
    return body.model_dump(exclude_unset=True)


@router.get("/", response_model=ApiResponse[Page[CustomerOut]], responses=_errors)
def list_customers(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), is_active: bool | None = None,
                   db: Session = Depends(get_db), _: User = Depends(_staff)):
    stmt = select(CustomerProfile).join(User, User.id == CustomerProfile.user_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like),
                              func.lower(func.coalesce(CustomerProfile.company_name, "")).like(like),
                              func.lower(CustomerProfile.customer_number).like(like)))
    if is_active is not None:
        stmt = stmt.where(User.is_active != is_active)
    return ApiResponse(data=paginate(db, stmt, page, CustomerOut, {**_SORTS, "full_name": User.full_name}, "-created_at"))


class CustomerSummary(BaseModel):
    active_subscriptions: int
    next_billing_date: date | None
    outstanding_amount: Decimal
    recent_invoices: list[InvoiceOut]
    recent_payments: list[PaymentOut]


@router.get("/me/summary/", response_model=ApiResponse[CustomerSummary], responses=_errors, dependencies=[Depends(require_roles(UserRole.CUSTOMER))])
def my_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Customer dashboard figures, aggregated server-side and confined to the caller's own records."""
    from app.modules.invoices.models import Invoice
    from app.modules.payments.models import Payment
    from app.modules.subscriptions.models import Subscription

    cid = service.profile_for_user(db, user).id
    payable = (Invoice.customer_id == cid, Invoice.status.in_([InvoiceStatus.CONFIRMED, InvoiceStatus.PARTIALLY_PAID]))
    return ApiResponse(data=CustomerSummary(
        active_subscriptions=db.scalar(select(func.count()).select_from(Subscription).where(Subscription.customer_id == cid, Subscription.status == SubscriptionStatus.ACTIVE)) or 0,
        next_billing_date=db.scalar(select(func.min(Subscription.next_billing_date)).where(Subscription.customer_id == cid, Subscription.status == SubscriptionStatus.ACTIVE)),
        outstanding_amount=q(db.scalar(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(*payable))),
        recent_invoices=[InvoiceOut.model_validate(i) for i in db.scalars(select(Invoice).where(Invoice.customer_id == cid, Invoice.status != InvoiceStatus.DRAFT).order_by(Invoice.created_at.desc()).limit(5)).unique()],
        recent_payments=[PaymentOut.model_validate(p) for p in db.scalars(select(Payment).where(Payment.customer_id == cid).order_by(Payment.created_at.desc()).limit(5)).unique()]))


@router.get("/me/", response_model=ApiResponse[CustomerOut], responses=_errors, dependencies=[Depends(require_roles(UserRole.CUSTOMER))])
def my_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ApiResponse(data=CustomerOut.model_validate(service.profile_for_user(db, user)))


@router.patch("/me/", response_model=ApiResponse[CustomerOut], responses=_errors, dependencies=[Depends(require_roles(UserRole.CUSTOMER))])
def update_my_profile(body: CustomerUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = service.profile_for_user(db, user)
    _apply(profile, body, allow_status=False)
    db.commit()
    return ApiResponse(message="Profile updated", data=CustomerOut.model_validate(profile))


@router.get("/{customer_id}/", response_model=ApiResponse[CustomerOut], responses=_errors)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_staff)):
    profile = db.get(CustomerProfile, customer_id)
    if not profile:
        raise AppError("Customer not found", 404)
    return ApiResponse(data=CustomerOut.model_validate(profile))


@router.patch("/{customer_id}/", response_model=ApiResponse[CustomerOut], responses=_errors)
def update_customer(customer_id: uuid.UUID, body: CustomerUpdateIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    profile = db.get(CustomerProfile, customer_id)
    if not profile:
        raise AppError("Customer not found", 404)
    changes = _apply(profile, body, allow_status=True)
    record_audit(db, actor, "CUSTOMER_UPDATED", "customer", profile.id, f"Updated {profile.customer_number}", changes)
    db.commit()
    return ApiResponse(message="Customer updated", data=CustomerOut.model_validate(profile))
