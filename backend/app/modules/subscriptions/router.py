import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.enums import BillingFrequency, RecordStatus, SubscriptionStatus
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.core.ratelimit import rate_limit_refresh
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.customers.models import CustomerProfile
from app.modules.customers.service import scope_customer_id
from app.modules.products import service as products
from app.modules.subscriptions import service
from app.modules.subscriptions.models import Subscription, SubscriptionEvent, SubscriptionPlan, SubscriptionRequest
from app.modules.subscriptions.schemas import (EventOut, PlanIn, PlanOut, PlanUpdateIn, PublicPlanOut, RequestIn, RequestOut, SubscribeIn, SubscribeOut,
                                               SubscriptionIn, SubscriptionOut, SubscriptionUpdateIn)
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

plans_router = APIRouter(prefix="/plans", tags=["plans"])
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
requests_router = APIRouter(prefix="/subscription-requests", tags=["subscriptions"])
public_router = APIRouter(prefix="/public", tags=["public"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
_admin = require_roles(UserRole.ADMIN)


# ---------------- plans ----------------
@plans_router.get("/", response_model=ApiResponse[Page[PlanOut]], responses=_errors)
def list_plans(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), status: RecordStatus | None = None,
               billing_frequency: BillingFrequency | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Staff see every plan; customers only see plans currently open for subscription."""
    stmt = select(SubscriptionPlan)
    if user.role == UserRole.CUSTOMER:
        from datetime import date
        today = date.today()
        stmt = stmt.where(SubscriptionPlan.status == RecordStatus.ACTIVE,
                          or_(SubscriptionPlan.available_from.is_(None), SubscriptionPlan.available_from <= today),
                          or_(SubscriptionPlan.available_until.is_(None), SubscriptionPlan.available_until >= today))
    elif status:
        stmt = stmt.where(SubscriptionPlan.status == status)
    if q:
        stmt = stmt.where(func.lower(SubscriptionPlan.name).like(f"%{q.lower()}%"))
    if billing_frequency:
        stmt = stmt.where(SubscriptionPlan.billing_frequency == billing_frequency)
    return ApiResponse(data=paginate(db, stmt, page, PlanOut, {"name": SubscriptionPlan.name, "price": SubscriptionPlan.price, "created_at": SubscriptionPlan.created_at}, "name"))


def _open_plans():
    today = date.today()
    return (SubscriptionPlan.status == RecordStatus.ACTIVE, or_(SubscriptionPlan.available_from.is_(None), SubscriptionPlan.available_from <= today),
            or_(SubscriptionPlan.available_until.is_(None), SubscriptionPlan.available_until >= today))


@public_router.get("/plans/", response_model=ApiResponse[list[PublicPlanOut]], dependencies=[Depends(rate_limit_refresh)])
def public_plans(db: Session = Depends(get_db)):
    """The plans open for subscription, for visitors who have not signed up yet (no login needed; no variants, costs or internal fields)."""
    rows = db.scalars(select(SubscriptionPlan).where(*_open_plans()).order_by(SubscriptionPlan.name).limit(100)).unique().all()
    return ApiResponse(data=[PublicPlanOut.model_validate(r) for r in rows])


@plans_router.post("/", status_code=201, response_model=ApiResponse[PlanOut], responses=_errors)
def create_plan(body: PlanIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    products.get_product(db, body.product_id)
    if body.available_from and body.available_until and body.available_until < body.available_from:
        raise AppError("Available-until must not be before available-from", 422)
    plan = SubscriptionPlan(**body.model_dump(exclude={"extra_product_ids"}))
    db.add(plan)
    db.flush()
    service.set_extra_products(db, plan, body.extra_product_ids)
    record_audit(db, admin, "PLAN_CREATED", "plan", plan.id, f"Created plan {plan.name}", {"price": str(plan.price), "frequency": plan.billing_frequency.value})
    db.commit()
    return ApiResponse(message="Plan created", data=PlanOut.model_validate(plan))


@plans_router.get("/{plan_id}/", response_model=ApiResponse[PlanOut], responses=_errors)
def get_plan(plan_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = service.get_plan(db, plan_id)
    if user.role == UserRole.CUSTOMER and not plan.is_available:
        raise AppError("Plan not found", 404)
    return ApiResponse(data=PlanOut.model_validate(plan))


@plans_router.patch("/{plan_id}/", response_model=ApiResponse[PlanOut], responses=_errors)
def update_plan(plan_id: uuid.UUID, body: PlanUpdateIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    """Existing subscriptions keep the lines (price, tax) and frequency they were created with; edits only affect new ones."""
    plan = service.get_plan(db, plan_id)
    changes = body.model_dump(exclude_unset=True, exclude={"extra_product_ids"})
    if "product_id" in changes:
        products.get_product(db, changes["product_id"])
    old = {k: str(getattr(plan, k)) for k in changes}
    for k, v in changes.items():
        setattr(plan, k, v)
    if plan.available_from and plan.available_until and plan.available_until < plan.available_from:
        raise AppError("Available-until must not be before available-from", 422)
    if body.extra_product_ids is not None:
        service.set_extra_products(db, plan, body.extra_product_ids)
    record_audit(db, admin, "PLAN_UPDATED", "plan", plan.id, f"Updated plan {plan.name}", {k: {"from": old[k], "to": str(v)} for k, v in changes.items()})
    db.commit()
    return ApiResponse(message="Plan updated", data=PlanOut.model_validate(plan))


# ---------------- subscriptions ----------------
_SORTS = {"created_at": Subscription.created_at, "start_date": Subscription.start_date, "next_billing_date": Subscription.next_billing_date,
          "number": Subscription.number, "total": Subscription.total, "expiry_date": Subscription.expiry_date}


@router.get("/", response_model=ApiResponse[Page[SubscriptionOut]], responses=_errors)
def list_subscriptions(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), status: SubscriptionStatus | None = None,
                       plan_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None, billing_frequency: BillingFrequency | None = None,
                       start_from: date | None = None, start_to: date | None = None, expiry_from: date | None = None, expiry_to: date | None = None,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Subscription)
    scope = scope_customer_id(db, user)
    if scope is not None:  # customers: own subscriptions only, never drafts/quotations; client-supplied customer_id is ignored
        stmt = stmt.where(Subscription.customer_id == scope, Subscription.status.notin_([SubscriptionStatus.DRAFT, SubscriptionStatus.QUOTATION]))
    elif customer_id:
        stmt = stmt.where(Subscription.customer_id == customer_id)
    if q:
        like = f"%{q.lower()}%"  # number, or the customer's name / email / company
        stmt = stmt.where(or_(func.lower(Subscription.number).like(like), Subscription.customer_id.in_(
            select(CustomerProfile.id).join(User, User.id == CustomerProfile.user_id).where(or_(
                func.lower(User.full_name).like(like), func.lower(User.email).like(like), func.lower(func.coalesce(CustomerProfile.company_name, "")).like(like))))))
    for col, lo, hi in ((Subscription.start_date, start_from, start_to), (Subscription.expiry_date, expiry_from, expiry_to)):
        if lo:
            stmt = stmt.where(col >= lo)
        if hi:
            stmt = stmt.where(col <= hi)
    if status:
        stmt = stmt.where(Subscription.status == status)
    if plan_id:
        stmt = stmt.where(Subscription.plan_id == plan_id)
    if billing_frequency:
        stmt = stmt.where(Subscription.billing_frequency == billing_frequency)
    return ApiResponse(data=paginate(db, stmt, page, SubscriptionOut, _SORTS, "-created_at"))


@router.post("/", status_code=201, response_model=ApiResponse[SubscriptionOut], responses=_errors)
def create_subscription(body: SubscriptionIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    sub = service.create_subscription(db, body, actor)
    db.commit()
    return ApiResponse(message="Subscription created", data=SubscriptionOut.model_validate(sub))


@router.post("/subscribe/", status_code=201, response_model=ApiResponse[SubscribeOut], responses=_errors)
def subscribe(body: SubscribeIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.CUSTOMER))):
    """Customer self-service: subscribe to an open plan. Confirmed and activated at once; the first invoice (if it starts today) comes back ready to pay."""
    sub, invoice = service.subscribe_to_plan(db, user, body)
    db.commit()
    return ApiResponse(message="You are subscribed", data=SubscribeOut(subscription=SubscriptionOut.model_validate(sub), invoice_id=invoice.id if invoice else None))


@router.get("/{sub_id}/", response_model=ApiResponse[SubscriptionOut], responses=_errors)
def get_subscription(sub_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ApiResponse(data=SubscriptionOut.model_validate(service.get_subscription(db, user, sub_id)))


@router.patch("/{sub_id}/", response_model=ApiResponse[SubscriptionOut], responses=_errors)
def update_subscription(sub_id: uuid.UUID, body: SubscriptionUpdateIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    sub = service.get_subscription(db, actor, sub_id, lock=True)
    service.update_subscription(db, sub, body, actor)
    db.commit()
    return ApiResponse(message="Subscription updated", data=SubscriptionOut.model_validate(sub))


@router.get("/{sub_id}/events/", response_model=ApiResponse[list[EventOut]], responses=_errors)
def subscription_events(sub_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(_staff)):
    """Subscription history: status changes, renewals and billing events."""
    sub = service.get_subscription(db, user, sub_id)
    events = db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.subscription_id == sub.id).order_by(SubscriptionEvent.created_at)).all()
    return ApiResponse(data=[EventOut.model_validate(e) for e in events])


_DONE = {"confirm": "confirmed", "activate": "activated", "pause": "paused", "resume": "resumed", "renew": "renewed", "cancel": "closed"}


_SELF_SERVICE = {"pause", "resume", "renew", "cancel"}  # customers act on their own subscription directly; plan flags still apply


def _action(name: str, fn):
    @router.post(f"/{{sub_id}}/{name}/", response_model=ApiResponse[SubscriptionOut], responses=_errors, name=f"{name}_subscription",
                 summary=f"{name.title()} a subscription")
    def endpoint(sub_id: uuid.UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
        if actor.role == UserRole.CUSTOMER and name not in _SELF_SERVICE:
            raise AppError("Insufficient permissions", 403)
        sub = service.get_subscription(db, actor, sub_id, lock=True)  # row lock: concurrent actions serialise
        fn(db, sub, actor)
        db.commit()
        return ApiResponse(message=f"Subscription {_DONE[name]}", data=SubscriptionOut.model_validate(sub))

    return endpoint


_action("confirm", service.confirm)
_action("activate", service.activate)
_action("pause", service.pause)
_action("resume", service.resume)
_action("renew", service.renew)
_action("cancel", service.cancel)


@router.post("/{sub_id}/requests/", status_code=201, response_model=ApiResponse[RequestOut], responses=_errors)
def request_change(sub_id: uuid.UUID, body: RequestIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.CUSTOMER))):
    """Customers cannot change status directly; they ask, and staff approve or reject."""
    sub = service.get_subscription(db, user, sub_id)
    req = service.create_request(db, user, sub, body.request_type, body.reason)
    db.commit()
    return ApiResponse(message="Request submitted", data=RequestOut.model_validate(req))


# ---------------- requests ----------------
@requests_router.get("/", response_model=ApiResponse[Page[RequestOut]], responses=_errors)
def list_requests(page: PageParams = Depends(), status: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(SubscriptionRequest)
    scope = scope_customer_id(db, user)
    if scope is not None:
        stmt = stmt.where(SubscriptionRequest.customer_id == scope)
    if status:
        stmt = stmt.where(SubscriptionRequest.status == status)
    return ApiResponse(data=paginate(db, stmt, page, RequestOut, {"created_at": SubscriptionRequest.created_at}, "-created_at"))


def _decide(req_id: uuid.UUID, approve: bool, db: Session, actor: User):
    req = db.get(SubscriptionRequest, req_id)
    if not req:
        raise AppError("Request not found", 404)
    service.decide_request(db, req, approve, actor)
    db.commit()
    return ApiResponse(message="Request approved" if approve else "Request rejected", data=RequestOut.model_validate(req))


@requests_router.post("/{req_id}/approve/", response_model=ApiResponse[RequestOut], responses=_errors)
def approve_request(req_id: uuid.UUID, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    return _decide(req_id, True, db, actor)


@requests_router.post("/{req_id}/reject/", response_model=ApiResponse[RequestOut], responses=_errors)
def reject_request(req_id: uuid.UUID, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    return _decide(req_id, False, db, actor)
