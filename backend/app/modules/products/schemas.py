import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RecordStatus
from app.schemas.common import Money


class VariantIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    attribute_name: str = Field(min_length=1, max_length=100)
    attribute_value: str = Field(min_length=1, max_length=100)
    additional_price: Money = Decimal("0.00")
    status: RecordStatus = RecordStatus.ACTIVE


class VariantUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    attribute_name: str | None = Field(default=None, min_length=1, max_length=100)
    attribute_value: str | None = Field(default=None, min_length=1, max_length=100)
    additional_price: Money | None = None
    status: RecordStatus | None = None


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    attribute_name: str
    attribute_value: str
    additional_price: Decimal
    status: RecordStatus


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    product_type: str = Field(default="SERVICE", min_length=1, max_length=50)
    sales_price: Money
    cost_price: Money = Decimal("0.00")
    description: str | None = Field(default=None, max_length=2000)
    tax_id: uuid.UUID | None = None
    extra_tax_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    status: RecordStatus = RecordStatus.ACTIVE


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    product_type: str | None = Field(default=None, min_length=1, max_length=50)
    sales_price: Money | None = None
    cost_price: Money | None = None
    description: str | None = Field(default=None, max_length=2000)
    tax_id: uuid.UUID | None = None
    extra_tax_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    status: RecordStatus | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    product_type: str
    sales_price: Decimal
    cost_price: Decimal
    description: str | None
    status: RecordStatus
    tax_id: uuid.UUID | None
    extra_tax_ids: list[uuid.UUID] = []
    variants: list[VariantOut]
    created_at: datetime
    updated_at: datetime
