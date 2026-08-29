"""Provider-neutral schemas used by realtime ASR implementations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class TranscriptEventType(str, Enum):
    """Events emitted by a realtime ASR provider."""

    SESSION_STARTED = "session_started"
    SEGMENT = "segment"
    SESSION_ENDED = "session_ended"
    ERROR = "error"


@dataclass(frozen=True)
class ASRStreamRequest:
    """Request metadata for one realtime transcription session.

    ``audio_stream`` is intentionally provider-defined. The mock provider ignores it;
    a WebSocket provider can consume browser audio chunks without changing the UI
    event schema.
    """

    session_id: str
    audio_stream: Any | None = None
    language: str = "zh"


@dataclass(frozen=True)
class TranscriptSegment:
    """One partial or final speaker-attributed transcript segment."""

    segment_id: str
    text: str
    start_ms: int
    end_ms: int
    speaker_id: str
    is_final: bool
    speaker_name: str | None = None
    verification_score: float | None = None

    @property
    def display_speaker(self) -> str:
        """Prefer a verified identity and fall back to the diarization label."""

        return self.speaker_name or self.speaker_id

    def to_state(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for ``gr.State``."""

        return asdict(self)

    @classmethod
    def from_state(cls, value: dict[str, Any]) -> TranscriptSegment:
        """Restore a segment from ``gr.State``."""

        return cls(**value)


@dataclass(frozen=True)
class TranscriptEvent:
    """An event in a realtime ASR session."""

    event_type: TranscriptEventType
    session_id: str
    segment: TranscriptSegment | None = None
    message: str | None = None


@dataclass(frozen=True)
class ProviderVoiceprint:
    """Voiceprint registration returned by an ASR provider."""

    provider_id: str
    sample_count: int = 1
