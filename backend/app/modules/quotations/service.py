import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import next_number
from app.core.enums import QuotationStatus as QS, RecordStatus, SubscriptionStatus
from app.core.exceptions import AppError
from app.core.money import ZERO, q, tax_amount
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.emails.service import queue_email
from app.modules.customers.models import CustomerProfile
from app.modules.customers.service import scope_customer_id
from app.modules.discounts import service as discounts
from app.modules.discounts.models import Discount, DiscountSubscription
from app.modules.quotations.models import Quotation, QuotationLine, QuotationTemplate, QuotationTemplateLine
from app.modules.quotations.schemas import ConvertIn, QuotationIn, QuotationUpdateIn, TemplateIn, TemplateUpdateIn
from app.modules.subscriptions import service as subs
from app.modules.subscriptions.schemas import LineIn, SubscriptionIn


# ---------- templates ----------
def get_template(db: Session, template_id: uuid.UUID) -> QuotationTemplate:
    t = db.get(QuotationTemplate, template_id)
    if not t:
        raise AppError("Template not found", 404)
    return t


def _tline(l) -> QuotationTemplateLine:
    ids = list(dict.fromkeys([*([l.variant_id] if l.variant_id else []), *l.variant_ids]))
    return QuotationTemplateLine(product_id=l.product_id, variant_id=ids[0] if ids else None, variant_ids=[str(i) for i in ids], quantity=l.quantity, unit_price=l.unit_price)


def _check_template_lines(db: Session, plan_id, lines) -> None:
    """Template lines must be valid against the template's plan when it has one."""
    if plan_id:
        subs.resolve_lines(db, subs.get_plan(db, plan_id), [LineIn(**l.model_dump()) for l in lines]) if lines else None


def create_template(db: Session, data: TemplateIn, actor: User) -> QuotationTemplate:
    _check_template_lines(db, data.plan_id, data.lines)
    t = QuotationTemplate(**data.model_dump(exclude={"lines"}))
    t.lines = [_tline(l) for l in data.lines]
    db.add(t)
    db.flush()
    record_audit(db, actor, "TEMPLATE_CREATED", "quotation_template", t.id, f"Created template {t.name}")
    return t


def update_template(db: Session, t: QuotationTemplate, data: TemplateUpdateIn, actor: User) -> QuotationTemplate:
    changes = data.model_dump(exclude_unset=True, exclude={"lines"})
    for k, v in changes.items():
        setattr(t, k, v)
    if data.lines is not None:
        _check_template_lines(db, t.plan_id, data.lines)
        t.lines = [_tline(l) for l in data.lines]
    record_audit(db, actor, "TEMPLATE_UPDATED", "quotation_template", t.id, f"Updated template {t.name}")
    return t


def _vids(l) -> list:
    return list(l.variant_ids or ([l.variant_id] if l.variant_id else []))


# ---------- quotations ----------
def _compute(db: Session, qt: Quotation, lines: list[dict]) -> None:
    """Totals with an *estimate* of the attached discount (usage is only consumed when invoices are generated)."""
    dl = [discounts.DLine(i, l["product_id"], l["quantity"], q(l["unit_price"] * l["quantity"]), q(l["unit_price"] * l["quantity"])) for i, l in enumerate(lines)]
    disc = {}
    d = db.get(Discount, qt.discount_id) if qt.discount_id else None
    if d and discounts.is_eligible(d, dl, qt.issue_date):
        disc = discounts.compute(d, dl)
    sub = sum((x.subtotal for x in dl), ZERO)
    tax = sum((tax_amount(x.subtotal - disc.get(x.key, ZERO), l.get("taxes"), l["tax_rate"]) for x, l in zip(dl, lines)), ZERO)
    dtot = sum(disc.values(), ZERO)
    qt.subtotal, qt.discount_total, qt.tax_total, qt.total = sub, dtot, tax, sub - dtot + tax
    qt.lines = [QuotationLine(**l) for l in lines]


def create_quotation(db: Session, data: QuotationIn, actor: User) -> Quotation:
    customer = db.get(CustomerProfile, data.customer_id)
    if not customer or not customer.is_active:
        raise AppError("Customer not found or inactive", 400)
    tpl = get_template(db, data.template_id) if data.template_id else None
    if tpl and tpl.status != RecordStatus.ACTIVE:
        raise AppError("Template is not active", 400)
    plan_id = data.plan_id or (tpl.plan_id if tpl else None)
    if not plan_id:
        raise AppError("A subscription plan is required", 422)
    plan = subs.get_plan(db, plan_id)
    subs.require_available(plan)
    lines_in = data.lines or ([LineIn(product_id=l.product_id, variant_ids=_vids(l), quantity=l.quantity, unit_price=l.unit_price) for l in tpl.lines] if tpl else [])
    discount_id = data.discount_id or (tpl.discount_id if tpl else None)  # a template may carry a default discount
    if discount_id and not db.get(Discount, discount_id):
        raise AppError("Discount not found", 400)
    today = date.today()
    validity = data.validity_days or (tpl.validity_days if tpl else 30)
    qt = Quotation(number=next_number(db, "quotation_number_seq", "QUO"), customer_id=customer.id, template_id=tpl.id if tpl else None,
                   plan_id=plan.id, discount_id=discount_id, status=QS.DRAFT, issue_date=today, expiry_date=today + timedelta(days=validity),
                   payment_terms_days=data.payment_terms_days if data.payment_terms_days is not None else (tpl.payment_terms_days if tpl else 0),
                   notes=data.notes if data.notes is not None else (tpl.notes if tpl else None), created_by_id=actor.id)
    _compute(db, qt, subs.resolve_lines(db, plan, lines_in))
    db.add(qt)
    db.flush()
    record_audit(db, actor, "QUOTATION_CREATED", "quotation", qt.id, f"Created {qt.number}", {"total": str(qt.total)})
    return qt


