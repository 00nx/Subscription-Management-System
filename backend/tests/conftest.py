import os

# Must be set before `app` is imported: settings are read at import time.
os.environ.setdefault("SECRET_KEY", "test-secret-not-for-production-0123456789")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://brightloop:brightloop_dev@localhost:5432/brightloop_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.accounts.models import UserRole  # noqa: E402
from app.modules.accounts.schemas import RegisterIn  # noqa: E402
from app.modules.accounts.service import create_user  # noqa: E402

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(scope="session", autouse=True)
def _migrated():
    command.upgrade(Config("alembic.ini"), "head")  # tests the migrations themselves


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE users, refresh_tokens CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user():
    def _make(email: str, role: UserRole = UserRole.CUSTOMER):
        with SessionLocal() as db:
            return create_user(db, RegisterIn(email=email, password=PASSWORD, full_name="Test User"), role)

    return _make


@pytest.fixture
def auth_header(client, make_user):
    def _header(email: str, role: UserRole = UserRole.CUSTOMER) -> dict:
        make_user(email, role)
        r = client.post("/api/v1/auth/login/", json={"email": email, "password": PASSWORD})
        client.cookies.clear()
        return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

    return _header
