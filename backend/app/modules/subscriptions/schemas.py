import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import BillingFrequency, RecordStatus, SubscriptionStatus
from app.schemas.common import Money


class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    product_id: uuid.UUID
    price: Money
    billing_frequency: BillingFrequency
    min_quantity: int = Field(default=1, ge=1)
    available_from: date | None = None
    available_until: date | None = None
    auto_close: bool = True
    allow_early_closure: bool = True
    allow_pause: bool = True
    allow_renewal: bool = True
    status: RecordStatus = RecordStatus.ACTIVE
    extra_product_ids: list[uuid.UUID] = []


class PlanUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    product_id: uuid.UUID | None = None
    price: Money | None = None
    billing_frequency: BillingFrequency | None = None
    min_quantity: int | None = Field(default=None, ge=1)
    available_from: date | None = None
    available_until: date | None = None
    auto_close: bool | None = None
    allow_early_closure: bool | None = None
    allow_pause: bool | None = None
    allow_renewal: bool | None = None
    status: RecordStatus | None = None
    extra_product_ids: list[uuid.UUID] | None = None


class PlanVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    attribute_name: str
    attribute_value: str
    additional_price: Decimal


class PublicPlanOut(BaseModel):
    """What a visitor who is not logged in may see."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    billing_frequency: BillingFrequency
    min_quantity: int
    available_until: date | None
    product_name: str


class SubscribeIn(BaseModel):
    plan_id: uuid.UUID
    quantity: int | None = Field(default=None, ge=1, le=100000)  # defaults to the plan's minimum
    variant_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    term_periods: int | None = Field(default=None, ge=1, le=1200)
    auto_renew: bool = False
    start_date: date | None = None  # today or later


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    product_id: uuid.UUID
    price: Decimal
    billing_frequency: BillingFrequency
    min_quantity: int
    available_from: date | None
    available_until: date | None
    auto_close: bool
    allow_early_closure: bool
    allow_pause: bool
    allow_renewal: bool
    status: RecordStatus
    extra_product_ids: list[uuid.UUID]
    is_available: bool
    product_name: str
    variants: list[PlanVariantOut] = []
    created_at: datetime


class LineIn(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None  # single-variant shorthand; merged into variant_ids
    variant_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    quantity: int = Field(default=1, ge=1, le=100000)
    unit_price: Money | None = None  # negotiated price; defaults to plan/product price
    description: str | None = Field(default=None, max_length=255)

    @property
    def all_variant_ids(self) -> list[uuid.UUID]:
        return list(dict.fromkeys([*([self.variant_id] if self.variant_id else []), *self.variant_ids]))


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    description: str
    quantity: int
    unit_price: Decimal
    tax_id: uuid.UUID | None
    tax_rate: Decimal
    variants: list[dict] = []
    taxes: list[dict] = []
    line_total: Decimal


class SubscriptionIn(BaseModel):
    customer_id: uuid.UUID
    plan_id: uuid.UUID
    start_date: date
    term_periods: int | None = Field(default=None, ge=1, le=1200)
    payment_terms_days: int = Field(default=0, ge=0, le=365)
    auto_renew: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineIn] = []


class SubscriptionUpdateIn(BaseModel):
    start_date: date | None = None
    term_periods: int | None = Field(default=None, ge=1, le=1200)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    auto_renew: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineIn] | None = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    customer_name: str
    plan_id: uuid.UUID
    plan_name: str
    quotation_id: uuid.UUID | None
    status: SubscriptionStatus
    start_date: date
    expiry_date: date | None
    next_billing_date: date | None
    billing_frequency: BillingFrequency
    payment_terms_days: int
    term_periods: int | None
    periods_billed: int
    renewal_count: int
    auto_renew: bool
    notes: str | None
    allow_pause: bool
    allow_renewal: bool
    allow_early_closure: bool
    renewal_opens: date | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    lines: list[LineOut]
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    detail: str | None
    actor_user_id: uuid.UUID | None
    created_at: datetime


class RequestIn(BaseModel):
    request_type: str = Field(pattern="^(CANCEL|PAUSE|RESUME)$")
    reason: str | None = Field(default=None, max_length=1000)


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_number: str
    customer_id: uuid.UUID
    request_type: str
    status: str
    reason: str | None
    created_at: datetime
    decided_at: datetime | None


class SubscribeOut(BaseModel):
    subscription: SubscriptionOut
    invoice_id: uuid.UUID | None  # the first invoice, confirmed and ready to pay (None when the start date is in the future)
