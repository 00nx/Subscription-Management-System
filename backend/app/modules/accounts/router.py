import secrets

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import AppError
from app.core.ratelimit import rate_limit, rate_limit_refresh
from app.modules.accounts import service
from app.core.pagination import paginate
from app.modules.accounts.models import Notification, User, UserRole
from app.modules.accounts.schemas import (ChangePasswordIn, LoginIn, NotificationOut, PasswordResetConfirmIn, PasswordResetIn,
                                          RegisterIn, TokenOut, UserCreateIn, UserOut, UserUpdateIn)
from app.modules.analytics.audit import record_audit
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

REFRESH_COOKIE, CSRF_COOKIE, CSRF_HEADER = "refresh_token", "csrf_token", "x-csrf-token"
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


def _set_cookies(response: Response, refresh: str) -> None:
    s = get_settings()
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_expire_days * 86400, httponly=True,
                        secure=s.cookie_secure, samesite="lax", path="/api/v1/auth")
    # Double-submit CSRF token: readable by our JS, echoed back in X-CSRF-Token and compared server-side.
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(32), max_age=s.refresh_token_expire_days * 86400,
                        secure=s.cookie_secure, samesite="lax", path="/")


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _check_csrf(request: Request) -> None:
    cookie, header = request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise AppError("CSRF validation failed", 403)


def _token_out(user: User, access: str) -> ApiResponse[TokenOut]:
    return ApiResponse(message="Login successful", data=TokenOut(
        access_token=access, expires_in=get_settings().access_token_expire_minutes * 60, user=UserOut.model_validate(user)))


@auth_router.post("/register/", status_code=201, response_model=ApiResponse[UserOut], dependencies=[Depends(rate_limit)])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Public sign-up. Always creates a CUSTOMER; any role in the payload is ignored."""
    return ApiResponse(message="Registered", data=UserOut.model_validate(service.create_user(db, body)))


@auth_router.post("/login/", response_model=ApiResponse[TokenOut], responses=_errors, dependencies=[Depends(rate_limit)])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = service.authenticate(db, body.email, body.password)
    access, refresh = service.issue_tokens(db, user)
    _set_cookies(response, refresh)
    return _token_out(user, access)


@auth_router.post("/refresh/", response_model=ApiResponse[TokenOut], responses=_errors, dependencies=[Depends(rate_limit_refresh)])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    _check_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise AppError("Missing refresh token", 401)
    user, access, new_raw = service.rotate_refresh_token(db, raw)
    _set_cookies(response, new_raw)
    return _token_out(user, access)


@auth_router.post("/logout/", response_model=ApiResponse[None], responses=_errors)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    _check_csrf(request)
    if raw := request.cookies.get(REFRESH_COOKIE):
        service.revoke_refresh_token(db, raw)
    _clear_cookies(response)
    return ApiResponse(message="Logged out")


@auth_router.post("/password-reset/", response_model=ApiResponse[None], dependencies=[Depends(rate_limit)])
def password_reset(body: PasswordResetIn, db: Session = Depends(get_db)):
    """Always answers the same way (no account enumeration). Emails a time-limited link (console backend without SMTP)."""
    service.request_password_reset(db, body.email)
    return ApiResponse(message="If that email is registered, a reset link will be sent")


@auth_router.post("/password-reset/confirm/", response_model=ApiResponse[None], dependencies=[Depends(rate_limit)])
def password_reset_confirm(body: PasswordResetConfirmIn, db: Session = Depends(get_db)):
    service.confirm_password_reset(db, body.token, body.new_password)
    return ApiResponse(message="Password updated. Please log in.")


@auth_router.post("/change-password/", response_model=ApiResponse[None], responses=_errors, dependencies=[Depends(rate_limit)])
def change_password(body: ChangePasswordIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.change_password(db, user, body.current_password, body.new_password)
    return ApiResponse(message="Password changed")


@auth_router.get("/me/", response_model=ApiResponse[UserOut], responses=_errors)
def me(user: User = Depends(get_current_user)):
    return ApiResponse(data=UserOut.model_validate(user))


_admin = require_roles(UserRole.ADMIN)


@users_router.get("/", response_model=ApiResponse[Page[UserOut]], responses=_errors)
def list_users(page: PageParams = Depends(), q: str | None = Query(None, max_length=100), role: UserRole | None = None,
               is_active: bool | None = None, db: Session = Depends(get_db), _: User = Depends(_admin)):
    stmt = select(User)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    return ApiResponse(data=paginate(db, stmt, page, UserOut, {"created_at": User.created_at, "email": User.email, "full_name": User.full_name}, "created_at"))


@users_router.post("/", status_code=201, response_model=ApiResponse[UserOut], responses=_errors)
def create_user(body: UserCreateIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    """Only administrators can create staff (or other privileged) accounts."""
    user = service.create_user(db, body, body.role)
    record_audit(db, admin, "USER_CREATED", "user", user.id, f"Created {body.role.value} account {user.email}")
    db.commit()
    return ApiResponse(message="User created", data=UserOut.model_validate(user))


@users_router.get("/{user_id}/", response_model=ApiResponse[UserOut], responses=_errors)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(_admin)):
    user = db.get(User, user_id)
    if not user:
        raise AppError("User not found", 404)
    return ApiResponse(data=UserOut.model_validate(user))


@users_router.patch("/{user_id}/", response_model=ApiResponse[UserOut], responses=_errors)
def update_user(user_id: uuid.UUID, body: UserUpdateIn, db: Session = Depends(get_db), admin: User = Depends(_admin)):
    user = db.get(User, user_id)
    if not user:
        raise AppError("User not found", 404)
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("role", admin.role) != admin.role or changes.get("is_active") is False):
        raise AppError("You cannot change your own role or deactivate yourself", 400)
    old = {k: getattr(user, k).value if hasattr(getattr(user, k), "value") else getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v)
    record_audit(db, admin, "USER_UPDATED", "user", user.id, f"Updated {user.email}",
                 {k: {"from": old[k], "to": v.value if hasattr(v, "value") else v} for k, v in changes.items()})
    db.commit()
    return ApiResponse(message="User updated", data=UserOut.model_validate(user))


@notifications_router.get("/", response_model=ApiResponse[Page[NotificationOut]], responses=_errors)
def list_notifications(page: PageParams = Depends(), unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return ApiResponse(data=paginate(db, stmt, page, NotificationOut, {"created_at": Notification.created_at}, "-created_at"))


@notifications_router.get("/unread-count/", response_model=ApiResponse[dict], responses=_errors)
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    return ApiResponse(data={"count": n})


@notifications_router.post("/read-all/", response_model=ApiResponse[None], responses=_errors)
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=func.now()))
    db.commit()
    return ApiResponse(message="All notifications marked as read")


@notifications_router.post("/{notification_id}/read/", response_model=ApiResponse[NotificationOut], responses=_errors)
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:  # ownership check: someone else's notification looks like a missing one
        raise AppError("Notification not found", 404)
    if n.read_at is None:
        n.read_at = func.now()
        db.commit()
        db.refresh(n)
    return ApiResponse(data=NotificationOut.model_validate(n))
