import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.billing.models import BillingRun, Tax
from app.modules.billing.schemas import TaxIn, TaxOut, TaxUpdateIn
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams
from app.core.enums import BillingFrequency, RecordStatus, SubscriptionStatus
from app.modules.subscriptions.models import Subscription, SubscriptionEvent

taxes_router = APIRouter(prefix="/taxes", tags=["taxes"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
_admin = require_roles(UserRole.ADMIN)


@taxes_router.get("/", response_model=ApiResponse[Page[TaxOut]], responses=_errors)
def list_taxes(page: PageParams = Depends(), status: RecordStatus | None = None, db: Session = Depends(get_db), _: User = Depends(_staff)):
    stmt = select(Tax)
    if status:
        stmt = stmt.where(Tax.status == status)
    return ApiResponse(data=paginate(db, stmt, page, TaxOut, {"name": Tax.name, "rate": Tax.rate, "created_at": Tax.created_at}, "name"))


@taxes_router.post("/", status_code=201, response_model=ApiResponse[TaxOut], responses=_errors)
def create_tax(body: TaxIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    tax = Tax(**body.model_dump())
    db.add(tax)
    try:
        db.flush()
    except IntegrityError:
        raise AppError("A tax with this name already exists", 409)
    record_audit(db, admin, "TAX_CREATED", "tax", tax.id, f"Created tax {tax.name} ({tax.rate}%)")
    db.commit()
    return ApiResponse(message="Tax created", data=TaxOut.model_validate(tax))


@taxes_router.get("/{tax_id}/", response_model=ApiResponse[TaxOut], responses=_errors)
def get_tax(tax_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_staff)):
    tax = db.get(Tax, tax_id)
    if not tax:
        raise AppError("Tax not found", 404)
    return ApiResponse(data=TaxOut.model_validate(tax))


@taxes_router.patch("/{tax_id}/", response_model=ApiResponse[TaxOut], responses=_errors)
def update_tax(tax_id: uuid.UUID, body: TaxUpdateIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    """Rate changes affect only future invoices: issued invoices and existing subscription lines keep their snapshot rate."""
    tax = db.get(Tax, tax_id)
    if not tax:
        raise AppError("Tax not found", 404)
    changes = body.model_dump(exclude_unset=True)
    old = {k: str(getattr(tax, k)) for k in changes}
    for k, v in changes.items():
        setattr(tax, k, v)
    record_audit(db, admin, "TAX_UPDATED", "tax", tax.id, f"Updated tax {tax.name}", {k: {"from": old[k], "to": str(v)} for k, v in changes.items()})
    try:
        db.commit()
    except IntegrityError:
        raise AppError("A tax with this name already exists", 409)
    return ApiResponse(message="Tax updated", data=TaxOut.model_validate(tax))


# ---------------- billing engine controls ----------------
billing_router = APIRouter(prefix="/billing", tags=["billing"])


class BillingRunOut(BaseModel):
    invoiced: int
    failed: int
    renewed: int
    expired: int
    run_id: uuid.UUID | None = None


class BillingRunRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trigger: str
    run_date: date
    status: str
    started_at: datetime
    finished_at: datetime | None
    batches: int
    examined: int
    invoiced: int
    recovered: int
    skipped_locked: int
    failed: int
    renewed: int
    expired: int
    failures: list[dict] = []


class DueSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    customer_name: str
    plan_name: str
    status: SubscriptionStatus
    next_billing_date: date | None
    billing_frequency: BillingFrequency
    total: Decimal


class BillingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    event_type: str
    detail: str | None
    created_at: datetime


@billing_router.get("/due/", response_model=ApiResponse[Page[DueSubscriptionOut]], responses=_errors)
def due_subscriptions(page: PageParams = Depends(), upcoming_days: int = Query(0, ge=0, le=365), db: Session = Depends(get_db), _: User = Depends(_staff)):
    """Active subscriptions due now (or within `upcoming_days`), soonest first."""
    stmt = select(Subscription).where(Subscription.status == SubscriptionStatus.ACTIVE,
                                      Subscription.next_billing_date <= date.today() + timedelta(days=upcoming_days))
    return ApiResponse(data=paginate(db, stmt, page, DueSubscriptionOut, {"next_billing_date": Subscription.next_billing_date, "number": Subscription.number}, "next_billing_date"))


@billing_router.post("/run/", response_model=ApiResponse[BillingRunOut], responses=_errors)
def run_billing_now(db: Session = Depends(get_db), admin: User = Depends(_admin)):
    """Runs the same code as the scheduled Celery job. Safe to press repeatedly: billing is idempotent."""
    from app.modules.billing.service import run_billing, run_expiry

    db.commit()  # end this request's transaction first: the engine opens its own sessions (SQLite would otherwise wait on our lock)
    res = run_billing(trigger="MANUAL", triggered_by=admin.id)
    exp = run_expiry(run_id=res.run_id)
    record_audit(db, admin, "BILLING_RUN", "billing", str(res.run_id), f"Manual billing run: {res.invoiced} invoiced, {len(res.failed)} failed")
    db.commit()
    return ApiResponse(message="Billing run complete", data=BillingRunOut(invoiced=res.invoiced, failed=len(res.failed), renewed=exp["renewed"], expired=exp["expired"], run_id=res.run_id))


@billing_router.get("/runs/", response_model=ApiResponse[Page[BillingRunRecordOut]], responses=_errors)
def billing_runs(page: PageParams = Depends(), status: str | None = None, trigger: str | None = None, db: Session = Depends(get_db), _: User = Depends(_staff)):
    """Execution history of the billing engine, newest first."""
    stmt = select(BillingRun)
    if status:
        stmt = stmt.where(BillingRun.status == status)
    if trigger:
        stmt = stmt.where(BillingRun.trigger == trigger)
    return ApiResponse(data=paginate(db, stmt, page, BillingRunRecordOut, {"started_at": BillingRun.started_at}, "-started_at"))


@billing_router.get("/failures/", response_model=ApiResponse[Page[BillingEventOut]], responses=_errors)
def billing_failures(page: PageParams = Depends(), db: Session = Depends(get_db), _: User = Depends(_staff)):
    stmt = select(SubscriptionEvent).where(SubscriptionEvent.event_type == "BILLING_FAILED")
    return ApiResponse(data=paginate(db, stmt, page, BillingEventOut, {"created_at": SubscriptionEvent.created_at}, "-created_at"))
