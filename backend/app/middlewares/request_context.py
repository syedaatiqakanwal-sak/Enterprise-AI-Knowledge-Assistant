"""
Request-scoped middleware utilities (pure ASGI — avoids BaseHTTPMiddleware loop bugs).
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import clear_request_ids, set_request_ids

logger = logging.getLogger(__name__)


class RequestContextMiddleware:
    """Attach request / correlation IDs + latency logging to every HTTP exchange."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id") or str(uuid4())
        correlation_id = headers.get("x-correlation-id") or request_id
        set_request_ids(request_id=request_id, correlation_id=correlation_id)

        if "state" not in scope:
            scope["state"] = {}

        started = time.perf_counter()
        status_code_holder = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code_holder["code"] = message["status"]
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                raw_headers.append(
                    (b"x-correlation-id", correlation_id.encode("latin-1"))
                )
                message = {**message, "headers": raw_headers}
            await send(message)

        scope["state"]["request_id"] = request_id
        scope["state"]["correlation_id"] = correlation_id

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            method = scope.get("method", "")
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.1fms) request_id=%s correlation_id=%s",
                method,
                path,
                status_code_holder["code"],
                elapsed_ms,
                request_id,
                correlation_id,
            )
            try:
                from app.services.telemetry import buffer_api_request

                buffer_api_request(
                    request_id=request_id,
                    method=method,
                    path=path,
                    status_code=int(status_code_holder["code"]),
                    latency_ms=elapsed_ms,
                )
            except Exception:
                logger.debug("analytics buffer skipped", exc_info=True)
            clear_request_ids()
