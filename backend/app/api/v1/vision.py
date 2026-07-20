"""Vision / YOLO API routes — Module 7."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_permissions
from app.models.user import User
from app.schemas.ocr import VisionAnalysisOut, VisionHistoryOut, VisionObjectOut
from app.schemas.response import ApiResponse
from app.services.vision_service import VisionService

router = APIRouter()


@router.post(
    "/analyze",
    response_model=ApiResponse[VisionAnalysisOut],
    status_code=status.HTTP_201_CREATED,
    summary="Analyze image (caption + scene + objects)",
)
async def vision_analyze(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permissions("vision:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[VisionAnalysisOut]:
    data = await VisionService(db).analyze(current_user, file)
    return ApiResponse.ok(
        VisionAnalysisOut(
            **{
                **data,
                "objects": [VisionObjectOut(**o) for o in data.get("objects", [])],
            }
        ),
        message="Vision analysis complete",
    )


@router.post(
    "/detect",
    response_model=ApiResponse[VisionAnalysisOut],
    status_code=status.HTTP_201_CREATED,
    summary="YOLO object detection",
)
async def vision_detect(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permissions("vision:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[VisionAnalysisOut]:
    data = await VisionService(db).analyze(current_user, file, detect_only=True)
    return ApiResponse.ok(
        VisionAnalysisOut(
            **{
                **data,
                "objects": [VisionObjectOut(**o) for o in data.get("objects", [])],
            }
        ),
        message="Detection complete",
    )


@router.get(
    "/history",
    response_model=ApiResponse[VisionHistoryOut],
    summary="Vision analysis history",
)
async def vision_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("vision:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[VisionHistoryOut]:
    data = await VisionService(db).history(current_user, limit=limit, offset=offset)
    return ApiResponse.ok(VisionHistoryOut(**data), message="Vision history")


@router.get(
    "/{analysis_id}",
    response_model=ApiResponse[VisionAnalysisOut],
    summary="Get vision analysis",
)
async def vision_get(
    analysis_id: uuid.UUID,
    current_user: User = Depends(require_permissions("vision:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[VisionAnalysisOut]:
    data = await VisionService(db).get(current_user, analysis_id)
    return ApiResponse.ok(
        VisionAnalysisOut(
            **{
                **data,
                "objects": [VisionObjectOut(**o) for o in data.get("objects", [])],
            }
        ),
        message="Vision analysis",
    )
