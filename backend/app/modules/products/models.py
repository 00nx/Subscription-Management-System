import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import RecordStatus
from app.models.base import JSONType, Timestamps, UUIDPrimaryKey, enum_col


class Product(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("sales_price >= 0 AND cost_price >= 0", name="ck_products_prices"),
                      Index("ix_products_status_type", "status", "product_type"))

    name: Mapped[str] = mapped_column(String(255), index=True)
    product_type: Mapped[str] = mapped_column(String(50), default="SERVICE")
    sales_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)
    tax_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"))
    extra_tax_ids: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))  # further taxes (e.g. CGST + SGST); taxes are archived, never deleted

    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan", lazy="selectin",
                                                            order_by="ProductVariant.created_at")


class ProductVariant(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "attribute_name", "attribute_value", name="uq_variant_attribute"),
                      CheckConstraint("additional_price >= 0", name="ck_variant_additional_price"))

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    attribute_name: Mapped[str] = mapped_column(String(100))
    attribute_value: Mapped[str] = mapped_column(String(100))
    additional_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)

    product: Mapped[Product] = relationship(back_populates="variants")
