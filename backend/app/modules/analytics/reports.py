"""Report endpoints: filter + search + sort + paginate, and `?format=csv` to export every matching row.
All figures come from database records. `format=csv` and `format=pdf` export the matching rows."""
import csv
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Date, Integer, Numeric, and_, case, cast, func, literal, select, type_coerce
from sqlalchemy.orm import Session

from app.core.database import IS_SQLITE, get_db
from app.core.dependencies import require_roles
from app.core.enums import BillingFrequency, InvoiceStatus as IS, PaymentMethod, PaymentStatus as PS, SubscriptionStatus as S
from app.core.money import ZERO, q
from app.modules.accounts.models import User, UserRole
from app.modules.accounts.models import User as _User
from app.modules.analytics import service
from app.modules.analytics.pdf import PDF_ROW_LIMIT, render_table_pdf
from app.modules.analytics.service import date_bucket
from app.modules.customers.models import CustomerProfile
from app.modules.invoices.models import Invoice, InvoiceLine
from app.modules.payments.models import Payment
from app.modules.products.models import Product
from app.modules.subscriptions.models import Subscription, SubscriptionPlan
from app.modules.subscriptions.periods import add_months
from app.schemas.common import ApiResponse, ErrorResponse, PageParams

reports_router = APIRouter(prefix="/reports", tags=["reports"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)  # staff: operational reports
_admin = require_roles(UserRole.ADMIN)  # revenue reports are admin-only
CSV_LIMIT = 50


class ReportPage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class ReportOut(BaseModel):
    summary: dict[str, Any]
    rows: ReportPage


def _dt(d: date | None, end: bool = False) -> datetime | None:
    return None if d is None else datetime.combine(d - timedelta(days=1) if end else d, time.min, tzinfo=UTC)


def _run(db: Session, stmt, params: PageParams, sorts: dict, default: str, summary: dict, fmt: str, name: str, columns: list[str]):
    """Executes a column-select statement as either a page of rows or a CSV of all rows."""
    key = params.sort or default
    col = sorts.get(key.lstrip("-"))
    ordered = stmt.order_by(col.desc() if key.startswith("-") else col.asc()) if col is not None else stmt
    if fmt == "csv":
        rows = db.execute(ordered.limit(CSV_LIMIT)).mappings().all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(columns[::-1])
        for r in rows:
            w.writerow(["" if r[c] is None else (r[c].value if hasattr(r[c], "value") else r[c]) for c in columns])
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}-{date.today().isoformat()}.csv"'})
    if fmt == "pdf":
        return _pdf(name, summary, columns, [dict(r) for r in db.execute(ordered.limit(PDF_ROW_LIMIT + 1)).mappings().all()])
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(ordered.offset(params.offset).limit(params.page_size)).mappings().all()
    items = [{k: (v.value if hasattr(v, "value") else v) for k, v in r.items()} for r in rows]
    return ApiResponse(data=ReportOut(summary=summary, rows=ReportPage(items=items, total=total, page=params.page, page_size=params.page_size)))


Format = Literal["json", "csv", "pdf"]


def _flat(summary: dict) -> list[str]:
    """One line per scalar / {count, amount} figure of a report summary (lists such as by_plan are summarised inline)."""
    out = []
    for k, v in summary.items():
        label = k.replace("_", " ").capitalize()
        if isinstance(v, dict) and "count" in v:
            out.append(f"{label}: {v['count']} ({v.get('amount', '')})".replace(" ()", ""))
        elif isinstance(v, list):
            out.append(f"{label}: " + ", ".join(" ".join(str(x) for x in i.values()) for i in v[:8]))
        elif isinstance(v, dict):
            out.append(f"{label}: " + ", ".join(f"{a}={b}" for a, b in v.items()))
        elif v is not None:
            out.append(f"{label}: {v}")
    return out


