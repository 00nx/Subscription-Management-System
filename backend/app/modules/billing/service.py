"""Recurring billing engine.

Safety properties (each covered by tests):
* One invoice per (subscription, billing period): DB unique constraint `uq_invoice_subscription_period`.
* Each subscription is billed in its own transaction under a row lock (`FOR UPDATE SKIP LOCKED`): two workers never
  bill the same subscription at once, and a crash rolls back invoice + date advance together.
* Re-running is a no-op: a subscription is due only while `next_billing_date <= today`, and that date advances in the
  same transaction as the invoice. A period whose invoice already exists is skipped (and the date still advances).
* A failure is rolled back, logged as a BILLING_FAILED event, and the subscription stays due, so the next run retries it.
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.core.config import get_settings
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.emails.service import queue_email
from app.core.enums import InvoiceStatus as IS, SubscriptionStatus as S
from app.core.money import ZERO, q
from app.modules.accounts import notifications as N
from app.modules.analytics.audit import record_audit
from app.modules.billing.models import BillingRun
from app.modules.customers.models import CustomerProfile
from app.modules.discounts import service as discounts
from app.modules.discounts.models import Discount, DiscountUsage
from app.modules.invoices import service as invoices
from app.modules.invoices.models import Invoice
from app.modules.subscriptions import service as subs
from app.modules.subscriptions.models import Subscription, SubscriptionEvent
from app.modules.subscriptions.periods import period_end, period_start

log = logging.getLogger(__name__)
MAX_CATCHUP = 0  # periods billed per subscription per run (a long outage catches up over a few runs)


@dataclass
class BillingResult:
    invoiced: int = 0
    skipped_locked: int = 0
    failed: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    run_id: uuid.UUID | None = None


def _is_due(sub: Subscription, today: date) -> bool:
    return (sub.status == S.ACTIVE and sub.next_billing_date is not None and sub.next_billing_date <= today
            and (sub.expiry_date is None or sub.next_billing_date <= sub.expiry_date))


def _advance(sub: Subscription) -> None:
    sub.periods_billed += 1
    sub.next_billing_date = period_start(sub.start_date, sub.billing_frequency, sub.periods_billed)


def _invoice_period(db: Session, sub: Subscription, today: date) -> Invoice | None:
    """Creates the invoice for the period starting at sub.next_billing_date. Returns None if it already exists."""
    pstart = sub.next_billing_date
    pend = period_end(sub.start_date, sub.billing_frequency, sub.periods_billed)
    if sub.expiry_date and pend > sub.expiry_date:
        pend = sub.expiry_date
    if db.scalar(select(Invoice.id).where(Invoice.subscription_id == sub.id, Invoice.period_start == pstart)):
        return None

    lines = [dict(product_id=l.product_id, description=l.description, quantity=l.quantity, unit_price=l.unit_price, tax_rate=l.tax_rate, discount=ZERO,
                  variants=l.variants or [], taxes=l.taxes or [])
             for l in sub.lines]
    dl = [discounts.DLine(i, l["product_id"], l["quantity"], q(l["unit_price"] * l["quantity"]), q(l["unit_price"] * l["quantity"])) for i, l in enumerate(lines)]

    # Discounts: rows are locked (FOR UPDATE, refreshed) so concurrent jobs cannot push usage past the limit.
    applied: list[tuple[Discount, object]] = []
    for d in discounts.applicable_discounts(db, sub.id, {l["product_id"] for l in lines}, lock=True):
        if discounts.is_eligible(d, dl, today):
            amounts = discounts.compute(d, dl)
            if amounts:
                for i, amt in amounts.items():
                    lines[i]["discount"] += amt
                    dl[i].remaining -= amt
                applied.append((d, sum(amounts.values(), ZERO)))

    auto = get_settings().auto_confirm_invoices  # default: DRAFT, staff review then bulk confirm/send
    inv = invoices.build_invoice(db, sub.customer, lines, status=IS.CONFIRMED if auto else IS.DRAFT, source="AUTO", issue_date=today,
                                 payment_terms_days=sub.payment_terms_days, subscription=sub, period_start=pstart, period_end=pend)
    inv.discount_breakdown = [{"name": d.name, "amount": str(amount)} for d, amount in applied]
    try:
        with db.begin_nested():
            db.add(inv)
            db.flush()
    except IntegrityError:  # a concurrent writer got there first (the unique constraint is the final arbiter)
        return None
    for d, amount in applied:
        d.usage_count += 1
        db.add(DiscountUsage(discount_id=d.id, invoice_id=inv.id, subscription_id=sub.id, amount=amount))
    return inv


def bill_subscription(db: Session, sub_id: uuid.UUID, today: date) -> list[Invoice]:
    """Bills every due period (up to MAX_CATCHUP) of one subscription inside the caller's transaction."""
    sub = db.scalars(select(Subscription).where(Subscription.id == sub_id).with_for_update(skip_locked=True, of=Subscription)
                     .execution_options(populate_existing=True)).unique().first()
    if sub is None:
        return []  # locked by another worker (it is handling it) or gone
    created: list[Invoice] = []
    for _ in range(MAX_CATCHUP):
        if not _is_due(sub, today):
            break
        pstart = sub.next_billing_date
        inv = _invoice_period(db, sub, today)
        _advance(sub)
        if inv is None:
            subs.add_event(db, sub, "BILLING_SKIPPED", detail=f"Period starting {pstart.isoformat()} was already invoiced")
            continue
        created.append(inv)
        subs.add_event(db, sub, "INVOICE_GENERATED", detail=f"{inv.number} for {inv.period_start.isoformat()} to {inv.period_end.isoformat()}")
        if inv.status == IS.CONFIRMED:  # drafts are invisible to customers until confirmed
            N.notify(db, sub.customer.user_id, N.INVOICE_GENERATED, f"Invoice {inv.number} issued", f"{inv.currency} {inv.total} due {inv.due_date.isoformat()}", "invoice", inv.id)
        record_audit(db, None, "INVOICE_GENERATED", "invoice", inv.id, f"Billing engine issued {inv.number} for {sub.number}", {"total": str(inv.total)})
    return created


