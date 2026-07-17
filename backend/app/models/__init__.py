"""
SQLAlchemy ORM models.

Import concrete models here so Alembic's ``env.py`` can discover metadata via:

    from app.models import Base
"""

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.associations import RolePermission, UserRole
from app.models.enums import RoleName
from app.models.password_reset import PasswordResetToken
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User
from app.models.verification_token import EmailVerificationToken

__all__ = [
    "Base",
    "EmailVerificationToken",
    "PasswordResetToken",
    "Permission",
    "RefreshToken",
    "Role",
    "RoleName",
    "RolePermission",
    "SoftDeleteMixin",
    "TimestampMixin",
    "User",
    "UserRole",
]
