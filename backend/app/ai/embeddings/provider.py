"""Embedding provider abstraction — swap models without changing callers."""

from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)


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
        # Lightweight bag-of-characters + token hashes for better test retrieval
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


class SentenceTransformerProvider(EmbeddingProvider):
    """Sentence-Transformers backed embeddings (BGE / MiniLM)."""

    def __init__(self, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model %s …", self._model_name)
        self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        batch = settings.EMBEDDING_BATCH_SIZE
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch):
            chunk = list(texts[i : i + batch])
            emb = model.encode(chunk, normalize_embeddings=True, show_progress_bar=False)
            vectors.extend([v.tolist() for v in emb])
        return vectors


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """
    Resolve embedding backend from settings.

    Order: configured provider → primary BGE → MiniLM fallback → mock.
    """
    provider = (settings.EMBEDDING_PROVIDER or "bge").lower()
    if provider == "mock" or settings.is_testing:
        return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM_MINILM)

    if provider == "minilm":
        try:
            model_name = (
                settings.EMBEDDING_MODEL
                or settings.EMBEDDING_MODEL_FALLBACK
            )
            if model_name and "/" not in model_name and not model_name.startswith(
                "sentence-transformers/"
            ):
                # Allow short name: all-MiniLM-L6-v2
                model_name = f"sentence-transformers/{model_name}"
            return SentenceTransformerProvider(
                model_name,
                settings.EMBEDDING_DIM_MINILM,
            )
        except Exception:
            logger.exception("MiniLM load failed — using mock embeddings")
            return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM_MINILM)

    # bge (default)
    try:
        return SentenceTransformerProvider(
            settings.EMBEDDING_MODEL_PRIMARY,
            settings.EMBEDDING_DIM_BGE,
        )
    except Exception:
        logger.warning(
            "Primary embedding model failed; falling back to %s",
            settings.EMBEDDING_MODEL_FALLBACK,
        )
        try:
            return SentenceTransformerProvider(
                settings.EMBEDDING_MODEL_FALLBACK,
                settings.EMBEDDING_DIM_MINILM,
            )
        except Exception:
            logger.exception("All embedding models failed — using mock")
            return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM_MINILM)
