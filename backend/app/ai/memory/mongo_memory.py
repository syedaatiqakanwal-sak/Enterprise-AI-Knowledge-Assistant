"""MongoDB conversation memory / agent-state store (Module 6)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def save_turn(
    *,
    user_id: str,
    chat_id: str,
    question: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
) -> None:
    """Persist a conversation turn for memory / analytics (best-effort)."""
    try:
        from app.db.mongodb import MongoDBManager

        db = MongoDBManager.get_db()
        await db.conversation_memory.insert_one(
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "question": question,
                "answer": answer,
                "citations": citations or [],
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logger.debug("Mongo conversation_memory write skipped", exc_info=True)


async def save_agent_state(
    *, user_id: str, chat_id: str, state: dict[str, Any]
) -> None:
    """Placeholder for future agent state (Module 8+)."""
    try:
        from app.db.mongodb import MongoDBManager

        db = MongoDBManager.get_db()
        await db.agent_state.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {
                "$set": {
                    "state": state,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception:
        logger.debug("Mongo agent_state write skipped", exc_info=True)
