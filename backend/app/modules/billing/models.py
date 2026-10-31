import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import RecordStatus
from app.models.base import JSONType, Timestamps, UTCDateTime, UUIDPrimaryKey, enum_col


class Tax(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "taxes"
    __table_args__ = (CheckConstraint("rate >= 0 AND rate <= 100", name="ck_taxes_rate_range"),)

    name: Mapped[str] = mapped_column(String(100), unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # percent, e.g. 18.00
    tax_type: Mapped[str] = mapped_column(String(20), default="PERCENTAGE")
    description: Mapped[str | None] = mapped_column(Text)
    applies_to: Mapped[str] = mapped_column(String(20), default="PRODUCTS", server_default="PRODUCTS")  # PRODUCTS = only products that select it; ALL = every line
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)


class BillingRun(UUIDPrimaryKey, Base):
    """One execution of the billing engine (scheduled or manual): what was examined, created, recovered and what failed."""

    __tablename__ = "billing_runs"

    trigger: Mapped[str] = mapped_column(String(20), default="SCHEDULED")  # SCHEDULED | MANUAL
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    run_date: Mapped[date] = mapped_column(Date)  # the "today" the run billed against
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", index=True)  # RUNNING | COMPLETED | COMPLETED_WITH_ERRORS | FAILED
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    batches: Mapped[int] = mapped_column(Integer, default=0)
    examined: Mapped[int] = mapped_column(Integer, default=0)  # due subscriptions looked at
    invoiced: Mapped[int] = mapped_column(Integer, default=0)
    recovered: Mapped[int] = mapped_column(Integer, default=0)  # invoices for periods that were missed (catch-up)
    skipped_locked: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    renewed: Mapped[int] = mapped_column(Integer, default=0)
    expired: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # first 50: {subscription_id, error}
