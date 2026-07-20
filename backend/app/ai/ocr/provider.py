"""OCR provider abstraction — PaddleOCR primary, EasyOCR fallback, Mock for tests."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OCRBox:
    text: str
    confidence: float
    bbox: list[list[float]]  # 4 points [[x,y],...]
    page: int = 1


@dataclass
class OCREngineResult:
    text: str
    boxes: list[OCRBox] = field(default_factory=list)
    average_confidence: float = 0.0
    provider: str = "mock"
    language: str = "en"
    pages: int = 1


class OCRProvider(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, image: np.ndarray, *, lang: str = "en") -> OCREngineResult:
        ...


class MockOCRProvider(OCRProvider):
    """Deterministic OCR for CI / offline — extracts any embedded printable text heuristics."""

    name = "mock"

    def extract(self, image: np.ndarray, *, lang: str = "en") -> OCREngineResult:
        h, w = image.shape[:2]
        # Synthetic invoice-like text so classification / KV / RAG demos work
        sample = (
            "INVOICE\n"
            "Invoice Number: INV-2026-0042\n"
            "Company Name: Acme Corporation\n"
            "Vendor: Office Supplies Ltd\n"
            "Customer: Enterprise AI Inc\n"
            "Date: 2026-07-15\n"
            "Address: 100 Market Street, San Francisco, CA\n"
            "Subtotal: 1,250.00\n"
            "Tax: 100.00\n"
            "Grand Total: 1,350.00\n"
            "Currency: USD\n"
            "Thank you for your business.\n"
        )
        lines = sample.strip().split("\n")
        boxes: list[OCRBox] = []
        y = 40.0
        for line in lines:
            boxes.append(
                OCRBox(
                    text=line,
                    confidence=0.92,
                    bbox=[[40, y], [min(w - 20, 600), y], [min(w - 20, 600), y + 22], [40, y + 22]],
                )
            )
            y += 28
        return OCREngineResult(
            text=sample,
            boxes=boxes,
            average_confidence=0.92,
            provider=self.name,
            language=lang,
        )


class PaddleOCRProvider(OCRProvider):
    name = "paddle"

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(use_angle_cls=True, lang=settings.OCR_LANG, show_log=False)

    def extract(self, image: np.ndarray, *, lang: str = "en") -> OCREngineResult:
        result = self._ocr.ocr(image, cls=True)
        boxes: list[OCRBox] = []
        parts: list[str] = []
        confs: list[float] = []
        for page in result or []:
            for line in page or []:
                bbox, (text, conf) = line
                boxes.append(
                    OCRBox(
                        text=text,
                        confidence=float(conf),
                        bbox=[[float(p[0]), float(p[1])] for p in bbox],
                    )
                )
                parts.append(text)
                confs.append(float(conf))
        avg = sum(confs) / len(confs) if confs else 0.0
        return OCREngineResult(
            text="\n".join(parts),
            boxes=boxes,
            average_confidence=avg,
            provider=self.name,
            language=lang,
        )


class EasyOCRProvider(OCRProvider):
    name = "easyocr"

    def __init__(self) -> None:
        import easyocr

        self._reader = easyocr.Reader([settings.OCR_LANG], gpu=False)

    def extract(self, image: np.ndarray, *, lang: str = "en") -> OCREngineResult:
        raw = self._reader.readtext(image)
        boxes: list[OCRBox] = []
        parts: list[str] = []
        confs: list[float] = []
        for bbox, text, conf in raw:
            boxes.append(
                OCRBox(
                    text=text,
                    confidence=float(conf),
                    bbox=[[float(p[0]), float(p[1])] for p in bbox],
                )
            )
            parts.append(text)
            confs.append(float(conf))
        avg = sum(confs) / len(confs) if confs else 0.0
        return OCREngineResult(
            text="\n".join(parts),
            boxes=boxes,
            average_confidence=avg,
            provider=self.name,
            language=lang,
        )


@lru_cache
def get_ocr_provider() -> OCRProvider:
    name = (settings.OCR_PROVIDER or "mock").lower()
    if name == "mock" or settings.is_testing:
        return MockOCRProvider()
    if name == "paddle":
        try:
            return PaddleOCRProvider()
        except Exception:
            logger.warning("PaddleOCR unavailable — trying EasyOCR", exc_info=True)
            name = "easyocr"
    if name == "easyocr":
        try:
            return EasyOCRProvider()
        except Exception:
            logger.warning("EasyOCR unavailable — using mock OCR", exc_info=True)
            return MockOCRProvider()
    return MockOCRProvider()


# ---------- Intelligence helpers ----------

_CLASSIFY_RULES: list[tuple[str, list[str]]] = [
    ("invoice", ["invoice", "inv-", "bill to", "grand total"]),
    ("receipt", ["receipt", "cashier", "change due"]),
    ("passport", ["passport", "nationality", "date of birth"]),
    ("national_id", ["national id", "identity card", "cnic", "ssn"]),
    ("business_card", ["tel:", "mobile:", "@", "www."]),
    ("contract", ["agreement", "hereinafter", "party a", "party b"]),
    ("resume", ["curriculum vitae", "resume", "work experience", "education"]),
    ("form", ["please fill", "signature", "checkbox"]),
    ("letter", ["dear ", "sincerely", "yours faithfully"]),
    ("report", ["executive summary", "findings", "conclusion"]),
    ("screenshot", ["screenshot", "http://", "https://"]),
    ("chart", ["chart", "figure", "axis", "legend"]),
]


def classify_document(text: str) -> str:
    lower = text.lower()
    best, score = "unknown", 0
    for label, keys in _CLASSIFY_RULES:
        hits = sum(1 for k in keys if k in lower)
        if hits > score:
            best, score = label, hits
    return best if score > 0 else "unknown"


def extract_key_values(text: str) -> dict[str, Any]:
    patterns = {
        "invoice_number": r"(?:invoice\s*(?:number|#|no\.?)[:\s]*)([A-Z0-9\-/]+)",
        "company_name": r"(?:company\s*name[:\s]*)([^\n]+)",
        "vendor": r"(?:vendor[:\s]*)([^\n]+)",
        "customer": r"(?:customer[:\s]*)([^\n]+)",
        "date": r"(?:date[:\s]*)(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        "address": r"(?:address[:\s]*)([^\n]+)",
        "subtotal": r"(?:subtotal[:\s]*)([\$€£]?\s*[\d,]+\.?\d*)",
        "tax": r"(?:tax[:\s]*)([\$€£]?\s*[\d,]+\.?\d*)",
        "grand_total": r"(?:grand\s*total|total[:\s]*)([\$€£]?\s*[\d,]+\.?\d*)",
        "currency": r"(?:currency[:\s]*)([A-Z]{3})",
    }
    out: dict[str, Any] = {}
    for key, pat in patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            out[key] = m.group(1).strip()
    return out


def extract_tables_heuristic(text: str) -> list[dict[str, Any]]:
    """Simple whitespace/CSV-like table detector from plain OCR text."""
    rows = []
    for line in text.splitlines():
        if "\t" in line:
            cells = [c.strip() for c in line.split("\t") if c.strip()]
        elif re.search(r"\s{2,}", line):
            cells = [c.strip() for c in re.split(r"\s{2,}", line) if c.strip()]
        else:
            continue
        if len(cells) >= 2:
            rows.append(cells)
    if not rows:
        return []
    headers = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    return [
        {
            "headers": headers,
            "rows": body,
            "row_count": len(body),
            "column_count": len(headers),
        }
    ]


def analyze_layout(boxes: list[OCRBox]) -> dict[str, Any]:
    paragraphs = []
    headings = []
    for b in boxes:
        entry = {"text": b.text, "bbox": b.bbox, "confidence": b.confidence}
        if b.text.isupper() and len(b.text) < 40:
            headings.append(entry)
        else:
            paragraphs.append(entry)
    return {
        "headings": headings,
        "paragraphs": paragraphs,
        "tables": [],
        "headers": headings[:1],
        "footers": paragraphs[-1:] if paragraphs else [],
        "lists": [p for p in paragraphs if p["text"].lstrip().startswith(("-", "•", "*"))],
        "images": [],
    }
