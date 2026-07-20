"""Meeting Intelligence API schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class MeetingChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class MeetingProcessRequest(BaseModel):
    meeting_id: Optional[str] = None


class MeetingOut(BaseModel):
    id: str
    title: str
    original_filename: str
    extension: str
    mime_type: str = ""
    size: int = 0
    status: str
    duration_seconds: float = 0
    language: str = "en"
    provider: Optional[str] = None
    linked_document_id: Optional[str] = None
    error: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    speaker_count: int = 0
    speakers: list[dict[str, Any]] = Field(default_factory=list)
    segments: list[dict[str, Any]] = Field(default_factory=list)
    summary: Optional[dict[str, Any]] = None
    action_items: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    chat_messages: list[dict[str, Any]] = Field(default_factory=list)


class MeetingListOut(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class MeetingTranscriptOut(BaseModel):
    meeting_id: str
    duration_seconds: float = 0
    language: str = "en"
    speakers: list[dict[str, Any]] = Field(default_factory=list)
    segments: list[dict[str, Any]] = Field(default_factory=list)


class MeetingSummaryOut(BaseModel):
    meeting_id: str
    executive_summary: str
    key_points: list[Any] = Field(default_factory=list)
    risks: list[Any] = Field(default_factory=list)
    open_questions: list[Any] = Field(default_factory=list)
    minutes: dict[str, Any] = Field(default_factory=dict)
    attendance: list[Any] = Field(default_factory=list)
    action_items: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    deadlines: list[Any] = Field(default_factory=list)


class MeetingChatOut(BaseModel):
    meeting_id: str
    message_id: str
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    grounded: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
