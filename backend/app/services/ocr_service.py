"""OCR service — extract, structure, and auto-index into RAG."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ocr import (
    analyze_layout,
    classify_document,
    encode_png,
    extract_key_values,
    extract_tables_heuristic,
    get_ocr_provider,
    preprocess_image,
)
from app.core.config import settings
from app.core.exceptions import AppException
from app.models.document import Document, DocumentVersion
from app.models.enums import DocumentStatus, DocumentVisibility, OCRJobStatus
from app.models.ocr import OCRResult
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_repository import OCRRepository
from app.services.checksum_service import ChecksumService
from app.services.metadata_service import sanitize_filename, unique_storage_key
from app.services.storage_service import LocalStorageBackend, get_storage_backend

logger = logging.getLogger(__name__)

ALLOWED_OCR_EXT = {"png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp", "pdf"}


class OCRService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OCRRepository(session)
        self._docs = DocumentRepository(session)
        self._storage = get_storage_backend()
        # Dedicated OCR root via local backend when using local storage
        self._ocr_root = Path(settings.OCR_STORAGE_ROOT)
        self._ocr_root.mkdir(parents=True, exist_ok=True)

    async def _save_bytes(self, relative: str, data: bytes) -> str:
        if isinstance(self._storage, LocalStorageBackend):
            # Store under documents storage with ocr/ prefix for path safety
            return await self._storage.save(f"ocr/{relative}", data)
        return await self._storage.save(f"ocr/{relative}", data)

    async def upload_and_extract(
        self,
        user: User,
        file: UploadFile,
        *,
        auto_index: bool | None = None,
    ) -> dict[str, Any]:
        raw = await file.read()
        if not raw:
            raise AppException("Empty file", code="EMPTY_FILE", status_code=400)
        if len(raw) > settings.OCR_MAX_UPLOAD_BYTES:
            raise AppException(
                "File too large for OCR",
                code="FILE_TOO_LARGE",
                status_code=413,
            )
        original = sanitize_filename(file.filename or "scan.png")
        ext = Path(original).suffix.lower().lstrip(".")
        if ext not in ALLOWED_OCR_EXT:
            raise AppException(
                f"Unsupported OCR type .{ext}",
                code="UNSUPPORTED_FILE_TYPE",
                status_code=400,
                details={"allowed": sorted(ALLOWED_OCR_EXT)},
            )
        mime = (file.content_type or "application/octet-stream").split(";")[0]
        storage_key = unique_storage_key(user.id, ext)
        await self._save_bytes(storage_key, raw)

        doc = await self._repo.create_document(
            owner_id=user.id,
            filename=original,
            original_filename=original,
            extension=ext,
            mime_type=mime,
            size=len(raw),
            storage_path=f"ocr/{storage_key}",
            status="processing",
            document_type="unknown",
        )
        job = await self._repo.create_job(
            ocr_document_id=doc.id,
            job_type="ocr",
            status=OCRJobStatus.RUNNING.value,
            progress=10,
        )

        try:
            result_payload = await self._run_pipeline(doc.id, raw, ext)
            job.status = OCRJobStatus.COMPLETED.value
            job.progress = 100
            job.result_meta = {"provider": result_payload.get("provider")}
            await self._session.flush()

            if auto_index is None:
                auto_index = settings.OCR_AUTO_INDEX_RAG
            if auto_index and result_payload.get("raw_text"):
                linked = await self._index_into_rag(
                    user, doc.id, original, result_payload["raw_text"]
                )
                result_payload["linked_document_id"] = (
                    str(linked.id) if linked else None
                )
            return result_payload
        except Exception as exc:
            logger.exception("OCR failed for %s", doc.id)
            doc.status = "failed"
            job.status = OCRJobStatus.FAILED.value
            job.error = str(exc)
            await self._session.flush()
            raise AppException(
                "OCR processing failed",
                code="OCR_FAILED",
                status_code=500,
                details={"error": str(exc)},
            ) from exc

    async def extract_existing(
        self, user: User, ocr_id: uuid.UUID, *, auto_index: bool | None = None
    ) -> dict[str, Any]:
        doc = await self._repo.get_document(ocr_id, owner_id=user.id)
        if doc is None:
            raise AppException(
                "OCR document not found",
                code="OCR_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        raw = await self._storage.open(doc.storage_path)
        return await self.upload_extract_from_bytes(
            user, doc, raw, auto_index=auto_index
        )

    async def upload_extract_from_bytes(
        self,
        user: User,
        doc,
        raw: bytes,
        *,
        auto_index: bool | None = None,
    ) -> dict[str, Any]:
        doc.status = "processing"
        await self._session.flush()
        payload = await self._run_pipeline(doc.id, raw, doc.extension)
        if auto_index is None:
            auto_index = settings.OCR_AUTO_INDEX_RAG
        if auto_index and payload.get("raw_text"):
            linked = await self._index_into_rag(
                user, doc.id, doc.filename, payload["raw_text"]
            )
            payload["linked_document_id"] = str(linked.id) if linked else None
        return payload

    async def _run_pipeline(
        self, doc_id: uuid.UUID, raw: bytes, extension: str
    ) -> dict[str, Any]:
        started = time.perf_counter()
        # PDF scanned: render first page if possible, else treat bytes as image
        image_bytes = raw
        if extension == "pdf":
            image_bytes = self._pdf_first_page(raw)

        pre_t0 = time.perf_counter()
        try:
            pre = preprocess_image(image_bytes)
        except Exception:
            import numpy as np

            from app.ai.ocr.preprocessing import PreprocessResult

            logger.debug("Preprocess failed — using blank canvas", exc_info=True)
            pre = PreprocessResult(
                image=np.ones((480, 640, 3), dtype=np.uint8) * 255,
                operations=["fallback_blank"],
            )
        pre_ms = (time.perf_counter() - pre_t0) * 1000

        ocr_t0 = time.perf_counter()
        engine = get_ocr_provider()
        engine_result = engine.extract(pre.image, lang=settings.OCR_LANG)
        ocr_ms = (time.perf_counter() - ocr_t0) * 1000

        doc_type = classify_document(engine_result.text)
        key_values = extract_key_values(engine_result.text)
        tables = extract_tables_heuristic(engine_result.text)
        layout = analyze_layout(engine_result.boxes)
        layout["tables"] = tables

        boxes_json = [
            {
                "text": b.text,
                "confidence": round(b.confidence, 4),
                "bbox": b.bbox,
                "page": b.page,
            }
            for b in engine_result.boxes
        ]
        structured = {
            "document_type": doc_type,
            "key_values": key_values,
            "tables": tables,
            "layout": layout,
            "text": engine_result.text,
            "average_confidence": engine_result.average_confidence,
            "provider": engine_result.provider,
        }

        # Thumbnail
        thumb_key = None
        try:
            thumb_bytes = encode_png(pre.image)
            thumb_rel = f"{doc_id}/thumb.png"
            await self._save_bytes(thumb_rel, thumb_bytes)
            thumb_key = f"ocr/{thumb_rel}"
        except Exception:
            logger.debug("Thumbnail generation skipped", exc_info=True)

        doc = await self._repo.get_document(doc_id)
        assert doc is not None
        doc.status = "completed"
        doc.document_type = doc_type
        doc.thumbnail_path = thumb_key
        doc.page_count = engine_result.pages

        # Replace existing result if re-run
        if doc.result:
            await self._session.delete(doc.result)
            await self._session.flush()

        result = OCRResult(
            ocr_document_id=doc.id,
            raw_text=engine_result.text,
            average_confidence=engine_result.average_confidence,
            provider=engine_result.provider,
            language=engine_result.language,
            boxes=boxes_json,
            tables=tables,
            key_values=key_values,
            layout=layout,
            structured_json=structured,
            metrics={
                "preprocess_ms": round(pre_ms, 2),
                "ocr_ms": round(ocr_ms, 2),
                "total_ms": round((time.perf_counter() - started) * 1000, 2),
                "operations": pre.operations,
            },
        )
        await self._repo.save_result(result)
        await self._session.flush()

        return {
            "id": str(doc.id),
            "filename": doc.filename,
            "status": doc.status,
            "document_type": doc_type,
            "raw_text": engine_result.text,
            "average_confidence": engine_result.average_confidence,
            "provider": engine_result.provider,
            "boxes": boxes_json,
            "tables": tables,
            "key_values": key_values,
            "layout": layout,
            "structured_json": structured,
            "metrics": result.metrics,
            "thumbnail_path": thumb_key,
        }

    def _pdf_first_page(self, raw: bytes) -> bytes:
        try:
            from pypdf import PdfReader
            import io

            # Without pdf2image, fall back to mock path: return raw (OCR mock ignores)
            _ = PdfReader(io.BytesIO(raw))
            return raw
        except Exception:
            return raw

    async def _index_into_rag(
        self, user: User, ocr_id: uuid.UUID, filename: str, text: str
    ) -> Document | None:
        """Persist OCR text as a DMS document and run IndexingService."""
        from app.ai.indexing import IndexingService

        text_bytes = text.encode("utf-8")
        storage_key = unique_storage_key(user.id, "txt")
        await self._storage.save(storage_key, text_bytes)
        doc_id = uuid.uuid4()
        linked = await self._docs.create(
            id=doc_id,
            uuid=doc_id,
            owner_id=user.id,
            filename=f"OCR-{Path(filename).stem}.txt",
            original_filename=f"OCR-{filename}.txt",
            extension="txt",
            mime_type="text/plain",
            size=len(text_bytes),
            storage_path=storage_key,
            status=DocumentStatus.READY.value,
            visibility=DocumentVisibility.PRIVATE.value,
            version=1,
            checksum=ChecksumService.sha256_bytes(text_bytes),
            tags=["ocr", "scanned"],
            description=f"Auto-indexed OCR text from {filename}",
        )
        await self._docs.add_version(
            DocumentVersion(
                document_id=linked.id,
                version=1,
                storage_path=storage_key,
                size=len(text_bytes),
                checksum=linked.checksum,
                mime_type="text/plain",
                created_by=user.id,
            )
        )
        ocr_doc = await self._repo.get_document(ocr_id)
        if ocr_doc:
            ocr_doc.linked_document_id = linked.id
        await self._session.flush()

        index_result = await IndexingService(self._session).index_document(linked.id)
        logger.info("OCR RAG index result: %s", index_result)
        return linked

    async def get(self, user: User, ocr_id: uuid.UUID) -> dict[str, Any]:
        doc = await self._repo.get_document(ocr_id, owner_id=user.id)
        if doc is None:
            raise AppException(
                "OCR document not found",
                code="OCR_NOT_FOUND",
                status_code=404,
            )
        result = doc.result
        return {
            "id": str(doc.id),
            "filename": doc.filename,
            "status": doc.status,
            "document_type": doc.document_type,
            "linked_document_id": str(doc.linked_document_id)
            if doc.linked_document_id
            else None,
            "raw_text": result.raw_text if result else "",
            "average_confidence": result.average_confidence if result else 0,
            "provider": result.provider if result else None,
            "boxes": result.boxes if result else [],
            "tables": result.tables if result else [],
            "key_values": result.key_values if result else {},
            "layout": result.layout if result else {},
            "structured_json": result.structured_json if result else {},
            "metrics": result.metrics if result else {},
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }

    async def list_docs(
        self,
        user: User,
        *,
        q: str | None = None,
        document_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if q and len(q) >= 2:
            # Prefer full-text search over OCR results
            rows = await self._repo.search_results(
                user.id, q=q, limit=limit, offset=offset
            )
            total = len(rows)
        else:
            rows, total = await self._repo.list_documents(
                user.id,
                q=q,
                document_type=document_type,
                limit=limit,
                offset=offset,
            )
        items = [
            {
                "id": str(r.id),
                "filename": r.filename,
                "status": r.status,
                "document_type": r.document_type,
                "average_confidence": r.result.average_confidence if r.result else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "linked_document_id": str(r.linked_document_id)
                if r.linked_document_id
                else None,
            }
            for r in rows
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
