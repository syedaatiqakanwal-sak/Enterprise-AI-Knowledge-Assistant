"""OCR & Vision API schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class OCRResultOut(BaseModel):
    id: str
    filename: str
    status: str
    document_type: str
    raw_text: str = ""
    average_confidence: float = 0.0
    provider: Optional[str] = None
    boxes: list[Any] = Field(default_factory=list)
    tables: list[Any] = Field(default_factory=list)
    key_values: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)
    structured_json: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    linked_document_id: Optional[str] = None
    thumbnail_path: Optional[str] = None
    created_at: Optional[str] = None


class OCRListOut(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class VisionObjectOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: Optional[str] = None
    label: str
    confidence: float
    bbox: Optional[list[Any]] = None
    model_name: str = "yolo"


class VisionAnalysisOut(BaseModel):
    id: str
    filename: str
    status: str
    caption: Optional[str] = None
    scene_description: Optional[str] = None
    chart_summary: Optional[str] = None
    screenshot_explanation: Optional[str] = None
    provider: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    objects: list[VisionObjectOut] = Field(default_factory=list)
    created_at: Optional[str] = None


class VisionHistoryOut(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
