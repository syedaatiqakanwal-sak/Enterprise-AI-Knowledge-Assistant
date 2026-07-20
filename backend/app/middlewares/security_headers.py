"""Security headers middleware (Module 12) — defense-in-depth for API responses."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

_SECURITY_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"strict-origin-when-cross-origin",
    b"x-xss-protection": b"0",
    b"permissions-policy": b"geolocation=(), microphone=(), camera=()",
    b"cache-control": b"no-store",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.SECURITY_HEADERS_ENABLED:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                existing = {k.lower() for k, _ in headers}
                for key, value in _SECURITY_HEADERS.items():
                    if key not in existing:
                        headers.append((key, value))
                if settings.is_production or settings.is_staging:
                    if b"strict-transport-security" not in existing:
                        headers.append(
                            (
                                b"strict-transport-security",
                                b"max-age=31536000; includeSubDomains",
                            )
                        )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
