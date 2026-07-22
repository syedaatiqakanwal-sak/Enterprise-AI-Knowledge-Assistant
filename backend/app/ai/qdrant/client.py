"""Qdrant vector store with in-memory fallback for local/dev/tests."""

from __future__ import annotations

import logging
import math
import pickle
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


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


def _memory_store_path() -> Path:
    root = Path(settings.STORAGE_LOCAL_ROOT).resolve().parent / "vectors"
    root.mkdir(parents=True, exist_ok=True)
    return root / "memory_store.pkl"


class InMemoryVectorStore:
    """Cosine + keyword store used when Qdrant is unavailable.

    Persists to disk so indexed documents survive API restarts (common in
    local Windows/dev without Docker Qdrant).
    """

    def __init__(self, *, persist_path: Path | None = None) -> None:
        self._points: list[_MemPoint] = []
        self._lock = threading.Lock()
        self._persist_path = persist_path or _memory_store_path()
        self._load()

    def _load(self) -> None:
        path = self._persist_path
        if not path.exists():
            return
        try:
            with path.open("rb") as fh:
                raw = pickle.load(fh)
            points: list[_MemPoint] = []
            for item in raw or []:
                points.append(
                    _MemPoint(
                        id=str(item["id"]),
                        vector=list(item["vector"]),
                        payload=dict(item["payload"]),
                    )
                )
            self._points = points
            logger.info(
                "Loaded %s in-memory vector points from %s",
                len(self._points),
                path,
            )
        except Exception:
            logger.exception("Failed to load vector store from %s", path)

    def _save(self) -> None:
        path = self._persist_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                {"id": p.id, "vector": p.vector, "payload": p.payload}
                for p in self._points
            ]
            tmp = path.with_suffix(".pkl.tmp")
            with tmp.open("wb") as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(path)
        except Exception:
            logger.exception("Failed to persist vector store to %s", path)

    def upsert(self, points: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        with self._lock:
            ids = {p[0] for p in points}
            self._points = [p for p in self._points if p.id not in ids]
            for pid, vec, payload in points:
                self._points.append(_MemPoint(pid, vec, payload))
            self._save()

    def delete_by_document(self, document_id: str) -> None:
        with self._lock:
            self._points = [
                p
                for p in self._points
                if str(p.payload.get("document_id")) != str(document_id)
            ]
            self._save()

    def count(self) -> int:
        with self._lock:
            return len(self._points)

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

    def keyword_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Token-overlap ranking — helps when mock hash embeddings miss paraphrases."""
        q_tokens = set(_TOKEN_RE.findall(query.lower()))
        if not q_tokens:
            return []
        with self._lock:
            candidates = list(self._points)
        if filters:
            candidates = [
                p for p in candidates if self._match(p.payload, filters)
            ]
        scored: list[VectorHit] = []
        for p in candidates:
            text = str(p.payload.get("text", ""))
            if not text:
                continue
            t_tokens = set(_TOKEN_RE.findall(text.lower()))
            if not t_tokens:
                continue
            overlap = q_tokens & t_tokens
            if not overlap:
                continue
            # Prefer denser overlap; mild boost for rarer multi-token matches
            score = len(overlap) / len(q_tokens)
            if len(overlap) >= 2:
                score = min(1.0, score + 0.15)
            scored.append(
                VectorHit(
                    id=p.id,
                    score=score,
                    payload=p.payload,
                    text=text,
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
                # Empty allow-list must match nothing (not everything)
                allowed = {str(v) for v in value}
                if not allowed or str(payload.get("document_id")) not in allowed:
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
        query: str | None = None,
    ) -> list[VectorHit]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        score_threshold = (
            score_threshold
            if score_threshold is not None
            else settings.RETRIEVAL_SCORE_THRESHOLD
        )
        if self._use_memory or self._client is None:
            hits = _MEMORY.search(
                vector,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters,
            )
            # Keyword fallback when vectors miss (mock embeddings / empty store)
            if query and (not hits or (settings.EMBEDDING_PROVIDER or "").lower() == "mock"):
                kw = _MEMORY.keyword_search(query, top_k=top_k, filters=filters)
                hits = _merge_hits(hits, kw, top_k=top_k)
            return hits

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

    def keyword_search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Lexical search over the in-memory store (dev fallback)."""
        return _MEMORY.keyword_search(
            query,
            top_k=top_k or settings.RETRIEVAL_TOP_K,
            filters=filters,
        )

    @property
    def using_memory(self) -> bool:
        return self._use_memory or self._client is None

    def memory_count(self) -> int:
        return _MEMORY.count()

    def count_points(self) -> int:
        """Return active vector count (Qdrant collection or in-memory store)."""
        if self._use_memory or self._client is None:
            return _MEMORY.count()
        try:
            info = self._client.get_collection(settings.QDRANT_COLLECTION)
            return int(
                getattr(info, "points_count", None)
                or getattr(info, "vectors_count", None)
                or 0
            )
        except Exception:  # noqa: BLE001
            return _MEMORY.count()


def _merge_hits(
    primary: list[VectorHit],
    secondary: list[VectorHit],
    *,
    top_k: int,
) -> list[VectorHit]:
    """Prefer higher scores; keep unique chunk ids."""
    by_id: dict[str, VectorHit] = {}
    for hit in primary + secondary:
        prev = by_id.get(hit.id)
        if prev is None or hit.score > prev.score:
            by_id[hit.id] = hit
    merged = sorted(by_id.values(), key=lambda h: h.score, reverse=True)
    return merged[:top_k]


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
