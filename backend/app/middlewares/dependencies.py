"""
Authentication and authorization dependencies / RBAC decorators (Module 3).

Canonical import path for routers:
    from app.middlewares.dependencies import get_current_user, require_admin, ...
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any, Optional

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer access token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            "Not authenticated",
            code="NOT_AUTHENTICATED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
        if not subject:
            raise JWTError("missing subject")
        user_id = uuid.UUID(str(subject))
    except (JWTError, ValueError) as exc:
        raise AppException(
            "Invalid or expired access token",
            code="INVALID_ACCESS_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AppException(
            "User not found or inactive",
            code="USER_INACTIVE",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    user_status = getattr(user, "status", None) or "active"
    if user_status in ("suspended", "disabled"):
        raise AppException(
            f"User account is {user_status}",
            code="USER_SUSPENDED" if user_status == "suspended" else "USER_DISABLED",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    from app.middlewares.tenant_context import TenantContext, set_tenant_context

    set_tenant_context(
        TenantContext(
            tenant_id=user.tenant_id
            or (
                uuid.UUID(str(payload["tenant_id"]))
                if payload.get("tenant_id")
                else None
            ),
            organization_id=user.organization_id
            or (
                uuid.UUID(str(payload["organization_id"]))
                if payload.get("organization_id")
                else None
            ),
            team_id=user.team_id
            or (
                uuid.UUID(str(payload["team_id"])) if payload.get("team_id") else None
            ),
            user_id=user.id,
            auth_mode="jwt",
        )
    )

    request.state.user = user
    request.state.token_roles = payload.get("roles") or []
    return user


def require_roles(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """Require the current user to hold at least one of the listed roles."""

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        role_names = {role.name for role in (user.roles or [])}
        if not role_names.intersection(set(allowed_roles)):
            raise AppException(
                "Insufficient role privileges",
                code="FORBIDDEN_ROLE",
                status_code=status.HTTP_403_FORBIDDEN,
                details={"required_roles": list(allowed_roles)},
            )
        return user

    return _dependency


def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: Admin role required."""
    role_names = {role.name for role in (user.roles or [])}
    if RoleName.ADMIN.value not in role_names:
        raise AppException(
            "Administrator role required",
            code="FORBIDDEN_ROLE",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"required_roles": [RoleName.ADMIN.value]},
        )
    return user


def require_manager(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: Manager or Admin role required."""
    role_names = {role.name for role in (user.roles or [])}
    if not role_names.intersection(
        {RoleName.MANAGER.value, RoleName.ADMIN.value}
    ):
        raise AppException(
            "Manager or Administrator role required",
            code="FORBIDDEN_ROLE",
            status_code=status.HTTP_403_FORBIDDEN,
            details={
                "required_roles": [RoleName.MANAGER.value, RoleName.ADMIN.value]
            },
        )
    return user


def require_permission(
    *permission_codes: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Require all listed permission codes (alias of require_permissions)."""
    return require_permissions(*permission_codes)


def require_permissions(
    *permission_codes: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Require all listed permission codes via the user's roles."""

    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        fresh = await UserRepository(db).get_by_id(user.id)
        if fresh is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        codes: set[str] = set()
        for role in fresh.roles or []:
            for permission in role.permissions or []:
                codes.add(permission.code)
        missing = [code for code in permission_codes if code not in codes]
        if missing:
            raise AppException(
                "Insufficient permissions",
                code="FORBIDDEN_PERMISSION",
                status_code=status.HTTP_403_FORBIDDEN,
                details={"missing": missing},
            )
        return fresh

    return _dependency


__all__ = [
    "get_current_user",
    "get_db",
    "require_admin",
    "require_manager",
    "require_permission",
    "require_permissions",
    "require_roles",
]
