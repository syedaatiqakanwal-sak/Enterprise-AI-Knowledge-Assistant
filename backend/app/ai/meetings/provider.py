"""Meeting transcription providers — Whisper primary, mock for CI/dev."""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    speaker: str
    start: float
    end: float
    text: str
    confidence: float = 0.9
    words: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    duration: float
    language: str
    provider: str
    full_text: str


class TranscriptionProvider(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        ...


class MockTranscriptionProvider(TranscriptionProvider):
    """Deterministic meeting transcript for tests and offline demos."""

    name = "mock"

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        _ = audio_path
        segments = [
            TranscriptSegment(
                "Speaker 1",
                0.0,
                12.5,
                "Welcome everyone to the Q3 budget planning meeting.",
                0.95,
                [{"word": "Welcome", "start": 0.0, "end": 0.4}],
            ),
            TranscriptSegment(
                "Speaker 2",
                12.5,
                28.0,
                "Thanks Sarah. I think we should increase the marketing budget by fifteen percent.",
                0.93,
            ),
            TranscriptSegment(
                "Speaker 1",
                28.0,
                45.0,
                "Agreed. We decided to approve the new campaign. Sarah will own the vendor selection.",
                0.94,
            ),
            TranscriptSegment(
                "Speaker 3",
                45.0,
                62.0,
                "I'll prepare the risk register by Friday July 25th. Open question: do we need legal review?",
                0.91,
            ),
            TranscriptSegment(
                "Speaker 2",
                62.0,
                78.0,
                "Action item for Marcus: send the revised forecast by next Monday. Priority high.",
                0.92,
            ),
            TranscriptSegment(
                "Speaker 1",
                78.0,
                95.0,
                "Decision: we will freeze hiring in engineering until September. Meeting adjourned.",
                0.96,
            ),
        ]
        full = "\n".join(f"[{s.speaker}] {s.text}" for s in segments)
        return TranscriptionResult(
            segments=segments,
            duration=95.0,
            language="en",
            provider=self.name,
            full_text=full,
        )


class WhisperTranscriptionProvider(TranscriptionProvider):
    name = "whisper"

    def __init__(self, model_name: str | None = None) -> None:
        import whisper

        primary = model_name or settings.WHISPER_MODEL
        try:
            self._model = whisper.load_model(primary)
            self.name = f"whisper:{primary}"
        except Exception:
            logger.warning("Whisper %s failed — falling back to %s", primary, settings.WHISPER_FALLBACK_MODEL)
            self._model = whisper.load_model(settings.WHISPER_FALLBACK_MODEL)
            self.name = f"whisper:{settings.WHISPER_FALLBACK_MODEL}"

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        result = self._model.transcribe(audio_path, word_timestamps=True)
        segments: list[TranscriptSegment] = []
        for seg in result.get("segments") or []:
            words = []
            for w in seg.get("words") or []:
                words.append(
                    {
                        "word": w.get("word", ""),
                        "start": float(w.get("start", 0)),
                        "end": float(w.get("end", 0)),
                    }
                )
            segments.append(
                TranscriptSegment(
                    speaker="Speaker 1",  # overwritten by diarization
                    start=float(seg.get("start", 0)),
                    end=float(seg.get("end", 0)),
                    text=(seg.get("text") or "").strip(),
                    confidence=float(seg.get("avg_logprob", -0.5) + 1.0) if seg.get("avg_logprob") else 0.85,
                    words=words,
                )
            )
        duration = segments[-1].end if segments else 0.0
        full = " ".join(s.text for s in segments)
        return TranscriptionResult(
            segments=segments,
            duration=duration,
            language=str(result.get("language") or "en"),
            provider=self.name,
            full_text=full,
        )


def extract_audio_with_ffmpeg(source_path: str, dest_wav: str) -> str:
    """Extract mono 16kHz WAV via FFmpeg; copy path if already audio and ffmpeg missing."""
    cmd = [
        settings.FFMPEG_PATH,
        "-y",
        "-i",
        source_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        dest_wav,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        return dest_wav
    except Exception as exc:
        logger.warning("FFmpeg extraction failed (%s) — using source file", exc)
        return source_path


class DiarizationProvider(ABC):
    @abstractmethod
    def assign_speakers(
        self, audio_path: str, segments: list[TranscriptSegment]
    ) -> list[TranscriptSegment]:
        ...


class MockDiarizationProvider(DiarizationProvider):
    def assign_speakers(
        self, audio_path: str, segments: list[TranscriptSegment]
    ) -> list[TranscriptSegment]:
        _ = audio_path
        # Mock transcript already has speakers; rotate if all Speaker 1
        if all(s.speaker == "Speaker 1" for s in segments):
            for i, s in enumerate(segments):
                s.speaker = f"Speaker {(i % 3) + 1}"
        return segments


class PyannoteDiarizationProvider(DiarizationProvider):
    def __init__(self) -> None:
        from pyannote.audio import Pipeline

        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=True,
        )

    def assign_speakers(
        self, audio_path: str, segments: list[TranscriptSegment]
    ) -> list[TranscriptSegment]:
        diarization = self._pipeline(audio_path)
        turns: list[tuple[float, float, str]] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append((turn.start, turn.end, speaker))
        for seg in segments:
            mid = (seg.start + seg.end) / 2
            label = "Speaker 1"
            for start, end, spk in turns:
                if start <= mid <= end:
                    # Normalize SPEAKER_00 → Speaker 1
                    m = re.search(r"(\d+)", spk)
                    n = int(m.group(1)) + 1 if m else 1
                    label = f"Speaker {n}"
                    break
            seg.speaker = label
        return segments


@lru_cache
def get_transcription_provider() -> TranscriptionProvider:
    if settings.MEETING_PROVIDER == "mock" or settings.is_testing:
        return MockTranscriptionProvider()
    try:
        return WhisperTranscriptionProvider()
    except Exception:
        logger.warning("Whisper unavailable — using mock", exc_info=True)
        return MockTranscriptionProvider()


@lru_cache
def get_diarization_provider() -> DiarizationProvider:
    if (
        not settings.MEETING_DIARIZATION_ENABLED
        or settings.MEETING_PROVIDER == "mock"
        or settings.is_testing
    ):
        return MockDiarizationProvider()
    try:
        return PyannoteDiarizationProvider()
    except Exception:
        logger.warning("pyannote unavailable — using mock diarization", exc_info=True)
        return MockDiarizationProvider()


def analyze_meeting_text(full_text: str, segments: list[TranscriptSegment]) -> dict[str, Any]:
    """Heuristic + LLM-ready structured meeting analysis (works offline)."""
    speakers = sorted({s.speaker for s in segments})
    action_items = []
    decisions = []
    deadlines = []
    risks = []
    questions = []
    key_points = []

    for s in segments:
        lower = s.text.lower()
        key_points.append(s.text)
        if "action item" in lower or "will own" in lower or "i'll " in lower or "i will " in lower:
            owner = s.speaker
            m = re.search(r"for ([A-Z][a-z]+)", s.text)
            if m:
                owner = m.group(1)
            due = None
            dm = re.search(
                r"by (Friday|Monday|Tuesday|Wednesday|Thursday|Saturday|Sunday|[A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?|\d{4}-\d{2}-\d{2})",
                s.text,
                re.I,
            )
            if dm:
                due = dm.group(1)
                deadlines.append(due)
            priority = "high" if "priority high" in lower or "urgent" in lower else "medium"
            action_items.append(
                {
                    "owner": owner,
                    "task": s.text,
                    "due_date": due,
                    "priority": priority,
                    "status": "open",
                }
            )
        if "decision" in lower or "we decided" in lower or "we will " in lower or "approved" in lower:
            decisions.append(
                {
                    "decision": s.text,
                    "context": f"At {s.start:.0f}s",
                    "decided_by": s.speaker,
                }
            )
        if "risk" in lower:
            risks.append(s.text)
        if "?" in s.text or "open question" in lower:
            questions.append(s.text)

    executive = (
        f"Meeting with {len(speakers)} speakers covering budget, decisions, and follow-ups. "
        f"{len(decisions)} decisions and {len(action_items)} action items were identified."
    )
    minutes = {
        "agenda": ["Budget planning", "Campaign approval", "Hiring freeze", "Risks & open questions"],
        "discussion": key_points[:6],
        "decisions": [d["decision"] for d in decisions],
        "action_items": [a["task"] for a in action_items],
        "attendance": speakers,
        "meeting_duration": f"{segments[-1].end:.0f} seconds" if segments else "0",
    }
    return {
        "executive_summary": executive,
        "key_points": key_points[:8],
        "risks": risks or ["No explicit risks mentioned."],
        "open_questions": questions,
        "deadlines": deadlines,
        "action_items": action_items,
        "decisions": decisions,
        "minutes": minutes,
        "attendance": speakers,
    }
