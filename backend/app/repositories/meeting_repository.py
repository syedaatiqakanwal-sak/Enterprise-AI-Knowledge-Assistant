"""Meeting Intelligence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import (
    Meeting,
    MeetingActionItem,
    MeetingChatMessage,
    MeetingDecision,
    MeetingSpeaker,
    MeetingSummary,
    MeetingTranscriptSegment,
)


class MeetingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _detail_options(self):
        return (
            selectinload(Meeting.speakers),
            selectinload(Meeting.segments),
            selectinload(Meeting.summary),
            selectinload(Meeting.action_items),
            selectinload(Meeting.decisions),
            selectinload(Meeting.chat_messages),
        )

    async def create(self, **kwargs) -> Meeting:
        meeting = Meeting(**kwargs)
        self._session.add(meeting)
        await self._session.flush()
        await self._session.refresh(meeting)
        return meeting

    async def get(
        self,
        meeting_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
        populate_existing: bool = False,
    ) -> Optional[Meeting]:
        stmt = (
            select(Meeting)
            .where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
            .options(*self._detail_options())
        )
        if owner_id:
            stmt = stmt.where(Meeting.owner_id == owner_id)
        if populate_existing:
            stmt = stmt.execution_options(populate_existing=True)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_meetings(
        self,
        owner_id: uuid.UUID,
        *,
        q: str | None = None,
        speaker: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Meeting], int]:
        conditions = [
            Meeting.owner_id == owner_id,
            Meeting.deleted_at.is_(None),
        ]
        if status:
            conditions.append(Meeting.status == status)
        if q:
            like = f"%{q.lower()}%"
            conditions.append(
                or_(
                    func.lower(Meeting.title).like(like),
                    func.lower(Meeting.original_filename).like(like),
                )
            )
        where = and_(*conditions)
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(Meeting).where(where)
                )
            ).scalar_one()
        )
        stmt = (
            select(Meeting)
            .where(where)
            .options(selectinload(Meeting.speakers), selectinload(Meeting.summary))
            .order_by(Meeting.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        if speaker:
            sp_like = speaker.lower()
            rows = [
                m
                for m in rows
                if any(
                    sp_like in (s.label or "").lower()
                    or sp_like in (s.display_name or "").lower()
                    for s in m.speakers
                )
            ]
            total = len(rows)
        return rows, total

    async def soft_delete(self, meeting: Meeting) -> None:
        meeting.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def clear_analysis(self, meeting_id: uuid.UUID) -> None:
        for model in (
            MeetingTranscriptSegment,
            MeetingSpeaker,
            MeetingActionItem,
            MeetingDecision,
            MeetingSummary,
        ):
            rows = (
                await self._session.execute(
                    select(model).where(model.meeting_id == meeting_id)
                )
            ).scalars().all()
            for row in rows:
                await self._session.delete(row)
        await self._session.flush()

    async def add_speakers(self, speakers: list[MeetingSpeaker]) -> None:
        for s in speakers:
            self._session.add(s)
        await self._session.flush()

    async def add_segments(self, segments: list[MeetingTranscriptSegment]) -> None:
        for s in segments:
            self._session.add(s)
        await self._session.flush()

    async def set_summary(self, summary: MeetingSummary) -> MeetingSummary:
        self._session.add(summary)
        await self._session.flush()
        return summary

    async def add_action_items(self, items: list[MeetingActionItem]) -> None:
        for i in items:
            self._session.add(i)
        await self._session.flush()

    async def add_decisions(self, decisions: list[MeetingDecision]) -> None:
        for d in decisions:
            self._session.add(d)
        await self._session.flush()

    async def add_chat_message(self, msg: MeetingChatMessage) -> MeetingChatMessage:
        self._session.add(msg)
        await self._session.flush()
        await self._session.refresh(msg)
        return msg
