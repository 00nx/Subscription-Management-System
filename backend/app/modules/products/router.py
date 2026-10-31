import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.enums import RecordStatus
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.products import service
from app.modules.products.models import Product, ProductVariant
from app.modules.products.schemas import ProductIn, ProductOut, ProductUpdateIn, VariantIn, VariantOut, VariantUpdateIn
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/products", tags=["products"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)  # read
_admin = require_roles(UserRole.ADMIN)  # write: only administrators create/configure products

_SORTS = {"name": Product.name, "sales_price": Product.sales_price, "created_at": Product.created_at, "updated_at": Product.updated_at}


@router.get("/", response_model=ApiResponse[Page[ProductOut]], responses=_errors)
def list_products(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), product_type: str | None = None,
                  status: RecordStatus | None = None, db: Session = Depends(get_db), _: User = Depends(_staff)):
    stmt = select(Product)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Product.name).like(like), func.lower(func.coalesce(Product.description, "")).like(like)))
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if status:
        stmt = stmt.where(Product.status == status)
    return ApiResponse(data=paginate(db, stmt, page, ProductOut, _SORTS, "-created_at"))


@router.post("/", status_code=201, response_model=ApiResponse[ProductOut], responses=_errors)
def create_product(body: ProductIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    service.check_tax(db, body.tax_id)
    data = body.model_dump()
    data["extra_tax_ids"] = service.check_extra_taxes(db, body.extra_tax_ids)
    product = Product(**data)
    db.add(product)
    db.flush()
    record_audit(db, admin, "PRODUCT_CREATED", "product", product.id, f"Created product {product.name}", {"sales_price": str(product.sales_price)})
    db.commit()
    return ApiResponse(message="Product created", data=ProductOut.model_validate(product))


@router.get("/{product_id}/", response_model=ApiResponse[ProductOut], responses=_errors)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_staff)):
    return ApiResponse(data=ProductOut.model_validate(service.get_product(db, product_id)))


@router.patch("/{product_id}/", response_model=ApiResponse[ProductOut], responses=_errors)
def update_product(product_id: uuid.UUID, body: ProductUpdateIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    """Price edits never touch existing subscription lines or invoices: those hold their own snapshot."""
    product = service.get_product(db, product_id)
    changes = body.model_dump(exclude_unset=True)
    service.check_tax(db, changes.get("tax_id"))
    if changes.get("extra_tax_ids") is not None:
        changes["extra_tax_ids"] = service.check_extra_taxes(db, body.extra_tax_ids)
    elif "extra_tax_ids" in changes:
        del changes["extra_tax_ids"]
    old = {k: str(getattr(product, k)) for k in changes}
    for k, v in changes.items():
        setattr(product, k, v)
    record_audit(db, admin, "PRODUCT_UPDATED", "product", product.id, f"Updated product {product.name}",
                 {k: {"from": old[k], "to": str(v)} for k, v in changes.items()})
    db.commit()
    return ApiResponse(message="Product updated", data=ProductOut.model_validate(product))


@router.post("/{product_id}/archive/", response_model=ApiResponse[ProductOut], responses=_errors)
def archive_product(product_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    product = service.get_product(db, product_id)
    product.status = RecordStatus.ARCHIVED
    record_audit(db, admin, "PRODUCT_ARCHIVED", "product", product.id, f"Archived product {product.name}")
    db.commit()
    return ApiResponse(message="Product archived", data=ProductOut.model_validate(product))


@router.delete("/{product_id}/", response_model=ApiResponse[None], responses=_errors)
def delete_product(product_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    product = service.get_product(db, product_id)
    if service.is_referenced(db, product.id):
        raise AppError("Product is used by plans, quotations, subscriptions or invoices. Archive it instead.", 409)
    record_audit(db, admin, "PRODUCT_DELETED", "product", product.id, f"Deleted product {product.name}")
    db.delete(product)
    db.commit()
    return ApiResponse(message="Product deleted")


@router.get("/{product_id}/variants/", response_model=ApiResponse[list[VariantOut]], responses=_errors)
def list_variants(product_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_staff)):
    return ApiResponse(data=[VariantOut.model_validate(v) for v in service.get_product(db, product_id).variants])


@router.post("/{product_id}/variants/", status_code=201, response_model=ApiResponse[VariantOut], responses=_errors)
def create_variant(product_id: uuid.UUID, body: VariantIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    product = service.get_product(db, product_id)
    variant = ProductVariant(product_id=product.id, **body.model_dump())
    db.add(variant)
    try:
        db.flush()
    except IntegrityError:
        raise AppError("This attribute value already exists for the product", 409)
    record_audit(db, admin, "VARIANT_CREATED", "product_variant", variant.id, f"Added variant {variant.name} to {product.name}",
                 {"additional_price": str(variant.additional_price)})
    db.commit()
    return ApiResponse(message="Variant created", data=VariantOut.model_validate(variant))


@router.patch("/{product_id}/variants/{variant_id}/", response_model=ApiResponse[VariantOut], responses=_errors)
def update_variant(product_id: uuid.UUID, variant_id: uuid.UUID, body: VariantUpdateIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    product = service.get_product(db, product_id)
    variant = service.get_variant(db, product, variant_id)
    changes = body.model_dump(exclude_unset=True)
    old = {k: str(getattr(variant, k)) for k in changes}
    for k, v in changes.items():
        setattr(variant, k, v)
    record_audit(db, admin, "VARIANT_UPDATED", "product_variant", variant.id, f"Updated variant {variant.name}",
                 {k: {"from": old[k], "to": str(v)} for k, v in changes.items()})
    try:
        db.commit()
    except IntegrityError:
        raise AppError("This attribute value already exists for the product", 409)
    return ApiResponse(message="Variant updated", data=VariantOut.model_validate(variant))


@router.delete("/{product_id}/variants/{variant_id}/", response_model=ApiResponse[None], responses=_errors)
def delete_variant(product_id: uuid.UUID, variant_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    product = service.get_product(db, product_id)
    variant = service.get_variant(db, product, variant_id)
    if service.references_exist(db, ("subscription_lines", "quotation_lines", "quotation_template_lines"), "variant_id", variant.id):
        raise AppError("Variant is used by quotations or subscriptions. Set it to ARCHIVED instead.", 409)
    db.delete(variant)
    record_audit(db, admin, "VARIANT_DELETED", "product_variant", variant.id, f"Deleted variant {variant.name}")
    db.commit()
    return ApiResponse(message="Variant deleted")
