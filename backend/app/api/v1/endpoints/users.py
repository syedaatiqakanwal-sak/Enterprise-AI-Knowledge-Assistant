""" Backward-compatible re-export — prefer ``app.api.v1.users``. """

from app.api.v1.users import router

__all__ = ["router"]
