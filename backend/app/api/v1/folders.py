"""Folder management API routes — Module 5 DMS."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_permissions
from app.models.user import User
from app.schemas.document import FolderCreate, FolderOut, FolderTreeOut, FolderUpdate
from app.schemas.response import ApiResponse
from app.services.folder_service import FolderService

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[FolderOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create folder",
)
async def create_folder(
    payload: FolderCreate,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FolderOut]:
    data = await FolderService(db).create(current_user, payload)
    return ApiResponse.ok(data, message="Folder created")


@router.get(
    "",
    response_model=ApiResponse[FolderTreeOut],
    summary="List folders (optionally under a parent)",
)
async def list_folders(
    parent_id: Optional[uuid.UUID] = Query(default=None),
    flat: bool = Query(default=False, description="Return all folders flat"),
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FolderTreeOut]:
    service = FolderService(db)
    if flat:
        folders = await service.list_all(current_user)
        data = FolderTreeOut(folders=folders, breadcrumb=[])
    else:
        data = await service.list_tree(current_user, parent_id=parent_id)
    return ApiResponse.ok(data, message="Folders retrieved")


@router.put(
    "/{folder_id}",
    response_model=ApiResponse[FolderOut],
    summary="Rename / move folder",
)
async def update_folder(
    folder_id: uuid.UUID,
    payload: FolderUpdate,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FolderOut]:
    data = await FolderService(db).update(current_user, folder_id, payload)
    return ApiResponse.ok(data, message="Folder updated")


@router.delete(
    "/{folder_id}",
    response_model=ApiResponse[None],
    summary="Soft-delete folder",
)
async def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await FolderService(db).delete(current_user, folder_id)
    return ApiResponse.ok(None, message="Folder deleted")