BATCH_SIZE = 500  # subscriptions loaded per batch: memory stays flat however many are due
MAX_RECORDED_FAILURES = 50


def due_batches(factory, today: date, batch_size: int = BATCH_SIZE):
    """Yields lists of due subscription ids, keyset-paginated on the immutable `number`, so billing a subscription (which moves
    its next_billing_date) can neither skip nor repeat another one, and no more than one batch of ids is ever in memory.
    Each batch is read in its own short session: nothing stays open (or locked) while subscriptions are being billed."""
    last = ""
    while True:
        with factory() as db:
            ids = [(r.id, r.number) for r in db.execute(select(Subscription.id, Subscription.number).where(
                Subscription.status == S.ACTIVE, Subscription.next_billing_date <= today, Subscription.number > last,
                (Subscription.expiry_date.is_(None)) | (Subscription.next_billing_date <= Subscription.expiry_date))
                .order_by(Subscription.number).limit(batch_size))]
        if not ids:
            return
        last = ids[-1][1]
        yield [i for i, _ in ids]


def _finish_run(factory, run_id, **values) -> None:
    with factory() as db:
        run = db.get(BillingRun, run_id)
        for k, v in values.items():
            setattr(run, k, v)
        db.commit()


def run_billing(today: date | None = None, factory=SessionLocal, trigger: str = "SCHEDULED", triggered_by: uuid.UUID | None = None,
                batch_size: int = BATCH_SIZE) -> BillingResult:
    """Entry point for Celery (and the admin 'run now' button). Never raises for a single bad subscription.
    Processes due subscriptions in batches and records the execution in `billing_runs`."""
    today = today or date.today()
    result = BillingResult()
    with factory() as db:
        run = BillingRun(trigger=trigger, triggered_by_id=triggered_by, run_date=today, started_at=datetime.now(UTC))
        db.add(run)
        db.commit()
        result.run_id = run.id
    examined = batches = recovered = 0
    try:
        for ids in due_batches(factory, today, batch_size):
            batches += 1
            for sid in ids:
                examined += 1
                try:
                    with factory() as bdb:
                        made = bill_subscription(bdb, sid, today)
                        bdb.commit()
                    result.invoiced += len(made)
                    recovered += max(len(made) - 1, 0)  # the 2nd..nth invoice of one run are periods that had been missed
                except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
                    log.exception("billing failed for subscription %s", sid)
                    result.failed.append((sid, str(exc)[:300]))
                    try:
                        with factory() as edb:
                            edb.add(SubscriptionEvent(subscription_id=sid, event_type="BILLING_FAILED", detail=str(exc)[:500]))
                            edb.commit()
                    except Exception:  # noqa: BLE001
                        log.exception("could not record billing failure for %s", sid)
        status = "COMPLETED_WITH_ERRORS" if result.failed else "COMPLETED"
    except Exception:  # the loop itself broke (e.g. database down): keep the partial counts and mark the run failed
        log.exception("billing run aborted")
        status = "FAILED"
    _finish_run(factory, result.run_id, status=status, finished_at=datetime.now(UTC), batches=batches, examined=examined, invoiced=result.invoiced,
                recovered=recovered, failed=len(result.failed),
                failures=[{"subscription_id": str(sid), "error": err} for sid, err in result.failed[:MAX_RECORDED_FAILURES]])
    log.info("billing run: %s invoiced, %s failed", result.invoiced, len(result.failed))
    return result


