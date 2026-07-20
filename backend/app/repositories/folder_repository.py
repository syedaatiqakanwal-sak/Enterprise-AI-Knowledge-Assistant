"""Folder persistence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.folder import Folder


class FolderRepository:
    """Data-access methods for nested folders."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, folder_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Optional[Folder]:
        stmt = select(Folder).where(Folder.id == folder_id)
        if not include_deleted:
            stmt = stmt.where(Folder.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        parent_id: uuid.UUID | None = None,
    ) -> Sequence[Folder]:
        conditions = [
            Folder.owner_id == owner_id,
            Folder.deleted_at.is_(None),
        ]
        if parent_id is None:
            conditions.append(Folder.parent_id.is_(None))
        else:
            conditions.append(Folder.parent_id == parent_id)
        stmt = (
            select(Folder)
            .where(and_(*conditions))
            .order_by(Folder.name.asc())
            .options(selectinload(Folder.children))
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_all_for_owner(self, owner_id: uuid.UUID) -> Sequence[Folder]:
        stmt = (
            select(Folder)
            .where(Folder.owner_id == owner_id, Folder.deleted_at.is_(None))
            .order_by(Folder.name.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def find_sibling_by_name(
        self,
        owner_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> Optional[Folder]:
        conditions = [
            Folder.owner_id == owner_id,
            Folder.name == name,
            Folder.deleted_at.is_(None),
        ]
        if parent_id is None:
            conditions.append(Folder.parent_id.is_(None))
        else:
            conditions.append(Folder.parent_id == parent_id)
        stmt = select(Folder).where(and_(*conditions))
        result = await self._session.execute(stmt)
        folder = result.scalar_one_or_none()
        if folder and exclude_id and folder.id == exclude_id:
            return None
        return folder

    async def create(
        self,
        *,
        name: str,
        owner_id: uuid.UUID,
        parent_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        description: str | None = None,
    ) -> Folder:
        folder = Folder(
            name=name,
            owner_id=owner_id,
            parent_id=parent_id,
            company_id=company_id,
            description=description,
        )
        self._session.add(folder)
        await self._session.flush()
        await self._session.refresh(folder)
        return folder

    async def soft_delete(self, folder: Folder) -> Folder:
        folder.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def get_ancestors(self, folder: Folder) -> list[Folder]:
        """Walk parent chain for breadcrumb (root → leaf)."""
        chain: list[Folder] = []
        current: Folder | None = folder
        seen: set[uuid.UUID] = set()
        while current is not None:
            if current.id in seen:
                break
            seen.add(current.id)
            chain.append(current)
            if current.parent_id is None:
                break
            current = await self.get_by_id(current.parent_id)
        chain.reverse()
        return chain
