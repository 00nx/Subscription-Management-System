import uuid
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.modules.accounts.models import User, UserRole

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    """Identity and role always come from the database row, never from client-supplied claims."""
    user_id = decode_access_token(creds.credentials) if creds else None
    user = db.get(User, uuid.UUID(user_id)) if user_id else None
    if not user or not user.is_active:
        raise AppError("Not authenticated", 401)
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError("Insufficient permissions", 403)
        return user

    return checker
