"""Input sanitization helpers for auth and user-facing strings."""

from __future__ import annotations

import html
import re


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"\s+")


def sanitize_text(value: str, *, max_length: int = 255) -> str:
    """
    Strip control characters, collapse whitespace, escape HTML entities,
    and truncate to ``max_length``.
    """
    cleaned = _CONTROL_CHARS.sub("", value)
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
    cleaned = html.escape(cleaned, quote=True)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def sanitize_email(value: str) -> str:
    """Normalize email for storage/lookup (lowercase, trimmed)."""
    return value.strip().lower()
