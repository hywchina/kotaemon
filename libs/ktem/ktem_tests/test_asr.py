"""Tests for realtime ASR streaming, rendering and voiceprint permissions."""

from __future__ import annotations

from pathlib import Path

import pytest
from ktem.asr.provider import MockASRProvider
from ktem.asr.render import render_live_transcript, upsert_segment
from ktem.asr.schema import ASRStreamRequest, TranscriptEventType, TranscriptSegment
from ktem.asr.service import ASRModelManager, ASRService
from ktem.asr.voiceprints import VoiceprintManager, VoiceprintPermissionError
from ktem.pages.chat.chat_panel import ChatPanel
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def admin_manager(db_engine):
    return VoiceprintManager(
        db_engine, admin_checker=lambda user_id: user_id == "admin"
    )


def test_mock_provider_streams_partial_and_final_diarized_segments() -> None:
    provider = MockASRProvider(interval_seconds=0)
    events = list(provider.stream(ASRStreamRequest(session_id="session-1")))

    assert events[0].event_type == TranscriptEventType.SESSION_STARTED
    assert events[-1].event_type == TranscriptEventType.SESSION_ENDED

    segment_events = [
        event for event in events if event.event_type == TranscriptEventType.SEGMENT
    ]
    assert {event.segment.speaker_id for event in segment_events} == {
        "speaker_00",
        "speaker_01",
    }
    assert any(not event.segment.is_final for event in segment_events)
    assert sum(event.segment.is_final for event in segment_events) == 4


def test_service_maps_diarized_speakers_to_registered_voiceprints(
    admin_manager: VoiceprintManager,
) -> None:
    admin_manager.add("admin", "张三", "provider-zhang")
    admin_manager.add("admin", "李四", "provider-li")
    service = ASRService(MockASRProvider(interval_seconds=0), admin_manager)

    events = list(service.stream(ASRStreamRequest(session_id="session-2")))
    final_segments = [
        event.segment
        for event in events
        if event.segment is not None and event.segment.is_final
    ]

    assert {segment.speaker_name for segment in final_segments} == {"张三", "李四"}
    assert all(segment.verification_score >= 0.8 for segment in final_segments)


def test_voiceprint_manager_rejects_non_admin(
    admin_manager: VoiceprintManager,
) -> None:
    with pytest.raises(VoiceprintPermissionError, match="只有管理员"):
        admin_manager.add("ordinary-user", "张三", "provider-zhang")

    with pytest.raises(VoiceprintPermissionError, match="只有管理员"):
        admin_manager.list_for_admin("ordinary-user")


def test_voiceprint_registration_and_deletion(
    admin_manager: VoiceprintManager, tmp_path: Path
) -> None:
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"mock wave data")
    service = ASRService(MockASRProvider(interval_seconds=0), admin_manager)

    voiceprint = service.register_voiceprint("admin", "王五", str(audio_path))
    assert voiceprint.display_name == "王五"
    assert voiceprint.is_mock is True
    assert len(admin_manager.list_for_admin("admin")) == 1

    service.delete_voiceprint("admin", voiceprint.id)
    assert admin_manager.list_for_admin("admin") == []


def test_asr_model_configuration_is_admin_managed(
    admin_manager: VoiceprintManager,
) -> None:
    manager = ASRModelManager(admin_manager)

    config = manager.update("admin", "mock", "", "", "mock-asr", 30)

    assert config.provider == "mock"
    assert config.model == "mock-asr"
    assert config.timeout == 30
    with pytest.raises(VoiceprintPermissionError, match="只有管理员"):
        manager.update("ordinary-user", "mock", "", "", "mock-asr", 30)


def test_live_transcript_upserts_partials_and_escapes_provider_text() -> None:
    partial = TranscriptSegment(
        segment_id="seg-1",
        text="<script>alert(1)</script>",
        start_ms=1000,
        end_ms=2000,
        speaker_id="speaker_00",
        is_final=False,
    )
    final = TranscriptSegment(
        segment_id="seg-1",
        text="最终文本 <img src=x onerror=alert(1)>",
        start_ms=1000,
        end_ms=2500,
        speaker_id="speaker_00",
        speaker_name="张三",
        verification_score=0.93,
        is_final=True,
    )

    state = upsert_segment([], partial)
    state = upsert_segment(state, final)
    rendered = render_live_transcript(
        state,
        status="已完成",
        is_recording=False,
        is_mock=True,
    )

    assert len(state) == 1
    assert "最终文本" in rendered
    assert "张三" in rendered
    assert "已识别" in rendered
    assert "<img" not in rendered
    assert "&lt;img" in rendered


def test_transcript_stream_updates_an_assistant_chat_message(
    admin_manager: VoiceprintManager,
) -> None:
    panel = object.__new__(ChatPanel)
    panel._asr_service = ASRService(MockASRProvider(interval_seconds=0), admin_manager)

    segments, history, message_index, *_ = panel.begin_transcription([])
    updates = list(panel.stream_transcription(segments, history, message_index))
    final_segments, final_history, final_index, *_ = updates[-1]

    assert final_index == 0
    assert final_history[0][0] is None
    assert "语音实时转写" in final_history[0][1]
    assert "转写已完成" in final_history[0][1]
    assert len(final_segments) == 4
