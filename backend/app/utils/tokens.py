"""Secure random token generation and hashing helpers."""

from __future__ import annotations

import hashlib
import secrets


def generate_url_safe_token(nbytes: int = 32) -> str:
    """Generate a cryptographically strong URL-safe token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """
    Hash a token with SHA-256 for at-rest storage.

    Only the hash is persisted; plaintext tokens are emailed/returned once.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
