"""Pluggable object-storage abstraction for Module 5 DMS."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import StorageBackendType


class StorageBackend(abc.ABC):
    """Abstract storage interface — swap Local ↔ S3/Azure/GCS without changing services."""

    @abc.abstractmethod
    async def save(self, relative_path: str, data: bytes | BinaryIO) -> str:
        """Persist bytes; return the storage key/path used."""

    @abc.abstractmethod
    async def open(self, relative_path: str) -> bytes:
        """Read full object bytes."""

    @abc.abstractmethod
    async def delete(self, relative_path: str) -> None:
        """Delete an object if it exists."""

    @abc.abstractmethod
    async def exists(self, relative_path: str) -> bool:
        """Return True when the object is present."""

    @abc.abstractmethod
    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a storage key to a filesystem path when applicable."""


class LocalStorageBackend(StorageBackend):
    """Filesystem storage under ``STORAGE_LOCAL_ROOT`` with path-traversal guards."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.STORAGE_LOCAL_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, relative_path: str) -> Path:
        cleaned = relative_path.replace("\\", "/").lstrip("/")
        if ".." in cleaned.split("/"):
            raise AppException(
                "Invalid storage path",
                code="PATH_TRAVERSAL",
                status_code=400,
            )
        full = (self.root / cleaned).resolve()
        if not str(full).startswith(str(self.root)):
            raise AppException(
                "Invalid storage path",
                code="PATH_TRAVERSAL",
                status_code=400,
            )
        return full

    async def save(self, relative_path: str, data: bytes | BinaryIO) -> str:
        path = self.resolve_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = data.read() if hasattr(data, "read") else data  # type: ignore[union-attr]
        if not isinstance(content, (bytes, bytearray)):
            content = bytes(content)
        path.write_bytes(content)
        return relative_path.replace("\\", "/")

    async def open(self, relative_path: str) -> bytes:
        path = self.resolve_path(relative_path)
        if not path.is_file():
            raise AppException(
                "File not found in storage",
                code="STORAGE_NOT_FOUND",
                status_code=404,
            )
        return path.read_bytes()

    async def delete(self, relative_path: str) -> None:
        path = self.resolve_path(relative_path)
        if path.is_file():
            path.unlink()

    async def exists(self, relative_path: str) -> bool:
        return self.resolve_path(relative_path).is_file()


class S3StorageBackend(StorageBackend):
    """Placeholder — implement with boto3 in a later infrastructure module."""

    def resolve_path(self, relative_path: str) -> Path:
        raise AppException(
            "S3 backend is not configured yet",
            code="STORAGE_NOT_CONFIGURED",
            status_code=501,
        )

    async def save(self, relative_path: str, data: bytes | BinaryIO) -> str:
        raise AppException(
            "S3 backend is not configured yet",
            code="STORAGE_NOT_CONFIGURED",
            status_code=501,
        )

    async def open(self, relative_path: str) -> bytes:
        raise AppException(
            "S3 backend is not configured yet",
            code="STORAGE_NOT_CONFIGURED",
            status_code=501,
        )

    async def delete(self, relative_path: str) -> None:
        raise AppException(
            "S3 backend is not configured yet",
            code="STORAGE_NOT_CONFIGURED",
            status_code=501,
        )

    async def exists(self, relative_path: str) -> bool:
        return False


class AzureBlobStorageBackend(S3StorageBackend):
    """Placeholder for Azure Blob Storage."""


class GCSStorageBackend(S3StorageBackend):
    """Placeholder for Google Cloud Storage."""


def get_storage_backend() -> StorageBackend:
    """Factory — switch backends via ``STORAGE_BACKEND`` env without code changes."""
    backend = (settings.STORAGE_BACKEND or "local").lower()
    if backend == StorageBackendType.LOCAL.value:
        return LocalStorageBackend()
    if backend == StorageBackendType.S3.value:
        return S3StorageBackend()
    if backend == StorageBackendType.AZURE.value:
        return AzureBlobStorageBackend()
    if backend == StorageBackendType.GCS.value:
        return GCSStorageBackend()
    raise AppException(
        f"Unknown storage backend: {backend}",
        code="STORAGE_CONFIG_ERROR",
        status_code=500,
    )
