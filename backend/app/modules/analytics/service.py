"""Dashboard/report aggregation. Everything is computed in SQL from real records (see docs/FINANCIAL_METRICS.md).

Definitions
* Active subscriptions: status = ACTIVE now.
* MRR: sum over ACTIVE subscriptions of (sum of line quantity x unit price, excluding tax and discounts) normalised to a month.
  Daily x 30.4167, weekly x 4.3333, monthly x 1, yearly / 12. One-time/manual invoices are not recurring and are excluded.
* ARR = MRR x 12.
* Revenue collected: sum of SUCCESS payments whose payment_date falls in the selected range. Invoicing is not collection;
  pending, failed and cancelled payments never count.
* Outstanding: sum(total - amount_paid) over CONFIRMED and PARTIALLY_PAID invoices, as of now.
* Overdue invoices: CONFIRMED/PARTIALLY_PAID, due_date before today, balance > 0.
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, cast, Date, exists, func, literal, select, text, type_coerce
from sqlalchemy.orm import Session

from app.core.database import IS_SQLITE
from app.core.enums import InvoiceStatus as IS, PaymentStatus as PS, SubscriptionStatus as S
from app.core.exceptions import AppError
from app.core.money import ZERO, q
from app.modules.customers.models import CustomerProfile
from app.modules.invoices.models import Invoice, InvoiceLine
from app.modules.payments.models import Payment
from app.modules.subscriptions.models import Subscription, SubscriptionEvent, SubscriptionLine, SubscriptionPlan
from app.modules.subscriptions.periods import MONTHLY_FACTOR, add_months

def date_bucket(col, unit: str):
    """First day of the day/month containing `col`, as a Date (date_trunc on PostgreSQL, date() modifiers on SQLite)."""
    if IS_SQLITE:
        return type_coerce(func.date(col) if unit == "day" else func.date(col, "start of month"), Date)
    return cast(func.date_trunc(unit, col), Date)


PRESETS = ("today", "last_7_days", "last_30_days", "this_month", "last_month", "this_year", "custom")
PAYABLE = (IS.CONFIRMED, IS.PARTIALLY_PAID)


def resolve_range(preset: str | None, date_from: date | None, date_to: date | None, today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    preset = preset or "last_30_days"
    if preset == "today":
        return today, today
    if preset == "last_7_days":
        return today - timedelta(days=7), today
    if preset == "last_30_days":
        return today - timedelta(days=30), today
    if preset == "this_month":
        return today.replace(day=1), today
    if preset == "last_month":
        first = today.replace(day=1)
        return add_months(first, -1), first - timedelta(days=1)
    if preset == "this_year":
        return date(today.year, 1, 1), today
    if preset == "custom":
        if not date_from or not date_to:
            raise AppError("date_from and date_to are required for a custom range", 422)
        if date_to < date_from:
            raise AppError("date_to must not be before date_from", 422)
        return date_from, date_to
    raise AppError(f"Unknown range '{preset}'. Use one of: {', '.join(PRESETS)}", 422)


@dataclass(frozen=True)
class Filters:
    """Optional dashboard filters. Subscription filters (frequency, plan, status, customer) narrow subscription metrics directly and
    invoice/payment metrics through the invoice's subscription; invoice_status narrows invoice and payment metrics."""
    frequency: object | None = None
    plan_id: uuid.UUID | None = None
    subscription_status: S | None = None
    invoice_status: IS | None = None
    customer_id: uuid.UUID | None = None

    @property
    def sub_filtered(self) -> bool:
        return any((self.frequency, self.plan_id, self.subscription_status))

    def sub(self, with_status: bool = True) -> list:
        c = []
        if self.frequency:
            c.append(Subscription.billing_frequency == self.frequency)
        if self.plan_id:
            c.append(Subscription.plan_id == self.plan_id)
        if self.subscription_status and with_status:
            c.append(Subscription.status == self.subscription_status)
        if self.customer_id:
            c.append(Subscription.customer_id == self.customer_id)
        return c

    def inv(self) -> list:
        c = []
        if self.customer_id:
            c.append(Invoice.customer_id == self.customer_id)
        if self.invoice_status:
            c.append(Invoice.status == self.invoice_status)
        if self.sub_filtered:
            c.append(exists().where(Subscription.id == Invoice.subscription_id, *self.sub()))  # EXISTS, not IN: PostgreSQL plans it as a semi-join
        return c

    def pay(self) -> list:
        c = []
        if self.customer_id:
            c.append(Payment.customer_id == self.customer_id)
        if self.invoice_status or self.sub_filtered:
            c.append(exists().where(Invoice.id == Payment.invoice_id, *self.inv()))
        return c


NO_FILTERS = Filters()


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min, tzinfo=UTC), datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)


def _success_in_range(start: date, end: date):
    lo, hi = _bounds(start, end)
    return and_(Payment.status == PS.SUCCESS, Payment.payment_date >= lo, Payment.payment_date <= hi)


def _monthly(amount: Decimal, freq) -> Decimal:
    return amount * Decimal(MONTHLY_FACTOR[freq])


