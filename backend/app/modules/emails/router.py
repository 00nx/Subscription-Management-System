import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.modules.accounts.models import User, UserRole
from app.modules.analytics.audit import record_audit
from app.modules.emails import service
from app.modules.emails.models import EmailLog
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

router = APIRouter(prefix="/email-logs", tags=["emails"])
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
_admin = require_roles(UserRole.ADMIN)


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    to_email: str
    subject: str
    template: str
    status: str
    attempts: int
    error: str | None
    entity_type: str | None
    entity_id: str | None
    created_at: datetime
    last_attempt_at: datetime | None
    sent_at: datetime | None


class EmailSummary(BaseModel):
    queued: int
    sent: int
    failed: int
    suppressed: int = 0


@router.get("/", response_model=ApiResponse[Page[EmailLogOut]], responses=_errors)
def list_email_logs(page: PageParams = Depends(), status: str | None = Query(None, pattern="^(QUEUED|SENT|FAILED|SUPPRESSED)$"), template: str | None = None,
                    q: str | None = Query(None, max_length=100), db: Session = Depends(get_db), _: User = Depends(_admin)):
    """Delivery tracking: what was sent to whom, when, and what failed."""
    stmt = select(EmailLog)
    if status:
        stmt = stmt.where(EmailLog.status == status)
    if template:
        stmt = stmt.where(EmailLog.template == template)
    if q:
        stmt = stmt.where(func.lower(EmailLog.to_email).like(f"%{q.lower()}%") | func.lower(EmailLog.subject).like(f"%{q.lower()}%"))
    return ApiResponse(data=paginate(db, stmt, page, EmailLogOut, {"created_at": EmailLog.created_at, "status": EmailLog.status}, "-created_at"))


@router.get("/summary/", response_model=ApiResponse[EmailSummary], responses=_errors)
def email_summary(db: Session = Depends(get_db), _: User = Depends(_admin)):
    counts = dict(db.execute(select(EmailLog.status, func.count()).group_by(EmailLog.status)).all())
    return ApiResponse(data=EmailSummary(queued=counts.get("QUEUED", 0), sent=counts.get("SENT", 0), failed=counts.get("FAILED", 0), suppressed=counts.get("SUPPRESSED", 0)))


@router.post("/{log_id}/retry/", response_model=ApiResponse[EmailLogOut], responses=_errors)
def retry_email(log_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    row = db.get(EmailLog, log_id)
    if not row:
        raise AppError("Email not found", 404)
    if row.status != "FAILED":
        raise AppError("Only failed emails can be retried", 409)
    service.requeue(db, row)
    record_audit(db, admin, "EMAIL_RETRY", "email", row.id, f"Retry of '{row.subject}' to {row.to_email}")
    db.commit()
    db.refresh(row)
    return ApiResponse(message="Email re-queued", data=EmailLogOut.model_validate(row))
