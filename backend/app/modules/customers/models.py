import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class CustomerProfile(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "customer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    customer_number: Mapped[str] = mapped_column(String(20), unique=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    company_name: Mapped[str | None] = mapped_column(String(255))
    billing_address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(50))

    user = relationship("User", lazy="joined")

    @property
    def full_name(self) -> str:
        return self.user.full_name

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def is_active(self) -> bool:
        return self.user.is_active