def _pdf(name: str, summary: dict, columns: list[str], rows: list[dict]) -> Response:
    title = name.replace("-", " ").title()
    body = render_table_pdf(title, _flat(summary), columns, rows[:PDF_ROW_LIMIT], truncated=len(rows) > PDF_ROW_LIMIT)
    return Response(body, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}-{date.today().isoformat()}.pdf"'})


# ---------------- subscriptions ----------------
@reports_router.get("/subscriptions/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def subscriptions_report(page: PageParams = Depends(), q_: str | None = Query(None, alias="q", max_length=100), status: S | None = None, plan_id: uuid.UUID | None = None,
                         billing_frequency: BillingFrequency | None = None, date_from: date | None = None, date_to: date | None = None,
                         format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_staff)):
    cond = []
    if q_:
        cond.append(func.lower(Subscription.number).like(f"%{q_.lower()}%"))
    if plan_id:
        cond.append(Subscription.plan_id == plan_id)
    if billing_frequency:
        cond.append(Subscription.billing_frequency == billing_frequency)
    if date_from:
        cond.append(Subscription.created_at >= _dt(date_from))
    if date_to:
        cond.append(Subscription.created_at < _dt(date_to, True))
    by_status = dict(db.execute(select(Subscription.status, func.count()).where(*cond).group_by(Subscription.status)).all())
    summary = {
        "total": sum(by_status.values()), "active": by_status.get(S.ACTIVE, 0), "cancelled": by_status.get(S.CLOSED, 0), "expired": by_status.get(S.EXPIRED, 0),
        "paused": by_status.get(S.PAUSED, 0),
        "by_plan": [{"plan": n, "count": c} for n, c in db.execute(select(SubscriptionPlan.name, func.count()).join(Subscription, Subscription.plan_id == SubscriptionPlan.id).where(*cond).group_by(SubscriptionPlan.name).order_by(func.count().desc()))],
        "by_frequency": [{"frequency": f.value, "count": c} for f, c in db.execute(select(Subscription.billing_frequency, func.count()).where(*cond).group_by(Subscription.billing_frequency))],
    }
    if status:
        cond.append(Subscription.status == status)
    cols = ["number", "customer", "plan", "status", "billing_frequency", "start_date", "expiry_date", "total", "created_at"]
    stmt = (select(Subscription.number.label("number"), _User.full_name.label("customer"), SubscriptionPlan.name.label("plan"), Subscription.status.label("status"),
                   Subscription.billing_frequency.label("billing_frequency"), Subscription.start_date.label("start_date"), Subscription.expiry_date.label("expiry_date"),
                   Subscription.total.label("total"), Subscription.created_at.label("created_at"))
            .join(CustomerProfile, CustomerProfile.id == Subscription.customer_id).join(_User, _User.id == CustomerProfile.user_id)
            .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id).where(*cond))
    sorts = {"number": Subscription.number, "customer": _User.full_name, "plan": SubscriptionPlan.name, "status": Subscription.status, "start_date": Subscription.start_date,
             "total": Subscription.total, "created_at": Subscription.created_at}
    return _run(db, stmt, page, sorts, "-created_at", summary, format, "subscriptions-report", cols)


