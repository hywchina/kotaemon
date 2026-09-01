"""Deterministic backend for API development and tests without model downloads."""

from __future__ import annotations

import numpy as np

from ..audio import pcm16le_to_float
from ..clustering import OnlineSpeakerTracker, normalize_embedding
from ..config import Settings
from ..schemas import EventType, Segment, TranscriptEvent
from ..voiceprints import VoiceprintStore
from .base import ASRBackend, SessionOptions, StreamingSession

MOCK_TEXTS = (
    "您好，我最近总觉得胸口有些闷。",
    "这种情况大概持续多久了？",
    "差不多有两个星期。",
    "先测一下血压和心率。",
)


def _mock_embedding(audio: np.ndarray) -> np.ndarray:
    if not len(audio):
        raise ValueError("Audio sample is empty")
    vector = np.asarray(
        [
            float(np.mean(audio)),
            float(np.std(audio)),
            float(np.sqrt(np.mean(np.square(audio)))),
            float(np.max(np.abs(audio))),
            min(1.0, len(audio) / 16000.0),
        ],
        dtype=np.float32,
    )
    return normalize_embedding(vector)


class MockSession(StreamingSession):
    def __init__(
        self,
        options: SessionOptions,
        store: VoiceprintStore,
        settings: Settings,
    ):
        self.options = options
        self.store = store
        self.settings = settings
        self.tracker = OnlineSpeakerTracker(
            threshold=settings.cluster_threshold,
            max_speakers=options.max_speakers,
        )
        self.total_samples = 0
        self.utterance_start = 0
        self.utterance_chunks: list[np.ndarray] = []
        self.utterance_index = 0

    @property
    def segment_id(self) -> str:
        return f"{self.options.session_id}-seg-{self.utterance_index:04d}"

    async def feed_audio(self, pcm16le: bytes) -> list[TranscriptEvent]:
        audio = pcm16le_to_float(pcm16le)
        if not len(audio):
            return []
        self.utterance_chunks.append(audio.copy())
        self.total_samples += len(audio)
        text = MOCK_TEXTS[self.utterance_index % len(MOCK_TEXTS)]
        visible = text[: max(1, min(len(text), self.total_samples // 800))]
        return [
            TranscriptEvent(
                event_type=EventType.SEGMENT,
                session_id=self.options.session_id,
                segment=Segment(
                    segment_id=self.segment_id,
                    text=visible,
                    start_ms=round(
                        self.utterance_start * 1000 / self.options.sample_rate
                    ),
                    end_ms=round(self.total_samples * 1000 / self.options.sample_rate),
                    speaker_id="speaker_pending",
                    is_final=False,
                ),
            )
        ]

    async def commit(self) -> list[TranscriptEvent]:
        if not self.utterance_chunks:
            return []
        audio = np.concatenate(self.utterance_chunks)
        embedding = _mock_embedding(audio)
        speaker_id, _ = self.tracker.assign(embedding)
        match = self.store.identify(
            embedding, threshold=self.settings.voiceprint_threshold
        )
        speaker_name = match[0].display_name if match else None
        verification_score = match[1] if match else None
        event = TranscriptEvent(
            event_type=EventType.SEGMENT,
            session_id=self.options.session_id,
            segment=Segment(
                segment_id=self.segment_id,
                text=MOCK_TEXTS[self.utterance_index % len(MOCK_TEXTS)],
                start_ms=round(self.utterance_start * 1000 / self.options.sample_rate),
                end_ms=round(self.total_samples * 1000 / self.options.sample_rate),
                speaker_id=speaker_id,
                speaker_name=speaker_name,
                verification_score=verification_score,
                is_final=True,
            ),
        )
        self.utterance_start = self.total_samples
        self.utterance_chunks = []
        self.utterance_index += 1
        return [event]

    async def close(self) -> list[TranscriptEvent]:
        return await self.commit()


class MockBackend(ASRBackend):
    name = "mock"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._ready = False

    async def startup(self) -> None:
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def model_info(self) -> dict[str, str]:
        return {"pipeline": "deterministic-mock"}

    def create_session(
        self, options: SessionOptions, voiceprints: VoiceprintStore
    ) -> StreamingSession:
        return MockSession(options, voiceprints, self.settings)

    async def embed_audio(self, audio: np.ndarray) -> np.ndarray:
        return _mock_embedding(audio)
