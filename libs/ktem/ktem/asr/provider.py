"""ASR provider contracts and a deterministic mock implementation."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator

from .schema import (
    ASRStreamRequest,
    ProviderVoiceprint,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
)


class ASRProvider(ABC):
    """Interface implemented by mock and remote realtime ASR providers."""

    name = "base"

    @abstractmethod
    def stream(self, request: ASRStreamRequest) -> Iterator[TranscriptEvent]:
        """Yield partial/final diarized transcript events."""

    @abstractmethod
    def register_voiceprint(
        self, display_name: str, audio_path: str
    ) -> ProviderVoiceprint:
        """Register a voice sample and return its provider-side identifier."""

    @abstractmethod
    def delete_voiceprint(self, provider_id: str) -> None:
        """Delete a provider-side voiceprint."""

    def healthcheck(self) -> None:
        """Raise when the provider cannot accept new sessions."""

    def open_live_session(self, request: ASRStreamRequest):
        """Open a stateful microphone stream for providers that support it."""

        raise NotImplementedError(f"{self.name} 不支持实时麦克风音频")


class MockASRProvider(ASRProvider):
    """Deterministic multi-speaker stream used before an ASR API is configured."""

    name = "mock"

    _SCRIPT = (
        (
            "speaker_00",
            0,
            3900,
            (
                "您好，",
                "您好，我最近总觉得胸口有些闷，",
                "您好，我最近总觉得胸口有些闷，走快一点就会喘。",
            ),
        ),
        (
            "speaker_01",
            4200,
            7800,
            (
                "这种情况",
                "这种情况大概持续多久了？",
                "这种情况大概持续多久了？有没有胸痛或者心悸？",
            ),
        ),
        (
            "speaker_00",
            8100,
            11300,
            (
                "差不多",
                "差不多有两个星期，",
                "差不多有两个星期，偶尔还会心跳得很快。",
            ),
        ),
        (
            "speaker_01",
            11600,
            15100,
            (
                "我了解了。",
                "我了解了。先测一下血压和心率，",
                "我了解了。先测一下血压和心率，再安排心电图检查。",
            ),
        ),
    )

    def __init__(self, interval_seconds: float = 0.55):
        self.interval_seconds = max(0.0, interval_seconds)

    def stream(self, request: ASRStreamRequest) -> Iterator[TranscriptEvent]:
        yield TranscriptEvent(
            event_type=TranscriptEventType.SESSION_STARTED,
            session_id=request.session_id,
        )

        for index, (speaker_id, start_ms, end_ms, partials) in enumerate(self._SCRIPT):
            segment_id = f"{request.session_id}-seg-{index:03d}"
            for partial_index, text in enumerate(partials):
                if self.interval_seconds:
                    time.sleep(self.interval_seconds)
                yield TranscriptEvent(
                    event_type=TranscriptEventType.SEGMENT,
                    session_id=request.session_id,
                    segment=TranscriptSegment(
                        segment_id=segment_id,
                        text=text,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        speaker_id=speaker_id,
                        is_final=partial_index == len(partials) - 1,
                    ),
                )

        yield TranscriptEvent(
            event_type=TranscriptEventType.SESSION_ENDED,
            session_id=request.session_id,
        )

    def register_voiceprint(
        self, display_name: str, audio_path: str
    ) -> ProviderVoiceprint:
        del display_name, audio_path
        return ProviderVoiceprint(provider_id=f"mock-{uuid.uuid4().hex}")

    def delete_voiceprint(self, provider_id: str) -> None:
        del provider_id
