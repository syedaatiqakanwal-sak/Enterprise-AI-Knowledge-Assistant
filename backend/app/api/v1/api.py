"""
API v1 router aggregator (Modules 3–11).
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agent,
    analytics,
    auth,
    chat,
    documents,
    folders,
    meetings,
    ocr,
    search,
    users,
    vision,
)
from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(
    search.index_router, prefix="/documents", tags=["Document Indexing"]
)
api_router.include_router(folders.router, prefix="/folders", tags=["Folders"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat / RAG"])
api_router.include_router(search.router, prefix="", tags=["Semantic Search"])
api_router.include_router(ocr.router, prefix="/ocr", tags=["OCR"])
api_router.include_router(vision.router, prefix="/vision", tags=["Vision"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])
api_router.include_router(agent.router, prefix="/agent", tags=["AI Agents"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin / Tenancy"])
