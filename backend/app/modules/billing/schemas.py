import uuid
from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RecordStatus
from app.schemas.common import Percent
from decimal import Decimal


class TaxIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rate: Percent
    description: str | None = Field(default=None, max_length=500)
    applies_to: Literal["PRODUCTS", "ALL"] = "PRODUCTS"  # ALL = added automatically to every line
    status: RecordStatus = RecordStatus.ACTIVE


class TaxUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    rate: Percent | None = None
    description: str | None = Field(default=None, max_length=500)
    applies_to: Literal["PRODUCTS", "ALL"] | None = None
    status: RecordStatus | None = None


class TaxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rate: Decimal
    tax_type: str
    description: str | None
    applies_to: str = "PRODUCTS"
    status: RecordStatus
    created_at: datetime