def mrr(db: Session, as_of: datetime | None = None, f: Filters = NO_FILTERS) -> Decimal:
    """MRR now (status ACTIVE) or reconstructed at `as_of` from the subscription event history.
    ponytail: historical MRR uses today's line prices (lines are edited only before activation, so drift is small)."""
    if as_of is None:
        active_ids = None
        rows = db.execute(select(Subscription.billing_frequency, func.sum(SubscriptionLine.unit_price * SubscriptionLine.quantity))
                          .join(SubscriptionLine, SubscriptionLine.subscription_id == Subscription.id)
                          .where(Subscription.status == S.ACTIVE, *f.sub(False)).group_by(Subscription.billing_frequency)).all()
    else:
        ranked = (select(SubscriptionEvent.subscription_id, SubscriptionEvent.event_type,
                         func.row_number().over(partition_by=SubscriptionEvent.subscription_id, order_by=SubscriptionEvent.created_at.desc()).label("rn"))
                  .where(SubscriptionEvent.event_type.in_(["ACTIVATED", "RESUMED", "RENEWED", "PAUSED", "CLOSED", "AUTO_EXPIRED"]),
                         SubscriptionEvent.created_at <= as_of,
                         *([exists().where(Subscription.id == SubscriptionEvent.subscription_id, *f.sub(False))] if f.sub(False) else [])).subquery())  # rank only the filtered subscriptions' events
        latest = select(ranked.c.subscription_id, ranked.c.event_type).where(ranked.c.rn == 1).subquery()  # newest state-changing event per subscription
        rows = db.execute(select(Subscription.billing_frequency, func.sum(SubscriptionLine.unit_price * SubscriptionLine.quantity))
                          .join(SubscriptionLine, SubscriptionLine.subscription_id == Subscription.id)
                          .join(latest, latest.c.subscription_id == Subscription.id)
                          .where(latest.c.event_type.in_(["ACTIVATED", "RESUMED", "RENEWED"]), *f.sub(False)).group_by(Subscription.billing_frequency)).all()
    return q(sum((total or ZERO for f, total in rows), ZERO))


def kpis(db: Session, start: date, end: date, include_revenue: bool = True, today: date | None = None, f: Filters = NO_FILTERS) -> dict:
    """`active_subscriptions` counts ACTIVE subscriptions (or the filtered status). Invoice/payment figures obey every filter."""
    today = today or date.today()
    inv_f = f.inv()
    overdue_cond = and_(Invoice.status.in_(PAYABLE), Invoice.due_date > today, Invoice.total - Invoice.amount_paid > 0)
    sub_where = [Subscription.status == S.ACTIVE, *f.sub(False)] if not f.subscription_status else f.sub()
    active = db.scalar(select(func.count()).select_from(Subscription).where(*sub_where)) or 0
    outstanding = db.scalar(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(Invoice.status.in_(PAYABLE), *inv_f)) or ZERO
    overdue = db.scalar(select(func.count()).select_from(Invoice).where(overdue_cond, *inv_f)) or 0
    customers = db.scalar(select(func.count()).select_from(CustomerProfile).where(*([CustomerProfile.id == f.customer_id] if f.customer_id else []))) or 0
    issued = (Invoice.status != IS.DRAFT, Invoice.issue_date >= start, Invoice.issue_date <= end, *inv_f)
    n_inv, billed = db.execute(select(func.count(), func.coalesce(func.sum(Invoice.total), 0)).where(*issued, Invoice.status != IS.CANCELLED)).one()
    out = {"active_subscriptions": active, "outstanding_amount": q(outstanding), "overdue_invoices": overdue, "total_customers": customers,
           "total_invoices": n_inv, "revenue_billed": None, "total_payments": None, "payments_count": None,
           "mrr": None, "arr": None, "revenue_collected": None}
    if include_revenue:
        m = mrr(db, None, f)
        n_pay, collected = db.execute(select(func.count(), func.coalesce(func.sum(Payment.amount), 0)).where(_success_in_range(start, end), *f.pay())).one()
        out.update(mrr=m, arr=q(m * 12), revenue_collected=q(collected), total_payments=q(collected), payments_count=n_pay, revenue_billed=q(billed))
    return out


def active_by_plan(db: Session, f: Filters = NO_FILTERS) -> list[dict]:
    where = [Subscription.status == (f.subscription_status or S.ACTIVE), *f.sub(False)]
    rows = db.execute(select(SubscriptionPlan.name, func.count()).join(Subscription, Subscription.plan_id == SubscriptionPlan.id)
                      .where(*where).group_by(SubscriptionPlan.name).order_by(func.count().desc(), SubscriptionPlan.name)).all()
    return [{"plan": n, "count": c} for n, c in rows]


