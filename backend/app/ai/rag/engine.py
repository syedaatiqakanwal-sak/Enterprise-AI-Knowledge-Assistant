"""RAG retriever + grounded answer generation with citations."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedding_provider
from app.ai.llm import SYSTEM_PROMPT, get_llm_provider
from app.ai.qdrant import get_qdrant_service
from app.core.config import settings
from app.models.enums import DocumentVisibility
from app.models.user import User
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    document_id: str
    filename: str
    page: int | None
    chunk_index: int
    confidence: float
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "confidence": round(self.confidence, 4),
            "snippet": self.snippet[:280],
        }


@dataclass
class RAGResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    grounded: bool = True


class RAGEngine:
    """Retrieve → prompt → LLM with permission-aware filters."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._docs = DocumentRepository(session)
        self._embeddings = get_embedding_provider()
        self._qdrant = get_qdrant_service()
        self._llm = get_llm_provider()

    async def _allowed_document_ids(self, user: User) -> list[str] | None:
        """
        Return None when no restriction needed (admin sees all indexed),
        otherwise an allow-list of document IDs.
        """
        is_admin = any(r.name == "admin" for r in (user.roles or []))
        items, _ = await self._docs.list_accessible(
            user,
            include_archived=False,
            limit=500,
            offset=0,
            status=None,
        )
        # Prefer indexed; still allow ready for edge cases
        ids = [
            str(d.id)
            for d in items
            if d.status in {"indexed", "ready", "processing"}
            or (is_admin and d.visibility == DocumentVisibility.ADMIN_ONLY.value)
        ]
        return ids

    async def retrieve(
        self,
        user: User,
        query: str,
        *,
        top_k: int | None = None,
        folder_id: uuid.UUID | None = None,
        tag: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> tuple[list[Citation], dict[str, float]]:
        t0 = time.perf_counter()
        vector = self._embeddings.embed_query(query)
        embed_ms = (time.perf_counter() - t0) * 1000

        allowed = await self._allowed_document_ids(user)
        filters: dict[str, Any] = {}
        if allowed is not None:
            filters["document_ids"] = allowed
        if folder_id:
            filters["folder_id"] = str(folder_id)
        if tag:
            filters["tags"] = [tag.lower()]
        if document_id:
            filters["document_ids"] = [str(document_id)]

        t1 = time.perf_counter()
        hits = self._qdrant.search(
            vector,
            top_k=top_k or settings.RETRIEVAL_TOP_K,
            filters=filters or None,
        )
        retrieval_ms = (time.perf_counter() - t1) * 1000

        citations = [
            Citation(
                document_id=str(h.payload.get("document_id")),
                filename=str(h.payload.get("filename", "document")),
                page=h.payload.get("page"),
                chunk_index=int(h.payload.get("chunk_index") or 0),
                confidence=float(h.score),
                snippet=h.text,
            )
            for h in hits
        ]
        return citations, {
            "embedding_ms": round(embed_ms, 2),
            "retrieval_ms": round(retrieval_ms, 2),
        }

    def _format_context(self, citations: list[Citation]) -> str:
        if not citations:
            return "(no relevant passages)"
        blocks = []
        for i, c in enumerate(citations, start=1):
            page = f"page {c.page}" if c.page is not None else "page ?"
            blocks.append(
                f"[{i}] {c.filename} | {page} | chunk {c.chunk_index} "
                f"| score={c.confidence:.3f}\n{c.snippet}"
            )
        return "\n\n".join(blocks)

    async def answer(
        self,
        user: User,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
        folder_id: uuid.UUID | None = None,
        tag: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> RAGResult:
        citations, metrics = await self.retrieve(
            user,
            question,
            folder_id=folder_id,
            tag=tag,
            document_id=document_id,
        )
        context = self._format_context(citations)

        t0 = time.perf_counter()
        if not citations:
            answer = (
                "I couldn't find information about that in your uploaded documents."
            )
            grounded = False
        else:
            answer = await self._llm.generate(
                system=SYSTEM_PROMPT,
                context=context,
                question=question,
                history=history,
            )
            grounded = True
        llm_ms = (time.perf_counter() - t0) * 1000
        metrics["llm_ms"] = round(llm_ms, 2)
        metrics["total_ms"] = round(
            metrics.get("embedding_ms", 0)
            + metrics.get("retrieval_ms", 0)
            + llm_ms,
            2,
        )
        return RAGResult(
            answer=answer,
            citations=citations,
            metrics=metrics,
            grounded=grounded,
        )

    async def stream_answer(
        self,
        user: User,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
        folder_id: uuid.UUID | None = None,
        tag: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE-friendly event dicts: meta → token* → done."""
        citations, metrics = await self.retrieve(
            user,
            question,
            folder_id=folder_id,
            tag=tag,
            document_id=document_id,
        )
        yield {
            "event": "meta",
            "data": {
                "citations": [c.to_dict() for c in citations],
                "metrics": metrics,
            },
        }
        context = self._format_context(citations)
        if not citations:
            msg = (
                "I couldn't find information about that in your uploaded documents."
            )
            yield {"event": "token", "data": {"token": msg}}
            yield {
                "event": "done",
                "data": {"answer": msg, "citations": [], "metrics": metrics},
            }
            return

        t0 = time.perf_counter()
        parts: list[str] = []
        async for token in self._llm.stream(
            system=SYSTEM_PROMPT,
            context=context,
            question=question,
            history=history,
        ):
            parts.append(token)
            yield {"event": "token", "data": {"token": token}}
        metrics["llm_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        metrics["total_ms"] = round(
            metrics.get("embedding_ms", 0)
            + metrics.get("retrieval_ms", 0)
            + metrics["llm_ms"],
            2,
        )
        answer = "".join(parts)
        yield {
            "event": "done",
            "data": {
                "answer": answer,
                "citations": [c.to_dict() for c in citations],
                "metrics": metrics,
            },
        }
