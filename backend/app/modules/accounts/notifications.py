from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import Notification, User, UserRole

# Notification type names used across modules
SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED"
SUBSCRIPTION_RENEWED = "SUBSCRIPTION_RENEWED"
SUBSCRIPTION_PAUSED = "SUBSCRIPTION_PAUSED"
SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
INVOICE_GENERATED = "INVOICE_GENERATED"
INVOICE_DUE = "INVOICE_DUE"
INVOICE_OVERDUE = "INVOICE_OVERDUE"
PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
PAYMENT_FAILED = "PAYMENT_FAILED"
DISCOUNT_EXPIRING = "DISCOUNT_EXPIRING"
REQUEST_SUBMITTED = "REQUEST_SUBMITTED"


def notify(db: Session, user_id, type: str, title: str, message: str = "", entity_type: str | None = None, entity_id=None) -> None:
    """Adds a notification to the caller's transaction."""
    db.add(Notification(user_id=user_id, type=type, title=title, message=message,
                        entity_type=entity_type, entity_id=str(entity_id) if entity_id else None))


def notify_staff(db: Session, type: str, title: str, message: str = "", entity_type: str | None = None, entity_id=None) -> None:
    for uid in db.scalars(select(User.id).where(User.role.in_([UserRole.ADMIN, UserRole.STAFF]), User.is_active.is_(True))):
        notify(db, uid, type, title, message, entity_type, entity_id)
