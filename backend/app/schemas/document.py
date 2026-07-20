"""Pydantic schemas for Module 5 Document Management."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[uuid.UUID] = None
    description: Optional[str] = Field(default=None, max_length=2000)


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    parent_id: Optional[uuid.UUID] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    move_to_root: bool = False


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: Optional[uuid.UUID] = None
    owner_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BreadcrumbItem(BaseModel):
    id: uuid.UUID
    name: str


class FolderTreeOut(BaseModel):
    folders: list[FolderOut]
    breadcrumb: list[BreadcrumbItem] = Field(default_factory=list)


class DocumentUpdate(BaseModel):
    filename: Optional[str] = Field(default=None, min_length=1, max_length=512)
    description: Optional[str] = Field(default=None, max_length=5000)
    visibility: Optional[str] = None
    folder_id: Optional[uuid.UUID] = None
    move_to_root: bool = False
    tags: Optional[list[str]] = None


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    size: int
    checksum: Optional[str] = None
    mime_type: str
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    uuid: uuid.UUID
    owner_id: uuid.UUID
    owner_name: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    folder_id: Optional[uuid.UUID] = None
    filename: str
    original_filename: str
    extension: str
    mime_type: str
    size: int
    storage_path: str
    thumbnail_path: Optional[str] = None
    status: str
    visibility: str
    version: int
    checksum: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    is_favorited: bool = False
    duplicate_of: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    versions: list[DocumentVersionOut] = Field(default_factory=list)


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class DocumentUploadResult(BaseModel):
    document: DocumentOut
    duplicate_detected: bool = False
    message: str = "Upload complete"


class PreviewOut(BaseModel):
    preview: dict[str, Any]


class TagUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)


class CopyMoveRequest(BaseModel):
    folder_id: Optional[uuid.UUID] = None
    move_to_root: bool = False
