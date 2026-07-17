"""
JWT authentication middleware.

Attaches decoded access-token claims to ``request.state`` when a valid Bearer
token is present. Does **not** reject unauthenticated requests — route-level
dependencies enforce authentication where required.
"""

from __future__ import annotations

import logging

from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Best-effort JWT parsing for observability and optional soft auth."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request.state.jwt_payload = None
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                request.state.jwt_payload = decode_access_token(token)
            except JWTError:
                logger.debug("JWT middleware: invalid access token on %s", request.url.path)
        return await call_next(request)
