import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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

    _pw = field_validator("password")(_check_password)


class UserCreateIn(RegisterIn):
    """Admin-only: the one place a role can be chosen."""

    role: UserRole = UserRole.STAFF


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class PasswordResetIn(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