# ---------------- invoices ----------------
@reports_router.get("/invoices/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def invoices_report(page: PageParams = Depends(), q_: str | None = Query(None, alias="q", max_length=100), status: IS | None = None, overdue: bool | None = None,
                    date_from: date | None = None, date_to: date | None = None, format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_staff)):
    today = date.today()
    base = []
    if q_:
        base.append(func.lower(Invoice.number).like(f"%{q_.lower()}%"))
    if date_from:
        base.append(Invoice.issue_date >= date_from)
    if date_to:
        base.append(Invoice.issue_date <= date_to)
    live = Invoice.status != IS.CANCELLED
    od = and_(Invoice.status.in_(service.PAYABLE), Invoice.due_date < today, Invoice.total - Invoice.amount_paid > 0)

    def agg(*extra):
        c, a = db.execute(select(func.count(), func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(*base, *extra)).one()
        return {"count": c, "amount": q(a)}

    summary = {"total_invoices": db.scalar(select(func.count()).select_from(Invoice).where(*base)) or 0,
               "paid": agg(Invoice.status == IS.PAID), "partially_paid": agg(Invoice.status == IS.PARTIALLY_PAID),
               "outstanding": agg(Invoice.status.in_(service.PAYABLE)), "overdue": agg(od), "cancelled": agg(Invoice.status == IS.CANCELLED)}
    cond = list(base)
    if status:
        cond.append(Invoice.status == status)
    if overdue is not None:
        cond.append(od if overdue else ~od)
    cols = ["number", "customer", "status", "issue_date", "due_date", "total", "amount_paid", "outstanding", "overdue"]
    outstanding = type_coerce(case((Invoice.status == IS.CANCELLED, literal(0, Numeric(12, 2))), else_=Invoice.total - Invoice.amount_paid), Numeric(12, 2))
    stmt = select(Invoice.number.label("number"), Invoice.customer_snapshot["name"].as_string().label("customer"), Invoice.status.label("status"),
                  Invoice.issue_date.label("issue_date"), Invoice.due_date.label("due_date"), Invoice.total.label("total"), Invoice.amount_paid.label("amount_paid"),
                  outstanding.label("outstanding"), od.label("overdue")).where(*cond)
    sorts = {"number": Invoice.number, "issue_date": Invoice.issue_date, "due_date": Invoice.due_date, "total": Invoice.total, "status": Invoice.status, "outstanding": outstanding}
    return _run(db, stmt, page, sorts, "-issue_date", summary, format, "invoices-report", cols)


# ---------------- payments ----------------
@reports_router.get("/payments/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def payments_report(page: PageParams = Depends(), q_: str | None = Query(None, alias="q", max_length=100), status: PS | None = None, method: PaymentMethod | None = None,
                    date_from: date | None = None, date_to: date | None = None, format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_staff)):
    base = []
    if date_from:
        base.append(Payment.created_at >= _dt(date_from))
    if date_to:
        base.append(Payment.created_at < _dt(date_to, True))
    if q_:
        like = f"%{q_.lower()}%"
        base.append(func.lower(Invoice.number).like(like) | func.lower(func.coalesce(Payment.transaction_reference, "")).like(like))
    join = lambda s: s.join(Invoice, Invoice.id == Payment.invoice_id)  # noqa: E731
    by_status = {s: (c, a) for s, c, a in db.execute(join(select(Payment.status, func.count(), func.coalesce(func.sum(Payment.amount), 0))).where(*base).group_by(Payment.status))}
    get = lambda st: {"count": by_status.get(st, (0, 0))[0], "amount": q(by_status.get(st, (0, 0))[1])}  # noqa: E731
    summary = {"successful": get(PS.SUCCESS), "failed": get(PS.FAILED), "pending": get(PS.PENDING), "cancelled": get(PS.CANCELLED),
               "by_method": [{"method": m.value, "count": c, "amount": q(a)} for m, c, a in db.execute(
                   join(select(Payment.method, func.count(), func.coalesce(func.sum(Payment.amount), 0))).where(*base, Payment.status == PS.SUCCESS).group_by(Payment.method).order_by(func.sum(Payment.amount).desc()))]}
    cond = list(base)
    if status:
        cond.append(Payment.status == status)
    if method:
        cond.append(Payment.method == method)
    cols = ["invoice", "method", "amount", "status", "reference", "payment_date", "created_at"]
    stmt = join(select(Invoice.number.label("invoice"), Payment.method.label("method"), Payment.amount.label("amount"), Payment.status.label("status"),
                       Payment.transaction_reference.label("reference"), Payment.payment_date.label("payment_date"), Payment.created_at.label("created_at"))).where(*cond)
    sorts = {"invoice": Invoice.number, "amount": Payment.amount, "status": Payment.status, "method": Payment.method, "payment_date": Payment.payment_date, "created_at": Payment.created_at}
    return _run(db, stmt, page, sorts, "-created_at", summary, format, "payments-report", cols)


