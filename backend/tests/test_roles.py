from app.modules.accounts.models import UserRole
from tests.conftest import PASSWORD

NEW_STAFF = {"email": "s@example.com", "password": PASSWORD, "full_name": "S", "role": "STAFF"}


def test_unauthenticated_users_endpoints_blocked(client):
    assert client.get("/api/v1/users/").status_code == 401
    assert client.post("/api/v1/users/", json=NEW_STAFF).status_code == 401


def test_customer_forbidden(client, auth_header):
    h = auth_header("c@example.com", UserRole.CUSTOMER)
    assert client.get("/api/v1/users/", headers=h).status_code == 403
    assert client.post("/api/v1/users/", json=NEW_STAFF, headers=h).status_code == 403


def test_staff_can_list_but_not_create(client, auth_header):
    h = auth_header("st@example.com", UserRole.STAFF)
    assert client.get("/api/v1/users/", headers=h).status_code == 200
    assert client.post("/api/v1/users/", json=NEW_STAFF, headers=h).status_code == 403


def test_admin_creates_staff_and_lists_with_pagination(client, auth_header):
    h = auth_header("ad@example.com", UserRole.ADMIN)
    r = client.post("/api/v1/users/", json=NEW_STAFF, headers=h)
    assert r.status_code == 201 and r.json()["data"]["role"] == "STAFF"
    page = client.get("/api/v1/users/?page=1&page_size=1", headers=h).json()["data"]
    assert page["total"] == 2 and len(page["items"]) == 1 and page["page_size"] == 1


def test_role_in_token_is_not_trusted(client, auth_header):
    """Role is read from the DB each request: demoting a user takes effect immediately."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.modules.accounts.models import User

    h = auth_header("ad@example.com", UserRole.ADMIN)
    assert client.get("/api/v1/users/", headers=h).status_code == 200
    with SessionLocal() as db:
        db.scalar(select(User)).role = UserRole.CUSTOMER
        db.commit()
    assert client.get("/api/v1/users/", headers=h).status_code == 403
