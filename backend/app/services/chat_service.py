"""Chat orchestration service — RAG-backed enterprise assistant."""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import RAGEngine
from app.core.exceptions import AppException
from app.models.user import User
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import (
    ChatAskResponse,
    ChatListOut,
    ChatMessageOut,
    ChatOut,
    ChatSummaryOut,
    ChatUpdate,
    CitationOut,
)
from app.utils.sanitize import sanitize_text

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._chats = ChatRepository(session)
        self._rag = RAGEngine(session)

    async def create_chat(self, user: User, title: str | None = None) -> ChatOut:
        chat = await self._chats.create_chat(
            user_id=user.id,
            title=sanitize_text(title or "New chat", max_length=255),
        )
        return ChatOut.model_validate(chat)

    async def list_history(
        self,
        user: User,
        *,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ChatListOut:
        rows, total = await self._chats.list_chats(
            user.id, q=q, limit=limit, offset=offset
        )
        items = [
            ChatSummaryOut(
                id=c.id,
                title=c.title,
                is_pinned=c.is_pinned,
                created_at=c.created_at,
                updated_at=c.updated_at,
                preview=None,
            )
            for c in rows
        ]
        return ChatListOut(items=items, total=total, limit=limit, offset=offset)

    async def get_chat(self, user: User, chat_id: uuid.UUID) -> ChatOut:
        chat = await self._chats.get_chat(chat_id, user.id)
        if chat is None:
            raise AppException(
                "Chat not found",
                code="CHAT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return ChatOut(
            id=chat.id,
            title=chat.title,
            is_pinned=chat.is_pinned,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            messages=[ChatMessageOut.model_validate(m) for m in chat.messages],
        )

    async def update_chat(
        self, user: User, chat_id: uuid.UUID, payload: ChatUpdate
    ) -> ChatOut:
        chat = await self._chats.get_chat(chat_id, user.id, with_messages=False)
        if chat is None:
            raise AppException(
                "Chat not found",
                code="CHAT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if payload.title is not None:
            await self._chats.rename(
                chat, sanitize_text(payload.title, max_length=255)
            )
        if payload.is_pinned is not None:
            await self._chats.set_pinned(chat, payload.is_pinned)
        return await self.get_chat(user, chat_id)

    async def delete_chat(self, user: User, chat_id: uuid.UUID) -> None:
        chat = await self._chats.get_chat(chat_id, user.id, with_messages=False)
        if chat is None:
            raise AppException(
                "Chat not found",
                code="CHAT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._chats.soft_delete(chat)

    async def ask(
        self,
        user: User,
        *,
        message: str,
        chat_id: uuid.UUID | None = None,
        folder_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        tag: str | None = None,
    ) -> ChatAskResponse:
        question = sanitize_text(message, max_length=8000)
        if chat_id:
            chat = await self._chats.get_chat(chat_id, user.id)
            if chat is None:
                raise AppException(
                    "Chat not found",
                    code="CHAT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            history = [
                {"role": m.role, "content": m.content}
                for m in (chat.messages or [])
                if m.role in {"user", "assistant"}
            ][-8:]
        else:
            chat = await self._chats.create_chat(user_id=user.id)
            history = []

        user_msg = await self._chats.add_message(
            chat_id=chat.id, role="user", content=question
        )

        result = await self._rag.answer(
            user,
            question,
            history=history,
            folder_id=folder_id,
            document_id=document_id,
            tag=tag,
        )
        citations = [c.to_dict() for c in result.citations]
        assistant_msg = await self._chats.add_message(
            chat_id=chat.id,
            role="assistant",
            content=result.answer,
            citations=citations,
            metrics=result.metrics,
        )

        try:
            from app.ai.llm import get_llm_provider
            from app.services.telemetry import TelemetryCollector

            tel = TelemetryCollector(self._session)
            avg_sim = 0.0
            if result.citations:
                avg_sim = sum(c.confidence for c in result.citations) / len(result.citations)
            await tel.record_rag(
                user_id=user.id,
                query=question,
                chunks_retrieved=len(result.citations),
                avg_similarity=avg_sim,
                metrics=result.metrics or {},
                grounded=result.grounded,
                citation_count=len(result.citations),
                top_document_ids=[c.document_id for c in result.citations[:5]],
            )
            llm = get_llm_provider()
            prompt_est = max(1, len(question) // 4)
            completion_est = max(1, len(result.answer) // 4)
            await tel.record_llm(
                user_id=user.id,
                provider=getattr(llm, "name", "unknown"),
                model=getattr(llm, "name", "unknown"),
                prompt_tokens=prompt_est,
                completion_tokens=completion_est,
                latency_ms=float((result.metrics or {}).get("llm_ms") or 0),
                context_size=len(result.citations),
                operation="rag_answer",
            )
            await tel.emit_event(
                event_type="chat_ask",
                category="chat",
                user_id=user.id,
                success=True,
                latency_ms=float((result.metrics or {}).get("total_ms") or 0),
                resource_type="chat",
                resource_id=str(chat.id),
            )
        except Exception:
            logger.debug("Analytics telemetry skipped", exc_info=True)

        # Best-effort Mongo memory (never block the request)
        try:
            import asyncio

            from app.ai.memory.mongo_memory import save_turn

            await asyncio.wait_for(
                save_turn(
                    user_id=str(user.id),
                    chat_id=str(chat.id),
                    question=question,
                    answer=result.answer,
                    citations=citations,
                ),
                timeout=2.0,
            )
        except Exception:
            logger.debug("Mongo memory save skipped", exc_info=True)

        return ChatAskResponse(
            chat_id=chat.id,
            user_message=ChatMessageOut.model_validate(user_msg),
            assistant_message=ChatMessageOut.model_validate(assistant_msg),
            citations=[CitationOut(**c) for c in citations],
            metrics=result.metrics,
        )

    async def stream_ask(
        self,
        user: User,
        *,
        message: str,
        chat_id: uuid.UUID | None = None,
        folder_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        tag: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        question = sanitize_text(message, max_length=8000)
        if chat_id:
            chat = await self._chats.get_chat(chat_id, user.id)
            if chat is None:
                raise AppException(
                    "Chat not found",
                    code="CHAT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            history = [
                {"role": m.role, "content": m.content}
                for m in (chat.messages or [])
                if m.role in {"user", "assistant"}
            ][-8:]
        else:
            chat = await self._chats.create_chat(user_id=user.id)
            history = []

        user_msg = await self._chats.add_message(
            chat_id=chat.id, role="user", content=question
        )
        yield {
            "event": "chat",
            "data": {
                "chat_id": str(chat.id),
                "user_message_id": str(user_msg.id),
            },
        }

        final_answer = ""
        final_citations: list[dict[str, Any]] = []
        final_metrics: dict[str, float] = {}

        async for event in self._rag.stream_answer(
            user,
            question,
            history=history,
            folder_id=folder_id,
            document_id=document_id,
            tag=tag,
        ):
            if event["event"] == "done":
                final_answer = event["data"]["answer"]
                final_citations = event["data"]["citations"]
                final_metrics = event["data"]["metrics"]
            yield event

        assistant_msg = await self._chats.add_message(
            chat_id=chat.id,
            role="assistant",
            content=final_answer,
            citations=final_citations,
            metrics=final_metrics,
        )
        yield {
            "event": "saved",
            "data": {
                "assistant_message_id": str(assistant_msg.id),
                "chat_id": str(chat.id),
            },
        }
