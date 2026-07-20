"""Meeting Intelligence API — Module 8."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_permissions
from app.models.user import User
from app.schemas.meeting import (
    MeetingChatOut,
    MeetingChatRequest,
    MeetingListOut,
    MeetingOut,
    MeetingSummaryOut,
    MeetingTranscriptOut,
)
from app.schemas.response import ApiResponse
from app.services.meeting_service import MeetingService

router = APIRouter()


@router.post(
    "/upload",
    response_model=ApiResponse[MeetingOut],
    status_code=status.HTTP_201_CREATED,
    summary="Upload meeting audio/video",
)
async def meetings_upload(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    current_user: User = Depends(require_permissions("meetings:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingOut]:
    data = await MeetingService(db).upload(
        current_user, file, title=title, auto_process=auto_process
    )
    return ApiResponse.ok(MeetingOut(**data), message="Meeting uploaded")


@router.post(
    "/transcribe",
    response_model=ApiResponse[MeetingOut],
    summary="Transcribe an uploaded meeting",
)
async def meetings_transcribe(
    meeting_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_permissions("meetings:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingOut]:
    data = await MeetingService(db).transcribe(current_user, meeting_id)
    return ApiResponse.ok(MeetingOut(**data), message="Transcription complete")


@router.post(
    "/process",
    response_model=ApiResponse[MeetingOut],
    summary="Run full meeting intelligence pipeline",
)
async def meetings_process(
    meeting_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_permissions("meetings:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingOut]:
    data = await MeetingService(db).process(current_user, meeting_id)
    return ApiResponse.ok(MeetingOut(**data), message="Meeting processed")


@router.get(
    "",
    response_model=ApiResponse[MeetingListOut],
    summary="List meetings",
)
async def meetings_list(
    q: Optional[str] = None,
    speaker: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("meetings:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingListOut]:
    data = await MeetingService(db).list_meetings(
        current_user,
        q=q,
        speaker=speaker,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApiResponse.ok(MeetingListOut(**data), message="Meetings")


@router.get(
    "/{meeting_id}",
    response_model=ApiResponse[MeetingOut],
    summary="Get meeting detail",
)
async def meetings_get(
    meeting_id: uuid.UUID,
    current_user: User = Depends(require_permissions("meetings:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingOut]:
    data = await MeetingService(db).get(current_user, meeting_id)
    return ApiResponse.ok(MeetingOut(**data), message="Meeting")


@router.get(
    "/{meeting_id}/transcript",
    response_model=ApiResponse[MeetingTranscriptOut],
    summary="Get meeting transcript",
)
async def meetings_transcript(
    meeting_id: uuid.UUID,
    current_user: User = Depends(require_permissions("meetings:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingTranscriptOut]:
    data = await MeetingService(db).get_transcript(current_user, meeting_id)
    return ApiResponse.ok(MeetingTranscriptOut(**data), message="Transcript")


@router.get(
    "/{meeting_id}/summary",
    response_model=ApiResponse[MeetingSummaryOut],
    summary="Get meeting summary, minutes, actions, decisions",
)
async def meetings_summary(
    meeting_id: uuid.UUID,
    current_user: User = Depends(require_permissions("meetings:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingSummaryOut]:
    data = await MeetingService(db).get_summary(current_user, meeting_id)
    return ApiResponse.ok(MeetingSummaryOut(**data), message="Summary")


@router.post(
    "/{meeting_id}/chat",
    response_model=ApiResponse[MeetingChatOut],
    summary="Chat with a meeting (RAG over transcript only)",
)
async def meetings_chat(
    meeting_id: uuid.UUID,
    body: MeetingChatRequest,
    current_user: User = Depends(require_permissions("meetings:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MeetingChatOut]:
    data = await MeetingService(db).chat(current_user, meeting_id, body.message)
    return ApiResponse.ok(MeetingChatOut(**data), message="Meeting chat answer")


@router.delete(
    "/{meeting_id}",
    response_model=ApiResponse[dict],
    summary="Soft-delete a meeting",
)
async def meetings_delete(
    meeting_id: uuid.UUID,
    current_user: User = Depends(require_permissions("meetings:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await MeetingService(db).delete(current_user, meeting_id)
    return ApiResponse.ok({"id": str(meeting_id)}, message="Meeting deleted")
