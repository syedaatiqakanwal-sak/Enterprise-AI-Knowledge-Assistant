"""
Document management API routes — Module 5 DMS.

No RAG / embeddings / LLM — storage + metadata only.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.middlewares.dependencies import get_current_user, require_permissions
from app.models.user import User
from app.schemas.document import (
    CopyMoveRequest,
    DocumentListOut,
    DocumentOut,
    DocumentUpdate,
    DocumentUploadResult,
    PreviewOut,
)
from app.schemas.response import ApiResponse
from app.services.document_service import DocumentService

router = APIRouter()


async def _enqueue_index(document_id: uuid.UUID) -> None:
    from app.api.v1.search import _index_in_background

    await _index_in_background(document_id)


@router.post(
    "/upload",
    response_model=ApiResponse[DocumentUploadResult],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    folder_id: Optional[uuid.UUID] = Form(default=None),
    visibility: str = Form(default="private"),
    description: Optional[str] = Form(default=None),
    tags: Optional[str] = Form(default=None, description="Comma-separated tags"),
    upload_id: Optional[str] = Form(default=None),
    chunk_index: Optional[int] = Form(default=None),
    chunk_total: Optional[int] = Form(default=None),
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentUploadResult]:
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    result = await DocumentService(db).upload(
        current_user,
        file,
        folder_id=folder_id,
        visibility=visibility,
        description=description,
        tags=tag_list,
        upload_id=upload_id,
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )
    if settings.AUTO_INDEX_ON_UPLOAD:
        background.add_task(_enqueue_index, uuid.UUID(str(result.document.id)))
    return ApiResponse.ok(result, message=result.message)


@router.get(
    "/search",
    response_model=ApiResponse[DocumentListOut],
    summary="Search documents",
)
async def search_documents(
    q: str = Query(..., min_length=1),
    folder_id: Optional[uuid.UUID] = None,
    extension: Optional[str] = None,
    file_type: Optional[str] = Query(default=None, description="pdf|images|documents"),
    tag: Optional[str] = None,
    date_preset: Optional[str] = Query(default=None, description="today|last_week|last_month"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentListOut]:
    data = await DocumentService(db).search(
        current_user,
        q=q,
        folder_id=folder_id,
        extension=extension,
        file_type=file_type,
        tag=tag,
        date_preset=date_preset,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApiResponse.ok(data, message="Search results")


@router.get(
    "/recent",
    response_model=ApiResponse[DocumentListOut],
    summary="Recent documents",
)
async def recent_documents(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentListOut]:
    data = await DocumentService(db).recent(current_user, limit=limit)
    return ApiResponse.ok(data, message="Recent documents")


@router.get(
    "/favorites",
    response_model=ApiResponse[DocumentListOut],
    summary="Favorite documents",
)
async def favorite_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentListOut]:
    data = await DocumentService(db).favorites(
        current_user, limit=limit, offset=offset
    )
    return ApiResponse.ok(data, message="Favorite documents")


@router.get(
    "",
    response_model=ApiResponse[DocumentListOut],
    summary="List documents",
)
async def list_documents(
    folder_id: Optional[uuid.UUID] = None,
    extension: Optional[str] = None,
    file_type: Optional[str] = None,
    tag: Optional[str] = None,
    visibility: Optional[str] = None,
    owner_id: Optional[uuid.UUID] = None,
    q: Optional[str] = None,
    date_preset: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    include_archived: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentListOut]:
    data = await DocumentService(db).list_documents(
        current_user,
        folder_id=folder_id,
        extension=extension,
        file_type=file_type,
        tag=tag,
        visibility=visibility,
        owner_id=owner_id,
        q=q,
        date_preset=date_preset,
        status_filter=status_filter,
        min_size=min_size,
        max_size=max_size,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ApiResponse.ok(data, message="Documents retrieved")


@router.get(
    "/{document_id}",
    response_model=ApiResponse[DocumentOut],
    summary="Get document metadata",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).get(current_user, document_id)
    return ApiResponse.ok(data, message="Document retrieved")


@router.put(
    "/{document_id}",
    response_model=ApiResponse[DocumentOut],
    summary="Update document (rename, tags, move, visibility)",
)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).update(current_user, document_id, payload)
    return ApiResponse.ok(data, message="Document updated")


@router.delete(
    "/{document_id}",
    response_model=ApiResponse[None],
    summary="Soft-delete a document",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await DocumentService(db).soft_delete(current_user, document_id)
    return ApiResponse.ok(None, message="Document deleted")


@router.post(
    "/{document_id}/restore",
    response_model=ApiResponse[DocumentOut],
    summary="Restore a soft-deleted document",
)
async def restore_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).restore(current_user, document_id)
    return ApiResponse.ok(data, message="Document restored")


@router.post(
    "/{document_id}/archive",
    response_model=ApiResponse[DocumentOut],
    summary="Archive a document",
)
async def archive_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).archive(current_user, document_id)
    return ApiResponse.ok(data, message="Document archived")


@router.post(
    "/{document_id}/favorite",
    response_model=ApiResponse[DocumentOut],
    summary="Toggle favorite / star",
)
async def favorite_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).toggle_favorite(current_user, document_id)
    return ApiResponse.ok(data, message="Favorite updated")


@router.get(
    "/{document_id}/preview",
    response_model=ApiResponse[PreviewOut],
    summary="Preview document content / metadata",
)
async def preview_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PreviewOut]:
    data = await DocumentService(db).preview(current_user, document_id)
    return ApiResponse.ok(data, message="Preview ready")


@router.get(
    "/{document_id}/download",
    summary="Download document binary",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    document, data = await DocumentService(db).download_bytes(
        current_user, document_id
    )
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"'
        },
    )


@router.post(
    "/{document_id}/copy",
    response_model=ApiResponse[DocumentOut],
    summary="Copy a document",
)
async def copy_document(
    document_id: uuid.UUID,
    payload: CopyMoveRequest,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).copy(current_user, document_id, payload)
    return ApiResponse.ok(data, message="Document copied")


@router.post(
    "/{document_id}/move",
    response_model=ApiResponse[DocumentOut],
    summary="Move a document to another folder",
)
async def move_document(
    document_id: uuid.UUID,
    payload: CopyMoveRequest,
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentOut]:
    data = await DocumentService(db).move(current_user, document_id, payload)
    return ApiResponse.ok(data, message="Document moved")
