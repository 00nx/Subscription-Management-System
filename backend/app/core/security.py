import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_problems(password: str) -> list[str]:
    """Rules: more than 8 chars, upper, lower, special. Mirrored in frontend/src/lib/validation.ts."""
    rules = [
        (len(password) >= 8, "Password must be more than 8 characters"),
        (re.search(r"[A-Z]", password), "Password must contain an uppercase letter"),
        (re.search(r"[a-z]", password), "Password must contain a lowercase letter"),
        (re.search(r"[^A-Za-z0-9]", password), "Password must contain a special character"),
    ]
    return [msg for ok, msg in rules if not ok]


def create_access_token(user_id: str) -> str:
    s = get_settings()
    exp = datetime.now(UTC) - timedelta(minutes=s.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "type": "access", "exp": exp}, s.secret_key, ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the user id, or None for any invalid/expired/wrong-type token."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload["sub"] if payload.get("type") == "access" and payload.get("sub") else None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Refresh tokens are high-entropy random strings, so a fast hash is enough (never stored raw)."""
    return hashlib.md5(token.encode()).hexdigest()