def revenue_series(db: Session, start: date, end: date, f: Filters = NO_FILTERS) -> list[dict]:
    """Collected revenue per day (ranges up to ~2 months) or per month."""
    by_day = (end - start).days <= 62
    day = date_bucket(Payment.payment_date, "day" if by_day else "month")
    rows = db.execute(select(day, func.sum(Payment.amount)).where(_success_in_range(start, end), *f.pay()).group_by(day).order_by(day)).all()
    got = {d: a for d, a in rows}
    out, cur = [], start if by_day else start.replace(day=1)
    while cur <= end:
        out.append({"period": cur.isoformat(), "amount": q(got.get(cur, ZERO))})
        cur = cur + timedelta(days=1) if by_day else add_months(cur, 1)
    return out


def mrr_trend(db: Session, months: int = 12, today: date | None = None, f: Filters = NO_FILTERS) -> list[dict]:
    today = today or date.today()
    out = []
    for i in range(months - 1, -1, -1):
        first = add_months(today.replace(day=1), -i)
        month_end = add_months(first, 1) - timedelta(days=1)
        as_of = None if i == 0 else datetime.combine(month_end, time.max, tzinfo=UTC)
        out.append({"period": first.isoformat(), "amount": mrr(db, as_of, f)})
    return out


def subscription_growth(db: Session, months: int = 12, today: date | None = None, f: Filters = NO_FILTERS) -> list[dict]:
    today = today or date.today()
    first = add_months(today.replace(day=1), -(months - 1))
    before = db.scalar(select(func.count()).select_from(Subscription).where(Subscription.created_at < datetime.combine(first, time.min, tzinfo=UTC), *f.sub())) or 0
    month = date_bucket(Subscription.created_at, "month")
    rows = dict(db.execute(select(month, func.count()).where(Subscription.created_at >= datetime.combine(first, time.min, tzinfo=UTC), *f.sub()).group_by(month)).all())
    out, total = [], before
    for i in range(months):
        m = add_months(first, i)
        total += rows.get(m, 0)
        out.append({"period": m.isoformat(), "new": rows.get(m, 0), "total": total})
    return out


def status_distribution(db: Session, f: Filters = NO_FILTERS) -> list[dict]:
    rows = dict(db.execute(select(Subscription.status, func.count()).where(*f.sub()).group_by(Subscription.status)).all())
    return [{"status": s.value, "count": rows.get(s, 0)} for s in S]


def payment_distribution(db: Session, start: date, end: date, f: Filters = NO_FILTERS) -> list[dict]:
    lo, hi = _bounds(start, end)
    rows = {s: (c, a) for s, c, a in db.execute(select(Payment.status, func.count(), func.coalesce(func.sum(Payment.amount), 0))
                                                .where(Payment.created_at >= lo, Payment.created_at < hi, *f.pay()).group_by(Payment.status)).all()}
    return [{"status": s.value, "count": rows.get(s, (0, 0))[0], "amount": q(rows.get(s, (0, 0))[1])} for s in PS]


def recent_activity(db: Session, limit: int = 15) -> list[dict]:
    items: list[dict] = []
    for s in db.scalars(select(Subscription).order_by(Subscription.created_at.desc()).limit(5)).unique():
        items.append({"type": "NEW_SUBSCRIPTION", "title": f"New subscription {s.number}", "detail": f"{s.customer_name} - {s.plan_name}", "at": s.created_at})
    for i in db.scalars(select(Invoice).where(Invoice.source == "AUTO").order_by(Invoice.created_at.desc()).limit(5)).unique():
        items.append({"type": "INVOICE_GENERATED", "title": f"Invoice {i.number} generated", "detail": f"{i.currency} {i.total}", "at": i.created_at})
    for p in db.scalars(select(Payment).where(Payment.status.in_([PS.SUCCESS, PS.FAILED])).order_by(Payment.created_at.desc()).limit(8)).unique():
        ok = p.status == PS.SUCCESS
        items.append({"type": "PAYMENT_SUCCESS" if ok else "PAYMENT_FAILED", "title": f"Payment {'received' if ok else 'failed'} on {p.invoice_number}",
                      "detail": f"{p.method.value} {p.amount}", "at": p.created_at})
    for e in db.execute(select(SubscriptionEvent, Subscription.number).join(Subscription, Subscription.id == SubscriptionEvent.subscription_id)
                        .where(SubscriptionEvent.event_type.in_(["RENEWED", "AUTO_RENEWED"])).order_by(SubscriptionEvent.created_at.desc()).limit(4)).all():
        items.append({"type": "SUBSCRIPTION_RENEWED", "title": f"Subscription {e[1]} renewed", "detail": e[0].detail or "", "at": e[0].created_at})
    for i in db.scalars(select(Invoice).where(Invoice.status.in_(PAYABLE), Invoice.due_date < date.today(), Invoice.total - Invoice.amount_paid > 0)
                        .order_by(Invoice.due_date).limit(4)).unique():
        items.append({"type": "INVOICE_OVERDUE", "title": f"Invoice {i.number} overdue", "detail": f"{i.currency} {i.outstanding} due {i.due_date.isoformat()}", "at": datetime.combine(i.due_date, time.min, tzinfo=UTC)})
    return sorted(items, key=lambda x: x["at"], reverse=True)[:limit]
