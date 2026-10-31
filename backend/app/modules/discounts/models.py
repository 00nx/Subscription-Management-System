import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import DiscountType
from app.models.base import Timestamps, UTCDateTime, UUIDPrimaryKey, enum_col


class Discount(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "discounts"
    __table_args__ = (CheckConstraint("value > 0", name="ck_discounts_value"),
                      CheckConstraint("discount_type <> 'PERCENTAGE' OR value <= 100", name="ck_discounts_percent"),
                      CheckConstraint("max_usage IS NULL OR usage_count <= max_usage", name="ck_discounts_usage_limit"))

    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[DiscountType] = mapped_column(enum_col(DiscountType))
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    min_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    min_quantity: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    max_usage: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expiry_notified: Mapped[bool] = mapped_column(Boolean, default=False)

    product_links: Mapped[list["DiscountProduct"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    subscription_links: Mapped[list["DiscountSubscription"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    @property
    def product_ids(self) -> list[uuid.UUID]:
        return [l.product_id for l in self.product_links]

    @property
    def subscription_ids(self) -> list[uuid.UUID]:
        return [l.subscription_id for l in self.subscription_links]


class DiscountProduct(Base):
    __tablename__ = "discount_products"

    discount_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discounts.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True, index=True)


class DiscountSubscription(Base):
    __tablename__ = "discount_subscriptions"

    discount_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discounts.id", ondelete="CASCADE"), primary_key=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True, index=True)


class DiscountUsage(UUIDPrimaryKey, Base):
    """Audit trail of every application; one row per (discount, invoice)."""

    __tablename__ = "discount_usages"
    __table_args__ = (UniqueConstraint("discount_id", "invoice_id", name="uq_discount_usage_invoice"),)

    discount_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discounts.id", ondelete="RESTRICT"), index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
