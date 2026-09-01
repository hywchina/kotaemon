"""Application service joining ASR, diarization and voice verification."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import replace
from functools import lru_cache
from threading import RLock
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from theflow.settings import settings as flowsettings

from .audio import audio_chunk_to_pcm16le
from .db import ASRModelTable
from .provider import ASRProvider, MockASRProvider
from .remote import LocalFunASRProvider
from .schema import ASRStreamRequest, TranscriptEvent, TranscriptEventType
from .voiceprints import VoiceprintManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ASRModelConfig:
    """Runtime configuration selected by an administrator."""

    provider: str
    api_base_url: str
    api_key: str
    model: str
    timeout: float


class ASRModelManager:
    """Persist the single ASR endpoint used by realtime transcription."""

    def __init__(self, voiceprints: VoiceprintManager | None = None):
        self.voiceprints = voiceprints or VoiceprintManager()
        self._ensure_default()

    def _ensure_default(self) -> None:
        with Session(self.voiceprints.db_engine) as session:
            item = session.get(ASRModelTable, "default")
            if item is not None:
                return
            session.add(
                ASRModelTable(
                    id="default",
                    provider=str(getattr(flowsettings, "KH_ASR_PROVIDER", "mock")),
                    api_base_url=str(getattr(flowsettings, "KH_ASR_API_BASE_URL", "")),
                    api_key=str(getattr(flowsettings, "KH_ASR_API_KEY", "")),
                    model=str(getattr(flowsettings, "KH_ASR_MODEL", "")),
                    timeout=float(getattr(flowsettings, "KH_ASR_TIMEOUT", 60.0)),
                )
            )
            session.commit()

    def get(self) -> ASRModelConfig:
        with Session(self.voiceprints.db_engine) as session:
            item = session.execute(
                select(ASRModelTable).where(ASRModelTable.id == "default")
            ).scalar_one()
            return ASRModelConfig(
                provider=item.provider,
                api_base_url=item.api_base_url,
                api_key=item.api_key,
                model=item.model,
                timeout=item.timeout,
            )

    def update(
        self,
        user_id: str | None,
        provider: str,
        api_base_url: str,
        api_key: str,
        model: str,
        timeout: float,
    ) -> ASRModelConfig:
        self.voiceprints.assert_admin(user_id)
        provider = (provider or "").strip().lower()
        if provider not in {"mock", "local-funasr"}:
            raise ValueError(f"不支持的语音识别供应商：{provider or '空'}")
        if provider == "local-funasr" and not (api_base_url or "").strip():
            raise ValueError("本地 FunASR 接口地址不能为空。")
        if timeout <= 0:
            raise ValueError("请求超时时间必须大于 0 秒。")
        if provider == "local-funasr":
            # Validate URL shape before persisting; connectivity is checked by the
            # explicit test action and startup preflight.
            LocalFunASRProvider(api_base_url, api_key, timeout)

        with Session(self.voiceprints.db_engine) as session:
            item = session.get(ASRModelTable, "default")
            if item is None:
                item = ASRModelTable(id="default")
            item.provider = provider
            item.api_base_url = (api_base_url or "").strip()
            item.api_key = api_key or ""
            item.model = (model or "").strip()
            item.timeout = float(timeout)
            session.add(item)
            session.commit()

        get_asr_service.cache_clear()
        return self.get()


class ASRService:
    """Provider-neutral facade consumed by the chat UI and admin UI."""

    def __init__(self, provider: ASRProvider, voiceprints: VoiceprintManager):
        self.provider = provider
        self.voiceprints = voiceprints
        self._live_sessions: dict[str, _LiveSessionState] = {}
        self._live_sessions_lock = RLock()

    @property
    def is_mock(self) -> bool:
        return self.provider.name == "mock"

    def stream(self, request: ASRStreamRequest) -> Iterator[TranscriptEvent]:
        """Stream diarized segments and attach mock verification identities.

        A real provider may return ``speaker_name`` and a verification score itself.
        The fallback mapping below exists so the complete UI can be exercised before
        that API is available.
        """

        registered = self.voiceprints.list_active(is_mock=True) if self.is_mock else []
        speaker_mapping: dict[str, tuple[str, float]] = {}

        for event in self.provider.stream(request):
            segment = event.segment
            if event.event_type != TranscriptEventType.SEGMENT or segment is None:
                yield event
                continue

            if segment.speaker_name:
                yield event
                continue

            # Never infer an identity from registration order in production. A real
            # provider must return a verified name and score itself.
            if not self.is_mock:
                yield event
                continue

            if segment.speaker_id not in speaker_mapping:
                mapping_index = len(speaker_mapping)
                if mapping_index < len(registered):
                    speaker_mapping[segment.speaker_id] = (
                        registered[mapping_index].display_name,
                        max(0.8, 0.96 - mapping_index * 0.04),
                    )

            match = speaker_mapping.get(segment.speaker_id)
            if match:
                segment = replace(
                    segment,
                    speaker_name=match[0],
                    verification_score=match[1],
                )
                event = replace(event, segment=segment)

            yield event

    def start_live_stream(self, request: ASRStreamRequest) -> list[TranscriptEvent]:
        """Open one server-side provider session without exposing its API key."""

        provider_session = self.provider.open_live_session(request)
        state = _LiveSessionState(session=provider_session, lock=RLock())
        with self._live_sessions_lock:
            old_state = self._live_sessions.pop(request.session_id, None)
            self._live_sessions[request.session_id] = state
        if old_state is not None:
            old_state.session.abort()
        return [provider_session.start_event]

    def feed_live_stream(
        self, session_id: str, audio_chunk: Any
    ) -> list[TranscriptEvent]:
        """Convert a Gradio microphone chunk and forward it to local FunASR."""

        state = self._get_live_session(session_id)
        pcm16le = audio_chunk_to_pcm16le(audio_chunk)
        with state.lock:
            return state.session.feed_audio(pcm16le)

    def finish_live_stream(self, session_id: str) -> list[TranscriptEvent]:
        """Finalize pending speech and close a live provider session."""

        with self._live_sessions_lock:
            state = self._live_sessions.pop(session_id, None)
        if state is None:
            return []
        with state.lock:
            return state.session.finish()

    def abort_live_stream(self, session_id: str) -> None:
        """Close a failed or abandoned live stream without waiting for results."""

        with self._live_sessions_lock:
            state = self._live_sessions.pop(session_id, None)
        if state is not None:
            with state.lock:
                state.session.abort()

    def _get_live_session(self, session_id: str) -> _LiveSessionState:
        if not session_id:
            raise ValueError("ASR 会话尚未启动")
        with self._live_sessions_lock:
            state = self._live_sessions.get(session_id)
        if state is None:
            raise ValueError("ASR 会话不存在或已经结束")
        return state

    def register_voiceprint(
        self, user_id: str | None, display_name: str, audio_path: str | None
    ):
        normalized_name = (display_name or "").strip()
        if not normalized_name:
            raise ValueError("姓名不能为空")
        registered_names = {
            item.display_name
            for item in self.voiceprints.list_for_admin(user_id, is_mock=self.is_mock)
        }
        if normalized_name in registered_names:
            raise ValueError(f"声纹姓名“{normalized_name}”已存在")
        if not audio_path or not os.path.isfile(audio_path):
            raise ValueError("请先上传或录制一段声纹音频")

        registration = self.provider.register_voiceprint(normalized_name, audio_path)
        try:
            return self.voiceprints.add(
                user_id,
                normalized_name,
                registration.provider_id,
                registration.sample_count,
                is_mock=self.is_mock,
            )
        except Exception:
            try:
                self.provider.delete_voiceprint(registration.provider_id)
            except Exception:
                logger.exception(
                    "Unable to roll back provider voiceprint %s",
                    registration.provider_id,
                )
            raise

    def delete_voiceprint(self, user_id: str | None, voiceprint_id: str) -> None:
        item = self.voiceprints.get_for_admin(
            user_id, voiceprint_id, is_mock=self.is_mock
        )
        self.provider.delete_voiceprint(item.provider_id)
        self.voiceprints.delete(user_id, voiceprint_id)


@dataclass
class _LiveSessionState:
    session: Any
    lock: RLock


def create_asr_provider(config: ASRModelConfig) -> ASRProvider:
    """Build a provider from persisted configuration."""

    provider_name = config.provider.lower()
    if provider_name == "mock":
        interval = float(getattr(flowsettings, "KH_ASR_MOCK_INTERVAL_SECONDS", 0.55))
        return MockASRProvider(interval_seconds=interval)
    if provider_name == "local-funasr":
        return LocalFunASRProvider(
            api_base_url=config.api_base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            rms_threshold=float(
                getattr(flowsettings, "KH_ASR_VAD_RMS_THRESHOLD", 500.0)
            ),
            silence_ms=int(getattr(flowsettings, "KH_ASR_VAD_SILENCE_MS", 700)),
            min_speech_ms=int(getattr(flowsettings, "KH_ASR_MIN_SPEECH_MS", 400)),
        )
    raise ValueError(f"Unsupported KH_ASR_PROVIDER={provider_name!r}")


@lru_cache(maxsize=1)
def get_asr_service() -> ASRService:
    """Build the configured ASR service once per application process."""

    voiceprints = VoiceprintManager()
    config = ASRModelManager(voiceprints).get()
    provider = create_asr_provider(config)

    if provider.name == "mock" and getattr(
        flowsettings, "KH_ASR_MOCK_SEED_VOICEPRINTS", True
    ):
        voiceprints.seed_mock(("张三", "李四"))

    return ASRService(provider, voiceprints)


@lru_cache(maxsize=1)
def get_asr_model_manager() -> ASRModelManager:
    return ASRModelManager()
