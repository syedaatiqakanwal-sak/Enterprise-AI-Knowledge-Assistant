"""Document persistence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentFavorite, DocumentVersion
from app.models.enums import DocumentStatus, DocumentVisibility
from app.models.user import User


class DocumentRepository:
    """Data-access methods for documents, versions, and favorites."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self, *, include_deleted: bool = False):
        stmt = select(Document).options(
            selectinload(Document.owner),
            selectinload(Document.folder),
            selectinload(Document.versions),
        )
        if not include_deleted:
            stmt = stmt.where(
                Document.deleted_at.is_(None),
                Document.status != DocumentStatus.DELETED.value,
            )
        return stmt

    async def get_by_id(
        self, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Optional[Document]:
        stmt = self._base_query(include_deleted=include_deleted).where(
            or_(Document.id == document_id, Document.uuid == document_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_checksum(
        self, owner_id: uuid.UUID, checksum: str
    ) -> Optional[Document]:
        stmt = self._base_query().where(
            Document.owner_id == owner_id,
            Document.checksum == checksum,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def filename_exists(
        self,
        owner_id: uuid.UUID,
        filename: str,
        *,
        folder_id: uuid.UUID | None,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        conditions = [
            Document.owner_id == owner_id,
            Document.filename == filename,
            Document.deleted_at.is_(None),
            Document.status != DocumentStatus.DELETED.value,
        ]
        if folder_id is None:
            conditions.append(Document.folder_id.is_(None))
        else:
            conditions.append(Document.folder_id == folder_id)
        if exclude_id is not None:
            conditions.append(Document.id != exclude_id)
        stmt = select(func.count()).select_from(Document).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return int(result.scalar_one()) > 0

    async def create(self, **kwargs) -> Document:
        doc = Document(**kwargs)
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)
        return doc

    async def add_version(self, version: DocumentVersion) -> DocumentVersion:
        self._session.add(version)
        await self._session.flush()
        return version

    async def soft_delete(self, document: Document) -> Document:
        document.deleted_at = datetime.now(timezone.utc)
        document.status = DocumentStatus.DELETED.value
        await self._session.flush()
        return document

    async def restore(self, document: Document) -> Document:
        document.deleted_at = None
        document.status = DocumentStatus.READY.value
        await self._session.flush()
        return document

    async def archive(self, document: Document) -> Document:
        document.status = DocumentStatus.ARCHIVED.value
        await self._session.flush()
        return document

    async def list_accessible(
        self,
        user: User,
        *,
        folder_id: uuid.UUID | None = None,
        status: str | None = None,
        extension: str | None = None,
        visibility: str | None = None,
        tag: str | None = None,
        owner_id: uuid.UUID | None = None,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Document], int]:
        is_admin = any(r.name == "admin" for r in (user.roles or []))
        access = [
            Document.owner_id == user.id,
            Document.visibility == DocumentVisibility.PUBLIC.value,
            Document.visibility == DocumentVisibility.COMPANY.value,
        ]
        if is_admin:
            access.append(Document.visibility == DocumentVisibility.ADMIN_ONLY.value)

        conditions = [
            Document.deleted_at.is_(None),
            Document.status != DocumentStatus.DELETED.value,
            or_(*access),
        ]
        if not include_archived:
            conditions.append(Document.status != DocumentStatus.ARCHIVED.value)
        if folder_id is not None:
            conditions.append(Document.folder_id == folder_id)
        if status:
            conditions.append(Document.status == status)
        if extension:
            conditions.append(Document.extension == extension.lower())
        if visibility:
            conditions.append(Document.visibility == visibility)
        if owner_id:
            conditions.append(Document.owner_id == owner_id)
        if tag:
            conditions.append(Document.tags.contains([tag.lower()]))
        if q:
            like = f"%{q.lower()}%"
            conditions.append(
                or_(
                    func.lower(Document.filename).like(like),
                    func.lower(Document.original_filename).like(like),
                    func.lower(func.coalesce(Document.description, "")).like(like),
                    Document.tags.contains([q.lower()]),
                )
            )
        if date_from:
            conditions.append(Document.created_at >= date_from)
        if date_to:
            conditions.append(Document.created_at <= date_to)
        if min_size is not None:
            conditions.append(Document.size >= min_size)
        if max_size is not None:
            conditions.append(Document.size <= max_size)

        where = and_(*conditions)
        count_stmt = select(func.count()).select_from(Document).where(where)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            self._base_query()
            .where(where)
            .order_by(Document.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total

    async def list_recent(
        self, user: User, *, limit: int = 20
    ) -> Sequence[Document]:
        items, _ = await self.list_accessible(user, limit=limit, offset=0)
        return items

    async def list_favorites(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[Document], int]:
        base = (
            select(Document)
            .join(DocumentFavorite, DocumentFavorite.document_id == Document.id)
            .where(
                DocumentFavorite.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.status != DocumentStatus.DELETED.value,
            )
            .options(selectinload(Document.owner), selectinload(Document.folder))
        )
        count_stmt = (
            select(func.count())
            .select_from(Document)
            .join(DocumentFavorite, DocumentFavorite.document_id == Document.id)
            .where(
                DocumentFavorite.user_id == user_id,
                Document.deleted_at.is_(None),
            )
        )
        total = int((await self._session.execute(count_stmt)).scalar_one())
        stmt = base.order_by(DocumentFavorite.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total

    async def is_favorited(self, user_id: uuid.UUID, document_id: uuid.UUID) -> bool:
        stmt = select(DocumentFavorite.id).where(
            DocumentFavorite.user_id == user_id,
            DocumentFavorite.document_id == document_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_favorite(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        if await self.is_favorited(user_id, document_id):
            return
        self._session.add(
            DocumentFavorite(user_id=user_id, document_id=document_id)
        )
        await self._session.flush()

    async def remove_favorite(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        stmt = select(DocumentFavorite).where(
            DocumentFavorite.user_id == user_id,
            DocumentFavorite.document_id == document_id,
        )
        fav = (await self._session.execute(stmt)).scalar_one_or_none()
        if fav:
            await self._session.delete(fav)
            await self._session.flush()

    @staticmethod
    def date_range_preset(preset: str | None) -> tuple[datetime | None, datetime | None]:
        if not preset:
            return None, None
        now = datetime.now(timezone.utc)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        key = preset.lower().replace(" ", "_")
        if key in {"today"}:
            return start_of_today, None
        if key in {"last_week", "week"}:
            return start_of_today - timedelta(days=7), None
        if key in {"last_month", "month"}:
            return start_of_today - timedelta(days=30), None
        return None, None
