import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, hash_token, new_opaque_token, verify_password
from app.core.database import next_number
from app.modules.emails.service import queue_email
from app.modules.accounts.models import PasswordResetToken, RefreshToken, User, UserRole
from app.modules.customers.models import CustomerProfile
from app.modules.accounts.schemas import RegisterIn

_DUMMY_HASH = hash_password("timing-equaliser")  # so unknown emails cost the same as wrong passwords


def create_user(db: Session, data: RegisterIn, role: UserRole = UserRole.CUSTOMER) -> User:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError("Email already registered", 409)
    user = User(email=email, hashed_password=hash_password(data.password), full_name=data.full_name, role=role)
    db.add(user)
    db.flush()
    if role == UserRole.CUSTOMER:
        db.add(CustomerProfile(user_id=user.id, customer_number=next_number(db, "customer_number_seq", "CUS")))
        queue_email(db, user.email, "welcome", {"name": user.full_name}, "user", user.id)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    now = datetime.now(UTC)
    if user and user.locked_until and user.locked_until > now:  # checked before the password so a locked account reveals nothing more
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        raise AppError(f"Too many failed attempts. Account locked; try again in {mins} minute(s) or reset your password.", 423)
    ok = verify_password(password, user.hashed_password if user else _DUMMY_HASH)
    if not (user and ok and user.is_active):
        if user and user.is_active:
            cfg = get_settings()
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= cfg.max_failed_logins:
                user.locked_until = now + timedelta(minutes=cfg.lockout_minutes)
                user.failed_login_count = 0
            db.commit()  # the counter must survive the 401
        raise AppError("Invalid email or password", 401)
    if user.failed_login_count or user.locked_until:
        user.failed_login_count, user.locked_until = 0, None
        db.commit()
    return user


def list_users(db: Session, offset: int, limit: int) -> tuple[list[User], int]:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    return list(db.scalars(select(User).order_by(User.created_at).offset(offset).limit(limit))), total


def issue_tokens(db: Session, user: User, family_id: uuid.UUID | None = None) -> tuple[str, str]:
    """Returns (access_token, raw_refresh_token); only the refresh token's hash is persisted."""
    raw = new_opaque_token()
    db.add(RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days),
    ))
    db.commit()
    return create_access_token(str(user.id)), raw


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=datetime.now(UTC)))
    db.commit()


def rotate_refresh_token(db: Session, raw: str) -> tuple[User, str, str]:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if not row:
        raise AppError("Invalid refresh token", 401)
    if row.revoked_at is not None:  # a rotated-out token came back: assume theft, kill the whole chain
        _revoke_family(db, row.family_id)
        raise AppError("Invalid refresh token", 401)
    user = db.get(User, row.user_id)
    if row.expires_at < datetime.now(UTC) or not user or not user.is_active:
        raise AppError("Invalid refresh token", 401)
    row.revoked_at = datetime.now(UTC)
    access, new_raw = issue_tokens(db, user, row.family_id)  # commits the revocation too
    return user, access, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if row:
        _revoke_family(db, row.family_id)


def bootstrap_admin(db: Session) -> None:
    s = get_settings()
    if s.bootstrap_admin_email and s.bootstrap_admin_password:
        if not db.scalar(select(User.id).where(User.email == s.bootstrap_admin_email.lower())):
            create_user(db, RegisterIn(email=s.bootstrap_admin_email, password=s.bootstrap_admin_password,
                                       full_name="Administrator"), UserRole.ADMIN)


def request_password_reset(db: Session, email: str) -> None:
    """Silently does nothing for unknown/inactive accounts (the endpoint answers identically either way)."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active:
        return
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=datetime.now(UTC)))  # a newer request invalidates every earlier link
    raw = new_opaque_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw),
                              expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_expire_minutes)))
    link = f"{get_settings().frontend_url}/reset-password?token={raw}"
    queue_email(db, user.email, "password_reset", {"name": user.full_name, "link": link, "minutes": get_settings().password_reset_expire_minutes}, "user", user.id)
    db.commit()  # the email is only handed to the worker once this commits


def _revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=datetime.now(UTC)))


def confirm_password_reset(db: Session, raw: str, new_password: str) -> None:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw)).with_for_update())
    if not row or row.used_at is not None or row.expires_at < datetime.now(UTC):
        raise AppError("Invalid or expired reset token", 400)
    user = db.get(User, row.user_id)
    user.hashed_password = hash_password(new_password)
    user.failed_login_count, user.locked_until = 0, None  # resetting the password also unlocks the account
    row.used_at = datetime.now(UTC)
    _revoke_all_refresh_tokens(db, user.id)  # a reset logs out every session
    db.commit()


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        raise AppError("Current password is incorrect", 400)
    user.hashed_password = hash_password(new)
    _revoke_all_refresh_tokens(db, user.id)
    db.commit()
