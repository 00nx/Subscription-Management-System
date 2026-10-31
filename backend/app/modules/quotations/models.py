import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import QuotationStatus, RecordStatus
from app.models.base import JSONType, Timestamps, UTCDateTime, UUIDPrimaryKey, enum_col


class QuotationTemplate(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "quotation_templates"

    name: Mapped[str] = mapped_column(String(150), unique=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscription_plans.id", ondelete="SET NULL"))
    validity_days: Mapped[int] = mapped_column(Integer, default=30)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    terms: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)
    discount_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("discounts.id", ondelete="SET NULL"))  # default for quotations made from this template

    lines: Mapped[list["QuotationTemplateLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class QuotationTemplateLine(UUIDPrimaryKey, Base):
    __tablename__ = "quotation_template_lines"

    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotation_templates.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"))
    variant_ids: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # all selected variants (variant_id mirrors the first)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # None = price from product/plan when used


class Quotation(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "quotations"

    number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotation_templates.id", ondelete="SET NULL"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="RESTRICT"))
    discount_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("discounts.id", ondelete="SET NULL"))
    status: Mapped[QuotationStatus] = mapped_column(enum_col(QuotationStatus), default=QuotationStatus.DRAFT, index=True)
    issue_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    customer = relationship("CustomerProfile", lazy="joined")
    lines: Mapped[list["QuotationLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="QuotationLine.created_at")

    subscription = relationship("Subscription", foreign_keys="Subscription.quotation_id", uselist=False, viewonly=True, lazy="selectin")

    @property
    def customer_name(self) -> str:
        return self.customer.full_name

    @property
    def is_expired(self) -> bool:
        return self.expiry_date < date.today()

    @property
    def subscription_id(self):
        return self.subscription.id if self.subscription else None


class QuotationLine(UUIDPrimaryKey, Base):
    __tablename__ = "quotation_lines"
    __table_args__ = (CheckConstraint("quantity >= 1 AND unit_price >= 0", name="ck_quote_lines_values"),)

    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    variants: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    taxes: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
