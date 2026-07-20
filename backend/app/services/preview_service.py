"""Preview helpers for supported document types (no OCR / AI)."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.core.exceptions import AppException
from app.models.document import Document
from app.services.storage_service import StorageBackend


class PreviewService:
    """Generate lightweight previews for PDF/images/TXT/CSV/DOCX."""

    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage

    async def build_preview(self, document: Document) -> dict[str, Any]:
        ext = document.extension.lower()
        meta = {
            "id": str(document.id),
            "filename": document.filename,
            "extension": ext,
            "mime_type": document.mime_type,
            "size": document.size,
            "owner_id": str(document.owner_id),
            "owner_name": document.owner.full_name if document.owner else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
            "version": document.version,
            "checksum": document.checksum,
            "tags": document.tags or [],
            "description": document.description,
            "status": document.status,
            "visibility": document.visibility,
            "pages": None,
            "preview_type": "unsupported",
            "content": None,
            "thumbnail_path": document.thumbnail_path,
        }

        if ext in {"png", "jpg", "jpeg", "webp"}:
            meta["preview_type"] = "image"
            return meta

        if ext == "pdf":
            meta["preview_type"] = "pdf"
            meta["pages"] = None  # page count deferred (no heavy PDF parsing yet)
            return meta

        if ext in {"txt", "csv"}:
            data = await self._storage.open(document.storage_path)
            text = data.decode("utf-8", errors="replace")
            if ext == "csv":
                meta["preview_type"] = "csv"
                meta["content"] = self._csv_preview(text)
            else:
                meta["preview_type"] = "text"
                meta["content"] = text[:50_000]
            return meta

        if ext == "docx":
            meta["preview_type"] = "docx"
            meta["content"] = await self._docx_text(document.storage_path)
            return meta

        if ext in {"xlsx", "pptx", "zip"}:
            meta["preview_type"] = "metadata_only"
            return meta

        return meta

    def _csv_preview(self, text: str, max_rows: int = 50) -> dict[str, Any]:
        reader = csv.reader(io.StringIO(text))
        rows = []
        headers: list[str] = []
        for i, row in enumerate(reader):
            if i == 0:
                headers = row
            if i >= max_rows:
                break
            rows.append(row)
        return {"headers": headers, "rows": rows, "truncated": True}

    async def _docx_text(self, storage_path: str) -> str:
        """Extract plain text from DOCX via zip/xml without heavy deps."""
        import zipfile
        from xml.etree import ElementTree

        data = await self._storage.open(storage_path)
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                xml = zf.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as exc:
            raise AppException(
                "Unable to preview DOCX file",
                code="PREVIEW_FAILED",
                status_code=400,
            ) from exc

        root = ElementTree.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = [
            node.text
            for node in root.findall(".//w:t", ns)
            if node.text
        ]
        return "\n".join(texts)[:50_000]
