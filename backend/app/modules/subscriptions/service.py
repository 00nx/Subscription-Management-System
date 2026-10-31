import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import next_number
from app.core.enums import InvoiceStatus, RecordStatus, SubscriptionStatus as S
from app.core.exceptions import AppError
from app.core.money import ZERO, q, tax_amount
from app.modules.accounts import notifications as N
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.customers.models import CustomerProfile
from app.modules.emails.service import queue_email
from app.modules.customers.service import scope_customer_id
from app.modules.products import service as products
from app.modules.subscriptions.models import (PlanProduct, Subscription, SubscriptionEvent, SubscriptionLine, SubscriptionPlan,
                                              SubscriptionRequest)
from app.modules.subscriptions.periods import period_start, term_expiry
from app.modules.subscriptions.schemas import LineIn, SubscriptionIn, SubscriptionUpdateIn

# Allowed lifecycle moves. Anything else is rejected, whoever asks.
TRANSITIONS: dict[S, set[S]] = {
    S.DRAFT: {S.QUOTATION, S.CONFIRMED, S.CLOSED},
    S.QUOTATION: {S.DRAFT, S.CONFIRMED, S.CLOSED},
    S.CONFIRMED: {S.ACTIVE, S.CLOSED},
    S.ACTIVE: {S.PAUSED, S.EXPIRED},
    S.PAUSED: {S.ACTIVE, S.CLOSED},
    S.EXPIRED: {S.ACTIVE, S.CLOSED},
    S.CLOSED: set(),
}
EDITABLE = {S.DRAFT, S.QUOTATION, S.CONFIRMED}


# ---------- plans ----------
def get_plan(db: Session, plan_id: uuid.UUID) -> SubscriptionPlan:
    plan = db.get(SubscriptionPlan, plan_id)
    if not plan:
        raise AppError("Plan not found", 404)
    return plan


def require_available(plan: SubscriptionPlan) -> None:
    if plan.is_available:
        raise AppError(f"Plan '{plan.name}' is not available for new subscriptions", 400)


def set_extra_products(db: Session, plan: SubscriptionPlan, product_ids: list[uuid.UUID]) -> None:
    ids = [p for p in dict.fromkeys(product_ids) if p != plan.product_id]
    for pid in ids:
        products.get_product(db, pid)
    plan.extra_products = [PlanProduct(product_id=pid) for pid in ids]


# ---------- lines & totals ----------
def resolve_lines(db: Session, plan: SubscriptionPlan, lines_in: list[LineIn]) -> list[dict]:
    """Validates lines against the plan and snapshots price + tax rate. Price default: plan price for the plan's own
    product, otherwise the product's sales price; plus the variant's additional amount. A supplied unit_price wins."""
    if not lines_in:
        lines_in = [LineIn(product_id=plan.product_id, quantity=plan.min_quantity)]
    allowed = {plan.product_id, *plan.extra_product_ids}
    out, plan_qty = [], 0
    for li in lines_in:
        product = products.get_product(db, li.product_id)
        if product.id not in allowed:
            raise AppError(f"Product '{product.name}' is not part of plan '{plan.name}'", 400)
        if product.status != RecordStatus.ACTIVE:
            raise AppError(f"Product '{product.name}' is not active", 400)
        chosen = [products.get_variant(db, product, vid) for vid in li.all_variant_ids]
        for v in chosen:
            if v.status != RecordStatus.ACTIVE:
                raise AppError(f"Variant '{v.name}' is not active", 400)
        attrs = [v.attribute_name for v in chosen]
        if len(set(attrs)) == len(attrs):
            raise AppError("Choose at most one variant per attribute", 400)
        extra = sum((v.additional_price for v in chosen), ZERO)
        # price = base (plan price for the plan's own product, else the product's sales price) + every selected variant's adjustment
        price = q(li.unit_price) if li.unit_price is not None else q((plan.price if product.id == plan.product_id else product.sales_price) + extra)
        taxes = products.taxes_for(db, product)
        if product.id == plan.product_id:
            plan_qty += li.quantity
        out.append(dict(product_id=product.id, variant_id=chosen[0].id if chosen else None, quantity=li.quantity, unit_price=price,
                        description=li.description or product.name + "".join(f" - {v.name}" for v in chosen),
                        variants=[dict(id=str(v.id), name=v.name, attribute=v.attribute_name, value=v.attribute_value, additional_price=str(v.additional_price)) for v in chosen],
                        tax_id=uuid.UUID(taxes[0]["id"]) if taxes else None, tax_rate=sum((Decimal(t["rate"]) for t in taxes), ZERO), taxes=taxes))
    if plan_qty <= plan.min_quantity:
        raise AppError(f"Plan '{plan.name}' requires a minimum quantity of {plan.min_quantity}", 400)
    return out


