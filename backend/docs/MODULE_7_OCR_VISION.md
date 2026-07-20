# Module 7 — Enterprise OCR & Vision Intelligence

Document Intelligence platform (Azure Document Intelligence–style), with automatic RAG indexing.

## Architecture

```
Upload image/PDF
  → Preprocess (deskew, denoise, CLAHE, …)
  → OCR Provider (Paddle → EasyOCR → Mock)
  → Classify · Tables · Key-Values · Layout
  → Persist OCRDocument + OCRResult
  → Write OCR text as DMS .txt document
  → IndexingService → Qdrant → searchable in Chat
```

Vision:

```
Upload → Caption + YOLO detector (pluggable) → ImageAnalysis + DetectedObject
```

## Providers

```
OCRProvider: paddle | easyocr | mock
YOLODetector: ultralytics (YOLO_MODEL=…) | mock
CaptionProvider: transformers | mock
```

```env
OCR_PROVIDER=mock
OCR_AUTO_INDEX_RAG=true
VISION_CAPTION_PROVIDER=mock
YOLO_MODEL=yolov8n.pt
```

## APIs

| Method | Path |
|--------|------|
| POST | `/api/v1/ocr/upload` |
| POST | `/api/v1/ocr/extract?ocr_id=` |
| GET | `/api/v1/ocr/{id}` |
| GET | `/api/v1/ocr` / `/ocr/search` |
| POST | `/api/v1/vision/analyze` |
| POST | `/api/v1/vision/detect` |
| GET | `/api/v1/vision/history` |

## Migration

`0006_ocr_vision`
