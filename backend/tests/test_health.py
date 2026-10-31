from sqlalchemy import text

from app.core.database import engine


def test_health_ok(client):
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json()["data"] == {"database": "ok", "redis": "ok"}


def test_database_connection():
    with engine.connect() as c:
        assert c.execute(text("SELECT 1")).scalar() == 1


def test_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert "/api/v1/auth/login/" in client.get("/openapi.json").json()["paths"]
