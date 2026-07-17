"""
API v1 router aggregator.

All version-1 routes are mounted here. Future modules (documents, chat)
must register their routers on ``api_router`` — never mount them at the app
root without a version prefix.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, users

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
