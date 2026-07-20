"""Tenant context — request-scoped tenant isolation (contextvars + middleware)."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

_tenant_ctx: ContextVar[Optional["TenantContext"]] = ContextVar("tenant_ctx", default=None)


@dataclass
class TenantContext:
    tenant_id: UUID | None = None
    organization_id: UUID | None = None
    team_id: UUID | None = None
    user_id: UUID | None = None
    api_key_id: UUID | None = None
    auth_mode: str = "jwt"  # jwt | api_key

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "team_id": str(self.team_id) if self.team_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "auth_mode": self.auth_mode,
        }


def get_tenant_context() -> TenantContext:
    return _tenant_ctx.get() or TenantContext()


def set_tenant_context(ctx: TenantContext) -> None:
    _tenant_ctx.set(ctx)


def clear_tenant_context() -> None:
    _tenant_ctx.set(None)


def require_tenant_id() -> UUID:
    ctx = get_tenant_context()
    if ctx.tenant_id is None:
        from app.core.exceptions import AppException

        raise AppException(
            "Tenant context required",
            code="TENANT_REQUIRED",
            status_code=403,
        )
    return ctx.tenant_id


def apply_tenant_filter(stmt, model, *, tenant_id: UUID | None = None):
    """Apply automatic tenant_id / company_id filter when the model supports it."""
    tid = tenant_id or get_tenant_context().tenant_id
    if tid is None:
        return stmt
    if hasattr(model, "tenant_id"):
        return stmt.where(model.tenant_id == tid)
    if hasattr(model, "company_id"):
        # Backward-compatible: company_id stores the same UUID as tenant_id
        return stmt.where((model.company_id == tid) | (model.company_id.is_(None)))
    return stmt


class TenantContextMiddleware:
    """
    Populate TenantContext from JWT claims or X-API-Key.

    Must run after the app can decode the Authorization header (reads raw headers).
    Full user resolution still happens in dependencies; this seeds tenant IDs early.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        clear_tenant_context()
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        ctx = TenantContext()

        api_key = headers.get("x-api-key")
        auth = headers.get("authorization", "")

        if api_key:
            ctx.auth_mode = "api_key"
            # Resolved fully in get_current_user / admin deps when DB available
            scope.setdefault("state", {})["api_key_raw"] = api_key
        elif auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                from app.core.security import decode_access_token

                payload = decode_access_token(token)
                if payload.get("tenant_id"):
                    ctx.tenant_id = UUID(str(payload["tenant_id"]))
                if payload.get("organization_id"):
                    ctx.organization_id = UUID(str(payload["organization_id"]))
                if payload.get("team_id"):
                    ctx.team_id = UUID(str(payload["team_id"]))
                if payload.get("sub"):
                    ctx.user_id = UUID(str(payload["sub"]))
                ctx.auth_mode = "jwt"
            except Exception:
                logger.debug("Tenant JWT parse skipped", exc_info=True)

        set_tenant_context(ctx)
        scope.setdefault("state", {})["tenant"] = ctx.as_dict()

        try:
            await self.app(scope, receive, send)
        finally:
            clear_tenant_context()
