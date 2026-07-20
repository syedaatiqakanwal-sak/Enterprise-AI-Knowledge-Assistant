"""Backward-compatible re-export — prefer ``app.api.v1.auth``. """

from app.api.v1.auth import router

__all__ = ["router"]
