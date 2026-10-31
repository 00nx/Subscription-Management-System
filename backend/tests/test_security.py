import jwt
import pytest

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password, password_problems, verify_password


@pytest.mark.parametrize("pw,count", [
    ("Str0ng!Passw0rd", 0),
    ("Short1!a", 1),          # exactly 8 chars: "more than eight" is required
    ("nouppercase1!", 1),
    ("NOLOWERCASE1!", 1),
    ("NoSpecial12345", 1),
])
def test_password_rules(pw, count):
    assert len(password_problems(pw)) == count


def test_password_hash_is_argon2_and_verifies():
    h = hash_password("Str0ng!Passw0rd")
    assert h.startswith("$argon2") and "Str0ng" not in h
    assert verify_password("Str0ng!Passw0rd", h) and not verify_password("wrong", h)


def test_jwt_roundtrip_and_rejection():
    assert decode_access_token(create_access_token("abc")) == "abc"
    assert decode_access_token("garbage") is None
    expired = jwt.encode({"sub": "abc", "type": "access", "exp": 1}, get_settings().secret_key, "HS256")
    assert decode_access_token(expired) is None
    wrong_type = jwt.encode({"sub": "abc", "type": "refresh"}, get_settings().secret_key, "HS256")
    assert decode_access_token(wrong_type) is None