def totals(lines: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = sum((l["unit_price"] * l["quantity"] for l in lines), ZERO)
    tax = sum((tax_amount(q(l["unit_price"] * l["quantity"]), l.get("taxes"), l["tax_rate"]) for l in lines), ZERO)
    return q(subtotal), q(tax), q(subtotal + tax)


def _apply_lines(sub: Subscription, lines: list[dict]) -> None:
    sub.lines = [SubscriptionLine(**l) for l in lines]
    sub.subtotal, sub.tax_total, sub.total = totals(lines)


# ---------- events ----------
def add_event(db: Session, sub: Subscription, event_type: str, frm: S | None = None, to: S | None = None, detail: str | None = None, actor: User | None = None) -> None:
    db.add(SubscriptionEvent(subscription_id=sub.id, event_type=event_type, from_status=frm.value if frm else None,
                             to_status=to.value if to else None, detail=detail, actor_user_id=getattr(actor, "id", None)))


def transition(db: Session, sub: Subscription, to: S, actor: User | None, event_type: str, detail: str | None = None) -> None:
    if to not in TRANSITIONS[sub.status]:
        raise AppError(f"A {sub.status.value.lower()} subscription cannot become {to.value.lower()}", 409)
    frm, sub.status = sub.status, to
    add_event(db, sub, event_type, frm, to, detail, actor)
    record_audit(db, actor, "SUBSCRIPTION_STATUS", "subscription", sub.id, f"{sub.number}: {frm.value} -> {to.value}", {"from": frm.value, "to": to.value})


# ---------- access ----------
def get_subscription(db: Session, user: User, sub_id: uuid.UUID, lock: bool = False) -> Subscription:
    stmt = select(Subscription).where(Subscription.id == sub_id)
    if lock:
        stmt = stmt.with_for_update(of=Subscription)
    sub = db.scalars(stmt).unique().first()
    scope = scope_customer_id(db, user)
    if not sub or (scope is not None and (sub.customer_id != scope or sub.status in (S.DRAFT, S.QUOTATION))):
        raise AppError("Subscription not found", 404)
    return sub


# ---------- create / update ----------
def create_subscription(db: Session, data: SubscriptionIn, actor: User | None, quotation_id: uuid.UUID | None = None,
                        lines: list[dict] | None = None, status: S = S.DRAFT, plan: SubscriptionPlan | None = None) -> Subscription:
    profile = db.get(CustomerProfile, data.customer_id)
    if not profile or not profile.is_active:
        raise AppError("Customer not found or inactive", 400)
    plan = plan or get_plan(db, data.plan_id)
    if quotation_id is None:
        require_available(plan)
    lines = lines if lines is not None else resolve_lines(db, plan, data.lines)
    sub = Subscription(number=next_number(db, "subscription_number_seq", "SUB"), customer_id=profile.id, plan_id=plan.id,
                       quotation_id=quotation_id, status=status, start_date=data.start_date, billing_frequency=plan.billing_frequency,
                       payment_terms_days=data.payment_terms_days, term_periods=data.term_periods,
                       expiry_date=term_expiry(data.start_date, plan.billing_frequency, data.term_periods),
                       next_billing_date=data.start_date, auto_renew=data.auto_renew, notes=data.notes,
                       created_by_id=getattr(actor, "id", None))
    _apply_lines(sub, lines)
    db.add(sub)
    db.flush()
    add_event(db, sub, "CREATED", None, status, "Created from quotation" if quotation_id else "Created", actor)
    record_audit(db, actor, "SUBSCRIPTION_CREATED", "subscription", sub.id, f"Created {sub.number} for {profile.customer_number}", {"total": str(sub.total)})
    return sub


def update_subscription(db: Session, sub: Subscription, data: SubscriptionUpdateIn, actor: User) -> Subscription:
    changes = data.model_dump(exclude_unset=True)
    if sub.status not in EDITABLE and set(changes) - {"notes", "auto_renew"}:
        raise AppError("Only notes and auto-renew can be changed once a subscription is active", 409)
    for k in ("notes", "auto_renew", "payment_terms_days"):
        if k in changes:
            setattr(sub, k, changes[k])
    if sub.status in EDITABLE:
        if "start_date" in changes and changes["start_date"]:
            sub.start_date = changes["start_date"]
        if "term_periods" in changes:
            sub.term_periods = changes["term_periods"]
        sub.expiry_date = term_expiry(sub.start_date, sub.billing_frequency, sub.term_periods)
        sub.next_billing_date = sub.start_date
        if data.lines is not None:
            _apply_lines(sub, resolve_lines(db, sub.plan, data.lines))
    record_audit(db, actor, "SUBSCRIPTION_UPDATED", "subscription", sub.id, f"Updated {sub.number}", {k: str(v) for k, v in changes.items() if k != "lines"})
    return sub


# ---------- lifecycle operations (callers lock the row first) ----------
def _notify(db: Session, sub: Subscription, type_: str, title: str, email: str | None = None) -> None:
    N.notify(db, sub.customer.user_id, type_, title, f"Subscription {sub.number}", "subscription", sub.id)
    if email:
        queue_email(db, sub.customer.email, email, {"name": sub.customer.full_name, "id": str(sub.id), "number": sub.number, "plan": sub.plan.name,
                                                    "start_date": sub.start_date.isoformat(), "expiry_date": sub.expiry_date.isoformat() if sub.expiry_date else "",
                                                    "next_billing_date": sub.next_billing_date.isoformat() if sub.next_billing_date else ""}, "subscription", sub.id)


def confirm(db: Session, sub: Subscription, actor: User) -> None:
    transition(db, sub, S.CONFIRMED, actor, "CONFIRMED")
    queue_email(db, sub.customer.email, "subscription_confirmed", {"name": sub.customer.full_name, "id": str(sub.id), "number": sub.number, "plan": sub.plan.name,
                                                                   "start_date": sub.start_date.isoformat()}, "subscription", sub.id)


def activate(db: Session, sub: Subscription, actor: User | None) -> None:
    transition(db, sub, S.ACTIVE, actor, "ACTIVATED")
    if sub.periods_billed == 0:
        sub.next_billing_date = sub.start_date
    _notify(db, sub, N.SUBSCRIPTION_ACTIVATED, "Your subscription is active", "subscription_activated")


def pause(db: Session, sub: Subscription, actor: User | None) -> None:
    if not sub.plan.allow_pause:
        raise AppError("This plan does not allow pausing", 400)
    transition(db, sub, S.PAUSED, actor, "PAUSED")
    _notify(db, sub, N.SUBSCRIPTION_PAUSED, "Your subscription was paused")


def resume(db: Session, sub: Subscription, actor: User | None, today: date | None = None) -> None:
    """Billing does not run while paused, so periods that elapsed during the pause are skipped (not back-billed)."""
    today = today or date.today()
    transition(db, sub, S.ACTIVE, actor, "RESUMED")
    skipped = 0
    while sub.next_billing_date and sub.next_billing_date < today and (sub.expiry_date is None or sub.next_billing_date <= sub.expiry_date):
        sub.periods_billed += 1
        sub.next_billing_date = period_start(sub.start_date, sub.billing_frequency, sub.periods_billed)
        skipped += 1
    if skipped:
        add_event(db, sub, "PERIODS_SKIPPED", detail=f"{skipped} billing period(s) elapsed while paused and were not billed", actor=actor)


def _extend_term(db: Session, sub: Subscription, actor: User | None, event: str) -> None:
    sub.renewal_count += 1
    sub.expiry_date = term_expiry(sub.start_date, sub.billing_frequency, sub.term_periods * (sub.renewal_count + 1))
    add_event(db, sub, event, detail=f"Term extended to {sub.expiry_date.isoformat()}", actor=actor)


def renew(db: Session, sub: Subscription, actor: User | None, today: date | None = None) -> None:
    """Manual renewal. Allowed in the last billing period of the current term, or once expired. After one renewal the
    window is closed again, so a double click cannot extend the term twice."""
    today = today or date.today()
    if not sub.plan.allow_renewal:
        raise AppError("This plan does not allow renewal", 400)
    if not sub.term_periods or not sub.expiry_date:
        raise AppError("An open-ended subscription has no term to renew", 400)
    if sub.status not in (S.ACTIVE, S.EXPIRED):
        raise AppError("Only active or expired subscriptions can be renewed", 409)
    opens = period_start(sub.start_date, sub.billing_frequency, sub.term_periods * (sub.renewal_count + 1) - 1)
    if sub.status == S.ACTIVE and today < opens:
        raise AppError(f"Renewal opens on {opens.isoformat()}", 409)
    if sub.status == S.EXPIRED:
        transition(db, sub, S.ACTIVE, actor, "RENEWED", "Reactivated by renewal")
    _extend_term(db, sub, actor, "RENEWED")
    _notify(db, sub, N.SUBSCRIPTION_RENEWED, "Your subscription was renewed", "subscription_renewed")


def cancel(db: Session, sub: Subscription, actor: User | None, today: date | None = None) -> None:
    today = today or date.today()
    if sub.status == S.ACTIVE and sub.expiry_date and sub.expiry_date > today and not sub.plan.allow_early_closure:
        raise AppError("This plan does not allow early closure", 400)
    transition(db, sub, S.CLOSED, actor, "CLOSED")
    _notify(db, sub, N.SUBSCRIPTION_CANCELLED, "Your subscription was closed")


def process_expiry(db: Session, sub: Subscription, today: date) -> str | None:
    """Scheduler entry (row locked by caller). Idempotent: acts only while the stored expiry is in the past."""
    if sub.status != S.ACTIVE or not sub.expiry_date or sub.expiry_date >= today:
        return None
    if sub.auto_renew and sub.plan.allow_renewal and sub.term_periods:
        for _ in range(1000):
            _extend_term(db, sub, None, "AUTO_RENEWED")
            if sub.expiry_date >= today:
                break
        _notify(db, sub, N.SUBSCRIPTION_RENEWED, "Your subscription was renewed", "subscription_renewed")
        return "renewed"
    if sub.plan.auto_close:
        transition(db, sub, S.EXPIRED, None, "AUTO_EXPIRED", f"Expired on {sub.expiry_date.isoformat()}")
        _notify(db, sub, N.SUBSCRIPTION_CANCELLED, "Your subscription has expired", "subscription_expired")
        return "expired"
    return None


# ---------- customer requests ----------
_REQUEST_FROM = {"CANCEL": {S.ACTIVE, S.PAUSED, S.CONFIRMED}, "PAUSE": {S.ACTIVE}, "RESUME": {S.PAUSED}}


def create_request(db: Session, user: User, sub: Subscription, request_type: str, reason: str | None) -> SubscriptionRequest:
    if user.role != UserRole.CUSTOMER:
        raise AppError("Only customers submit requests", 403)
    if sub.status not in _REQUEST_FROM[request_type]:
        raise AppError(f"A {request_type.lower()} request is not possible for a {sub.status.value.lower()} subscription", 409)
    if request_type == "PAUSE" and not sub.plan.allow_pause:
        raise AppError("This plan does not allow pausing", 400)
    if db.scalar(select(SubscriptionRequest.id).where(SubscriptionRequest.subscription_id == sub.id, SubscriptionRequest.request_type == request_type,
                                                      SubscriptionRequest.status == "PENDING")):
        raise AppError("You already have a pending request of this type", 409)
    req = SubscriptionRequest(subscription_id=sub.id, customer_id=sub.customer_id, request_type=request_type, reason=reason)
    db.add(req)
    add_event(db, sub, "REQUESTED", detail=f"Customer requested {request_type.lower()}", actor=user)
    N.notify_staff(db, N.REQUEST_SUBMITTED, f"{request_type.title()} request for {sub.number}", reason or "", "subscription", sub.id)
    return req


def decide_request(db: Session, req: SubscriptionRequest, approve: bool, actor: User) -> None:
    if req.status != "PENDING":
        raise AppError("Request was already decided", 409)
    sub = get_subscription(db, actor, req.subscription_id, lock=True)
    if approve:
        {"CANCEL": cancel, "PAUSE": pause, "RESUME": resume}[req.request_type](db, sub, actor)
    req.status = "APPROVED" if approve else "REJECTED"
    req.decided_by_id, req.decided_at = actor.id, datetime.now(UTC)
    N.notify(db, sub.customer.user_id, "REQUEST_DECIDED", f"Your {req.request_type.lower()} request was {req.status.lower()}", sub.number, "subscription", sub.id)
    record_audit(db, actor, "REQUEST_" + req.status, "subscription_request", req.id, f"{req.request_type} request on {sub.number} {req.status.lower()}")


# ---------- customer self-subscription ----------
def subscribe_to_plan(db: Session, user: User, data) -> tuple[Subscription, "Invoice | None"]:
    """A customer subscribes themselves to an open plan: created, confirmed and activated in one step. When it starts today the first
    invoice is generated, confirmed and emailed immediately so the customer can pay it right away."""
    from app.modules.billing.service import bill_subscription
    from app.modules.invoices import service as invoices
    from app.modules.invoices.models import Invoice

    if user.role != UserRole.CUSTOMER:
        raise AppError("Only customers can subscribe themselves; staff create subscriptions for customers", 403)
    profile = db.scalar(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
    if profile is None:
        raise AppError("Customer profile not found", 404)
    plan = get_plan(db, data.plan_id)
    require_available(plan)
    today = date.today()
    start = data.start_date or today
    if start < today:
        raise AppError("The start date cannot be in the past", 422)
    if db.scalar(select(Subscription.id).where(Subscription.customer_id == profile.id, Subscription.plan_id == plan.id,
                                                Subscription.status.in_([S.CONFIRMED, S.ACTIVE, S.PAUSED]))):
        raise AppError(f"You already have a subscription to {plan.name}. Manage it under My Subscriptions.", 409)
    sub_in = SubscriptionIn(customer_id=profile.id, plan_id=plan.id, start_date=start, term_periods=data.term_periods, payment_terms_days=14, auto_renew=data.auto_renew,
                            lines=[LineIn(product_id=plan.product_id, variant_ids=data.variant_ids, quantity=data.quantity or plan.min_quantity)])
    sub = create_subscription(db, sub_in, user)
    confirm(db, sub, user)
    activate(db, sub, user)
    invoice = None
    if start <= today:
        made = bill_subscription(db, sub.id, today)
        if made:
            invoice = made[0]
            if invoice.status == InvoiceStatus.DRAFT:
                invoices.confirm(db, invoice, user)
            invoices.send(db, invoice, user)
    return sub, invoice
