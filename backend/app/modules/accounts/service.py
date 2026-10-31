import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, hash_token, new_opaque_token, verify_password
from app.modules.accounts.models import RefreshToken, User, UserRole
from app.modules.accounts.schemas import RegisterIn

_DUMMY_HASH = hash_password("timing-equaliser")  # so unknown emails cost the same as wrong passwords


def create_user(db: Session, data: RegisterIn, role: UserRole = UserRole.CUSTOMER) -> User:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError("Email already registered", 409)
    user = User(email=email, hashed_password=hash_password(data.password), full_name=data.full_name, role=role)
    db.add(user)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    ok = verify_password(password, user.hashed_password if user else _DUMMY_HASH)
    if not (user and ok and user.is_active):
        raise AppError("Invalid email or password", 401)
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
