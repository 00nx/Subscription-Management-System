from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import IS_SQLITE, SessionLocal, init_sqlite_schema
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.modules.accounts.service import bootstrap_admin


@asynccontextmanager
async def lifespan(_: FastAPI):
    if IS_SQLITE:
        init_sqlite_schema()  # idempotent; PostgreSQL schemas come from Alembic migrations
    with SessionLocal() as db:
        bootstrap_admin(db)
    yield


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Brightloop API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,  # explicit list: credentials + "*" is not allowed
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
