"""
User management service — profile, listing, soft-delete, password change.

No SQL here; all persistence goes through UserRepository.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import get_password_hash, verify_password
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import RoleOut, UpdateProfileRequest, UserListOut, UserOut
from app.utils.sanitize import sanitize_text
from fastapi import status


class UserService:
    """User profile and administration use-cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._refresh = RefreshTokenRepository(session)

    def to_user_out(self, user: User) -> UserOut:
        """Map ORM user to public schema (never exposes password hash)."""
        role_names = [r.name for r in (user.roles or [])]
        primary = "employee"
        if RoleName.ADMIN.value in role_names:
            primary = "admin"
        elif RoleName.MANAGER.value in role_names:
            primary = "manager"
        permissions: list[str] = []
        for role in user.roles or []:
            for perm in role.permissions or []:
                if perm.code not in permissions:
                    permissions.append(perm.code)
        return UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[
                RoleOut(id=r.id, name=r.name, description=r.description)
                for r in (user.roles or [])
            ],
            role=primary,
            permissions=permissions,
            tenant_id=getattr(user, "tenant_id", None),
            organization_id=getattr(user, "organization_id", None),
            team_id=getattr(user, "team_id", None),
        )

    async def get_me(self, user: User) -> UserOut:
        """Return the authenticated user's profile."""
        fresh = await self._users.get_by_id(user.id)
        if fresh is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.to_user_out(fresh)

    async def update_profile(
        self, user: User, payload: UpdateProfileRequest
    ) -> UserOut:
        """Update full_name and/or phone for the current user."""
        fresh = await self._users.get_by_id(user.id)
        if fresh is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        full_name = (
            sanitize_text(payload.full_name)
            if payload.full_name is not None
            else None
        )
        await self._users.update_profile(
            fresh,
            full_name=full_name,
            phone=payload.phone if payload.phone is not None else None,
            clear_phone=payload.phone is None and "phone" in payload.model_fields_set,
        )
        fresh = await self._users.get_by_id(user.id)
        assert fresh is not None
        return self.to_user_out(fresh)

    async def change_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change password for the authenticated user; revoke all refresh tokens."""
        fresh = await self._users.get_by_id(user.id)
        if fresh is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if not verify_password(current_password, fresh.hashed_password):
            raise AppException(
                "Current password is incorrect",
                code="INVALID_CURRENT_PASSWORD",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if verify_password(new_password, fresh.hashed_password):
            raise AppException(
                "New password must be different from the current password",
                code="PASSWORD_UNCHANGED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._users.set_password(fresh, get_password_hash(new_password))
        await self._refresh.revoke_all_for_user(fresh.id)

    async def get_by_id(
        self, user_id: uuid.UUID, *, requester: User
    ) -> UserOut:
        """
        Fetch a user by id.

        Admins/managers can read any user; employees may only read themselves.
        """
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if not self._can_view(requester, target):
            raise AppException(
                "Insufficient privileges to view this user",
                code="FORBIDDEN_ROLE",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return self.to_user_out(target)

    async def list_users(
        self,
        *,
        requester: User,
        limit: int = 50,
        offset: int = 0,
    ) -> UserListOut:
        """List users (admin/manager only)."""
        if not self._is_admin_or_manager(requester):
            raise AppException(
                "Insufficient privileges to list users",
                code="FORBIDDEN_ROLE",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        items: Sequence[User] = await self._users.list_active(
            limit=limit, offset=offset
        )
        total = await self._users.count_active()
        return UserListOut(
            items=[self.to_user_out(u) for u in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def delete_user(
        self, user_id: uuid.UUID, *, requester: User
    ) -> None:
        """Soft-delete a user (admin only). Cannot delete yourself."""
        if not self._has_role(requester, RoleName.ADMIN.value):
            raise AppException(
                "Only administrators can delete users",
                code="FORBIDDEN_ROLE",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if requester.id == user_id:
            raise AppException(
                "You cannot delete your own account via this endpoint",
                code="CANNOT_DELETE_SELF",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._users.soft_delete(target)
        await self._refresh.revoke_all_for_user(target.id)

    @staticmethod
    def _has_role(user: User, role_name: str) -> bool:
        return any(r.name == role_name for r in (user.roles or []))

    def _is_admin_or_manager(self, user: User) -> bool:
        names = {r.name for r in (user.roles or [])}
        return bool(
            names.intersection({RoleName.ADMIN.value, RoleName.MANAGER.value})
        )

    def _can_view(self, requester: User, target: User) -> bool:
        if requester.id == target.id:
            return True
        return self._is_admin_or_manager(requester)
