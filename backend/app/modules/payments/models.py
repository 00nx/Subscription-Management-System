import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import PaymentMethod, PaymentStatus
from app.models.base import JSONType, Timestamps, UTCDateTime, UUIDPrimaryKey, enum_col


class Payment(UUIDPrimaryKey, Timestamps, Base):
    """Only SUCCESS payments count as money received. Card numbers/CVVs are never stored."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payments_amount"),
                      Index("ix_payments_status_date", "status", "payment_date"))

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(enum_col(PaymentMethod))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[PaymentStatus] = mapped_column(enum_col(PaymentStatus), default=PaymentStatus.PENDING)
    payment_date: Mapped[datetime | None] = mapped_column(UTCDateTime())  # set when the payment succeeds
    transaction_reference: Mapped[str | None] = mapped_column(String(100), unique=True)
    notes: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(30), default="MANUAL")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    invoice = relationship("Invoice", lazy="joined")
    transactions: Mapped[list["PaymentTransaction"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                                    order_by="PaymentTransaction.created_at")

    @property
    def invoice_number(self) -> str:
        return self.invoice.number


class PaymentTransaction(UUIDPrimaryKey, Base):
    """Provider interaction log for a payment (no sensitive credentials)."""

    __tablename__ = "payment_transactions"

    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    event: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
