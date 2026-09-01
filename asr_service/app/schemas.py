"""Provider-neutral HTTP and WebSocket schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    SESSION_STARTED = "session_started"
    SEGMENT = "segment"
    SESSION_ENDED = "session_ended"
    ERROR = "error"


class StartMessage(BaseModel):
    type: str = "start"
    session_id: str = Field(min_length=1, max_length=128)
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "pcm_s16le"
    language: str = "zh"
    hotwords: list[str] = Field(default_factory=list, max_length=100)
    max_speakers: int | None = Field(default=None, ge=1, le=32)


class Segment(BaseModel):
    segment_id: str
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_id: str
    is_final: bool
    speaker_name: str | None = None
    verification_score: float | None = Field(default=None, ge=-1.0, le=1.0)


class TranscriptEvent(BaseModel):
    event_type: EventType
    session_id: str
    segment: Segment | None = None
    message: str | None = None


class VoiceprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    sample_count: int
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    backend: str
    models: dict[str, str] = Field(default_factory=dict)
