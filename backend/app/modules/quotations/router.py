import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.enums import QuotationStatus
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.customers.service import scope_customer_id
from app.modules.quotations import service
from app.modules.quotations.models import Quotation, QuotationTemplate
from app.modules.quotations.schemas import ConvertIn, QuotationIn, QuotationOut, QuotationUpdateIn, TemplateIn, TemplateOut, TemplateUpdateIn
from app.modules.subscriptions.schemas import SubscriptionOut
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/quotations", tags=["quotations"])
templates_router = APIRouter(prefix="/quotation-templates", tags=["quotations"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
_SORTS = {"created_at": Quotation.created_at, "number": Quotation.number, "total": Quotation.total, "expiry_date": Quotation.expiry_date}


# ---------------- templates ----------------
@templates_router.get("/", response_model=ApiResponse[Page[TemplateOut]], responses=_errors)
def list_templates(page: PageParams = Depends(), db: Session = Depends(get_db), _: User = Depends(_staff)):
    return ApiResponse(data=paginate(db, select(QuotationTemplate), page, TemplateOut, {"name": QuotationTemplate.name, "created_at": QuotationTemplate.created_at}, "name"))


@templates_router.post("/", status_code=201, response_model=ApiResponse[TemplateOut], responses=_errors)
def create_template(body: TemplateIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    try:
        t = service.create_template(db, body, actor)
        db.commit()
    except IntegrityError:
        raise AppError("A template with this name already exists", 409)
    return ApiResponse(message="Template created", data=TemplateOut.model_validate(t))


@templates_router.get("/{template_id}/", response_model=ApiResponse[TemplateOut], responses=_errors)
def get_template(template_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_staff)):
    return ApiResponse(data=TemplateOut.model_validate(service.get_template(db, template_id)))


@templates_router.patch("/{template_id}/", response_model=ApiResponse[TemplateOut], responses=_errors)
def update_template(template_id: uuid.UUID, body: TemplateUpdateIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    try:
        t = service.update_template(db, service.get_template(db, template_id), body, actor)
        db.commit()
    except IntegrityError:
        raise AppError("A template with this name already exists", 409)
    return ApiResponse(message="Template updated", data=TemplateOut.model_validate(t))


# ---------------- quotations ----------------
@router.get("/", response_model=ApiResponse[Page[QuotationOut]], responses=_errors)
def list_quotations(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), status: QuotationStatus | None = None,
                    customer_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Quotation)
    scope = scope_customer_id(db, user)
    if scope is not None:
        stmt = stmt.where(Quotation.customer_id == scope, Quotation.status != QuotationStatus.DRAFT)
    elif customer_id:
        stmt = stmt.where(Quotation.customer_id == customer_id)
    if q:
        stmt = stmt.where(func.lower(Quotation.number).like(f"%{q.lower()}%"))
    if status:
        stmt = stmt.where(Quotation.status == status)
    return ApiResponse(data=paginate(db, stmt, page, QuotationOut, _SORTS, "-created_at"))


@router.post("/", status_code=201, response_model=ApiResponse[QuotationOut], responses=_errors)
def create_quotation(body: QuotationIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    qt = service.create_quotation(db, body, actor)
    db.commit()
    return ApiResponse(message="Quotation created", data=QuotationOut.model_validate(qt))


@router.get("/{qid}/", response_model=ApiResponse[QuotationOut], responses=_errors)
def get_quotation(qid: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ApiResponse(data=QuotationOut.model_validate(service.get_quotation(db, user, qid)))


@router.patch("/{qid}/", response_model=ApiResponse[QuotationOut], responses=_errors)
def update_quotation(qid: uuid.UUID, body: QuotationUpdateIn, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    qt = service.update_quotation(db, service.get_quotation(db, actor, qid, lock=True), body, actor)
    db.commit()
    return ApiResponse(message="Quotation updated", data=QuotationOut.model_validate(qt))


@router.post("/{qid}/send/", response_model=ApiResponse[QuotationOut], responses=_errors)
def send_quotation(qid: uuid.UUID, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    qt = service.get_quotation(db, actor, qid, lock=True)
    service.send(db, qt, actor)
    db.commit()
    return ApiResponse(message="Quotation sent", data=QuotationOut.model_validate(qt))


@router.post("/{qid}/confirm/", response_model=ApiResponse[QuotationOut], responses=_errors)
def confirm_quotation(qid: uuid.UUID, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    qt = service.get_quotation(db, actor, qid, lock=True)
    service.confirm(db, qt, actor)
    db.commit()
    return ApiResponse(message="Quotation confirmed", data=QuotationOut.model_validate(qt))


@router.post("/{qid}/convert/", status_code=201, response_model=ApiResponse[SubscriptionOut], responses=_errors)
def convert_quotation(qid: uuid.UUID, body: ConvertIn | None = None, db: Session = Depends(get_db), actor: User = Depends(_staff)):
    qt = service.get_quotation(db, actor, qid, lock=True)  # row lock makes concurrent conversions queue up
    sub = service.convert(db, qt, body or ConvertIn(), actor)
    db.commit()
    return ApiResponse(message="Subscription created from quotation", data=SubscriptionOut.model_validate(sub))
