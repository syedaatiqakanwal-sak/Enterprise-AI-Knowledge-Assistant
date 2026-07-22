"""Embedding provider abstraction — swap models without changing callers."""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)

# Process-wide lock so concurrent requests share one model load/encode path
_MODEL_LOCK = threading.RLock()


class EmbeddingProvider(ABC):
    """Interface for text → vector embedding backends."""

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def status(self) -> dict[str, Any]:
        """Runtime snapshot for Admin / system probes."""
        return {
            "provider": "unknown",
            "model": self.model_name,
            "dimension": self.dimension,
            "loaded": False,
            "cached": False,
            "memory_mb": None,
            "load_time_ms": None,
            "loaded_at": None,
            "error": None,
        }


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash embeddings for tests / offline mode."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "mock-hash-embedding"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._hash_vec(t) for t in texts]

    def _hash_vec(self, text: str) -> list[float]:
        vals = [0.0] * self._dim
        tokens = text.lower().split()
        for tok in tokens or [text]:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(0, min(len(digest), self._dim // 4)):
                idx = digest[i] % self._dim
                vals[idx] += 1.0
        for i, ch in enumerate(text.lower()[:200]):
            vals[ord(ch) % self._dim] += 0.15
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]

    def status(self) -> dict[str, Any]:
        return {
            "provider": "mock",
            "model": self.model_name,
            "dimension": self.dimension,
            "loaded": True,
            "cached": True,
            "memory_mb": 0.0,
            "load_time_ms": 0.0,
            "loaded_at": None,
            "error": None,
        }


class _LRUEmbedCache:
    """Bounded cache for query / short-document embeddings."""

    def __init__(self, maxsize: int = 2048) -> None:
        self._maxsize = max(16, maxsize)
        self._data: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> list[float] | None:
        with self._lock:
            if key not in self._data:
                self.misses += 1
                return None
            self.hits += 1
            self._data.move_to_end(key)
            return list(self._data[key])

    def put(self, key: str, value: list[float]) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Sentence-Transformers backed embeddings (BGE / MiniLM).

    The underlying ``SentenceTransformer`` is loaded once (lazy or via
    ``warmup()``) and reused under a process lock for thread safety.
    """

    def __init__(self, model_name: str, dimension: int, *, provider_label: str = "sentence-transformers") -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._provider_label = provider_label
        self._model = None
        self._load_time_ms: float | None = None
        self._loaded_at: str | None = None
        self._error: str | None = None
        self._query_cache = _LRUEmbedCache(maxsize=2048)

    def _load(self):
        # Double-checked locking — only one load across threads
        if self._model is not None:
            return self._model
        with _MODEL_LOCK:
            if self._model is not None:
                return self._model
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s …", self._model_name)
            started = time.perf_counter()
            try:
                self._model = SentenceTransformer(self._model_name)
                # Prefer reported dimension when available
                try:
                    dim = int(self._model.get_sentence_embedding_dimension())
                    if dim > 0:
                        self._dimension = dim
                except Exception:  # noqa: BLE001
                    pass
                self._load_time_ms = round((time.perf_counter() - started) * 1000, 2)
                self._loaded_at = datetime.now(timezone.utc).isoformat()
                self._error = None
                logger.info(
                    "Embedding model ready model=%s dim=%s load_ms=%.1f",
                    self._model_name,
                    self._dimension,
                    self._load_time_ms or 0.0,
                )
            except Exception as exc:
                self._error = str(exc)
                logger.exception("Failed to load embedding model %s", self._model_name)
                raise
            return self._model

    def warmup(self) -> dict[str, Any]:
        """Force a single load at application startup."""
        self._load()
        # Tiny encode to initialize kernels / device buffers once
        with _MODEL_LOCK:
            self._model.encode(
                ["warmup"],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return self.status()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        batch = settings.EMBEDDING_BATCH_SIZE
        vectors: list[list[float]] = []
        with _MODEL_LOCK:
            for i in range(0, len(texts), batch):
                chunk = list(texts[i : i + batch])
                # Cache short single texts (queries / tiny chunks)
                if len(chunk) == 1 and len(chunk[0]) <= 512:
                    key = hashlib.sha256(chunk[0].encode("utf-8")).hexdigest()
                    cached = self._query_cache.get(key)
                    if cached is not None:
                        vectors.append(cached)
                        continue
                    emb = model.encode(
                        chunk, normalize_embeddings=True, show_progress_bar=False
                    )
                    vec = emb[0].tolist()
                    self._query_cache.put(key, vec)
                    vectors.append(vec)
                else:
                    emb = model.encode(
                        chunk, normalize_embeddings=True, show_progress_bar=False
                    )
                    vectors.extend([v.tolist() for v in emb])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self._query_cache.get(key)
        if cached is not None:
            return cached
        vec = self.embed_documents([text])[0]
        self._query_cache.put(key, vec)
        return vec

    def _estimate_memory_mb(self) -> float | None:
        if self._model is None:
            return None
        try:
            import sys

            # Rough estimate: model object + param tensors
            total = sys.getsizeof(self._model)
            try:
                import torch

                for p in self._model.parameters():
                    total += p.numel() * p.element_size()
            except Exception:  # noqa: BLE001
                pass
            return round(total / (1024 * 1024), 2)
        except Exception:  # noqa: BLE001
            return None

    def status(self) -> dict[str, Any]:
        return {
            "provider": self._provider_label,
            "model": self._model_name,
            "dimension": self._dimension,
            "loaded": self._model is not None,
            "cached": True,
            "cache_size": self._query_cache.size,
            "cache_hits": self._query_cache.hits,
            "cache_misses": self._query_cache.misses,
            "memory_mb": self._estimate_memory_mb(),
            "load_time_ms": self._load_time_ms,
            "loaded_at": self._loaded_at,
            "error": self._error,
        }


def resolve_embedding_model_name(provider: str) -> tuple[str, int, str]:
    """
    Resolve (hf_model_id, dimension, label) from settings.

    Supports short names like ``all-MiniLM-L6-v2``.
    """
    provider = (provider or "bge").lower()
    if provider == "minilm":
        raw = (
            settings.EMBEDDING_MODEL
            or settings.EMBEDDING_MODEL_FALLBACK
            or "sentence-transformers/all-MiniLM-L6-v2"
        )
        if "/" not in raw and not raw.startswith("sentence-transformers/"):
            raw = f"sentence-transformers/{raw}"
        return raw, settings.EMBEDDING_DIM_MINILM, "minilm"
    if provider == "bge":
        return (
            settings.EMBEDDING_MODEL or settings.EMBEDDING_MODEL_PRIMARY,
            settings.EMBEDDING_DIM_BGE,
            "bge",
        )
    return "mock-hash-embedding", settings.EMBEDDING_DIM_MINILM, "mock"


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """
    Resolve embedding backend from settings (singleton per process).

    Order: configured provider → primary BGE → MiniLM fallback → mock.
    ``EMBEDDING_PROVIDER`` env var wins over the cached Settings object so
    tests can monkeypatch the provider without restarting the process.
    """
    import os

    provider = (
        os.getenv("EMBEDDING_PROVIDER")
        or settings.EMBEDDING_PROVIDER
        or "bge"
    ).lower().strip()
    if provider == "mock" or settings.is_testing:
        return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM_MINILM)

    if provider == "minilm":
        try:
            model_name, dim, label = resolve_embedding_model_name("minilm")
            # Prefer env EMBEDDING_MODEL when set (tests / runtime overrides)
            env_model = os.getenv("EMBEDDING_MODEL")
            if env_model:
                if "/" not in env_model and not env_model.startswith(
                    "sentence-transformers/"
                ):
                    env_model = f"sentence-transformers/{env_model}"
                model_name = env_model
            return SentenceTransformerProvider(
                model_name, dim, provider_label=label
            )
        except Exception:
            logger.exception("MiniLM init failed — using mock embeddings")
            return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM_MINILM)

    # bge (default)
    try:
        model_name, dim, label = resolve_embedding_model_name("bge")
        return SentenceTransformerProvider(model_name, dim, provider_label=label)
    except Exception:
        logger.warning(
            "Primary embedding model failed; falling back to %s",
            settings.EMBEDDING_MODEL_FALLBACK,
        )
        try:
            model_name, dim, label = resolve_embedding_model_name("minilm")
            return SentenceTransformerProvider(
                model_name, dim, provider_label=label
            )
        except Exception:
            logger.exception("All embedding models failed — using mock")
            return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM_MINILM)


def warmup_embedding_provider() -> dict[str, Any]:
    """
    Load the configured embedding model once at application startup.

    Safe to call repeatedly — subsequent calls reuse the singleton.
    """
    provider = get_embedding_provider()
    if isinstance(provider, SentenceTransformerProvider):
        return provider.warmup()
    return provider.status()


def get_embedding_status() -> dict[str, Any]:
    """Admin / system status payload for the active embedding provider."""
    provider = get_embedding_provider()
    data = provider.status()
    data["provider_setting"] = settings.EMBEDDING_PROVIDER

    # Vector store size (Qdrant or in-memory fallback) — read-only probe
    total_vectors: int | None = None
    try:
        from app.ai.qdrant import get_qdrant_service

        qs = get_qdrant_service()
        total_vectors = qs.count_points()
    except Exception:  # noqa: BLE001
        total_vectors = None

    data["total_vectors"] = total_vectors
    return data


def clear_embedding_provider_cache() -> None:
    """Allow runtime config changes to take effect (tests / admin)."""
    get_embedding_provider.cache_clear()
