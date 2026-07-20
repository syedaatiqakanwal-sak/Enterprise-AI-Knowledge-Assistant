"""Semantic search + document indexing endpoints — Module 6."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.indexing import IndexingService
from app.ai.rag import RAGEngine
from app.db.postgres import AsyncSessionLocal
from app.db.session import get_db
from app.middlewares.dependencies import get_current_user, require_permissions
from app.models.user import User
from app.schemas.chat import (
    IndexResultOut,
    SemanticSearchHit,
    SemanticSearchOut,
    SemanticSearchRequest,
)
from app.schemas.response import ApiResponse

router = APIRouter()


async def _index_in_background(document_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await IndexingService(session).index_document(document_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@router.post(
    "/search",
    response_model=ApiResponse[SemanticSearchOut],
    summary="Semantic search across indexed documents",
)
async def semantic_search(
    payload: SemanticSearchRequest,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SemanticSearchOut]:
    citations, metrics = await RAGEngine(db).retrieve(
        current_user,
        payload.q,
        top_k=payload.top_k,
        folder_id=payload.folder_id,
        tag=payload.tag,
        document_id=payload.document_id,
    )
    data = SemanticSearchOut(
        hits=[
            SemanticSearchHit(
                document_id=c.document_id,
                filename=c.filename,
                page=c.page,
                chunk_index=c.chunk_index,
                confidence=round(c.confidence, 4),
                snippet=c.snippet[:500],
            )
            for c in citations
        ],
        metrics=metrics,
    )
    return ApiResponse.ok(data, message="Semantic search results")


@router.get(
    "/search",
    response_model=ApiResponse[SemanticSearchOut],
    summary="Semantic search (GET)",
)
async def semantic_search_get(
    q: str = Query(..., min_length=1),
    folder_id: Optional[uuid.UUID] = None,
    document_id: Optional[uuid.UUID] = None,
    tag: Optional[str] = None,
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SemanticSearchOut]:
    return await semantic_search(
        SemanticSearchRequest(
            q=q,
            folder_id=folder_id,
            document_id=document_id,
            tag=tag,
            top_k=top_k,
        ),
        current_user,
        db,
    )


# Document indexing routes are mounted under /documents via documents router extensions
index_router = APIRouter()


@index_router.post(
    "/{document_id}/index",
    response_model=ApiResponse[IndexResultOut],
    summary="Index or reindex a document into Qdrant",
)
async def index_document(
    document_id: uuid.UUID,
    background: BackgroundTasks,
    sync: bool = Query(False, description="Run inline instead of background"),
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[IndexResultOut]:
    _ = current_user
    if sync:
        result = await IndexingService(db).index_document(document_id)
        return ApiResponse.ok(IndexResultOut(**result), message="Indexing complete")
    background.add_task(_index_in_background, document_id)
    return ApiResponse.ok(
        IndexResultOut(success=True, document_id=str(document_id)),
        message="Indexing queued",
    )


@index_router.post(
    "/reindex",
    response_model=ApiResponse[dict],
    summary="Reindex all accessible documents",
)
async def reindex_all(
    background: BackgroundTasks,
    sync: bool = Query(False),
    current_user: User = Depends(require_permissions("documents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    if sync:
        result = await IndexingService(db).reindex_all(owner_id=current_user.id)
        return ApiResponse.ok(result, message="Reindex complete")

    async def _job(uid: uuid.UUID) -> None:
        async with AsyncSessionLocal() as session:
            try:
                await IndexingService(session).reindex_all(owner_id=uid)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    background.add_task(_job, current_user.id)
    return ApiResponse.ok({"queued": True}, message="Reindex queued")
