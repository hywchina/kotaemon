"""Application service joining ASR, diarization and voice verification."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import replace
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session
from theflow.settings import settings as flowsettings

from .db import ASRModelTable
from .provider import ASRProvider, MockASRProvider
from .schema import ASRStreamRequest, TranscriptEvent, TranscriptEventType
from .voiceprints import VoiceprintManager


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
        if provider != "mock":
            raise ValueError("当前版本仅启用模拟 ASR；接入真实接口后再选择对应供应商。")
        if timeout <= 0:
            raise ValueError("请求超时时间必须大于 0 秒。")

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

    @property
    def is_mock(self) -> bool:
        return self.provider.name == "mock"

    def stream(self, request: ASRStreamRequest) -> Iterator[TranscriptEvent]:
        """Stream diarized segments and attach mock verification identities.

        A real provider may return ``speaker_name`` and a verification score itself.
        The fallback mapping below exists so the complete UI can be exercised before
        that API is available.
        """

        registered = self.voiceprints.list_active()
        speaker_mapping: dict[str, tuple[str, float]] = {}

        for event in self.provider.stream(request):
            segment = event.segment
            if event.event_type != TranscriptEventType.SEGMENT or segment is None:
                yield event
                continue

            if segment.speaker_name:
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

    def register_voiceprint(
        self, user_id: str | None, display_name: str, audio_path: str | None
    ):
        normalized_name = (display_name or "").strip()
        if not normalized_name:
            raise ValueError("姓名不能为空")
        registered_names = {
            item.display_name for item in self.voiceprints.list_for_admin(user_id)
        }
        if normalized_name in registered_names:
            raise ValueError(f"声纹姓名“{normalized_name}”已存在")
        if not audio_path or not os.path.isfile(audio_path):
            raise ValueError("请先上传或录制一段声纹音频")

        registration = self.provider.register_voiceprint(normalized_name, audio_path)
        return self.voiceprints.add(
            user_id,
            normalized_name,
            registration.provider_id,
            registration.sample_count,
            is_mock=self.is_mock,
        )

    def delete_voiceprint(self, user_id: str | None, voiceprint_id: str) -> None:
        item = self.voiceprints.get_for_admin(user_id, voiceprint_id)
        self.provider.delete_voiceprint(item.provider_id)
        self.voiceprints.delete(user_id, voiceprint_id)


@lru_cache(maxsize=1)
def get_asr_service() -> ASRService:
    """Build the configured ASR service once per application process."""

    voiceprints = VoiceprintManager()
    config = ASRModelManager(voiceprints).get()
    provider_name = config.provider.lower()
    if provider_name != "mock":
        raise ValueError(
            f"Unsupported KH_ASR_PROVIDER={provider_name!r}; configure 'mock' until "
            "the remote ASR provider is implemented"
        )

    interval = float(getattr(flowsettings, "KH_ASR_MOCK_INTERVAL_SECONDS", 0.55))
    if getattr(flowsettings, "KH_ASR_MOCK_SEED_VOICEPRINTS", True):
        voiceprints.seed_mock(("张三", "李四"))

    return ASRService(MockASRProvider(interval_seconds=interval), voiceprints)


@lru_cache(maxsize=1)
def get_asr_model_manager() -> ASRModelManager:
    return ASRModelManager()
