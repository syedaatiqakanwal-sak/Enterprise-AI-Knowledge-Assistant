"""OCR API routes — Module 7."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_permissions
from app.models.user import User
from app.schemas.ocr import OCRListOut, OCRResultOut
from app.schemas.response import ApiResponse
from app.services.ocr_service import OCRService

router = APIRouter()


@router.post(
    "/upload",
    response_model=ApiResponse[OCRResultOut],
    status_code=status.HTTP_201_CREATED,
    summary="Upload scanned document and run OCR",
)
async def ocr_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permissions("ocr:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[OCRResultOut]:
    data = await OCRService(db).upload_and_extract(current_user, file)
    return ApiResponse.ok(OCRResultOut(**data), message="OCR complete")


@router.post(
    "/extract",
    response_model=ApiResponse[OCRResultOut],
    summary="Re-run OCR on an existing upload",
)
async def ocr_extract(
    ocr_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_permissions("ocr:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[OCRResultOut]:
    data = await OCRService(db).extract_existing(current_user, ocr_id)
    return ApiResponse.ok(OCRResultOut(**data), message="OCR extraction complete")


@router.get(
    "/search",
    response_model=ApiResponse[OCRListOut],
    summary="Search OCR text / invoice fields",
)
async def ocr_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("ocr:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[OCRListOut]:
    data = await OCRService(db).list_docs(
        current_user, q=q, limit=limit, offset=offset
    )
    return ApiResponse.ok(OCRListOut(**data), message="OCR search results")


@router.get(
    "",
    response_model=ApiResponse[OCRListOut],
    summary="List OCR documents",
)
async def ocr_list(
    q: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("ocr:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[OCRListOut]:
    data = await OCRService(db).list_docs(
        current_user,
        q=q,
        document_type=document_type,
        limit=limit,
        offset=offset,
    )
    return ApiResponse.ok(OCRListOut(**data), message="OCR documents")


@router.get(
    "/{ocr_id}",
    response_model=ApiResponse[OCRResultOut],
    summary="Get OCR result",
)
async def ocr_get(
    ocr_id: uuid.UUID,
    current_user: User = Depends(require_permissions("ocr:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[OCRResultOut]:
    data = await OCRService(db).get(current_user, ocr_id)
    return ApiResponse.ok(OCRResultOut(**data), message="OCR result")
