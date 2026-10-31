import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, errors: dict | None = None):
        self.message, self.status_code, self.errors = message, status_code, errors or {}


def _body(message: str, errors: dict | None = None) -> dict:
    return {"success": False, "message": message, "errors": errors or {}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.message, exc.errors), status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(str(exc.detail)), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors: dict[str, list[str]] = {}
        for e in exc.errors():
            field = ".".join(str(p) for p in e["loc"] if p != "body") or "request"
            errors.setdefault(field, []).append(e["msg"].removeprefix("Value error, "))
        return JSONResponse(_body("Validation failed", errors), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")  # details stay in logs, never in the response
        return JSONResponse(_body("Internal server error"), status_code=500)
