import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PaymentMethod, PaymentStatus
from app.schemas.common import Money


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    provider_reference: str | None
    event: str
    status: str
    message: str | None
    created_at: datetime


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    method: PaymentMethod
    amount: Decimal
    status: PaymentStatus
    payment_date: datetime | None
    transaction_reference: str | None
    notes: str | None
    provider: str
    created_at: datetime
    transactions: list[TransactionOut]


class PaymentStatusOut(BaseModel):
    id: uuid.UUID
    status: PaymentStatus
    invoice_status: str
    invoice_outstanding: Decimal


class RecordPaymentIn(BaseModel):
    """Staff record an external payment (cash, bank transfer, card terminal, UPI, other)."""
    invoice_id: uuid.UUID
    method: PaymentMethod
    amount: Money = Field(gt=0)
    transaction_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, max_length=100)


class InitiatePaymentIn(BaseModel):
    invoice_id: uuid.UUID
    method: PaymentMethod = PaymentMethod.CARD
    amount: Money | None = Field(default=None, gt=0)  # default: the full outstanding balance
    idempotency_key: str | None = Field(default=None, max_length=100)


class SimulateIn(BaseModel):
    outcome: str = Field(pattern="^(SUCCESS|FAILED|CANCELLED)$")


class RazorpayOrderIn(BaseModel):
    invoice_id: uuid.UUID
    amount: Money | None = None  # defaults to the full outstanding balance; validated server-side
    idempotency_key: str | None = Field(default=None, max_length=100)


class RazorpayOrderOut(BaseModel):
    payment_id: uuid.UUID
    order_id: str
    amount: int  # paise, what Checkout must be opened with
    currency: str
    key_id: str  # public test key id
    invoice_number: str
    description: str


class RazorpayVerifyIn(BaseModel):
    payment_id: uuid.UUID
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=200)


class RazorpayConfigOut(BaseModel):
    enabled: bool
    mode: str = "test"
    key_id: str | None = None
    reason: str | None = None
