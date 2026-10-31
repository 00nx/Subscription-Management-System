from sqlalchemy.orm import Session

from app.modules.analytics.models import AuditLog


def record_audit(db: Session, actor, action: str, entity_type: str, entity_id, summary: str = "", changes: dict | None = None) -> None:
    """Adds an audit row to the caller's transaction (so it commits or rolls back with the change). `actor` may be None (system/Celery)."""
    db.add(AuditLog(user_id=getattr(actor, "id", None), action=action, entity_type=entity_type,
                    entity_id=str(entity_id), summary="", changes=changes))
