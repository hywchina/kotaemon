"""FunASR Paraformer + 3D-Speaker implementation.

Models are imported and downloaded only when ``ASR_BACKEND=funasr``. Streaming
Paraformer produces low-latency partials; offline Paraformer with FSMN-VAD and
CT-Punc corrects each utterance at commit time. CAM++ supplies embeddings for
online diarization and registered-speaker identification.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import numpy as np

from ..audio import pcm16le_to_float
from ..clustering import OnlineSpeakerTracker, normalize_embedding
from ..config import Settings
from ..schemas import EventType, Segment, TranscriptEvent
from ..voiceprints import VoiceprintStore
from .base import ASRBackend, SessionOptions, StreamingSession


def _result_text(result: Any) -> str:
    if isinstance(result, list) and result:
        result = result[0]
    if isinstance(result, dict):
        return str(result.get("text", "") or "").strip()
    return ""


def _merge_text(current: str, incoming: str) -> str:
    incoming = incoming.strip()
    if not incoming:
        return current
    if not current or incoming.startswith(current):
        return incoming
    if current.endswith(incoming):
        return current
    max_overlap = min(len(current), len(incoming))
    for size in range(max_overlap, 0, -1):
        if current[-size:] == incoming[:size]:
            return current + incoming[size:]
    return current + incoming


class _FunASRRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.streaming_model: Any = None
        self.offline_model: Any = None
        self.speaker_model: Any = None
        self.lock = threading.RLock()

    def load(self) -> None:
        try:
            from funasr import AutoModel
        except ImportError as exc:
            raise RuntimeError(
                "FunASR dependencies are not installed; run "
                "`uv sync --extra funasr` inside asr_service"
            ) from exc

        common = {"device": self.settings.device, "disable_update": True}
        self.streaming_model = AutoModel(
            model=self.settings.streaming_model,
            **common,
        )
        self.offline_model = AutoModel(
            model=self.settings.offline_model,
            vad_model=self.settings.vad_model,
            punc_model=self.settings.punctuation_model,
            **common,
        )
        self.speaker_model = AutoModel(
            model=self.settings.speaker_model,
            **common,
        )

    def stream_decode(
        self, audio: np.ndarray, cache: dict[str, Any], *, is_final: bool
    ) -> str:
        with self.lock:
            result = self.streaming_model.generate(
                input=audio,
                cache=cache,
                is_final=is_final,
                chunk_size=[0, 10, 5],
                encoder_chunk_look_back=self.settings.encoder_chunk_look_back,
                decoder_chunk_look_back=self.settings.decoder_chunk_look_back,
            )
        return _result_text(result)

    def offline_decode(self, audio: np.ndarray, hotwords: tuple[str, ...]) -> str:
        kwargs: dict[str, Any] = {}
        if hotwords:
            kwargs["hotword"] = " ".join(hotwords)
        with self.lock:
            result = self.offline_model.generate(input=audio, **kwargs)
        return _result_text(result)

    def speaker_embedding(self, audio: np.ndarray) -> np.ndarray:
        with self.lock:
            result = self.speaker_model.generate(
                input=audio,
                cache={},
                is_final=True,
            )
        if isinstance(result, list) and result:
            result = result[0]
        if not isinstance(result, dict) or "spk_embedding" not in result:
            raise RuntimeError("CAM++ did not return spk_embedding")
        embedding = result["spk_embedding"]
        if hasattr(embedding, "detach"):
            embedding = embedding.detach().cpu().numpy()
        return normalize_embedding(np.asarray(embedding, dtype=np.float32))


class FunASRSession(StreamingSession):
    def __init__(
        self,
        runtime: _FunASRRuntime,
        settings: Settings,
        options: SessionOptions,
        store: VoiceprintStore,
    ):
        self.runtime = runtime
        self.settings = settings
        self.options = options
        self.store = store
        self.cache: dict[str, Any] = {}
        self.tracker = OnlineSpeakerTracker(
            threshold=settings.cluster_threshold,
            max_speakers=options.max_speakers,
        )
        self.total_samples = 0
        self.utterance_start = 0
        self.utterance_index = 0
        self.utterance_chunks: list[np.ndarray] = []
        self.partial_text = ""

    @property
    def segment_id(self) -> str:
        return f"{self.options.session_id}-seg-{self.utterance_index:04d}"

    async def feed_audio(self, pcm16le: bytes) -> list[TranscriptEvent]:
        audio = pcm16le_to_float(pcm16le)
        if not len(audio):
            return []
        self.utterance_chunks.append(audio.copy())
        self.total_samples += len(audio)
        text = await asyncio.to_thread(
            self.runtime.stream_decode, audio, self.cache, is_final=False
        )
        self.partial_text = _merge_text(self.partial_text, text)
        if not self.partial_text:
            return []
        return [self._segment_event(self.partial_text, "speaker_pending", False)]

    def _segment_event(
        self,
        text: str,
        speaker_id: str,
        is_final: bool,
        *,
        speaker_name: str | None = None,
        verification_score: float | None = None,
    ) -> TranscriptEvent:
        return TranscriptEvent(
            event_type=EventType.SEGMENT,
            session_id=self.options.session_id,
            segment=Segment(
                segment_id=self.segment_id,
                text=text,
                start_ms=round(self.utterance_start * 1000 / self.options.sample_rate),
                end_ms=round(self.total_samples * 1000 / self.options.sample_rate),
                speaker_id=speaker_id,
                speaker_name=speaker_name,
                verification_score=verification_score,
                is_final=is_final,
            ),
        )

    async def commit(self) -> list[TranscriptEvent]:
        if not self.utterance_chunks:
            return []
        audio = np.concatenate(self.utterance_chunks)
        final_text, embedding = await asyncio.gather(
            asyncio.to_thread(
                self.runtime.offline_decode, audio, self.options.hotwords
            ),
            asyncio.to_thread(self.runtime.speaker_embedding, audio),
        )
        final_text = final_text or self.partial_text
        speaker_id, _ = self.tracker.assign(embedding)
        match = self.store.identify(
            embedding, threshold=self.settings.voiceprint_threshold
        )
        event = self._segment_event(
            final_text,
            speaker_id,
            True,
            speaker_name=match[0].display_name if match else None,
            verification_score=match[1] if match else None,
        )
        self.utterance_start = self.total_samples
        self.utterance_chunks = []
        self.utterance_index += 1
        self.partial_text = ""
        self.cache = {}
        return [event]

    async def close(self) -> list[TranscriptEvent]:
        return await self.commit()


class FunASRBackend(ASRBackend):
    name = "funasr"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.runtime = _FunASRRuntime(settings)
        self._ready = False

    async def startup(self) -> None:
        await asyncio.to_thread(self.runtime.load)
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def model_info(self) -> dict[str, str]:
        return {
            "streaming_asr": self.settings.streaming_model,
            "offline_asr": self.settings.offline_model,
            "vad": self.settings.vad_model,
            "punctuation": self.settings.punctuation_model,
            "speaker": self.settings.speaker_model,
        }

    def create_session(
        self, options: SessionOptions, voiceprints: VoiceprintStore
    ) -> StreamingSession:
        if not self._ready:
            raise RuntimeError("FunASR models are not ready")
        return FunASRSession(self.runtime, self.settings, options, voiceprints)

    async def embed_audio(self, audio: np.ndarray) -> np.ndarray:
        if not self._ready:
            raise RuntimeError("FunASR models are not ready")
        return await asyncio.to_thread(self.runtime.speaker_embedding, audio)
