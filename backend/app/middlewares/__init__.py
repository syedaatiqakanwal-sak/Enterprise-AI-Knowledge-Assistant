"""HTTP middleware package."""

from app.middlewares.dependencies import (
    get_current_user,
    require_admin,
    require_manager,
    require_permission,
    require_permissions,
    require_roles,
)
from app.middlewares.jwt import JWTAuthMiddleware, JWTMiddleware
from app.middlewares.portal import (
    AdminMiddleware,
    AdminRoute,
    UserMiddleware,
    UserRoute,
    require_admin_portal,
    require_user_portal,
)
from app.middlewares.rate_limit import enforce_rate_limit
from app.middlewares.request_context import RequestContextMiddleware

__all__ = [
    "AdminMiddleware",
    "AdminRoute",
    "JWTAuthMiddleware",
    "JWTMiddleware",
    "RequestContextMiddleware",
    "UserMiddleware",
    "UserRoute",
    "enforce_rate_limit",
    "get_current_user",
    "require_admin",
    "require_admin_portal",
    "require_manager",
    "require_permission",
    "require_permissions",
    "require_roles",
    "require_user_portal",
]
