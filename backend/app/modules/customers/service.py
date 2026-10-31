import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.accounts.models import User, UserRole
from app.modules.customers.models import CustomerProfile


def profile_for_user(db: Session, user: User) -> CustomerProfile:
    p = db.scalar(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
    if not p:
        raise AppError("Customer profile not found", 404)
    return p


def scope_customer_id(db: Session, user: User) -> uuid.UUID | None:
    """The customer id a request is confined to: the caller's own for CUSTOMER role, None (= unrestricted) for staff/admin.
    Every customer-visible list/detail must filter by this; the client never supplies it."""
    return profile_for_user(db, user).id if user.role == UserRole.CUSTOMER else None


def assert_owns(db: Session, user: User, customer_id: uuid.UUID) -> None:
    """404 (not 403) so customers can't probe which ids exist."""
    scope = scope_customer_id(db, user)
    if scope is not None and scope != customer_id:
        raise AppError("Not found", 404)
