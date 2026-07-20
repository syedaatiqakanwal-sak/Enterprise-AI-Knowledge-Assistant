"""Meeting Intelligence service — upload, Whisper, diarization, analysis, RAG chat."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.meetings import (
    analyze_meeting_text,
    extract_audio_with_ffmpeg,
    get_diarization_provider,
    get_transcription_provider,
)
from app.ai.rag.engine import RAGEngine
from app.core.config import settings
from app.core.exceptions import AppException
from app.models.document import Document, DocumentVersion
from app.models.enums import (
    ActionItemPriority,
    ActionItemStatus,
    DocumentStatus,
    DocumentVisibility,
    MeetingStatus,
)
from app.models.meeting import (
    Meeting,
    MeetingActionItem,
    MeetingChatMessage,
    MeetingDecision,
    MeetingSpeaker,
    MeetingSummary,
    MeetingTranscriptSegment,
)
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.meeting_repository import MeetingRepository
from app.services.checksum_service import ChecksumService
from app.services.meeting_jobs import meeting_job_queue, run_pipeline_stages
from app.services.metadata_service import sanitize_filename, unique_storage_key
from app.services.storage_service import get_storage_backend

logger = logging.getLogger(__name__)

ALLOWED_MEETING_EXT = {
    "mp3",
    "wav",
    "m4a",
    "aac",
    "flac",
    "ogg",
    "mp4",
    "mov",
    "mkv",
    "avi",
}

VIDEO_EXT = {"mp4", "mov", "mkv", "avi"}


class MeetingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MeetingRepository(session)
        self._docs = DocumentRepository(session)
        self._storage = get_storage_backend()
        Path(settings.MEETING_STORAGE_ROOT).mkdir(parents=True, exist_ok=True)

    async def _save_bytes(self, relative: str, data: bytes) -> str:
        return await self._storage.save(f"meetings/{relative}", data)

    async def upload(
        self,
        user: User,
        file: UploadFile,
        *,
        title: str | None = None,
        auto_process: bool = False,
    ) -> dict[str, Any]:
        raw = await file.read()
        if not raw:
            raise AppException("Empty file", code="EMPTY_FILE", status_code=400)
        if len(raw) > settings.MEETING_MAX_UPLOAD_BYTES:
            raise AppException(
                "Meeting file too large",
                code="FILE_TOO_LARGE",
                status_code=413,
            )
        original = sanitize_filename(file.filename or "meeting.mp3")
        ext = Path(original).suffix.lower().lstrip(".")
        if ext not in ALLOWED_MEETING_EXT:
            raise AppException(
                f"Unsupported meeting type .{ext}",
                code="UNSUPPORTED_FILE_TYPE",
                status_code=400,
                details={"allowed": sorted(ALLOWED_MEETING_EXT)},
            )
        mime = (file.content_type or "application/octet-stream").split(";")[0]
        storage_key = unique_storage_key(user.id, ext)
        await self._save_bytes(storage_key, raw)

        meeting = await self._repo.create(
            owner_id=user.id,
            title=title or Path(original).stem,
            original_filename=original,
            extension=ext,
            mime_type=mime,
            size=len(raw),
            storage_path=f"meetings/{storage_key}",
            status=MeetingStatus.UPLOADED.value,
        )
        if auto_process:
            return await self.process(user, meeting.id)
        meeting = await self._repo.get(meeting.id)
        assert meeting is not None
        return await self._serialize(meeting)

    async def transcribe(self, user: User, meeting_id: uuid.UUID) -> dict[str, Any]:
        meeting = await self._require(user, meeting_id)
        await self._run_transcription(meeting, finalize=True)
        meeting = await self._repo.get(
            meeting_id, owner_id=user.id, populate_existing=True
        )
        assert meeting is not None
        await meeting_job_queue.notify(
            user.id, "transcription_complete", meeting.id, "Transcript ready"
        )
        return await self._serialize(meeting)

    async def process(self, user: User, meeting_id: uuid.UUID) -> dict[str, Any]:
        meeting = await self._require(user, meeting_id)

        async def _runner() -> None:
            await self._run_full_pipeline(meeting.id)

        await run_pipeline_stages(meeting.id, user.id, _runner)
        meeting = await self._repo.get(
            meeting_id, owner_id=user.id, populate_existing=True
        )
        assert meeting is not None
        await meeting_job_queue.notify(
            user.id, "summary_ready", meeting.id, "Meeting analysis complete"
        )
        await meeting_job_queue.notify(
            user.id, "action_items_generated", meeting.id, "Action items extracted"
        )
        return await self._serialize(meeting)

    async def _run_full_pipeline(self, meeting_id: uuid.UUID) -> None:
        meeting = await self._repo.get(meeting_id)
        if meeting is None:
            return
        started = time.perf_counter()
        meeting.status = MeetingStatus.PROCESSING.value
        meeting.error = None
        await self._session.flush()

        try:
            await self._repo.clear_analysis(meeting_id)
            await self._run_transcription(meeting, finalize=False)
            meeting = await self._repo.get(meeting_id, populate_existing=True)
            assert meeting is not None

            meeting.status = MeetingStatus.ANALYZING.value
            await self._session.flush()

            full_text = "\n".join(
                f"[{s.speaker_label} {s.start_time:.1f}-{s.end_time:.1f}] {s.text}"
                for s in meeting.segments
            )
            from app.ai.meetings.provider import TranscriptSegment

            segs = [
                TranscriptSegment(
                    s.speaker_label, s.start_time, s.end_time, s.text, s.confidence
                )
                for s in meeting.segments
            ]
            analysis = await asyncio.to_thread(analyze_meeting_text, full_text, segs)

            await self._repo.set_summary(
                MeetingSummary(
                    meeting_id=meeting.id,
                    executive_summary=analysis["executive_summary"],
                    key_points=analysis["key_points"],
                    risks=analysis["risks"],
                    open_questions=analysis["open_questions"],
                    minutes=analysis["minutes"],
                    attendance=analysis["attendance"],
                )
            )
            await self._repo.add_action_items(
                [
                    MeetingActionItem(
                        meeting_id=meeting.id,
                        owner=a.get("owner"),
                        task=a["task"],
                        due_date=a.get("due_date"),
                        priority=a.get("priority", ActionItemPriority.MEDIUM.value),
                        status=a.get("status", ActionItemStatus.OPEN.value),
                    )
                    for a in analysis.get("action_items") or []
                ]
            )
            await self._repo.add_decisions(
                [
                    MeetingDecision(
                        meeting_id=meeting.id,
                        decision=d["decision"],
                        context=d.get("context"),
                        decided_by=d.get("decided_by"),
                    )
                    for d in analysis.get("decisions") or []
                ]
            )

            meeting.status = MeetingStatus.INDEXING.value
            await self._session.flush()

            if settings.MEETING_AUTO_INDEX_RAG and full_text.strip():
                from sqlalchemy import select
                from app.models.user import User as UserModel

                user = (
                    await self._session.execute(
                        select(UserModel).where(UserModel.id == meeting.owner_id)
                    )
                ).scalar_one()
                linked = await self._index_into_rag(
                    user, meeting.id, meeting.title, full_text
                )
                if linked:
                    meeting.linked_document_id = linked.id

            meeting.status = MeetingStatus.READY.value
            meeting.metrics = {
                **(meeting.metrics or {}),
                "pipeline_ms": round((time.perf_counter() - started) * 1000, 2),
                "deadlines": analysis.get("deadlines") or [],
            }
            await self._session.flush()
        except Exception as exc:
            logger.exception("Meeting pipeline failed")
            meeting.status = MeetingStatus.FAILED.value
            meeting.error = str(exc)
            await self._session.flush()
            raise AppException(
                f"Meeting processing failed: {exc}",
                code="MEETING_PROCESS_FAILED",
                status_code=500,
            ) from exc

    async def _run_transcription(
        self, meeting: Meeting, *, finalize: bool = True
    ) -> None:
        meeting.status = MeetingStatus.TRANSCRIBING.value
        await self._session.flush()

        data = await self._storage.open(meeting.storage_path)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / f"source.{meeting.extension}"
            src.write_bytes(bytes(data))
            wav = Path(tmp) / "audio.wav"
            audio_path = await asyncio.to_thread(
                extract_audio_with_ffmpeg, str(src), str(wav)
            )
            meeting.audio_path = meeting.storage_path
            if Path(audio_path).exists() and audio_path != str(src):
                wav_bytes = Path(audio_path).read_bytes()
                wav_key = unique_storage_key(meeting.owner_id, "wav")
                await self._save_bytes(wav_key, wav_bytes)
                meeting.audio_path = f"meetings/{wav_key}"
                audio_for_asr = audio_path
            else:
                audio_for_asr = str(src)

            provider = get_transcription_provider()
            result = await asyncio.to_thread(provider.transcribe, audio_for_asr)

            meeting.status = MeetingStatus.DIARIZING.value
            await self._session.flush()

            diarizer = get_diarization_provider()
            segments = await asyncio.to_thread(
                diarizer.assign_speakers, audio_for_asr, result.segments
            )

        # Replace speakers/segments only (keep summary if re-transcribing alone)
        for model in (MeetingTranscriptSegment, MeetingSpeaker):
            rows = (
                await self._session.execute(
                    select(model).where(model.meeting_id == meeting.id)
                )
            ).scalars().all()
            for row in rows:
                await self._session.delete(row)
        await self._session.flush()

        talk: dict[str, float] = {}
        for s in segments:
            talk[s.speaker] = talk.get(s.speaker, 0.0) + max(0.0, s.end - s.start)

        await self._repo.add_speakers(
            [
                MeetingSpeaker(
                    meeting_id=meeting.id,
                    label=label,
                    display_name=label,
                    talk_time_seconds=round(secs, 2),
                )
                for label, secs in sorted(talk.items())
            ]
        )
        await self._repo.add_segments(
            [
                MeetingTranscriptSegment(
                    meeting_id=meeting.id,
                    speaker_label=s.speaker,
                    start_time=s.start,
                    end_time=s.end,
                    text=s.text,
                    confidence=s.confidence,
                    words=s.words or None,
                )
                for s in segments
            ]
        )
        meeting.duration_seconds = result.duration
        meeting.language = result.language
        meeting.provider = result.provider
        meeting.metrics = {
            "segment_count": len(segments),
            "speaker_count": len(talk),
        }
        meeting.status = (
            MeetingStatus.READY.value if finalize else MeetingStatus.DIARIZING.value
        )
        await self._session.flush()
        await self._session.refresh(
            meeting, attribute_names=["speakers", "segments", "status", "metrics"]
        )

    async def _index_into_rag(
        self, user: User, meeting_id: uuid.UUID, title: str, text: str
    ) -> Document | None:
        from app.ai.indexing import IndexingService

        text_bytes = text.encode("utf-8")
        storage_key = unique_storage_key(user.id, "txt")
        await self._storage.save(storage_key, text_bytes)
        doc_id = uuid.uuid4()
        linked = await self._docs.create(
            id=doc_id,
            uuid=doc_id,
            owner_id=user.id,
            filename=f"Meeting-{title[:80]}.txt",
            original_filename=f"Meeting-{title[:80]}.txt",
            extension="txt",
            mime_type="text/plain",
            size=len(text_bytes),
            storage_path=storage_key,
            status=DocumentStatus.READY.value,
            visibility=DocumentVisibility.PRIVATE.value,
            version=1,
            checksum=ChecksumService.sha256_bytes(text_bytes),
            tags=["meeting", "transcript"],
            description=f"Auto-indexed meeting transcript: {title}",
        )
        await self._docs.add_version(
            DocumentVersion(
                document_id=linked.id,
                version=1,
                storage_path=storage_key,
                size=len(text_bytes),
                checksum=linked.checksum,
                mime_type="text/plain",
                created_by=user.id,
            )
        )
        meeting = await self._repo.get(meeting_id)
        if meeting:
            meeting.linked_document_id = linked.id
        await self._session.flush()
        index_result = await IndexingService(self._session).index_document(linked.id)
        logger.info("Meeting RAG index result: %s", index_result)
        return linked

    async def list_meetings(
        self,
        user: User,
        *,
        q: str | None = None,
        speaker: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        rows, total = await self._repo.list_meetings(
            user.id, q=q, speaker=speaker, status=status, limit=limit, offset=offset
        )
        items = [await self._serialize(m, brief=True) for m in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def get(self, user: User, meeting_id: uuid.UUID) -> dict[str, Any]:
        meeting = await self._require(user, meeting_id)
        return await self._serialize(meeting)

    async def get_transcript(self, user: User, meeting_id: uuid.UUID) -> dict[str, Any]:
        meeting = await self._require(user, meeting_id)
        return {
            "meeting_id": str(meeting.id),
            "duration_seconds": meeting.duration_seconds,
            "language": meeting.language,
            "speakers": [
                {
                    "label": s.label,
                    "display_name": s.display_name,
                    "talk_time_seconds": s.talk_time_seconds,
                }
                for s in meeting.speakers
            ],
            "segments": [
                {
                    "id": str(seg.id),
                    "speaker": seg.speaker_label,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "text": seg.text,
                    "confidence": seg.confidence,
                    "words": seg.words or [],
                }
                for seg in meeting.segments
            ],
        }

    async def get_summary(self, user: User, meeting_id: uuid.UUID) -> dict[str, Any]:
        meeting = await self._require(user, meeting_id)
        if meeting.summary is None:
            raise AppException(
                "Summary not ready",
                code="SUMMARY_NOT_READY",
                status_code=404,
            )
        s = meeting.summary
        return {
            "meeting_id": str(meeting.id),
            "executive_summary": s.executive_summary,
            "key_points": s.key_points or [],
            "risks": s.risks or [],
            "open_questions": s.open_questions or [],
            "minutes": s.minutes or {},
            "attendance": s.attendance or [],
            "action_items": [
                {
                    "id": str(a.id),
                    "owner": a.owner,
                    "task": a.task,
                    "due_date": a.due_date,
                    "priority": a.priority,
                    "status": a.status,
                }
                for a in meeting.action_items
            ],
            "decisions": [
                {
                    "id": str(d.id),
                    "decision": d.decision,
                    "context": d.context,
                    "decided_by": d.decided_by,
                }
                for d in meeting.decisions
            ],
            "deadlines": (meeting.metrics or {}).get("deadlines") or [],
        }

    async def chat(
        self, user: User, meeting_id: uuid.UUID, message: str
    ) -> dict[str, Any]:
        meeting = await self._require(user, meeting_id)
        if not meeting.linked_document_id:
            raise AppException(
                "Meeting transcript is not indexed for chat yet. Run process first.",
                code="MEETING_NOT_INDEXED",
                status_code=400,
            )
        history = [
            {"role": m.role, "content": m.content}
            for m in meeting.chat_messages
            if m.role in ("user", "assistant")
        ][-12:]

        await self._repo.add_chat_message(
            MeetingChatMessage(
                meeting_id=meeting.id, role="user", content=message
            )
        )

        rag = RAGEngine(self._session)
        result = await rag.answer(
            user,
            message,
            history=history,
            document_id=meeting.linked_document_id,
        )
        citations = [c.to_dict() for c in result.citations]
        assistant = await self._repo.add_chat_message(
            MeetingChatMessage(
                meeting_id=meeting.id,
                role="assistant",
                content=result.answer,
                citations=citations,
                metrics=result.metrics,
            )
        )
        return {
            "meeting_id": str(meeting.id),
            "message_id": str(assistant.id),
            "answer": result.answer,
            "citations": citations,
            "grounded": result.grounded,
            "metrics": result.metrics,
            "history": [
                {"role": m.role, "content": m.content, "id": str(m.id)}
                for m in (
                    await self._repo.get(meeting.id, populate_existing=True)
                ).chat_messages  # type: ignore[union-attr]
            ],
        }

    async def delete(self, user: User, meeting_id: uuid.UUID) -> None:
        meeting = await self._require(user, meeting_id)
        if meeting.linked_document_id:
            try:
                from app.ai.indexing import IndexingService

                await IndexingService(self._session).delete_embeddings(
                    meeting.linked_document_id
                )
            except Exception:
                logger.warning("Failed to delete meeting embeddings", exc_info=True)
        await self._repo.soft_delete(meeting)

    async def _require(self, user: User, meeting_id: uuid.UUID) -> Meeting:
        meeting = await self._repo.get(meeting_id, owner_id=user.id)
        if meeting is None:
            raise AppException(
                "Meeting not found",
                code="MEETING_NOT_FOUND",
                status_code=404,
            )
        return meeting

    async def _serialize(self, meeting: Meeting, *, brief: bool = False) -> dict[str, Any]:
        base = {
            "id": str(meeting.id),
            "title": meeting.title,
            "original_filename": meeting.original_filename,
            "extension": meeting.extension,
            "mime_type": meeting.mime_type,
            "size": meeting.size,
            "status": meeting.status,
            "duration_seconds": meeting.duration_seconds,
            "language": meeting.language,
            "provider": meeting.provider,
            "linked_document_id": str(meeting.linked_document_id)
            if meeting.linked_document_id
            else None,
            "error": meeting.error,
            "metrics": meeting.metrics or {},
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            "speaker_count": len(meeting.speakers or []),
        }
        if brief:
            return base

        speakers = list(meeting.speakers or [])
        segments = list(meeting.segments or [])
        summary = meeting.summary
        action_items = list(meeting.action_items or [])
        decisions = list(meeting.decisions or [])
        chat_messages = list(meeting.chat_messages or [])

        base.update(
            {
                "speakers": [
                    {
                        "id": str(s.id),
                        "label": s.label,
                        "display_name": s.display_name,
                        "talk_time_seconds": s.talk_time_seconds,
                    }
                    for s in speakers
                ],
                "segments": [
                    {
                        "id": str(seg.id),
                        "speaker": seg.speaker_label,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "text": seg.text,
                        "confidence": seg.confidence,
                    }
                    for seg in segments
                ],
                "summary": {
                    "executive_summary": summary.executive_summary,
                    "key_points": summary.key_points or [],
                    "risks": summary.risks or [],
                    "open_questions": summary.open_questions or [],
                    "minutes": summary.minutes or {},
                    "attendance": summary.attendance or [],
                }
                if summary
                else None,
                "action_items": [
                    {
                        "id": str(a.id),
                        "owner": a.owner,
                        "task": a.task,
                        "due_date": a.due_date,
                        "priority": a.priority,
                        "status": a.status,
                    }
                    for a in action_items
                ],
                "decisions": [
                    {
                        "id": str(d.id),
                        "decision": d.decision,
                        "context": d.context,
                        "decided_by": d.decided_by,
                    }
                    for d in decisions
                ],
                "chat_messages": [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "citations": m.citations or [],
                    }
                    for m in chat_messages
                ],
            }
        )
        return base
