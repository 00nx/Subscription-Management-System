from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.accounts.router import auth_router, users_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
# Phase 2: each module owner adds `api_router.include_router(<module>.router)` here.