# ---------------- revenue (admin) ----------------
@reports_router.get("/revenue/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def revenue_report(page: PageParams = Depends(), group_by: Literal["period", "product", "plan"] = "period", range: str | None = None,
                   date_from: date | None = None, date_to: date | None = None, format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_admin)):
    """`invoiced` = net billed (lines after discount, plus tax) on non-cancelled invoices issued in range.
    `collected` = successful payments in range (period grouping only: payments are per invoice, not per product)."""
    start, end = service.resolve_range(range, date_from, date_to)
    k = service.kpis(db, start, end)
    summary = {"range": {"date_from": start.isoformat(), "date_to": end.isoformat()}, "mrr": k["mrr"], "arr": k["arr"], "revenue_collected": k["revenue_collected"]}
    valid = (Invoice.status != IS.CANCELLED, Invoice.status != IS.DRAFT, Invoice.issue_date >= start, Invoice.issue_date <= end)
    if group_by == "product":
        label = func.coalesce(Product.name, "Other / manual").label("label")
        stmt = (select(label, func.sum(InvoiceLine.line_total).label("invoiced"), func.sum(InvoiceLine.quantity).label("quantity"))
                .select_from(InvoiceLine).join(Invoice, Invoice.id == InvoiceLine.invoice_id).outerjoin(Product, Product.id == InvoiceLine.product_id).where(*valid).group_by(label))
        return _run(db, stmt, page, {"label": label, "invoiced": func.sum(InvoiceLine.line_total)}, "-invoiced", summary, format, "revenue-by-product", ["label", "invoiced", "quantity"])
    if group_by == "plan":
        label = func.coalesce(SubscriptionPlan.name, "No plan (manual)").label("label")
        stmt = (select(label, func.sum(Invoice.total).label("invoiced"), func.count().label("invoices")).select_from(Invoice)
                .outerjoin(Subscription, Subscription.id == Invoice.subscription_id).outerjoin(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id).where(*valid).group_by(label))
        return _run(db, stmt, page, {"label": label, "invoiced": func.sum(Invoice.total)}, "-invoiced", summary, format, "revenue-by-plan", ["label", "invoiced", "invoices"])
    im = date_bucket(Invoice.issue_date, "month")
    inv_m = select(im.label("m"), func.sum(Invoice.total).label("invoiced")).where(*valid).group_by(im).subquery()
    lo, hi = _dt(start), _dt(end, True)
    pm = date_bucket(Payment.payment_date, "month")
    pay_m = (select(pm.label("m"), func.sum(Payment.amount).label("collected"))
             .where(Payment.status == PS.SUCCESS, Payment.payment_date >= lo, Payment.payment_date < hi).group_by(pm).subquery())
    keys, cur = [], start.replace(day=1)
    while cur <= end:
        keys.append(cur)
        cur = add_months(cur, 1)
    inv = {m: a for m, a in db.execute(select(inv_m.c.m, inv_m.c.invoiced))}
    col = {m: a for m, a in db.execute(select(pay_m.c.m, pay_m.c.collected))}
    rows = [{"label": m.strftime("%Y-%m"), "invoiced": q(inv.get(m, ZERO)), "collected": q(col.get(m, ZERO))} for m in keys]
    rows = sorted(rows, key=lambda r: r["label"], reverse=page.sort in (None, "-label"))
    if format == "pdf":
        return _pdf("revenue-by-period", summary, ["label", "invoiced", "collected"], rows)
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["label", "invoiced", "collected"])
        for r in rows:
            w.writerow([r["label"], r["invoiced"], r["collected"]])
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="revenue-by-period.csv"'})
    return ApiResponse(data=ReportOut(summary=summary, rows=ReportPage(items=rows[page.offset:page.offset + page.page_size], total=len(rows), page=page.page, page_size=page.page_size)))


