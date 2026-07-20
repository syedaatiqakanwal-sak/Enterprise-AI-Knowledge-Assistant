"""Chat persistence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Chat, ChatMessage


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_chat(
        self, *, user_id: uuid.UUID, title: str = "New chat"
    ) -> Chat:
        chat = Chat(user_id=user_id, title=title)
        self._session.add(chat)
        await self._session.flush()
        await self._session.refresh(chat)
        return chat

    async def get_chat(
        self, chat_id: uuid.UUID, user_id: uuid.UUID, *, with_messages: bool = True
    ) -> Optional[Chat]:
        stmt = select(Chat).where(
            Chat.id == chat_id,
            Chat.user_id == user_id,
            Chat.deleted_at.is_(None),
        )
        if with_messages:
            stmt = stmt.options(selectinload(Chat.messages))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_chats(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Chat], int]:
        conditions = [Chat.user_id == user_id, Chat.deleted_at.is_(None)]
        if q:
            like = f"%{q.lower()}%"
            conditions.append(func.lower(Chat.title).like(like))
        count = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(Chat).where(and_(*conditions))
                )
            ).scalar_one()
        )
        stmt = (
            select(Chat)
            .where(and_(*conditions))
            .order_by(Chat.is_pinned.desc(), Chat.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, count

    async def soft_delete(self, chat: Chat) -> None:
        chat.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def rename(self, chat: Chat, title: str) -> Chat:
        chat.title = title[:255]
        await self._session.flush()
        return chat

    async def set_pinned(self, chat: Chat, pinned: bool) -> Chat:
        chat.is_pinned = pinned
        await self._session.flush()
        return chat

    async def add_message(
        self,
        *,
        chat_id: uuid.UUID,
        role: str,
        content: str,
        citations: list[Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            chat_id=chat_id,
            role=role,
            content=content,
            citations=citations,
            metrics=metrics,
        )
        self._session.add(msg)
        # bump chat updated_at
        chat = await self._session.get(Chat, chat_id)
        if chat:
            chat.updated_at = datetime.now(timezone.utc)
            if chat.title == "New chat" and role == "user":
                chat.title = content.strip()[:80] or "New chat"
        await self._session.flush()
        await self._session.refresh(msg)
        return msg
