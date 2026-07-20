"""Checksum helpers for duplicate detection and integrity."""

from __future__ import annotations

import hashlib


class ChecksumService:
    """SHA-256 checksums for uploaded document binaries."""

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify(data: bytes, expected: str) -> bool:
        return ChecksumService.sha256_bytes(data) == expected.lower()
