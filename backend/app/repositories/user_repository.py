"""User persistence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.associations import UserRole
from app.models.role import Role
from app.models.user import User


class UserRepository:
    """Data-access methods for the ``users`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Return a non-deleted user by primary key with roles/permissions loaded."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(
                selectinload(User.roles).selectinload(Role.permissions),
                selectinload(User.user_roles).selectinload(UserRole.role),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Return a non-deleted user by email (case-insensitive via stored lower)."""
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str,
        phone: str | None = None,
        is_verified: bool = False,
        tenant_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        status: str = "active",
    ) -> User:
        """Insert a new user row."""
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            phone=phone,
            is_verified=is_verified,
            is_active=status == "active",
            tenant_id=tenant_id,
            organization_id=organization_id,
            team_id=team_id,
            status=status,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_profile(
        self,
        user: User,
        *,
        full_name: str | None = None,
        phone: str | None = None,
        clear_phone: bool = False,
    ) -> User:
        """Update mutable profile fields."""
        if full_name is not None:
            user.full_name = full_name
        if clear_phone:
            user.phone = None
        elif phone is not None:
            user.phone = phone
        await self._session.flush()
        return user

    async def assign_role(self, user: User, role: Role) -> UserRole:
        """Attach a role to a user if not already assigned."""
        link = UserRole(user_id=user.id, role_id=role.id)
        self._session.add(link)
        await self._session.flush()
        return link

    async def update_last_login(self, user: User) -> None:
        """Stamp ``last_login`` to now (UTC)."""
        user.last_login = datetime.now(timezone.utc)
        await self._session.flush()

    async def set_password(self, user: User, hashed_password: str) -> None:
        """Update the user's password hash."""
        user.hashed_password = hashed_password
        await self._session.flush()

    async def mark_verified(self, user: User) -> None:
        """Mark the user email as verified."""
        user.is_verified = True
        await self._session.flush()

    async def soft_delete(self, user: User) -> None:
        """Soft-delete a user."""
        user.deleted_at = datetime.now(timezone.utc)
        user.is_active = False
        await self._session.flush()

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> Sequence[User]:
        """List active, non-deleted users (admin/manager use)."""
        stmt = (
            select(User)
            .where(User.deleted_at.is_(None), User.is_active.is_(True))
            .options(selectinload(User.roles))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_active(self) -> int:
        """Count non-deleted active users."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(User).where(
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
