"""Tests for realtime ASR streaming, rendering and voiceprint permissions."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import websocket
import gradio as gr
from ktem.asr.audio import audio_chunk_to_pcm16le
from ktem.asr.provider import ASRProvider, MockASRProvider
from ktem.asr.remote import LocalFunASRProvider, SilenceEndpointDetector
from ktem.asr.render import render_live_transcript, upsert_segment
from ktem.asr.schema import (
    ASRStreamRequest,
    ProviderVoiceprint,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
)
from ktem.asr.service import ASRModelManager, ASRService
from ktem.asr.ui import VoiceprintManagement
from ktem.asr.voiceprints import VoiceprintManager, VoiceprintPermissionError
from ktem.pages.chat.chat_panel import ChatPanel
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace


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
    admin_manager.add("admin", "张三", "provider-zhang", is_mock=True)
    admin_manager.add("admin", "李四", "provider-li", is_mock=True)
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


def test_voiceprint_ui_separates_recording_and_upload_actions() -> None:
    service = SimpleNamespace(
        is_mock=False,
        provider=SimpleNamespace(name="local-funasr"),
    )

    with gr.Blocks():
        page = VoiceprintManagement(SimpleNamespace(), service=service)

    assert page.recorded_voice_sample.sources == ["microphone"]
    assert page.uploaded_voice_sample.sources == ["upload"]
    assert page.recorded_voice_sample.min_length == 3
    assert page.uploaded_voice_sample.max_length == 30
    assert page.register_recording_button.interactive is False
    assert page.register_upload_button.interactive is False


def test_voiceprint_register_actions_require_name_and_matching_audio() -> None:
    recording, upload = VoiceprintManagement.update_register_actions(
        "张医生", "/tmp/recorded.wav", None
    )

    assert recording["interactive"] is True
    assert upload["interactive"] is False

    recording, upload = VoiceprintManagement.update_register_actions(
        "", "/tmp/recorded.wav", "/tmp/uploaded.wav"
    )
    assert recording["interactive"] is False
    assert upload["interactive"] is False


def test_local_voiceprint_errors_are_translated(tmp_path: Path) -> None:
    class ErrorResponse:
        status_code = 422

        @staticmethod
        def json():
            return {"detail": "sample.wav: sample must be at least 1 second"}

    class ErrorSession:
        @staticmethod
        def post(*args, **kwargs):
            return ErrorResponse()

    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"not-long-enough")
    provider = LocalFunASRProvider(
        "http://127.0.0.1:8002",
        "secret",
        http_session=ErrorSession(),
    )

    with pytest.raises(ValueError, match="至少 3 秒"):
        provider.register_voiceprint("张医生", str(audio_path))


def test_mock_and_real_voiceprints_are_isolated(
    admin_manager: VoiceprintManager,
) -> None:
    admin_manager.add("admin", "模拟人员", "mock-id", is_mock=True)
    admin_manager.add("admin", "真实人员", "real-id", is_mock=False)

    mock_items = admin_manager.list_for_admin("admin", is_mock=True)
    real_items = admin_manager.list_for_admin("admin", is_mock=False)

    assert [item.provider_id for item in mock_items] == ["mock-id"]
    assert [item.provider_id for item in real_items] == ["real-id"]


def test_real_voiceprint_replaces_same_name_mock_fixture(
    admin_manager: VoiceprintManager,
) -> None:
    admin_manager.add("admin", "张三", "mock-id", is_mock=True)

    admin_manager.add("admin", "张三", "real-id", is_mock=False)

    assert admin_manager.list_for_admin("admin", is_mock=True) == []
    real_items = admin_manager.list_for_admin("admin", is_mock=False)
    assert [item.provider_id for item in real_items] == ["real-id"]


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


def test_asr_model_configuration_accepts_local_funasr(
    admin_manager: VoiceprintManager,
) -> None:
    manager = ASRModelManager(admin_manager)

    config = manager.update(
        "admin",
        "local-funasr",
        "http://127.0.0.1:8002",
        "secret",
        "paraformer-campplus",
        90,
    )

    assert config.provider == "local-funasr"
    assert config.api_base_url == "http://127.0.0.1:8002"
    with pytest.raises(ValueError, match="接口地址不能为空"):
        manager.update("admin", "local-funasr", "", "", "", 30)


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


def test_cancel_live_transcription_removes_temporary_asr_turn() -> None:
    class AbortOnlyService:
        def __init__(self):
            self.aborted = []

        def abort_live_stream(self, session_id):
            self.aborted.append(session_id)

    panel = object.__new__(ChatPanel)
    panel._asr_service = AbortOnlyService()
    chat_history = [
        (None, '<section data-ktem-message-type="asr">临时转写</section>'),
        ("保留的问题", "保留的回答"),
    ]

    result = panel.finish_live_transcription(
        "cancel",
        "live-cancel",
        [{"segment_id": "one"}],
        chat_history,
        0,
        ["临时证据", "保留证据"],
        ["临时图表", "保留图表"],
    )

    assert panel._asr_service.aborted == ["live-cancel"]
    assert result == (
        "",
        [],
        [("保留的问题", "保留的回答")],
        -1,
        ["保留证据"],
        ["保留图表"],
    )


def test_browser_audio_is_converted_to_mono_16khz_pcm() -> None:
    stereo = np.column_stack(
        [
            np.full(800, 1000, dtype=np.int16),
            np.full(800, 3000, dtype=np.int16),
        ]
    )

    pcm = audio_chunk_to_pcm16le((8000, stereo))
    samples = np.frombuffer(pcm, dtype="<i2")

    assert len(samples) == 1600
    assert np.all(samples == 2000)


def test_silence_detector_commits_after_speech_pause() -> None:
    detector = SilenceEndpointDetector(
        rms_threshold=500,
        silence_ms=100,
        min_speech_ms=100,
    )
    speech = np.full(1600, 2000, dtype="<i2").tobytes()
    silence = np.zeros(1600, dtype="<i2").tobytes()

    assert detector.update(speech) is False
    assert detector.update(silence) is True
    assert detector.update(silence) is False


class _FakeWebSocket:
    def __init__(self):
        self.messages = []
        self.pending = []
        self.closed = False

    def send(self, payload):
        command = json.loads(payload)
        self.messages.append(command)
        if command["type"] == "start":
            self.pending.append(
                {"event_type": "session_started", "session_id": "live-1"}
            )
        elif command["type"] == "commit":
            self.pending.append(
                {
                    "event_type": "segment",
                    "session_id": "live-1",
                    "segment": {
                        "segment_id": "segment-1",
                        "text": "最终结果",
                        "start_ms": 0,
                        "end_ms": 200,
                        "speaker_id": "speaker_00",
                        "is_final": True,
                    },
                }
            )
        elif command["type"] == "stop":
            self.pending.append(
                {"event_type": "session_ended", "session_id": "live-1"}
            )

    def send_binary(self, payload):
        self.messages.append(payload)
        self.pending.append(
            {
                "event_type": "segment",
                "session_id": "live-1",
                "segment": {
                    "segment_id": "segment-1",
                    "text": "最终",
                    "start_ms": 0,
                    "end_ms": 100,
                    "speaker_id": "speaker_00",
                    "is_final": False,
                },
            }
        )

    def recv(self):
        if not self.pending:
            raise websocket.WebSocketTimeoutException()
        return json.dumps(self.pending.pop(0), ensure_ascii=False)

    def settimeout(self, timeout):
        self.timeout = timeout

    def close(self):
        self.closed = True


def test_local_funasr_live_session_streams_and_commits_on_silence() -> None:
    socket = _FakeWebSocket()
    calls = []

    def websocket_factory(url, **kwargs):
        calls.append((url, kwargs))
        return socket

    provider = LocalFunASRProvider(
        "http://127.0.0.1:8002/v1",
        "secret",
        timeout=1,
        silence_ms=100,
        min_speech_ms=100,
        websocket_factory=websocket_factory,
    )
    session = provider.open_live_session(ASRStreamRequest(session_id="live-1"))
    chunk = np.concatenate(
        [
            np.full(1600, 2000, dtype="<i2"),
            np.zeros(1600, dtype="<i2"),
        ]
    ).tobytes()

    events = session.feed_audio(chunk)
    events.extend(session.finish())

    assert calls[0][0] == "ws://127.0.0.1:8002/v1/asr/stream"
    assert calls[0][1]["header"] == ["X-ASR-API-Key: secret"]
    assert [message["type"] for message in socket.messages if isinstance(message, dict)] == [
        "start",
        "commit",
        "stop",
    ]
    assert any(event.segment and event.segment.is_final for event in events)
    assert events[-1].event_type == TranscriptEventType.SESSION_ENDED
    assert socket.closed is True


class _RealProviderWithoutVerification(ASRProvider):
    name = "real-test"

    def stream(self, request):
        yield TranscriptEvent(
            event_type=TranscriptEventType.SEGMENT,
            session_id=request.session_id,
            segment=TranscriptSegment(
                segment_id="one",
                text="你好",
                start_ms=0,
                end_ms=1000,
                speaker_id="speaker_00",
                is_final=True,
            ),
        )

    def register_voiceprint(self, display_name, audio_path):
        return ProviderVoiceprint(provider_id="unused")

    def delete_voiceprint(self, provider_id):
        return None


def test_real_provider_does_not_guess_voiceprint_identity(
    admin_manager: VoiceprintManager,
) -> None:
    admin_manager.add("admin", "不应自动匹配", "provider-id")
    service = ASRService(_RealProviderWithoutVerification(), admin_manager)

    event = next(service.stream(ASRStreamRequest(session_id="real-1")))

    assert event.segment.speaker_name is None
