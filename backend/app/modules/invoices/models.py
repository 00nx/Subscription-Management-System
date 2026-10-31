import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import InvoiceStatus
from app.models.base import JSONType, Timestamps, UTCDateTime, UUIDPrimaryKey, enum_col


class Invoice(UUIDPrimaryKey, Timestamps, Base):
    """All amounts and customer details are snapshots: later product/tax/discount/customer edits never alter an issued invoice."""

    __tablename__ = "invoices"
    __table_args__ = (
        # Duplicate-billing guard: one invoice per subscription per billing period (NULL period = manual invoice, exempt).
        UniqueConstraint("subscription_id", "period_start", name="uq_invoice_subscription_period"),
        CheckConstraint("total >= 0 AND amount_paid >= 0", name="ck_invoices_amounts"),
        Index("ix_invoices_status_due", "status", "due_date"),
        Index("ix_invoices_customer_status", "customer_id", "status"),
    )

    number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True)
    subscription_number: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[InvoiceStatus] = mapped_column(enum_col(InvoiceStatus), default=InvoiceStatus.DRAFT)
    source: Mapped[str] = mapped_column(String(10), default="MANUAL")  # AUTO (billing engine) | MANUAL
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    customer_snapshot: Mapped[dict] = mapped_column(JSONType, default=dict)
    tax_breakdown: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # [{name, rate, base, amount}] aggregated over lines
    discount_breakdown: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # [{name, amount}] discounts applied
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reminder_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    overdue_notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # manual 'send reminder' actions
    last_reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", lazy="selectin",
                                                      order_by="InvoiceLine.position")

    @property
    def outstanding(self) -> Decimal:
        return Decimal("0.00") if self.status == InvoiceStatus.CANCELLED else self.total - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return (self.status in (InvoiceStatus.CONFIRMED, InvoiceStatus.PARTIALLY_PAID)
                and self.outstanding > 0 and self.due_date < date.today())


class InvoiceLine(UUIDPrimaryKey, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    variants: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # snapshot of the selected variants
    taxes: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # [{name, rate, amount}] snapshot
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
