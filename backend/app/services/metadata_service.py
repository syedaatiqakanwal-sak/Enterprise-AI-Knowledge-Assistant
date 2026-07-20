"""MIME / extension / filename validation for document uploads."""

from __future__ import annotations

import re
import uuid
from pathlib import PurePosixPath

from app.core.config import settings
from app.core.exceptions import AppException

# Canonical extension → accepted MIME types
EXTENSION_MIME_MAP: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    "txt": {"text/plain", "application/octet-stream"},
    "csv": {"text/csv", "application/csv", "text/plain", "application/octet-stream"},
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/octet-stream",
    },
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "webp": {"image/webp"},
    "zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
}

_UNSAFE_CHARS = re.compile(r"[^\w.\- ()\[\]]+", re.UNICODE)


def sanitize_filename(filename: str) -> str:
    """Strip path components and unsafe characters; prevent traversal."""
    name = PurePosixPath(filename.replace("\\", "/")).name
    name = name.strip().strip(".")
    if not name or name in {".", ".."}:
        raise AppException(
            "Invalid filename",
            code="INVALID_FILENAME",
            status_code=400,
        )
    name = _UNSAFE_CHARS.sub("_", name)
    if len(name) > 200:
        stem = PurePosixPath(name).stem[:160]
        suffix = PurePosixPath(name).suffix[:40]
        name = f"{stem}{suffix}"
    return name


def get_extension(filename: str) -> str:
    ext = PurePosixPath(filename).suffix.lower().lstrip(".")
    return ext


def validate_upload(
    *,
    filename: str,
    content_type: str | None,
    size: int,
) -> tuple[str, str, str]:
    """
    Validate size/extension/MIME.

    Returns ``(safe_filename, extension, normalized_mime)``.
    """
    if size <= 0:
        raise AppException(
            "Empty files are not allowed",
            code="EMPTY_FILE",
            status_code=400,
        )
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise AppException(
            f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_BYTES} bytes",
            code="FILE_TOO_LARGE",
            status_code=413,
        )

    safe_name = sanitize_filename(filename)
    extension = get_extension(safe_name)
    if extension not in settings.allowed_extensions_set:
        raise AppException(
            f"File type '.{extension}' is not allowed",
            code="UNSUPPORTED_FILE_TYPE",
            status_code=400,
            details={"allowed": sorted(settings.allowed_extensions_set)},
        )

    mime = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    allowed_mimes = EXTENSION_MIME_MAP.get(extension, set())
    if allowed_mimes and mime not in allowed_mimes and mime != "application/octet-stream":
        # Browsers sometimes send odd MIMEs; allow if extension is trusted
        if mime not in allowed_mimes:
            # Prefer extension-derived default MIME
            mime = next(iter(allowed_mimes))

    if not mime or mime == "*/*":
        mime = next(iter(EXTENSION_MIME_MAP.get(extension, {"application/octet-stream"})))

    return safe_name, extension, mime


def virus_scan_placeholder(data: bytes) -> bool:
    """
    Placeholder virus scan hook.

    Always returns True (clean). Replace with ClamAV / cloud AV in production.
    """
    _ = data
    return True


def unique_storage_key(owner_id: uuid.UUID, extension: str) -> str:
    """Generate a non-guessable relative storage key."""
    return f"{owner_id}/{uuid.uuid4().hex}.{extension}"
