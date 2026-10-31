import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.discounts.models import Discount, DiscountProduct, DiscountSubscription, DiscountUsage
from app.modules.discounts.schemas import DiscountIn, DiscountOut, DiscountUpdateIn, DiscountUsageOut
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/discounts", tags=["discounts"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
_admin = require_roles(UserRole.ADMIN)


def _discount_writer(user: User = Depends(get_current_user)) -> User:
    """Administrators always; staff only when an administrator explicitly granted can_manage_discounts."""
    if user.role == UserRole.ADMIN or (user.role == UserRole.STAFF and user.can_manage_discounts):
        return user
    raise AppError("Insufficient permissions", 403)
_SORTS = {"name": Discount.name, "created_at": Discount.created_at, "end_date": Discount.end_date, "usage_count": Discount.usage_count}


def _get(db: Session, discount_id: uuid.UUID) -> Discount:
    d = db.get(Discount, discount_id)
    if not d:
        raise AppError("Discount not found", 404)
    return d


def _set_links(db: Session, d: Discount, product_ids, subscription_ids) -> None:
    from app.modules.products.models import Product
    from app.modules.subscriptions.models import Subscription

    if product_ids is not None:
        if len(set(product_ids)) != db.scalar(select(func.count()).select_from(Product).where(Product.id.in_(product_ids))):
            raise AppError("Unknown product in product_ids", 400)
        d.product_links = [DiscountProduct(product_id=p) for p in dict.fromkeys(product_ids)]
    if subscription_ids is not None:
        if len(set(subscription_ids)) != db.scalar(select(func.count()).select_from(Subscription).where(Subscription.id.in_(subscription_ids))):
            raise AppError("Unknown subscription in subscription_ids", 400)
        d.subscription_links = [DiscountSubscription(subscription_id=s) for s in dict.fromkeys(subscription_ids)]


@router.get("/", response_model=ApiResponse[Page[DiscountOut]], responses=_errors)
def list_discounts(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), is_active: bool | None = None,
                   db: Session = Depends(get_db), _: User = Depends(_staff)):
    stmt = select(Discount)
    if q:
        stmt = stmt.where(func.lower(Discount.name).like(f"%{q.lower()}%"))
    if is_active is not None:
        stmt = stmt.where(Discount.is_active == is_active)
    return ApiResponse(data=paginate(db, stmt, page, DiscountOut, _SORTS, "-created_at"))


@router.post("/", status_code=201, response_model=ApiResponse[DiscountOut], responses=_errors)
def create_discount(body: DiscountIn, db: Session = Depends(get_db), admin: User = Depends(_discount_writer)):
    data = body.model_dump(exclude={"product_ids", "subscription_ids"})
    d = Discount(**data)
    db.add(d)
    _set_links(db, d, body.product_ids, body.subscription_ids)
    try:
        db.flush()
    except IntegrityError:
        raise AppError("A discount with this name already exists", 409)
    record_audit(db, admin, "DISCOUNT_CREATED", "discount", d.id, f"Created discount {d.name}", {"type": d.discount_type.value, "value": str(d.value)})
    db.commit()
    return ApiResponse(message="Discount created", data=DiscountOut.model_validate(d))


@router.get("/{discount_id}/", response_model=ApiResponse[DiscountOut], responses=_errors)
def get_discount(discount_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_staff)):
    return ApiResponse(data=DiscountOut.model_validate(_get(db, discount_id)))


@router.patch("/{discount_id}/", response_model=ApiResponse[DiscountOut], responses=_errors)
def update_discount(discount_id: uuid.UUID, body: DiscountUpdateIn, db: Session = Depends(get_db), admin: User = Depends(_discount_writer)):
    d = _get(db, discount_id)
    changes = body.model_dump(exclude_unset=True, exclude={"product_ids", "subscription_ids"})
    old = {k: str(getattr(d, k)) for k in changes}
    for k, v in changes.items():
        setattr(d, k, v)
    if d.discount_type.value == "PERCENTAGE" and d.value > 100:
        raise AppError("A percentage discount cannot exceed 100", 422)
    if d.end_date and d.start_date and d.end_date < d.start_date:
        raise AppError("End date must not be before the start date", 422)
    _set_links(db, d, body.product_ids, body.subscription_ids)
    record_audit(db, admin, "DISCOUNT_UPDATED", "discount", d.id, f"Updated discount {d.name}", {k: {"from": old[k], "to": str(v)} for k, v in changes.items()})
    try:
        db.commit()
    except IntegrityError:
        raise AppError("A discount with this name already exists or usage limit is below current usage", 409)
    return ApiResponse(message="Discount updated", data=DiscountOut.model_validate(d))


@router.get("/{discount_id}/usages/", response_model=ApiResponse[Page[DiscountUsageOut]], responses=_errors)
def list_usages(discount_id: uuid.UUID, page: PageParams = Depends(), db: Session = Depends(get_db), _: User = Depends(_staff)):
    _get(db, discount_id)
    stmt = select(DiscountUsage).where(DiscountUsage.discount_id == discount_id)
    return ApiResponse(data=paginate(db, stmt, page, DiscountUsageOut, {"created_at": DiscountUsage.created_at}, "-created_at"))
