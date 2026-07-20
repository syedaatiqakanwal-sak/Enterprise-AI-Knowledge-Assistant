"""Chat schemas for Module 6."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)


class ChatUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_pinned: Optional[bool] = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    citations: Optional[list[Any]] = None
    metrics: Optional[dict[str, Any]] = None
    created_at: datetime


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut] = Field(default_factory=list)


class ChatSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    preview: Optional[str] = None


class ChatListOut(BaseModel):
    items: list[ChatSummaryOut]
    total: int
    limit: int
    offset: int


class ChatAskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    chat_id: Optional[uuid.UUID] = None
    folder_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    tag: Optional[str] = None


class CitationOut(BaseModel):
    document_id: str
    filename: str
    page: Optional[int] = None
    chunk_index: int
    confidence: float
    snippet: str


class ChatAskResponse(BaseModel):
    chat_id: uuid.UUID
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    citations: list[CitationOut]
    metrics: dict[str, float]


class SemanticSearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=2000)
    folder_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    tag: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class SemanticSearchHit(BaseModel):
    document_id: str
    filename: str
    page: Optional[int] = None
    chunk_index: int
    confidence: float
    snippet: str


class SemanticSearchOut(BaseModel):
    hits: list[SemanticSearchHit]
    metrics: dict[str, float]


class IndexResultOut(BaseModel):
    success: bool
    document_id: Optional[str] = None
    chunks: Optional[int] = None
    skipped: Optional[bool] = None
    reason: Optional[str] = None
    error: Optional[str] = None
    embedding_ms: Optional[float] = None
    total_ms: Optional[float] = None
    embedding_model: Optional[str] = None
