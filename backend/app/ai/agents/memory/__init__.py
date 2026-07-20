"""Agent memory — short-term, long-term, conversation, tool history, agent state."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)

# Process-local short-term memory (Redis preferred when available)
_SHORT_TERM: dict[str, tuple[float, dict[str, Any]]] = {}


class AgentMemory:
    def __init__(self, *, user_id: UUID, session_id: UUID | None = None) -> None:
        self.user_id = str(user_id)
        self.session_id = str(session_id) if session_id else "global"
        self._key = f"agent:{self.user_id}:{self.session_id}"

    async def get_short_term(self) -> dict[str, Any]:
        cached = await self._redis_get(self._key)
        if cached is not None:
            return cached
        entry = _SHORT_TERM.get(self._key)
        if not entry:
            return {}
        expires, data = entry
        if expires < time.time():
            _SHORT_TERM.pop(self._key, None)
            return {}
        return dict(data)

    async def set_short_term(self, data: dict[str, Any]) -> None:
        ttl = settings.AGENT_MEMORY_TTL_SECONDS
        _SHORT_TERM[self._key] = (time.time() + ttl, dict(data))
        await self._redis_set(self._key, data, ttl)

    async def merge_short_term(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_short_term()
        current.update(patch)
        await self.set_short_term(current)
        return current

    async def save_long_term(self, state: dict[str, Any]) -> None:
        try:
            from app.ai.memory.mongo_memory import save_agent_state

            await save_agent_state(
                user_id=self.user_id,
                chat_id=self.session_id,
                state=state,
            )
        except Exception:
            logger.debug("Long-term agent memory skipped", exc_info=True)

    async def append_conversation(
        self, role: str, content: str, *, meta: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        mem = await self.get_short_term()
        history = list(mem.get("conversation") or [])
        history.append({"role": role, "content": content, "meta": meta or {}})
        history = history[-40:]
        mem["conversation"] = history
        await self.set_short_term(mem)
        return history

    async def append_tool_history(self, record: dict[str, Any]) -> None:
        mem = await self.get_short_term()
        hist = list(mem.get("tool_history") or [])
        hist.append(record)
        mem["tool_history"] = hist[-50:]
        await self.set_short_term(mem)

    async def _redis_get(self, key: str) -> dict[str, Any] | None:
        try:
            from app.db.redis import RedisManager

            client = RedisManager.get_client()
            raw = await client.get(key)
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    async def _redis_set(self, key: str, data: dict[str, Any], ttl: int) -> None:
        try:
            from app.db.redis import RedisManager

            client = RedisManager.get_client()
            await client.set(key, json.dumps(data, default=str), ex=ttl)
        except Exception:
            logger.debug("Redis agent memory set skipped", exc_info=True)
