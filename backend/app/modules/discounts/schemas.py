import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import DiscountType
from app.schemas.common import Money


class _Rules(BaseModel):
    @model_validator(mode="after")
    def _check(self):
        t, v = getattr(self, "discount_type", None), getattr(self, "value", None)
        if v is not None and v <= 0:
            raise ValueError("Discount value must be greater than zero")
        if t == DiscountType.PERCENTAGE and v is not None and v > 100:
            raise ValueError("A percentage discount cannot exceed 100")
        s, e = getattr(self, "start_date", None), getattr(self, "end_date", None)
        if s and e and e < s:
            raise ValueError("End date must not be before the start date")
        return self


class DiscountIn(_Rules):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    discount_type: DiscountType
    value: Money
    min_purchase_amount: Money = Decimal("0.00")
    min_quantity: int = Field(default=0, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    max_usage: int | None = Field(default=None, ge=1)
    is_active: bool = True
    product_ids: list[uuid.UUID] = []
    subscription_ids: list[uuid.UUID] = []


class DiscountUpdateIn(_Rules):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    discount_type: DiscountType | None = None
    value: Money | None = None
    min_purchase_amount: Money | None = None
    min_quantity: int | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    max_usage: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    product_ids: list[uuid.UUID] | None = None
    subscription_ids: list[uuid.UUID] | None = None


class DiscountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    discount_type: DiscountType
    value: Decimal
    min_purchase_amount: Decimal
    min_quantity: int
    start_date: date | None
    end_date: date | None
    max_usage: int | None
    usage_count: int
    is_active: bool
    product_ids: list[uuid.UUID]
    subscription_ids: list[uuid.UUID]
    created_at: datetime


class DiscountUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    discount_id: uuid.UUID
    invoice_id: uuid.UUID
    subscription_id: uuid.UUID | None
    amount: Decimal
    created_at: datetime
