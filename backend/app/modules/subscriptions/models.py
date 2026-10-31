import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import BillingFrequency, RecordStatus, SubscriptionStatus
from app.models.base import JSONType, Timestamps, UTCDateTime, UUIDPrimaryKey, enum_col


class SubscriptionPlan(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_plans_price"), CheckConstraint("min_quantity >= 1", name="ck_plans_min_qty"))

    name: Mapped[str] = mapped_column(String(150), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    billing_frequency: Mapped[BillingFrequency] = mapped_column(enum_col(BillingFrequency))
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    available_from: Mapped[date | None] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    auto_close: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_early_closure: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_pause: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_renewal: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)

    extra_products: Mapped[list["PlanProduct"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    product = relationship("Product", lazy="joined")

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def variants(self) -> list:
        """Active variants of the plan's own product: what a customer may add when subscribing."""
        return [v for v in self.product.variants if v.status == RecordStatus.ACTIVE]

    @property
    def extra_product_ids(self) -> list[uuid.UUID]:
        return [p.product_id for p in self.extra_products]

    @property
    def is_available(self) -> bool:
        """Open for new subscriptions today: ACTIVE and inside its availability window."""
        today = date.today()
        return (self.status == RecordStatus.ACTIVE and (self.available_from is None or self.available_from <= today)
                and (self.available_until is None or today <= self.available_until))


class PlanProduct(UUIDPrimaryKey, Base):
    """Additional products a plan allows on its subscriptions (the plan's own `product_id` is always allowed)."""

    __tablename__ = "plan_products"
    __table_args__ = (UniqueConstraint("plan_id", "product_id", name="uq_plan_product"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)


class Subscription(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscriptions_billing_due", "status", "next_billing_date"),
                      Index("ix_subscriptions_customer_status", "customer_id", "status"))

    number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="RESTRICT"), index=True)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id", ondelete="SET NULL"), unique=True)
    status: Mapped[SubscriptionStatus] = mapped_column(enum_col(SubscriptionStatus), default=SubscriptionStatus.DRAFT)
    start_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    next_billing_date: Mapped[date | None] = mapped_column(Date)
    billing_frequency: Mapped[BillingFrequency] = mapped_column(enum_col(BillingFrequency))  # snapshot of the plan's
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0)
    term_periods: Mapped[int | None] = mapped_column(Integer)  # length of one term, in billing periods (None = open-ended)
    periods_billed: Mapped[int] = mapped_column(Integer, default=0)
    renewal_count: Mapped[int] = mapped_column(Integer, default=0)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))  # per billing period, before discount rules
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    plan: Mapped[SubscriptionPlan] = relationship(lazy="joined")
    customer = relationship("CustomerProfile", lazy="joined")
    lines: Mapped[list["SubscriptionLine"]] = relationship(back_populates="subscription", cascade="all, delete-orphan", lazy="selectin",
                                                           order_by="SubscriptionLine.created_at")

    @property
    def customer_name(self) -> str:
        return self.customer.full_name

    @property
    def plan_name(self) -> str:
        return self.plan.name

    # plan permissions, exposed so UIs only offer what the backend will accept
    @property
    def allow_pause(self) -> bool:
        return self.plan.allow_pause

    @property
    def allow_renewal(self) -> bool:
        return self.plan.allow_renewal

    @property
    def allow_early_closure(self) -> bool:
        return self.plan.allow_early_closure

    @property
    def renewal_opens(self) -> date | None:
        """First day a manual renewal is accepted (last billing period of the current term); None if not renewable."""
        if not (self.plan.allow_renewal and self.term_periods and self.expiry_date):
            return None
        from app.modules.subscriptions.periods import period_start
        return period_start(self.start_date, self.billing_frequency, self.term_periods * (self.renewal_count + 1) - 1)


class SubscriptionLine(UUIDPrimaryKey, Base):
    __tablename__ = "subscription_lines"
    __table_args__ = (CheckConstraint("quantity >= 1 AND unit_price >= 0", name="ck_sub_lines_values"),)

    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # agreed price, immune to later product/plan edits
    tax_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))  # snapshot at line creation: sum of `taxes`
    variants: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # [{id, name, attribute, value, additional_price}] snapshot
    taxes: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # [{id, name, rate}] snapshot
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    subscription: Mapped[Subscription] = relationship(back_populates="lines")

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class SubscriptionEvent(UUIDPrimaryKey, Base):
    """History of status changes and billing events for a subscription."""

    __tablename__ = "subscription_events"
    __table_args__ = (Index("ix_sub_events_sub_created", "subscription_id", "created_at"),)

    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    detail: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class SubscriptionRequest(UUIDPrimaryKey, Base):
    """Customer asks for cancel / pause / resume; staff approve or reject."""

    __tablename__ = "subscription_requests"

    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_profiles.id", ondelete="CASCADE"), index=True)
    request_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    subscription: Mapped[Subscription] = relationship(lazy="joined")

    @property
    def subscription_number(self) -> str:
        return self.subscription.number