# ---------------- outstanding / overdue (aging) ----------------
def _receivables(db, page, q_, customer_id, due_from, due_to, fmt, overdue_only: bool, name: str):
    today = date.today()
    outstanding = Invoice.total - Invoice.amount_paid
    cond = [Invoice.status.in_(service.PAYABLE), outstanding > 0]
    if overdue_only:
        cond.append(Invoice.due_date < today)
    if q_:
        like = f"%{q_.lower()}%"
        cond.append(func.lower(Invoice.number).like(like) | func.lower(Invoice.customer_snapshot["name"].as_string()).like(like))
    if customer_id:
        cond.append(Invoice.customer_id == customer_id)
    if due_from:
        cond.append(Invoice.due_date >= due_from)
    if due_to:
        cond.append(Invoice.due_date <= due_to)
    n, amt = db.execute(select(func.count(), func.coalesce(func.sum(outstanding), 0)).where(*cond)).one()

    def bucket(lo, hi):  # days overdue in [lo, hi]; "current" = not yet due
        c = [Invoice.due_date <= today - timedelta(days=lo)] if lo else [Invoice.due_date >= today]
        if hi:
            c.append(Invoice.due_date >= today - timedelta(days=hi))
        count, total = db.execute(select(func.count(), func.coalesce(func.sum(outstanding), 0)).where(*cond, *c)).one()
        return {"count": count, "amount": q(total)}

    summary = {"count": n, "outstanding_amount": q(amt)}
    if not overdue_only:
        summary["not_yet_due"] = bucket(0, None)
    summary.update({"overdue_1_30_days": bucket(1, 30), "overdue_31_60_days": bucket(31, 60), "overdue_61_90_days": bucket(61, 90), "overdue_over_90_days": bucket(91, None)})
    gap = cast(func.julianday(today.isoformat()) - func.julianday(Invoice.due_date), Integer) if IS_SQLITE else type_coerce(today - Invoice.due_date, Integer)
    days = case((Invoice.due_date < today, gap), else_=0)
    cols = ["number", "customer", "status", "issue_date", "due_date", "days_overdue", "total", "amount_paid", "outstanding"]
    stmt = select(Invoice.number.label("number"), Invoice.customer_snapshot["name"].as_string().label("customer"), Invoice.status.label("status"), Invoice.issue_date.label("issue_date"),
                  Invoice.due_date.label("due_date"), days.label("days_overdue"), Invoice.total.label("total"), Invoice.amount_paid.label("amount_paid"),
                  type_coerce(outstanding, Numeric(12, 2)).label("outstanding")).where(*cond)
    sorts = {"number": Invoice.number, "due_date": Invoice.due_date, "outstanding": outstanding, "total": Invoice.total, "days_overdue": Invoice.due_date}
    return _run(db, stmt, page, sorts, "due_date", summary, fmt, name, cols)


@reports_router.get("/outstanding/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def outstanding_report(page: PageParams = Depends(), q_: str | None = Query(None, alias="q", max_length=100), customer_id: uuid.UUID | None = None,
                       due_from: date | None = None, due_to: date | None = None, format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_staff)):
    """Everything still owed (confirmed / partially paid invoices), with an aging summary."""
    return _receivables(db, page, q_, customer_id, due_from, due_to, format, False, "outstanding-report")


@reports_router.get("/overdue/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def overdue_report(page: PageParams = Depends(), q_: str | None = Query(None, alias="q", max_length=100), customer_id: uuid.UUID | None = None,
                   due_from: date | None = None, due_to: date | None = None, format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_staff)):
    """Only invoices past their due date, with an aging summary."""
    return _receivables(db, page, q_, customer_id, due_from, due_to, format, True, "overdue-report")


