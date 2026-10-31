import uuid
from datetime import datetime

from datetime import UTC

import uuid

from sqlalchemy import JSON, DateTime, TypeDecorator, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class UTCDateTime(TypeDecorator):
    """timestamptz on PostgreSQL. SQLite has no time zones, so store naive UTC and hand back aware UTC (same behaviour for the app)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and dialect.name == "sqlite" and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class GUID(TypeDecorator):
    """Native uuid on PostgreSQL; CHAR(32) on SQLite. Accepts str or UUID on the way in (JSON ids arrive as strings)."""

    impl = Uuid(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return uuid.UUID(value) if isinstance(value, str) else value


JSONType = JSON().with_variant(JSONB(), "postgresql")  # JSONB on PostgreSQL, JSON text on SQLite


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


def enum_col(cls):
    """Enum stored as a string (no native PG enum), so adding a value never needs ALTER TYPE."""
    from sqlalchemy import Enum

    return Enum(cls, native_enum=False, length=30, validate_strings=True)


def money_col(**kw):
    from decimal import Decimal

    from sqlalchemy import Numeric

    return mapped_column(Numeric(12, 2), default=Decimal("0.00"), **kw)
