"""Backend contracts shared by mock and FunASR implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..schemas import TranscriptEvent
from ..voiceprints import VoiceprintStore


@dataclass(frozen=True)
class SessionOptions:
    session_id: str
    sample_rate: int
    language: str
    hotwords: tuple[str, ...]
    max_speakers: int


class StreamingSession(ABC):
    @abstractmethod
    async def feed_audio(self, pcm16le: bytes) -> list[TranscriptEvent]:
        """Consume one PCM chunk and return zero or more partial events."""

    @abstractmethod
    async def commit(self) -> list[TranscriptEvent]:
        """Finalize the current utterance without ending the session."""

    @abstractmethod
    async def close(self) -> list[TranscriptEvent]:
        """Finalize pending audio and release per-session state."""


class ASRBackend(ABC):
    name = "base"

    @abstractmethod
    async def startup(self) -> None:
        """Load and validate models."""

    async def shutdown(self) -> None:
        """Release optional backend resources."""
        return None

    @abstractmethod
    def is_ready(self) -> bool:
        """Return whether new sessions can be accepted."""

    @abstractmethod
    def model_info(self) -> dict[str, str]:
        """Return non-secret model identifiers for readiness reporting."""

    @abstractmethod
    def create_session(
        self, options: SessionOptions, voiceprints: VoiceprintStore
    ) -> StreamingSession:
        """Create isolated streaming state for one client."""

    @abstractmethod
    async def embed_audio(self, audio: np.ndarray) -> np.ndarray:
        """Extract one normalized speaker embedding for voiceprint enrollment."""
