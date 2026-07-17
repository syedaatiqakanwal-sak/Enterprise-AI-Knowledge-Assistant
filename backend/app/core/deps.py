"""
Authentication and authorization FastAPI dependencies.

- ``get_current_user`` — JWT Bearer authentication
- ``require_roles`` — RBAC gate for Admin / Manager / Employee
- ``require_permissions`` — fine-grained permission codes
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any, Optional

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the authenticated user from a Bearer access token.

    Also attaches ``request.state.user`` for downstream middleware/handlers.
    """
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

    request.state.user = user
    request.state.token_roles = payload.get("roles") or []
    return user


def require_roles(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """
    Dependency factory that requires the current user to hold at least one role.

    Example::

        @router.get("/admin")
        async def admin_only(user: User = Depends(require_roles("admin"))):
            ...
    """

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


def require_permissions(
    *permission_codes: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """
    Dependency factory that requires all listed permission codes.

    Permissions are resolved via the user's roles (eager-loaded).
    """

    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Ensure permissions are loaded
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


# Re-export DB helpers for a single import surface
from app.db.mongodb import get_mongo_db  # noqa: E402
from app.db.redis import get_redis  # noqa: E402

__all__ = [
    "get_current_user",
    "get_db",
    "get_mongo_db",
    "get_redis",
    "require_permissions",
    "require_roles",
]
