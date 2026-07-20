"""OCR & Vision Intelligence ORM models (Module 7)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class OCRDocument(Base, TimestampMixin, SoftDeleteMixin):
    """Uploaded scanned document / image for OCR processing."""

    __tablename__ = "ocr_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploaded", index=True
    )
    document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="unknown", index=True
    )
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    linked_document: Mapped[Optional["Document"]] = relationship(
        "Document", foreign_keys=[linked_document_id]
    )
    result: Mapped[Optional["OCRResult"]] = relationship(
        "OCRResult",
        back_populates="ocr_document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["OCRJob"]] = relationship(
        "OCRJob", back_populates="ocr_document", cascade="all, delete-orphan"
    )


class OCRResult(Base, TimestampMixin):
    """Structured OCR extraction output."""

    __tablename__ = "ocr_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ocr_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ocr_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    average_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    boxes: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    tables: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    key_values: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    layout: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    structured_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    ocr_document: Mapped["OCRDocument"] = relationship(
        "OCRDocument", back_populates="result"
    )


class OCRJob(Base, TimestampMixin):
    """Async OCR / indexing job tracker."""

    __tablename__ = "ocr_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ocr_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ocr_documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="ocr")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    ocr_document: Mapped[Optional["OCRDocument"]] = relationship(
        "OCRDocument", back_populates="jobs"
    )


class ImageAnalysis(Base, TimestampMixin, SoftDeleteMixin):
    """Vision analysis run for an uploaded image."""

    __tablename__ = "image_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", index=True
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    objects: Mapped[list["DetectedObject"]] = relationship(
        "DetectedObject",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class DetectedObject(Base, TimestampMixin):
    """YOLO / vision detected object instance."""

    __tablename__ = "detected_objects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("image_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="yolo")

    analysis: Mapped["ImageAnalysis"] = relationship(
        "ImageAnalysis", back_populates="objects"
    )
