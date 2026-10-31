import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import password_problems
from app.modules.accounts.models import UserRole


def _check_password(v: str) -> str:
    if problems := password_problems(v):
        raise ValueError("; ".join(problems))
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    confirm_password: str | None = Field(default=None, max_length=128)  # checked only when sent

    _pw = field_validator("password")(_check_password)

    @model_validator(mode="after")
    def _match(self):
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Passwords do not match")
        return self


class UserCreateIn(RegisterIn):
    """Admin-only: the one place a role can be chosen."""

    role: UserRole = UserRole.STAFF


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class PasswordResetIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_check_password)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_check_password)


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    can_manage_discounts: bool | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    message: str
    entity_type: str | None
    entity_id: str | None
    read_at: datetime | None
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    can_manage_discounts: bool = False
    locked_until: datetime | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
