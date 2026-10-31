import secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import AppError
from app.core.ratelimit import rate_limit
from app.modules.accounts import service
from app.modules.accounts.models import User, UserRole
from app.modules.accounts.schemas import LoginIn, PasswordResetIn, RegisterIn, TokenOut, UserCreateIn, UserOut
from app.schemas.common import ApiResponse, ErrorResponse, Page, PageParams

REFRESH_COOKIE, CSRF_COOKIE, CSRF_HEADER = "refresh_token", "csrf_token", "x-csrf-token"
_errors = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


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
    if not cookie or not header or cookie != header:
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


@auth_router.post("/refresh/", response_model=ApiResponse[TokenOut], responses=_errors, dependencies=[Depends(rate_limit)])
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
def password_reset(body: PasswordResetIn):
    """Foundation only: always answers the same way (no account enumeration). No email is sent yet."""
    return ApiResponse(message="If that email is registered, a reset link will be sent")


@auth_router.get("/me/", response_model=ApiResponse[UserOut], responses=_errors)
def me(user: User = Depends(get_current_user)):
    return ApiResponse(data=UserOut.model_validate(user))


@users_router.get("/", response_model=ApiResponse[Page[UserOut]], responses=_errors)
def list_users(page: PageParams = Depends(), db: Session = Depends(get_db),
               _: User = Depends(require_roles(UserRole.ADMIN, UserRole.STAFF))):
    users, total = service.list_users(db, page.offset, page.page_size)
    return ApiResponse(data=Page(items=[UserOut.model_validate(u) for u in users], total=total,
                                 page=page.page, page_size=page.page_size))


@users_router.post("/", status_code=201, response_model=ApiResponse[UserOut], responses=_errors)
def create_user(body: UserCreateIn, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    """Only administrators can create staff (or other privileged) accounts."""
    return ApiResponse(message="User created", data=UserOut.model_validate(service.create_user(db, body, body.role)))