# ---------------- renewals ----------------
@reports_router.get("/renewals/", response_model=ApiResponse[ReportOut], responses={**_errors, 200: {"content": {"text/csv": {}, "application/pdf": {}}}})
def renewals_report(page: PageParams = Depends(), q_: str | None = Query(None, alias="q", max_length=100), days: int = Query(30, ge=1, le=365),
                    plan_id: uuid.UUID | None = None, auto_renew: bool | None = None, date_from: date | None = None, date_to: date | None = None,
                    format: Format = "json", db: Session = Depends(get_db), _: User = Depends(_staff)):
    """Active subscriptions whose term ends within `days` (the renewal pipeline), plus how many renewed / expired in the date range
    (default: last 30 days)."""
    from app.modules.subscriptions.models import SubscriptionEvent
    today = date.today()
    start, end = service.resolve_range("custom" if date_from and date_to else None, date_from, date_to)
    cond = [Subscription.status == S.ACTIVE, Subscription.expiry_date.is_not(None), Subscription.expiry_date >= today, Subscription.expiry_date <= today + timedelta(days=days)]
    if q_:
        like = f"%{q_.lower()}%"
        cond.append(func.lower(Subscription.number).like(like) | func.lower(_User.full_name).like(like))
    if plan_id:
        cond.append(Subscription.plan_id == plan_id)
    if auto_renew is not None:
        cond.append(Subscription.auto_renew.is_(auto_renew))
    lo, hi = _dt(start), _dt(end, True)

    def events(*types):
        return db.scalar(select(func.count()).select_from(SubscriptionEvent).where(SubscriptionEvent.event_type.in_(types), SubscriptionEvent.created_at >= lo, SubscriptionEvent.created_at < hi)) or 0

    base = (select(func.count(), func.coalesce(func.sum(Subscription.total), 0)).select_from(Subscription).join(CustomerProfile, CustomerProfile.id == Subscription.customer_id)
            .join(_User, _User.id == CustomerProfile.user_id))
    n, value = db.execute(base.where(*cond)).one()
    auto_n = db.scalar(select(func.count()).select_from(Subscription).join(CustomerProfile, CustomerProfile.id == Subscription.customer_id).join(_User, _User.id == CustomerProfile.user_id)
                       .where(*cond, Subscription.auto_renew.is_(True))) or 0
    summary = {"range": {"date_from": start.isoformat(), "date_to": end.isoformat()}, "expiring_within_days": days, "expiring": n, "auto_renewing": auto_n, "manual_renewal_needed": n - auto_n,
               "value_per_period": q(value), "renewed_in_range": events("RENEWED", "AUTO_RENEWED"), "expired_in_range": events("AUTO_EXPIRED")}
    cols = ["number", "customer", "plan", "expiry_date", "days_to_expiry", "auto_renew", "renewal_count", "total"]
    left = cast(func.julianday(Subscription.expiry_date) - func.julianday(today.isoformat()), Integer) if IS_SQLITE else type_coerce(Subscription.expiry_date - today, Integer)
    stmt = (select(Subscription.number.label("number"), _User.full_name.label("customer"), SubscriptionPlan.name.label("plan"), Subscription.expiry_date.label("expiry_date"),
                   left.label("days_to_expiry"), Subscription.auto_renew.label("auto_renew"), Subscription.renewal_count.label("renewal_count"), Subscription.total.label("total"))
            .join(CustomerProfile, CustomerProfile.id == Subscription.customer_id).join(_User, _User.id == CustomerProfile.user_id)
            .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id).where(*cond))
    sorts = {"expiry_date": Subscription.expiry_date, "number": Subscription.number, "customer": _User.full_name, "total": Subscription.total}
    return _run(db, stmt, page, sorts, "expiry_date", summary, format, "renewals-report", cols)
