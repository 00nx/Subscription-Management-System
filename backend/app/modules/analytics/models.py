import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import JSONType, UTCDateTime, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, Base):
    """Append-only. Never put passwords, tokens or payment credentials in `changes`."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[dict | None] = mapped_column(JSONType, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), index=True)
