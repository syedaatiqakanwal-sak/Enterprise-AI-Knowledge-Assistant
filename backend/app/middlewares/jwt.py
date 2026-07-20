"""
JWT authentication middleware (pure ASGI).

Soft-parses Bearer access tokens onto ``scope["state"]["jwt_payload"]``.
"""

from __future__ import annotations

import logging

from jose import JWTError
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    """Best-effort JWT parsing for observability and optional soft auth."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["jwt_payload"] = None

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        auth = headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                scope["state"]["jwt_payload"] = decode_access_token(token)
            except JWTError:
                logger.debug(
                    "JWT middleware: invalid access token on %s",
                    scope.get("path"),
                )

        await self.app(scope, receive, send)


JWTMiddleware = JWTAuthMiddleware
