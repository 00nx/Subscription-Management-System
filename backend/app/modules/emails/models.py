import uuid
from datetime import datetime

from sqlalchemy import Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UTCDateTime, UUIDPrimaryKey


class EmailLog(UUIDPrimaryKey, Base):
    """Every email the system sends: queued in the caller's transaction, delivered by a background task, outcome tracked here."""

    __tablename__ = "email_logs"
    __table_args__ = (Index("ix_email_logs_status_created", "status", "created_at"),)

    to_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    template: Mapped[str] = mapped_column(String(50), index=True)
    html: Mapped[str] = mapped_column(Text)
    text_body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="QUEUED")  # QUEUED | SENT | FAILED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
