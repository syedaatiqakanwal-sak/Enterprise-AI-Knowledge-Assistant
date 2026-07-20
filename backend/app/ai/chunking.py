"""Recursive character chunking for RAG (Module 6)."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    chunk_index: int
    page: int | None
    position: int
    char_count: int


_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def normalize_text(text: str) -> str:
    """Clean and normalize extracted document text."""
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def recursive_chunk(
    text: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    page: int | None = None,
) -> list[TextChunk]:
    """
    Recursive splitter with overlap.

    Defaults: 1000 chars / 200 overlap (configurable).
    """
    size = chunk_size or settings.CHUNK_SIZE
    overlap = chunk_overlap or settings.CHUNK_OVERLAP
    cleaned = normalize_text(text)
    if not cleaned:
        return []

    raw_parts = _split_recursive(cleaned, size, _SEPARATORS)
    chunks: list[TextChunk] = []
    position = 0
    for i, part in enumerate(raw_parts):
        part = part.strip()
        if not part:
            continue
        digest = hashlib.sha1(f"{i}:{part[:64]}".encode()).hexdigest()[:16]
        chunks.append(
            TextChunk(
                chunk_id=f"chk_{digest}_{uuid.uuid4().hex[:8]}",
                text=part,
                chunk_index=len(chunks),
                page=page,
                position=position,
                char_count=len(part),
            )
        )
        position += max(1, len(part) - overlap)
    return chunks


def chunk_pages(
    pages: list[tuple[int, str]],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """Chunk each page separately, preserving page numbers."""
    all_chunks: list[TextChunk] = []
    global_index = 0
    for page_num, page_text in pages:
        page_chunks = recursive_chunk(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            page=page_num,
        )
        for ch in page_chunks:
            ch.chunk_index = global_index
            global_index += 1
            all_chunks.append(ch)
    if all_chunks:
        return all_chunks
    # Fallback: treat as single page
    return recursive_chunk(
        "\n\n".join(t for _, t in pages),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        page=1,
    )


def _split_recursive(text: str, size: int, separators: list[str]) -> list[str]:
    if len(text) <= size:
        return [text]
    sep = separators[0] if separators else ""
    rest = separators[1:] if len(separators) > 1 else [""]
    if sep:
        pieces = text.split(sep)
    else:
        pieces = list(text)

    results: list[str] = []
    current = ""
    for piece in pieces:
        candidate = current + (sep if current and sep else "") + piece if sep else current + piece
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            results.append(current)
        if len(piece) > size:
            results.extend(_split_recursive(piece, size, rest))
            current = ""
        else:
            # start new window with overlap from previous
            current = piece
    if current:
        results.append(current)

    # Apply overlap by merging tails when needed
    if len(results) <= 1:
        return results
    overlapped: list[str] = [results[0]]
    overlap = settings.CHUNK_OVERLAP
    for nxt in results[1:]:
        prev = overlapped[-1]
        if overlap > 0 and len(prev) > overlap:
            prefix = prev[-overlap:]
            overlapped.append(prefix + " " + nxt if not nxt.startswith(prefix) else nxt)
        else:
            overlapped.append(nxt)
    return overlapped
