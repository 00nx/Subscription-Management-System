from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.accounts.models import RefreshToken, User, UserRole
from tests.conftest import PASSWORD

API = "/api/v1/auth"


def register(client, email="a@example.com", **extra):
    return client.post(f"{API}/register/", json={"email": email, "password": PASSWORD, "full_name": "A", **extra})


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


def test_register_creates_customer_even_if_role_sent(client):
    r = register(client, role="ADMIN")
    assert r.status_code == 201
    assert r.json()["data"]["role"] == "CUSTOMER"
    assert "password" not in r.text


def test_register_stores_hash_only(client):
    register(client)
    with SessionLocal() as db:
        assert db.scalar(select(User)).hashed_password.startswith("$argon2")


def test_register_duplicate_email_case_insensitive(client):
    register(client)
    r = register(client, "A@Example.com")
    assert r.status_code == 409 and r.json()["success"] is False


def test_register_weak_password_rejected(client):
    r = client.post(f"{API}/register/", json={"email": "a@example.com", "password": "weak", "full_name": "A"})
    assert r.status_code == 422
    assert r.json()["success"] is False and "password" in r.json()["errors"]


def test_login_success_sets_httponly_refresh_cookie(client):
    register(client)
    r = client.post(f"{API}/login/", json={"email": "a@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["data"]["access_token"]
    cookie = next(h for h in r.headers.get_list("set-cookie") if h.startswith("refresh_token="))
    assert "HttpOnly" in cookie and "refresh_token" not in r.text


def test_login_wrong_password_and_unknown_user_look_identical(client):
    register(client)
    bad = client.post(f"{API}/login/", json={"email": "a@example.com", "password": "Wrong!Passw0rd"})
    unknown = client.post(f"{API}/login/", json={"email": "x@example.com", "password": PASSWORD})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()


def test_me_requires_valid_token(client, auth_header):
    assert client.get(f"{API}/me/").status_code == 401
    assert client.get(f"{API}/me/", headers={"Authorization": "Bearer nope"}).status_code == 401
    r = client.get(f"{API}/me/", headers=auth_header("a@example.com"))
    assert r.status_code == 200 and r.json()["data"]["email"] == "a@example.com"


def test_refresh_rotates_and_old_token_reuse_revokes_family(client):
    register(client)
    client.post(f"{API}/login/", json={"email": "a@example.com", "password": PASSWORD})
    old = client.cookies.get("refresh_token")
    r = client.post(f"{API}/refresh/", headers=csrf(client))
    assert r.status_code == 200 and client.cookies.get("refresh_token") != old
    new = client.cookies.get("refresh_token")

    client.cookies.set("refresh_token", old, path="/api/v1/auth")  # attacker replays the rotated-out token
    assert client.post(f"{API}/refresh/", headers=csrf(client)).status_code == 401
    client.cookies.set("refresh_token", new, path="/api/v1/auth")  # ...which kills the legitimate descendant too
    assert client.post(f"{API}/refresh/", headers=csrf(client)).status_code == 401


def test_refresh_requires_csrf_header(client):
    register(client)
    client.post(f"{API}/login/", json={"email": "a@example.com", "password": PASSWORD})
    assert client.post(f"{API}/refresh/").status_code == 403
    assert client.post(f"{API}/refresh/", headers={"X-CSRF-Token": "wrong"}).status_code == 403


def test_logout_revokes_refresh_token(client):
    register(client)
    client.post(f"{API}/login/", json={"email": "a@example.com", "password": PASSWORD})
    raw, headers = client.cookies.get("refresh_token"), csrf(client)
    assert client.post(f"{API}/logout/", headers=headers).status_code == 200
    client.cookies.set("refresh_token", raw, path="/api/v1/auth")
    client.cookies.set("csrf_token", "x")
    assert client.post(f"{API}/refresh/", headers={"X-CSRF-Token": "x"}).status_code == 401
    with SessionLocal() as db:
        assert all(t.revoked_at for t in db.scalars(select(RefreshToken)))


def test_refresh_tokens_not_stored_raw(client):
    register(client)
    client.post(f"{API}/login/", json={"email": "a@example.com", "password": PASSWORD})
    with SessionLocal() as db:
        assert db.scalar(select(RefreshToken)).token_hash != client.cookies.get("refresh_token")


def test_inactive_user_cannot_login(client, make_user):
    make_user("a@example.com")
    with SessionLocal() as db:
        u = db.scalar(select(User))
        u.is_active = False
        db.commit()
    assert client.post(f"{API}/login/", json={"email": "a@example.com", "password": PASSWORD}).status_code == 401


def test_password_reset_does_not_reveal_accounts(client):
    register(client)
    a = client.post(f"{API}/password-reset/", json={"email": "a@example.com"})
    b = client.post(f"{API}/password-reset/", json={"email": "nobody@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()


def test_rate_limit(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 2)
    from app.core import ratelimit

    ratelimit._hits.clear()
    codes = [client.post(f"{API}/login/", json={"email": "a@example.com", "password": "x"}).status_code for _ in range(3)]
    assert codes == [401, 401, 429]
    ratelimit._hits.clear()
