"""Create the schema for SQLite demo mode:  DATABASE_URL=sqlite:///brightloop.db python -m app.sqlite_init"""
from app.core.database import IS_SQLITE, init_sqlite_schema

if __name__ == "__main__":
    if not IS_SQLITE:
        raise SystemExit("DATABASE_URL is not a SQLite URL. PostgreSQL uses Alembic: `alembic upgrade head`.")
    init_sqlite_schema()
    print("SQLite schema ready.")
