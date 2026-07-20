"""
Portal access guards — Admin Portal vs User Portal (dual-app architecture).

Does not change business logic; only enforces which portal a role may enter.
Maps to existing roles:
  Admin portal  → admin, manager  (Tenant/Org Admin, Manager)
  User portal   → employee        (end-user ChatGPT-style app)
"""

from __future__ import annotations

from fastapi import Depends, status

from app.core.exceptions import AppException
from app.middlewares.dependencies import get_current_user
from app.models.enums import RoleName
from app.models.user import User

ADMIN_PORTAL_ROLES = {RoleName.ADMIN.value, RoleName.MANAGER.value}
USER_PORTAL_ROLES = {RoleName.EMPLOYEE.value}


def _role_names(user: User) -> set[str]:
    return {role.name for role in (user.roles or [])}


def is_admin_portal_user(user: User) -> bool:
    return bool(_role_names(user).intersection(ADMIN_PORTAL_ROLES))


def is_user_portal_user(user: User) -> bool:
    names = _role_names(user)
    # Pure employees; admins/managers belong to admin portal
    return RoleName.EMPLOYEE.value in names and not names.intersection(
        ADMIN_PORTAL_ROLES
    )


async def require_admin_portal(
    user: User = Depends(get_current_user),
) -> User:
    """Admin Portal only — Super/Tenant/Org Admin and Managers."""
    if not is_admin_portal_user(user):
        raise AppException(
            "Admin portal access denied",
            code="ADMIN_PORTAL_FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"required_roles": sorted(ADMIN_PORTAL_ROLES)},
        )
    return user


async def require_user_portal(
    user: User = Depends(get_current_user),
) -> User:
    """
    User Portal — end users (employees).

    Admins may still call chat APIs (shared backend); this guard is for
    explicit user-portal-only endpoints if added later. Chat/documents
    keep existing permission checks.
    """
    if is_admin_portal_user(user):
        # Admins are allowed to use chat APIs via shared services;
        # block only if we need exclusive employee-only routes.
        return user
    if not is_user_portal_user(user) and not _role_names(user):
        raise AppException(
            "User portal access denied",
            code="USER_PORTAL_FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return user


# Aliases matching the deliverable naming
AdminRoute = require_admin_portal
UserRoute = require_user_portal
AdminMiddleware = require_admin_portal
UserMiddleware = require_user_portal
