import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import BillingFrequency, InvoiceStatus, SubscriptionStatus
from app.core.dependencies import require_roles
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.analytics import service
from app.modules.analytics.models import AuditLog
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

audit_router = APIRouter(prefix="/audit-logs", tags=["audit"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
_admin = require_roles(UserRole.STAFF)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str
    summary: str
    changes: dict | None
    created_at: datetime


@audit_router.get("/", response_model=ApiResponse[Page[AuditLogOut]], responses=_errors)
def list_audit_logs(page: PageParams = Depends(), entity_type: str | None = None, action: str | None = None, user_id: uuid.UUID | None = None,
                    db: Session = Depends(get_db), _: User = Depends(_admin)):
    """Read-only, ADMIN only."""
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return ApiResponse(data=paginate(db, stmt, page, AuditLogOut, {"created_at": AuditLog.created_at}, "-created_at"))


class Range(BaseModel):
    preset: str
    date_from: date
    date_to: date


class Kpis(BaseModel):
    active_subscriptions: int
    outstanding_amount: Decimal
    overdue_invoices: int
    total_customers: int
    mrr: Decimal | None  # null for staff: revenue figures are admin-only
    arr: Decimal | None
    revenue_collected: Decimal | None
    total_invoices: int
    revenue_billed: Decimal | None
    total_payments: Decimal | None  # money received in range (successful payments)
    payments_count: int | None


class Point(BaseModel):
    period: str
    amount: Decimal


class GrowthPoint(BaseModel):
    period: str
    new: int
    total: int


class StatusCount(BaseModel):
    status: str
    count: int


class PaymentStatusCount(StatusCount):
    amount: Decimal


class Activity(BaseModel):
    type: str
    title: str
    detail: str
    at: datetime


class OutstandingVsCollected(BaseModel):
    collected: Decimal | None
    outstanding: Decimal


class PlanCount(BaseModel):
    plan: str
    count: int


class Dashboard(BaseModel):
    range: Range
    filters: dict[str, str | None]
    active_by_plan: list[PlanCount]
    kpis: Kpis
    revenue_over_time: list[Point] | None
    mrr_trend: list[Point] | None
    subscription_growth: list[GrowthPoint]
    subscription_status: list[StatusCount]
    payment_status: list[PaymentStatusCount]
    outstanding_vs_collected: OutstandingVsCollected
    recent_activity: list[Activity]


def _range(range: str | None, date_from: date | None, date_to: date | None):
    return range or "last_30_days", *service.resolve_range(range, date_from, date_to)


@analytics_router.get("/dashboard/", response_model=ApiResponse[Dashboard], responses=_errors)
def dashboard(range: str | None = Query(None, description="today | last_7_days | last_30_days | this_month | last_month | this_year | custom"),
              date_from: date | None = None, date_to: date | None = None, billing_frequency: BillingFrequency | None = None,
              subscription_status: SubscriptionStatus | None = None, invoice_status: InvoiceStatus | None = None, customer_id: uuid.UUID | None = None,
              plan_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(_staff)):
    """One aggregation call for the whole dashboard. Staff get the operational view (no revenue/MRR/ARR figures).
    Filters (frequency, subscription status, invoice status, customer, plan) apply to every figure they can logically narrow."""
    preset, start, end = _range(range, date_from, date_to)
    full = user.role == UserRole.ADMIN
    f = service.Filters(frequency=billing_frequency, plan_id=plan_id, subscription_status=subscription_status, invoice_status=invoice_status, customer_id=customer_id)
    k = service.kpis(db, start, end, include_revenue=full, f=f)
    return ApiResponse(data=Dashboard(
        range=Range(preset=preset, date_from=start, date_to=end), kpis=Kpis(**k),
        filters={"billing_frequency": billing_frequency.value if billing_frequency else None, "subscription_status": subscription_status.value if subscription_status else None,
                 "invoice_status": invoice_status.value if invoice_status else None, "customer_id": str(customer_id) if customer_id else None, "plan_id": str(plan_id) if plan_id else None},
        active_by_plan=service.active_by_plan(db, f),
        revenue_over_time=service.revenue_series(db, start, end, f) if full else None,
        mrr_trend=service.mrr_trend(db, f=f) if full else None,
        subscription_growth=service.subscription_growth(db, f=f), subscription_status=service.status_distribution(db, f),
        payment_status=service.payment_distribution(db, start, end, f),
        outstanding_vs_collected=OutstandingVsCollected(collected=k["revenue_collected"], outstanding=k["outstanding_amount"]),
        recent_activity=service.recent_activity(db)))


class RevenueAnalytics(BaseModel):
    range: Range
    mrr: Decimal
    arr: Decimal
    revenue_collected: Decimal
    revenue_over_time: list[Point]
    mrr_trend: list[Point]


@analytics_router.get("/revenue/", response_model=ApiResponse[RevenueAnalytics], responses=_errors)
def revenue(range: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), _: User = Depends(_admin)):
    preset, start, end = _range(range, date_from, date_to)
    k = service.kpis(db, start, end)
    return ApiResponse(data=RevenueAnalytics(range=Range(preset=preset, date_from=start, date_to=end), mrr=k["mrr"], arr=k["arr"],
                                             revenue_collected=k["revenue_collected"], revenue_over_time=service.revenue_series(db, start, end),
                                             mrr_trend=service.mrr_trend(db)))


class SubscriptionAnalytics(BaseModel):
    active_subscriptions: int
    growth: list[GrowthPoint]
    status_distribution: list[StatusCount]


@analytics_router.get("/subscriptions/", response_model=ApiResponse[SubscriptionAnalytics], responses=_errors)
def subscription_analytics(db: Session = Depends(get_db), _: User = Depends(_staff)):
    return ApiResponse(data=SubscriptionAnalytics(active_subscriptions=service.kpis(db, date.today(), date.today(), False)["active_subscriptions"],
                                                  growth=service.subscription_growth(db), status_distribution=service.status_distribution(db)))


class PaymentAnalytics(BaseModel):
    range: Range
    status_distribution: list[PaymentStatusCount]


@analytics_router.get("/payments/", response_model=ApiResponse[PaymentAnalytics], responses=_errors)
def payment_analytics(range: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), _: User = Depends(_staff)):
    preset, start, end = _range(range, date_from, date_to)
    return ApiResponse(data=PaymentAnalytics(range=Range(preset=preset, date_from=start, date_to=end), status_distribution=service.payment_distribution(db, start, end)))
