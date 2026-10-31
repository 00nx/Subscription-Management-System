import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import QuotationStatus, RecordStatus
from app.modules.subscriptions.schemas import LineIn, LineOut
from app.schemas.common import Money


class TemplateLineIn(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    variant_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    quantity: int = Field(default=1, ge=1, le=100000)
    unit_price: Money | None = None


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    plan_id: uuid.UUID | None = None
    discount_id: uuid.UUID | None = None  # default discount for quotations made from this template
    validity_days: int = Field(default=30, ge=1, le=730)
    payment_terms_days: int = Field(default=0, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    terms: str | None = Field(default=None, max_length=4000)
    status: RecordStatus = RecordStatus.ACTIVE
    lines: list[TemplateLineIn] = []


class TemplateUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    plan_id: uuid.UUID | None = None
    discount_id: uuid.UUID | None = None
    validity_days: int | None = Field(default=None, ge=1, le=730)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    terms: str | None = Field(default=None, max_length=4000)
    status: RecordStatus | None = None
    lines: list[TemplateLineIn] | None = None


class TemplateLineOut(TemplateLineIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    unit_price: Decimal | None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    plan_id: uuid.UUID | None
    discount_id: uuid.UUID | None
    validity_days: int
    payment_terms_days: int
    notes: str | None
    terms: str | None
    status: RecordStatus
    lines: list[TemplateLineOut]
    created_at: datetime


class QuotationIn(BaseModel):
    customer_id: uuid.UUID
    template_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None  # required unless the template names one
    discount_id: uuid.UUID | None = None
    validity_days: int | None = Field(default=None, ge=1, le=730)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineIn] = []


class QuotationUpdateIn(BaseModel):
    plan_id: uuid.UUID | None = None
    discount_id: uuid.UUID | None = None
    validity_days: int | None = Field(default=None, ge=1, le=730)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineIn] | None = None


class QuotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    customer_name: str
    template_id: uuid.UUID | None
    plan_id: uuid.UUID
    discount_id: uuid.UUID | None
    status: QuotationStatus
    issue_date: date
    expiry_date: date
    is_expired: bool
    payment_terms_days: int
    notes: str | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    lines: list[LineOut]
    subscription_id: uuid.UUID | None
    sent_at: datetime | None
    confirmed_at: datetime | None
    created_at: datetime


class ConvertIn(BaseModel):
    start_date: date | None = None
    term_periods: int | None = Field(default=None, ge=1, le=1200)
    auto_renew: bool = False
