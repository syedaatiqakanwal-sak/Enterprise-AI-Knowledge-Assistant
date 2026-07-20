"""Vision / YOLO provider abstraction — plug in new detection models easily."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DetectedItem:
    label: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]
    model_name: str = "yolo"


@dataclass
class VisionResult:
    caption: str
    scene_description: str
    chart_summary: str | None
    screenshot_explanation: str | None
    objects: list[DetectedItem] = field(default_factory=list)
    provider: str = "mock"
    metrics: dict[str, Any] = field(default_factory=dict)


class YOLODetector(ABC):
    """Pluggable object detector interface (YOLOv8/v11/custom)."""

    name: str = "yolo"

    @abstractmethod
    def detect(self, image: np.ndarray, *, conf: float = 0.35) -> list[DetectedItem]:
        ...


class MockYOLODetector(YOLODetector):
    name = "mock-yolo"

    def detect(self, image: np.ndarray, *, conf: float = 0.35) -> list[DetectedItem]:
        h, w = image.shape[:2]
        return [
            DetectedItem(
                label="document",
                confidence=0.88,
                bbox=[w * 0.1, h * 0.1, w * 0.9, h * 0.9],
                model_name=self.name,
            ),
            DetectedItem(
                label="logo",
                confidence=0.71,
                bbox=[w * 0.05, h * 0.05, w * 0.25, h * 0.18],
                model_name=self.name,
            ),
        ]


class UltralyticsYOLODetector(YOLODetector):
    """Ultralytics YOLO (v8/v11) — swap weights via YOLO_MODEL env."""

    def __init__(self, model_path: str | None = None) -> None:
        from ultralytics import YOLO

        self._model_path = model_path or settings.YOLO_MODEL
        self._model = YOLO(self._model_path)
        self.name = f"ultralytics:{self._model_path}"

    def detect(self, image: np.ndarray, *, conf: float = 0.35) -> list[DetectedItem]:
        results = self._model.predict(image, conf=conf, verbose=False)
        items: list[DetectedItem] = []
        for r in results:
            names = r.names or {}
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = names.get(cls_id, str(cls_id))
                # Map COCO-ish labels to enterprise categories when relevant
                mapped = _map_label(label)
                xyxy = [float(x) for x in box.xyxy[0].tolist()]
                items.append(
                    DetectedItem(
                        label=mapped,
                        confidence=float(box.conf[0]),
                        bbox=xyxy,
                        model_name=self.name,
                    )
                )
        return items


def _map_label(label: str) -> str:
    lower = label.lower()
    mapping = {
        "person": "people",
        "car": "cars",
        "truck": "cars",
        "bus": "cars",
        "fire hydrant": "fire",
        "dog": "animals",
    }
    return mapping.get(lower, lower)


class CaptionProvider(ABC):
    @abstractmethod
    def caption(self, image: np.ndarray) -> str:
        ...


class MockCaptionProvider(CaptionProvider):
    def caption(self, image: np.ndarray) -> str:
        h, w = image.shape[:2]
        return (
            f"A {w}x{h} business document image showing printed text, "
            f"likely a scanned form or invoice."
        )


class TransformersCaptionProvider(CaptionProvider):
    def __init__(self) -> None:
        from transformers import pipeline

        self._pipe = pipeline(
            "image-to-text", model="Salesforce/blip-image-captioning-base"
        )

    def caption(self, image: np.ndarray) -> str:
        from PIL import Image

        pil = Image.fromarray(image.astype(np.uint8))
        out = self._pipe(pil)
        if isinstance(out, list) and out:
            return out[0].get("generated_text", "") or ""
        return str(out)


@lru_cache
def get_yolo_detector() -> YOLODetector:
    if settings.is_testing or settings.OCR_PROVIDER == "mock":
        return MockYOLODetector()
    try:
        return UltralyticsYOLODetector()
    except Exception:
        logger.warning("YOLO model load failed — using mock detector", exc_info=True)
        return MockYOLODetector()


@lru_cache
def get_caption_provider() -> CaptionProvider:
    if settings.VISION_CAPTION_PROVIDER == "mock" or settings.is_testing:
        return MockCaptionProvider()
    try:
        return TransformersCaptionProvider()
    except Exception:
        logger.warning("Caption model unavailable — using mock", exc_info=True)
        return MockCaptionProvider()


def analyze_vision(image: np.ndarray) -> VisionResult:
    import time

    t0 = time.perf_counter()
    captioner = get_caption_provider()
    detector = get_yolo_detector()
    caption = captioner.caption(image)
    objects = detector.detect(image, conf=settings.YOLO_CONFIDENCE)
    labels = {o.label for o in objects}
    scene = (
        f"Scene contains: {', '.join(sorted(labels))}. {caption}"
        if labels
        else caption
    )
    chart = None
    if any(l in labels for l in ("chart", "document")):
        chart = "Possible chart or structured document region detected."
    screenshot = None
    if "document" in labels or "logo" in labels:
        screenshot = "Image resembles a document screenshot or scanned page."
    ms = (time.perf_counter() - t0) * 1000
    return VisionResult(
        caption=caption,
        scene_description=scene,
        chart_summary=chart,
        screenshot_explanation=screenshot,
        objects=objects,
        provider=f"{captioner.__class__.__name__}+{detector.name}",
        metrics={"vision_ms": round(ms, 2), "object_count": len(objects)},
    )
