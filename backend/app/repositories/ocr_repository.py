"""OCR / Vision persistence repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ocr import (
    DetectedObject,
    ImageAnalysis,
    OCRDocument,
    OCRJob,
    OCRResult,
)


class OCRRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(self, **kwargs) -> OCRDocument:
        doc = OCRDocument(**kwargs)
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)
        return doc

    async def get_document(
        self, doc_id: uuid.UUID, *, owner_id: uuid.UUID | None = None
    ) -> Optional[OCRDocument]:
        stmt = (
            select(OCRDocument)
            .where(OCRDocument.id == doc_id, OCRDocument.deleted_at.is_(None))
            .options(selectinload(OCRDocument.result), selectinload(OCRDocument.jobs))
        )
        if owner_id:
            stmt = stmt.where(OCRDocument.owner_id == owner_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def save_result(self, result: OCRResult) -> OCRResult:
        self._session.add(result)
        await self._session.flush()
        return result

    async def create_job(self, **kwargs) -> OCRJob:
        job = OCRJob(**kwargs)
        self._session.add(job)
        await self._session.flush()
        return job

    async def list_documents(
        self,
        owner_id: uuid.UUID,
        *,
        q: str | None = None,
        document_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[OCRDocument], int]:
        conditions = [
            OCRDocument.owner_id == owner_id,
            OCRDocument.deleted_at.is_(None),
        ]
        if document_type:
            conditions.append(OCRDocument.document_type == document_type)
        if q:
            like = f"%{q.lower()}%"
            conditions.append(
                or_(
                    func.lower(OCRDocument.filename).like(like),
                    func.lower(OCRDocument.original_filename).like(like),
                )
            )
        where = and_(*conditions)
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(OCRDocument).where(where)
                )
            ).scalar_one()
        )
        stmt = (
            select(OCRDocument)
            .where(where)
            .options(selectinload(OCRDocument.result))
            .order_by(OCRDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total

    async def search_results(
        self,
        owner_id: uuid.UUID,
        *,
        q: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[OCRDocument]:
        like = f"%{q.lower()}%"
        stmt = (
            select(OCRDocument)
            .join(OCRResult, OCRResult.ocr_document_id == OCRDocument.id)
            .where(
                OCRDocument.owner_id == owner_id,
                OCRDocument.deleted_at.is_(None),
                or_(
                    func.lower(OCRResult.raw_text).like(like),
                    func.lower(OCRDocument.filename).like(like),
                ),
            )
            .options(selectinload(OCRDocument.result))
            .order_by(OCRDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self._session.execute(stmt)).scalars().all()


class VisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_analysis(self, **kwargs) -> ImageAnalysis:
        row = ImageAnalysis(**kwargs)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def add_objects(
        self, analysis_id: uuid.UUID, objects: list[dict[str, Any]]
    ) -> None:
        for obj in objects:
            self._session.add(
                DetectedObject(
                    analysis_id=analysis_id,
                    label=obj["label"],
                    confidence=obj["confidence"],
                    bbox=obj.get("bbox"),
                    model_name=obj.get("model_name", "yolo"),
                )
            )
        await self._session.flush()

    async def get(
        self, analysis_id: uuid.UUID, *, owner_id: uuid.UUID | None = None
    ) -> Optional[ImageAnalysis]:
        stmt = (
            select(ImageAnalysis)
            .where(
                ImageAnalysis.id == analysis_id,
                ImageAnalysis.deleted_at.is_(None),
            )
            .options(selectinload(ImageAnalysis.objects))
        )
        if owner_id:
            stmt = stmt.where(ImageAnalysis.owner_id == owner_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_history(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[ImageAnalysis], int]:
        where = and_(
            ImageAnalysis.owner_id == owner_id,
            ImageAnalysis.deleted_at.is_(None),
        )
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ImageAnalysis).where(where)
                )
            ).scalar_one()
        )
        stmt = (
            select(ImageAnalysis)
            .where(where)
            .options(selectinload(ImageAnalysis.objects))
            .order_by(ImageAnalysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total
