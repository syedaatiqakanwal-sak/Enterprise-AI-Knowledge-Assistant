"""Document indexing pipeline: extract → chunk → embed → Qdrant."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import chunk_pages, recursive_chunk
from app.ai.embeddings import get_embedding_provider
from app.ai.parsers import ParserFactory
from app.ai.qdrant import get_qdrant_service
from app.core.config import settings
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.repositories.document_repository import DocumentRepository
from app.services.storage_service import get_storage_backend

logger = logging.getLogger(__name__)


class IndexingService:
    """Background-friendly indexing for a single document or bulk reindex."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._docs = DocumentRepository(session)
        self._storage = get_storage_backend()
        self._embeddings = get_embedding_provider()
        self._qdrant = get_qdrant_service()

    async def index_document(self, document_id: uuid.UUID) -> dict[str, Any]:
        started = time.perf_counter()
        document = await self._docs.get_by_id(document_id, include_deleted=True)
        if document is None:
            return {"success": False, "error": "not_found"}

        if document.extension.lower() not in ParserFactory.supported():
            # Images/ZIP etc. stay ready without text index
            document.status = DocumentStatus.READY.value
            await self._session.flush()
            return {
                "success": True,
                "skipped": True,
                "reason": f"no parser for .{document.extension}",
            }

        document.status = DocumentStatus.PROCESSING.value
        await self._session.flush()

        try:
            raw = await self._storage.open(document.storage_path)
            extracted = ParserFactory.get(document.extension).extract(
                raw, document.filename
            )
            if extracted.pages:
                chunks = chunk_pages(
                    [(p.page, p.text) for p in extracted.pages if p.text.strip()]
                )
            else:
                chunks = recursive_chunk(extracted.text)

            if not chunks:
                document.status = DocumentStatus.READY.value
                await self._session.flush()
                return {"success": True, "chunks": 0, "message": "empty text"}

            self._qdrant.ensure_collection(self._embeddings.dimension)
            # Remove prior vectors for reindex
            self._qdrant.delete_document(str(document.id))

            texts = [c.text for c in chunks]
            embed_t0 = time.perf_counter()
            vectors = self._embeddings.embed_documents(texts)
            embed_ms = (time.perf_counter() - embed_t0) * 1000

            now = datetime.now(timezone.utc).isoformat()
            payloads: list[dict[str, Any]] = []
            ids: list[str] = []
            for ch, _vec in zip(chunks, vectors, strict=True):
                ids.append(str(uuid.uuid5(document.id, ch.chunk_id)))
                payloads.append(
                    {
                        "document_id": str(document.id),
                        "company_id": str(document.company_id)
                        if document.company_id
                        else None,
                        "owner_id": str(document.owner_id),
                        "chunk_id": ch.chunk_id,
                        "chunk_index": ch.chunk_index,
                        "page": ch.page,
                        "position": ch.position,
                        "filename": document.filename,
                        "folder_id": str(document.folder_id)
                        if document.folder_id
                        else None,
                        "tags": list(document.tags or []),
                        "visibility": document.visibility,
                        "created_at": now,
                        "text": ch.text,
                        "extension": document.extension,
                    }
                )

            self._qdrant.upsert_chunks(
                vectors=vectors, payloads=payloads, ids=ids
            )
            document.status = DocumentStatus.INDEXED.value
            await self._session.flush()

            total_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "Indexed document %s chunks=%s embed_ms=%.1f total_ms=%.1f model=%s",
                document.id,
                len(chunks),
                embed_ms,
                total_ms,
                self._embeddings.model_name,
            )
            return {
                "success": True,
                "document_id": str(document.id),
                "chunks": len(chunks),
                "embedding_ms": round(embed_ms, 2),
                "total_ms": round(total_ms, 2),
                "embedding_model": self._embeddings.model_name,
            }
        except Exception as exc:
            logger.exception("Indexing failed for %s", document_id)
            document.status = DocumentStatus.FAILED.value
            await self._session.flush()
            return {"success": False, "error": str(exc)}

    async def reindex_all(self, *, owner_id: uuid.UUID | None = None) -> dict[str, Any]:
        from sqlalchemy import select

        from app.models.document import Document as DocModel
        from app.models.enums import DocumentStatus as DS

        stmt = select(DocModel).where(
            DocModel.deleted_at.is_(None),
            DocModel.status.in_(
                [
                    DS.READY.value,
                    DS.INDEXED.value,
                    DS.FAILED.value,
                    DS.PROCESSING.value,
                ]
            ),
        )
        if owner_id:
            stmt = stmt.where(DocModel.owner_id == owner_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        results = []
        for doc in rows:
            results.append(await self.index_document(doc.id))
        ok = sum(1 for r in results if r.get("success"))
        return {"total": len(results), "success": ok, "results": results}

    async def delete_embeddings(self, document_id: uuid.UUID) -> None:
        self._qdrant.delete_document(str(document_id))
