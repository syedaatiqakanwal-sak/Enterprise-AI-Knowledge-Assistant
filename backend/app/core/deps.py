"""
Compatibility shim — Module 3 dependencies live in ``app.middlewares.dependencies``.
"""

from app.db.mongodb import get_mongo_db
from app.db.redis import get_redis
from app.db.session import get_db
from app.middlewares.dependencies import (
    get_current_user,
    require_admin,
    require_manager,
    require_permission,
    require_permissions,
    require_roles,
)

__all__ = [
    "get_current_user",
    "get_db",
    "get_mongo_db",
    "get_redis",
    "require_admin",
    "require_manager",
    "require_permission",
    "require_permissions",
    "require_roles",
]
