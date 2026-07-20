"""Meeting Intelligence ORM models (Module 8)."""

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


class Meeting(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "meetings"

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
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploaded", index=True
    )
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    linked_document: Mapped[Optional["Document"]] = relationship(
        "Document", foreign_keys=[linked_document_id]
    )
    speakers: Mapped[list["MeetingSpeaker"]] = relationship(
        "MeetingSpeaker", back_populates="meeting", cascade="all, delete-orphan"
    )
    segments: Mapped[list["MeetingTranscriptSegment"]] = relationship(
        "MeetingTranscriptSegment",
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="MeetingTranscriptSegment.start_time.asc()",
    )
    summary: Mapped[Optional["MeetingSummary"]] = relationship(
        "MeetingSummary",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
    )
    action_items: Mapped[list["MeetingActionItem"]] = relationship(
        "MeetingActionItem", back_populates="meeting", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["MeetingDecision"]] = relationship(
        "MeetingDecision", back_populates="meeting", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["MeetingChatMessage"]] = relationship(
        "MeetingChatMessage",
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="MeetingChatMessage.created_at.asc()",
    )


class MeetingSpeaker(Base, TimestampMixin):
    __tablename__ = "meeting_speakers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)  # Speaker 1
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    talk_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="speakers")


class MeetingTranscriptSegment(Base, TimestampMixin):
    __tablename__ = "meeting_transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_label: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    end_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    words: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="segments")


class MeetingSummary(Base, TimestampMixin):
    __tablename__ = "meeting_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    key_points: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    risks: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    open_questions: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    minutes: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    attendance: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="summary")


class MeetingActionItem(Base, TimestampMixin):
    __tablename__ = "meeting_action_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="action_items")


class MeetingDecision(Base, TimestampMixin):
    __tablename__ = "meeting_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="decisions")


class MeetingChatMessage(Base, TimestampMixin):
    __tablename__ = "meeting_chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="chat_messages")
