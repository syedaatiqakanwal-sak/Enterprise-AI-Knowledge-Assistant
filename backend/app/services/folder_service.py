"""Folder business logic for Module 5 DMS."""

from __future__ import annotations

import uuid

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.folder import Folder
from app.models.user import User
from app.repositories.folder_repository import FolderRepository
from app.schemas.document import (
    BreadcrumbItem,
    FolderCreate,
    FolderOut,
    FolderTreeOut,
    FolderUpdate,
)
from app.utils.sanitize import sanitize_text


class FolderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._folders = FolderRepository(session)

    def _to_out(self, folder: Folder) -> FolderOut:
        return FolderOut.model_validate(folder)

    async def create(self, user: User, payload: FolderCreate) -> FolderOut:
        name = sanitize_text(payload.name, max_length=255)
        if payload.parent_id:
            parent = await self._folders.get_by_id(payload.parent_id)
            if parent is None or parent.owner_id != user.id:
                raise AppException(
                    "Parent folder not found",
                    code="FOLDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
        existing = await self._folders.find_sibling_by_name(
            user.id, payload.parent_id, name
        )
        if existing:
            raise AppException(
                "A folder with this name already exists here",
                code="FOLDER_EXISTS",
                status_code=status.HTTP_409_CONFLICT,
            )
        folder = await self._folders.create(
            name=name,
            owner_id=user.id,
            parent_id=payload.parent_id,
            description=(
                sanitize_text(payload.description, max_length=2000)
                if payload.description
                else None
            ),
        )
        return self._to_out(folder)

    async def list_tree(
        self,
        user: User,
        *,
        parent_id: uuid.UUID | None = None,
    ) -> FolderTreeOut:
        folders = await self._folders.list_for_owner(user.id, parent_id=parent_id)
        breadcrumb: list[BreadcrumbItem] = []
        if parent_id:
            current = await self._folders.get_by_id(parent_id)
            if current is None or current.owner_id != user.id:
                raise AppException(
                    "Folder not found",
                    code="FOLDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            ancestors = await self._folders.get_ancestors(current)
            breadcrumb = [
                BreadcrumbItem(id=f.id, name=f.name) for f in ancestors
            ]
        return FolderTreeOut(
            folders=[self._to_out(f) for f in folders],
            breadcrumb=breadcrumb,
        )

    async def list_all(self, user: User) -> list[FolderOut]:
        folders = await self._folders.list_all_for_owner(user.id)
        return [self._to_out(f) for f in folders]

    async def update(
        self, user: User, folder_id: uuid.UUID, payload: FolderUpdate
    ) -> FolderOut:
        folder = await self._folders.get_by_id(folder_id)
        if folder is None or folder.owner_id != user.id:
            raise AppException(
                "Folder not found",
                code="FOLDER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if payload.name is not None:
            name = sanitize_text(payload.name, max_length=255)
            parent_id = folder.parent_id
            if payload.move_to_root:
                parent_id = None
            elif payload.parent_id is not None:
                parent_id = payload.parent_id
            clash = await self._folders.find_sibling_by_name(
                user.id, parent_id, name, exclude_id=folder.id
            )
            if clash:
                raise AppException(
                    "A folder with this name already exists here",
                    code="FOLDER_EXISTS",
                    status_code=status.HTTP_409_CONFLICT,
                )
            folder.name = name

        if payload.move_to_root:
            folder.parent_id = None
        elif payload.parent_id is not None:
            if payload.parent_id == folder.id:
                raise AppException(
                    "Cannot move a folder into itself",
                    code="INVALID_MOVE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            parent = await self._folders.get_by_id(payload.parent_id)
            if parent is None or parent.owner_id != user.id:
                raise AppException(
                    "Target parent folder not found",
                    code="FOLDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            # Prevent cycles: target must not be a descendant
            ancestors = await self._folders.get_ancestors(parent)
            if any(a.id == folder.id for a in ancestors):
                raise AppException(
                    "Cannot move a folder into its descendant",
                    code="INVALID_MOVE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            folder.parent_id = payload.parent_id

        if payload.description is not None:
            folder.description = sanitize_text(payload.description, max_length=2000)

        await self._session.flush()
        await self._session.refresh(folder)
        return self._to_out(folder)

    async def delete(self, user: User, folder_id: uuid.UUID) -> None:
        folder = await self._folders.get_by_id(folder_id)
        if folder is None or folder.owner_id != user.id:
            raise AppException(
                "Folder not found",
                code="FOLDER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        children = await self._folders.list_for_owner(user.id, parent_id=folder.id)
        if children:
            raise AppException(
                "Folder is not empty — remove child folders first",
                code="FOLDER_NOT_EMPTY",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._folders.soft_delete(folder)