def run_expiry(today: date | None = None, factory=SessionLocal, run_id: uuid.UUID | None = None) -> dict[str, int]:
    """Auto-renew or expire subscriptions past their expiry date (after billing, so in-term periods are never lost)."""
    today = today or date.today()
    counts = {"renewed": 0, "expired": 0}
    with factory() as db:
        ids = list(db.scalars(select(Subscription.id).where(Subscription.status == S.ACTIVE, Subscription.expiry_date < today)))
    for sid in ids:
        with factory() as db:
            sub = db.scalars(select(Subscription).where(Subscription.id == sid).with_for_update(skip_locked=True, of=Subscription)
                             .execution_options(populate_existing=True)).unique().first()
            if sub and (action := subs.process_expiry(db, sub, today)):
                counts[action] += 1
            db.commit()
    if run_id:
        _finish_run(factory, run_id, **counts)
    return counts


def send_due_reminders(db: Session, today: date, within_days: int = 3) -> int:
    """Reminder once per invoice (flag column) for payable invoices due within `within_days`."""
    n = 0
    for inv in db.scalars(select(Invoice).where(Invoice.status.in_(invoices.PAYABLE), Invoice.reminder_sent_at.is_(None),
                                                Invoice.due_date >= today, Invoice.due_date <= today + timedelta(days=within_days))
                          .with_for_update(skip_locked=True)).unique():
        if inv.outstanding <= 0:
            continue
        c = db.get(CustomerProfile, inv.customer_id)
        N.notify(db, c.user_id, N.INVOICE_DUE, f"Invoice {inv.number} is due {inv.due_date.isoformat()}", f"Outstanding {inv.currency} {inv.outstanding}", "invoice", inv.id)
        queue_email(db, c.email, "payment_reminder", {"name": c.full_name, "id": str(inv.id), "number": inv.number, "currency": inv.currency, "outstanding": str(inv.outstanding),
                                                      "due_date": inv.due_date.isoformat(), "days_overdue": 0}, "invoice", inv.id)
        inv.reminder_sent_at = datetime.now(UTC)
        n += 1
    return n


def detect_overdue(db: Session, today: date) -> int:
    """Notifies once per invoice when it becomes overdue. (Overdue itself is derived from due date + balance, never stored.)"""
    n = 0
    for inv in db.scalars(select(Invoice).where(Invoice.status.in_(invoices.PAYABLE), Invoice.overdue_notified_at.is_(None), Invoice.due_date < today)
                          .with_for_update(skip_locked=True)).unique():
        if inv.outstanding <= 0:
            continue
        c = db.get(CustomerProfile, inv.customer_id)
        N.notify(db, c.user_id, N.INVOICE_OVERDUE, f"Invoice {inv.number} is overdue", f"Outstanding {inv.currency} {inv.outstanding}", "invoice", inv.id)
        queue_email(db, c.email, "payment_reminder", {"name": c.full_name, "id": str(inv.id), "number": inv.number, "currency": inv.currency, "outstanding": str(inv.outstanding),
                                                      "due_date": inv.due_date.isoformat(), "days_overdue": (today - inv.due_date).days}, "invoice", inv.id)
        inv.overdue_notified_at = datetime.now(UTC)
        n += 1
    return n


def process_discount_expiry(db: Session, today: date, warn_days: int = 7) -> dict[str, int]:
    """Deactivates discounts whose end date passed; warns staff once about those ending soon."""
    out = {"deactivated": 0, "warned": 0}
    for d in db.scalars(select(Discount).where(Discount.is_active.is_(True), Discount.end_date.is_not(None)).with_for_update(skip_locked=True)).unique():
        if d.end_date < today:
            d.is_active = False
            record_audit(db, None, "DISCOUNT_EXPIRED", "discount", d.id, f"Discount {d.name} expired on {d.end_date.isoformat()}")
            out["deactivated"] += 1
        elif d.end_date <= today + timedelta(days=warn_days) and not d.expiry_notified:
            N.notify_staff(db, N.DISCOUNT_EXPIRING, f"Discount '{d.name}' expires {d.end_date.isoformat()}", "", "discount", d.id)
            d.expiry_notified = True
            out["warned"] += 1
    return out
