import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_number: str
    user_id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None
    company_name: str | None
    billing_address: str | None
    tax_id: str | None
    is_active: bool
    created_at: datetime


class CustomerUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    company_name: str | None = Field(default=None, max_length=255)
    billing_address: str | None = Field(default=None, max_length=1000)
    tax_id: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None  # staff/admin only; ignored-with-403 for customers
