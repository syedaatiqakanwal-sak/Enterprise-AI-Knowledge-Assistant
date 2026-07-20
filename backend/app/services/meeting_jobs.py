"""In-process meeting job queues (audio → transcribe → diarize → summarize → embed)."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Awaitable
from uuid import UUID

logger = logging.getLogger(__name__)


class MeetingJobType(StrEnum):
    AUDIO = "audio_processing"
    TRANSCRIPTION = "transcription"
    DIARIZATION = "diarization"
    SUMMARY = "summary"
    EMBEDDING = "embedding"


@dataclass
class MeetingJob:
    job_type: MeetingJobType
    meeting_id: UUID
    owner_id: UUID
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "queued"


class MeetingJobQueue:
    """Lightweight asyncio queues for meeting pipeline stages."""

    def __init__(self) -> None:
        self._queues: dict[MeetingJobType, deque[MeetingJob]] = defaultdict(deque)
        self._history: list[dict[str, Any]] = []
        self._notifications: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, job: MeetingJob) -> MeetingJob:
        async with self._lock:
            self._queues[job.job_type].append(job)
            self._history.append(
                {
                    "job_type": job.job_type.value,
                    "meeting_id": str(job.meeting_id),
                    "status": "queued",
                    "created_at": job.created_at.isoformat(),
                }
            )
        logger.info("Enqueued %s for meeting %s", job.job_type, job.meeting_id)
        return job

    async def notify(self, user_id: UUID, event: str, meeting_id: UUID, detail: str = "") -> None:
        async with self._lock:
            self._notifications.append(
                {
                    "user_id": str(user_id),
                    "event": event,
                    "meeting_id": str(meeting_id),
                    "detail": detail,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        logger.info("Notify %s: %s (%s)", user_id, event, meeting_id)

    def notifications_for(self, user_id: UUID) -> list[dict[str, Any]]:
        uid = str(user_id)
        return [n for n in self._notifications if n["user_id"] == uid]

    def stats(self) -> dict[str, int]:
        return {jt.value: len(self._queues[jt]) for jt in MeetingJobType}


meeting_job_queue = MeetingJobQueue()


async def run_pipeline_stages(
    meeting_id: UUID,
    owner_id: UUID,
    runner: Callable[[], Awaitable[None]],
) -> None:
    """Mark stages queued then execute the full pipeline runner."""
    for jt in MeetingJobType:
        await meeting_job_queue.enqueue(
            MeetingJob(job_type=jt, meeting_id=meeting_id, owner_id=owner_id)
        )
    await runner()