def get_quotation(db: Session, user: User, qid: uuid.UUID, lock: bool = False) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == qid)
    if lock:
        stmt = stmt.with_for_update(of=Quotation)
    qt = db.scalars(stmt).unique().first()
    scope = scope_customer_id(db, user)
    if not qt or (scope is not None and (qt.customer_id != scope or qt.status == QS.DRAFT)):
        raise AppError("Quotation not found", 404)
    return qt


def update_quotation(db: Session, qt: Quotation, data: QuotationUpdateIn, actor: User) -> Quotation:
    if qt.status != QS.DRAFT:
        raise AppError("Only draft quotations can be edited", 409)
    changes = data.model_dump(exclude_unset=True, exclude={"lines"})
    if "plan_id" in changes and changes["plan_id"]:
        subs.require_available(subs.get_plan(db, changes["plan_id"]))
    for k in ("plan_id", "discount_id", "notes", "payment_terms_days"):
        if k in changes and (changes[k] is not None or k in ("discount_id", "notes")):
            setattr(qt, k, changes[k])
    if data.validity_days:
        qt.expiry_date = qt.issue_date + timedelta(days=data.validity_days)
    plan = subs.get_plan(db, qt.plan_id)
    lines = subs.resolve_lines(db, plan, data.lines) if data.lines is not None else subs.resolve_lines(
        db, plan, [LineIn(product_id=l.product_id, variant_ids=[v["id"] for v in l.variants] or ([l.variant_id] if l.variant_id else []), quantity=l.quantity, unit_price=l.unit_price, description=l.description) for l in qt.lines])
    _compute(db, qt, lines)
    record_audit(db, actor, "QUOTATION_UPDATED", "quotation", qt.id, f"Updated {qt.number}", {"total": str(qt.total)})
    return qt


def send(db: Session, qt: Quotation, actor: User) -> None:
    if qt.status != QS.DRAFT:
        raise AppError("Only draft quotations can be sent", 409)
    if not qt.lines:
        raise AppError("A quotation needs at least one line", 422)
    qt.status, qt.sent_at = QS.QUOTATION, datetime.now(UTC)
    c = db.get(CustomerProfile, qt.customer_id)
    queue_email(db, c.email, "quotation_sent", {"name": c.full_name, "number": qt.number, "currency": "INR", "total": str(qt.total), "expiry_date": qt.expiry_date.isoformat()}, "quotation", qt.id)
    record_audit(db, actor, "QUOTATION_SENT", "quotation", qt.id, f"{qt.number} sent to customer")


def confirm(db: Session, qt: Quotation, actor: User) -> None:
    if qt.status != QS.QUOTATION:
        raise AppError("Only a sent quotation can be confirmed", 409)
    if qt.expiry_date < date.today():
        raise AppError(f"Quotation {qt.number} expired on {qt.expiry_date.isoformat()} and cannot be confirmed", 409)
    qt.status, qt.confirmed_at = QS.CONFIRMED, datetime.now(UTC)
    record_audit(db, actor, "QUOTATION_CONFIRMED", "quotation", qt.id, f"{qt.number} confirmed")


def convert(db: Session, qt: Quotation, body: ConvertIn, actor: User):
    """Caller holds a row lock on the quotation. At most one subscription per quotation (also enforced by a unique FK)."""
    if qt.status != QS.CONFIRMED:
        raise AppError("Only confirmed quotations can be converted", 409)
    if qt.expiry_date < date.today():
        raise AppError(f"Quotation {qt.number} has expired", 409)
    from app.modules.subscriptions.models import Subscription
    if db.scalar(select(Subscription.id).where(Subscription.quotation_id == qt.id)):
        raise AppError("This quotation was already converted to a subscription", 409)
    lines = [dict(product_id=l.product_id, variant_id=l.variant_id, variants=l.variants, taxes=l.taxes, quantity=l.quantity, unit_price=l.unit_price,
                  description=l.description, tax_id=l.tax_id, tax_rate=l.tax_rate) for l in qt.lines]  # negotiated pricing preserved as quoted
    data = SubscriptionIn(customer_id=qt.customer_id, plan_id=qt.plan_id, start_date=body.start_date or date.today(), term_periods=body.term_periods,
                          payment_terms_days=qt.payment_terms_days, auto_renew=body.auto_renew, notes=qt.notes)
    try:
        sub = subs.create_subscription(db, data, actor, quotation_id=qt.id, lines=lines, status=SubscriptionStatus.CONFIRMED)
    except IntegrityError:
        raise AppError("This quotation was already converted to a subscription", 409)
    if qt.discount_id:
        db.add(DiscountSubscription(discount_id=qt.discount_id, subscription_id=sub.id))
    subs.add_event(db, sub, "CONVERTED", detail=f"Converted from quotation {qt.number}", actor=actor)
    record_audit(db, actor, "QUOTATION_CONVERTED", "quotation", qt.id, f"{qt.number} converted to {sub.number}")
    return sub
