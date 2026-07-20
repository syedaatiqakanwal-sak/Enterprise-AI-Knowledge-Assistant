"""Vision analysis service — captioning + YOLO detection."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ocr.preprocessing import _load_rgb
from app.ai.vision import analyze_vision
from app.core.config import settings
from app.core.exceptions import AppException
from app.models.user import User
from app.repositories.ocr_repository import VisionRepository
from app.services.metadata_service import sanitize_filename, unique_storage_key
from app.services.storage_service import get_storage_backend

logger = logging.getLogger(__name__)

ALLOWED_VISION_EXT = {"png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp"}


class VisionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = VisionRepository(session)
        self._storage = get_storage_backend()

    async def analyze(
        self, user: User, file: UploadFile, *, detect_only: bool = False
    ) -> dict[str, Any]:
        raw = await file.read()
        if not raw:
            raise AppException("Empty file", code="EMPTY_FILE", status_code=400)
        if len(raw) > settings.OCR_MAX_UPLOAD_BYTES:
            raise AppException("File too large", code="FILE_TOO_LARGE", status_code=413)

        original = sanitize_filename(file.filename or "image.png")
        ext = Path(original).suffix.lower().lstrip(".")
        if ext not in ALLOWED_VISION_EXT:
            raise AppException(
                f"Unsupported image type .{ext}",
                code="UNSUPPORTED_FILE_TYPE",
                status_code=400,
            )
        mime = (file.content_type or "image/png").split(";")[0]
        storage_key = unique_storage_key(user.id, ext)
        await self._storage.save(f"vision/{storage_key}", raw)

        image = _load_rgb(raw)
        result = analyze_vision(image)
        if detect_only:
            # Keep objects; blank narrative fields optional
            pass

        analysis = await self._repo.create_analysis(
            owner_id=user.id,
            filename=original,
            original_filename=original,
            extension=ext,
            mime_type=mime,
            size=len(raw),
            storage_path=f"vision/{storage_key}",
            status="completed",
            caption=None if detect_only else result.caption,
            scene_description=None if detect_only else result.scene_description,
            chart_summary=None if detect_only else result.chart_summary,
            screenshot_explanation=None
            if detect_only
            else result.screenshot_explanation,
            provider=result.provider,
            metrics=result.metrics,
        )
        await self._repo.add_objects(
            analysis.id,
            [
                {
                    "label": o.label,
                    "confidence": o.confidence,
                    "bbox": o.bbox,
                    "model_name": o.model_name,
                }
                for o in result.objects
            ],
        )
        await self._session.flush()
        return await self._to_out(analysis.id, user.id)

    async def _to_out(self, analysis_id: uuid.UUID, owner_id: uuid.UUID) -> dict[str, Any]:
        row = await self._repo.get(analysis_id, owner_id=owner_id)
        assert row is not None
        return {
            "id": str(row.id),
            "filename": row.filename,
            "status": row.status,
            "caption": row.caption,
            "scene_description": row.scene_description,
            "chart_summary": row.chart_summary,
            "screenshot_explanation": row.screenshot_explanation,
            "provider": row.provider,
            "metrics": row.metrics or {},
            "objects": [
                {
                    "id": str(o.id),
                    "label": o.label,
                    "confidence": o.confidence,
                    "bbox": o.bbox,
                    "model_name": o.model_name,
                }
                for o in (row.objects or [])
            ],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def history(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        rows, total = await self._repo.list_history(
            user.id, limit=limit, offset=offset
        )
        items = []
        for r in rows:
            items.append(
                {
                    "id": str(r.id),
                    "filename": r.filename,
                    "caption": r.caption,
                    "object_count": len(r.objects or []),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def get(self, user: User, analysis_id: uuid.UUID) -> dict[str, Any]:
        row = await self._repo.get(analysis_id, owner_id=user.id)
        if row is None:
            raise AppException(
                "Vision analysis not found",
                code="VISION_NOT_FOUND",
                status_code=404,
            )
        return await self._to_out(analysis_id, user.id)
