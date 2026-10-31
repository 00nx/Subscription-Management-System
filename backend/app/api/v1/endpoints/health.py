import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.dependencies import require_roles
from app.core.exceptions import AppError
from app.modules.accounts.models import UserRole
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def health():
    checks = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"
    try:
        redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"success": ok, "message": "healthy" if ok else "unhealthy", "data": checks},
                        status_code=200 if ok else 503)


@router.post("/celery/", response_model=ApiResponse[dict], dependencies=[Depends(require_roles(UserRole.ADMIN))])
def celery_check():
    """Admin-only: enqueue the sample task and wait for the worker's result."""
    from app.tasks.sample_tasks import ping

    try:
        result = ping.delay().get(timeout=10)
    except Exception:
        raise AppError("Celery worker did not respond", 503)
    return ApiResponse(message="Celery worker responded", data={"result": result})
