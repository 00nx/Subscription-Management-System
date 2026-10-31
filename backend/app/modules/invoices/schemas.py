import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import InvoiceStatus
from app.schemas.common import Money


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: int
    unit_price: Decimal
    line_subtotal: Decimal
    discount_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    variants: list[dict] = []
    taxes: list[dict] = []
    line_total: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    customer_snapshot: dict
    subscription_id: uuid.UUID | None
    subscription_number: str | None
    status: InvoiceStatus
    source: str
    period_start: date | None
    period_end: date | None
    issue_date: date
    due_date: date
    payment_terms_days: int
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    is_overdue: bool
    notes: str | None
    tax_breakdown: list[dict] = []
    discount_breakdown: list[dict] = []
    lines: list[InvoiceLineOut]
    created_at: datetime
    confirmed_at: datetime | None


class ManualLineIn(BaseModel):
    product_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1, le=100000)
    unit_price: Money
    tax_id: uuid.UUID | None = None


class InvoiceIn(BaseModel):
    customer_id: uuid.UUID
    subscription_id: uuid.UUID | None = None
    lines: list[ManualLineIn] = Field(min_length=1, max_length=200)
    payment_terms_days: int = Field(default=0, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2000)


class BulkInvoiceIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    send: bool = False  # also email each invoice after confirming it


class BulkInvoiceOut(BaseModel):
    confirmed: int
    sent: int
    skipped: list[dict]
