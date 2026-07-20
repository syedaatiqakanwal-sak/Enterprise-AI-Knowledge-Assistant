# Module 5 — Enterprise Document Management System

Production DMS foundation for Module 6+ RAG. **No embeddings, LangChain, OCR, or LLMs.**

## Architecture

```
Upload / API
    → DocumentService / FolderService
        → DocumentRepository / FolderRepository
        → StorageBackend (Local | S3 | Azure | GCS stubs)
        → ChecksumService · MetadataService · PreviewService
    → PostgreSQL (documents, folders, versions, favorites)
```

## Storage switch

Set `STORAGE_BACKEND=local|s3|azure|gcs` in `.env`. Business logic never touches the filesystem directly.

## Key endpoints

| Method | Path |
|--------|------|
| POST | `/api/v1/documents/upload` |
| GET | `/api/v1/documents` |
| GET | `/api/v1/documents/search` |
| GET | `/api/v1/documents/recent` |
| GET | `/api/v1/documents/favorites` |
| GET/PUT/DELETE | `/api/v1/documents/{id}` |
| POST | `/api/v1/documents/{id}/restore\|archive\|favorite\|copy\|move` |
| GET | `/api/v1/documents/{id}/preview\|download` |
| CRUD | `/api/v1/folders` |

## Migration

`alembic upgrade head` → `0004_documents_dms`

## Tests

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_documents_module5.py -v
```
