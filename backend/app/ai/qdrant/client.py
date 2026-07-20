"""Qdrant vector store with in-memory fallback for local/dev/tests."""

from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VectorHit:
    id: str
    score: float
    payload: dict[str, Any]
    text: str


@dataclass
class _MemPoint:
    id: str
    vector: list[float]
    payload: dict[str, Any]


class InMemoryVectorStore:
    """Simple cosine-similarity store used when Qdrant is unavailable."""

    def __init__(self) -> None:
        self._points: list[_MemPoint] = []
        self._lock = threading.Lock()

    def upsert(self, points: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        with self._lock:
            ids = {p[0] for p in points}
            self._points = [p for p in self._points if p.id not in ids]
            for pid, vec, payload in points:
                self._points.append(_MemPoint(pid, vec, payload))

    def delete_by_document(self, document_id: str) -> None:
        with self._lock:
            self._points = [
                p
                for p in self._points
                if str(p.payload.get("document_id")) != str(document_id)
            ]

    def search(
        self,
        vector: list[float],
        *,
        top_k: int = 5,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        with self._lock:
            candidates = list(self._points)
        if filters:
            candidates = [
                p for p in candidates if self._match(p.payload, filters)
            ]
        scored: list[VectorHit] = []
        for p in candidates:
            score = _cosine(vector, p.vector)
            if score < score_threshold:
                continue
            scored.append(
                VectorHit(
                    id=p.id,
                    score=score,
                    payload=p.payload,
                    text=str(p.payload.get("text", "")),
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _match(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if value is None:
                continue
            if key == "document_ids":
                if str(payload.get("document_id")) not in {str(v) for v in value}:
                    return False
                continue
            if key == "tags":
                tags = payload.get("tags") or []
                if not any(t in tags for t in value):
                    return False
                continue
            if str(payload.get(key)) != str(value):
                return False
        return True


_MEMORY = InMemoryVectorStore()


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
    return dot / (na * nb)


class QdrantService:
    """
    Vector persistence for ``company_documents``.

    Falls back to in-memory store when Qdrant is unreachable and
    ``QDRANT_USE_MEMORY_FALLBACK`` is enabled.
    """

    def __init__(self) -> None:
        self._client = None
        self._use_memory = False
        self._dim: int | None = None
        self._ensure_client()

    def _ensure_client(self) -> None:
        try:
            from qdrant_client import QdrantClient

            kwargs: dict[str, Any] = {
                "url": settings.qdrant_url,
                "timeout": 5,
            }
            if settings.QDRANT_API_KEY:
                kwargs["api_key"] = settings.QDRANT_API_KEY
            client = QdrantClient(**kwargs)
            client.get_collections()
            self._client = client
            self._use_memory = False
            logger.info("Connected to Qdrant at %s", settings.qdrant_url)
        except Exception as exc:
            logger.warning(
                "Qdrant unavailable (%s) — using in-memory vector store", exc
            )
            self._client = None
            self._use_memory = True

    def ensure_collection(self, dimension: int) -> None:
        self._dim = dimension
        if self._use_memory or self._client is None:
            return
        from qdrant_client.http import models as qm

        name = settings.QDRANT_COLLECTION
        existing = {c.name for c in self._client.get_collections().collections}
        if name in existing:
            return
        self._client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(
                size=dimension, distance=qm.Distance.COSINE
            ),
        )
        logger.info("Created Qdrant collection %s (dim=%s)", name, dimension)

    def upsert_chunks(
        self,
        *,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> int:
        if not vectors:
            return 0
        point_ids = ids or [str(uuid.uuid4()) for _ in vectors]
        if self._use_memory or self._client is None:
            _MEMORY.upsert(
                list(zip(point_ids, vectors, payloads, strict=True))
            )
            return len(vectors)

        from qdrant_client.http import models as qm

        points = [
            qm.PointStruct(id=pid if _is_uuid(pid) else str(uuid.uuid5(uuid.NAMESPACE_URL, pid)), vector=vec, payload=payload)
            for pid, vec, payload in zip(point_ids, vectors, payloads, strict=True)
        ]
        self._client.upsert(
            collection_name=settings.QDRANT_COLLECTION, points=points
        )
        return len(points)

    def delete_document(self, document_id: str) -> None:
        if self._use_memory or self._client is None:
            _MEMORY.delete_by_document(document_id)
            return
        from qdrant_client.http import models as qm

        self._client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id",
                            match=qm.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )

    def search(
        self,
        vector: list[float],
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        score_threshold = (
            score_threshold
            if score_threshold is not None
            else settings.RETRIEVAL_SCORE_THRESHOLD
        )
        if self._use_memory or self._client is None:
            return _MEMORY.search(
                vector,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters,
            )

        from qdrant_client.http import models as qm

        qfilter = _build_qdrant_filter(filters) if filters else None
        results = self._client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=qfilter,
        )
        hits: list[VectorHit] = []
        for r in results:
            payload = r.payload or {}
            hits.append(
                VectorHit(
                    id=str(r.id),
                    score=float(r.score or 0.0),
                    payload=payload,
                    text=str(payload.get("text", "")),
                )
            )
        return hits


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _build_qdrant_filter(filters: dict[str, Any]):
    from qdrant_client.http import models as qm

    must = []
    for key, value in filters.items():
        if value is None:
            continue
        if key == "document_ids":
            must.append(
                qm.FieldCondition(
                    key="document_id",
                    match=qm.MatchAny(any=[str(v) for v in value]),
                )
            )
        elif key == "tags":
            must.append(
                qm.FieldCondition(
                    key="tags",
                    match=qm.MatchAny(any=list(value)),
                )
            )
        else:
            must.append(
                qm.FieldCondition(
                    key=key, match=qm.MatchValue(value=value)
                )
            )
    return qm.Filter(must=must) if must else None


_qdrant_singleton: QdrantService | None = None


def get_qdrant_service() -> QdrantService:
    global _qdrant_singleton
    if _qdrant_singleton is None:
        _qdrant_singleton = QdrantService()
    return _qdrant_singleton
