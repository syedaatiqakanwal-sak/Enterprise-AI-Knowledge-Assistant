"""
Chat + RAG API routes — Module 6.

POST /chat          — ask (JSON)
POST /chat/stream   — ask (SSE)
GET  /chat/history  — list chats
GET  /chat/{id}     — get chat
DELETE /chat/{id}   — delete chat
PATCH /chat/{id}    — rename / pin
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import get_current_user, require_permissions
from app.models.user import User
from app.schemas.chat import (
    ChatAskRequest,
    ChatAskResponse,
    ChatCreate,
    ChatListOut,
    ChatOut,
    ChatUpdate,
)
from app.schemas.response import ApiResponse
from app.services.chat_service import ChatService

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[ChatAskResponse],
    summary="Ask the knowledge assistant",
)
async def ask_chat(
    payload: ChatAskRequest,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatAskResponse]:
    data = await ChatService(db).ask(
        current_user,
        message=payload.message,
        chat_id=payload.chat_id,
        folder_id=payload.folder_id,
        document_id=payload.document_id,
        tag=payload.tag,
    )
    return ApiResponse.ok(data, message="Answer generated")


@router.post(
    "/stream",
    summary="Ask with Server-Sent Events streaming",
)
async def ask_chat_stream(
    payload: ChatAskRequest,
    current_user: User = Depends(require_permissions("documents:read")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    service = ChatService(db)

    async def event_generator():
        async for event in service.stream_ask(
            current_user,
            message=payload.message,
            chat_id=payload.chat_id,
            folder_id=payload.folder_id,
            document_id=payload.document_id,
            tag=payload.tag,
        ):
            yield (
                f"event: {event['event']}\n"
                f"data: {json.dumps(event['data'])}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/history",
    response_model=ApiResponse[ChatListOut],
    summary="List chat history",
)
async def chat_history(
    q: Optional[str] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatListOut]:
    data = await ChatService(db).list_history(
        current_user, q=q, limit=limit, offset=offset
    )
    return ApiResponse.ok(data, message="Chat history")


@router.post(
    "/sessions",
    response_model=ApiResponse[ChatOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create empty chat session",
)
async def create_session(
    payload: ChatCreate | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatOut]:
    title = payload.title if payload else None
    data = await ChatService(db).create_chat(current_user, title=title)
    return ApiResponse.ok(data, message="Chat created")


@router.get(
    "/{chat_id}",
    response_model=ApiResponse[ChatOut],
    summary="Get chat with messages",
)
async def get_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatOut]:
    data = await ChatService(db).get_chat(current_user, chat_id)
    return ApiResponse.ok(data, message="Chat retrieved")


@router.patch(
    "/{chat_id}",
    response_model=ApiResponse[ChatOut],
    summary="Rename or pin a chat",
)
async def update_chat(
    chat_id: uuid.UUID,
    payload: ChatUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatOut]:
    data = await ChatService(db).update_chat(current_user, chat_id, payload)
    return ApiResponse.ok(data, message="Chat updated")


@router.delete(
    "/{chat_id}",
    response_model=ApiResponse[None],
    summary="Delete a chat",
)
async def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await ChatService(db).delete_chat(current_user, chat_id)
    return ApiResponse.ok(None, message="Chat deleted")
