"""Provider for the standalone local FunASR and 3D-Speaker service."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import requests
import websocket

from .audio import audio_chunk_to_pcm16le
from .provider import ASRProvider
from .schema import (
    ASRStreamRequest,
    ProviderVoiceprint,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
)


def _service_root(api_base_url: str) -> str:
    value = (api_base_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("本地 ASR 接口地址不能为空")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("本地 ASR 接口地址必须是 http:// 或 https:// URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _websocket_url(api_base_url: str) -> str:
    parsed = urlsplit(_service_root(api_base_url))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = f"{parsed.path.rstrip('/')}/v1/asr/stream"
    return urlunsplit((scheme, parsed.netloc, path, "", ""))


def _voiceprint_error(response, action: str) -> None:
    if response.status_code < 400:
        return
    try:
        detail = response.json().get("detail", "")
    except (AttributeError, TypeError, ValueError):
        detail = ""
    detail = str(detail or "").strip()
    if response.status_code == 401:
        message = "本地 ASR 接口鉴权失败，请检查接口密钥"
    elif "already exists" in detail.lower():
        message = "该姓名已存在于本地 ASR 声纹库"
    elif "at least 1 second" in detail.lower():
        message = "声纹音频过短，请提供至少 3 秒的清晰语音"
    elif "wav" in detail.lower() or "audio" in detail.lower():
        message = "无法读取声纹音频，请使用有效的 WAV、MP3 或 M4A 文件"
    elif response.status_code == 404:
        message = "本地 ASR 声纹记录不存在"
    else:
        message = detail or f"本地 ASR 返回 HTTP {response.status_code}"
    raise ValueError(f"{action}失败：{message}")


def _parse_event(payload: str | bytes) -> TranscriptEvent:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    try:
        data = json.loads(payload)
        event_type = TranscriptEventType(data["event_type"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("本地 ASR 返回了无效事件") from exc

    segment_data = data.get("segment")
    segment = None
    if segment_data is not None:
        try:
            segment = TranscriptSegment(
                segment_id=str(segment_data["segment_id"]),
                text=str(segment_data.get("text", "")),
                start_ms=int(segment_data["start_ms"]),
                end_ms=int(segment_data["end_ms"]),
                speaker_id=str(segment_data["speaker_id"]),
                is_final=bool(segment_data["is_final"]),
                speaker_name=segment_data.get("speaker_name"),
                verification_score=segment_data.get("verification_score"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("本地 ASR 返回了无效转写片段") from exc
    return TranscriptEvent(
        event_type=event_type,
        session_id=str(data.get("session_id", "")),
        segment=segment,
        message=data.get("message"),
    )


class SilenceEndpointDetector:
    """Detect an utterance boundary after sustained low-energy audio."""

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        rms_threshold: float = 500.0,
        silence_ms: int = 700,
        min_speech_ms: int = 400,
    ):
        self.sample_rate = sample_rate
        self.rms_threshold = rms_threshold
        self.silence_samples_required = round(sample_rate * silence_ms / 1000)
        self.min_speech_samples = round(sample_rate * min_speech_ms / 1000)
        self.frame_samples = max(1, round(sample_rate * 20 / 1000))
        self._speech_samples = 0
        self._silence_samples = 0
        self._has_speech = False

    def reset(self) -> None:
        self._speech_samples = 0
        self._silence_samples = 0
        self._has_speech = False

    def update(self, pcm16le: bytes) -> bool:
        samples = np.frombuffer(pcm16le, dtype="<i2")
        for offset in range(0, len(samples), self.frame_samples):
            frame = samples[offset : offset + self.frame_samples]
            if not len(frame):
                continue
            values = frame.astype(np.float32)
            rms = float(np.sqrt(np.mean(values * values)))
            if rms >= self.rms_threshold:
                self._has_speech = True
                self._speech_samples += len(frame)
                self._silence_samples = 0
            elif self._has_speech:
                self._silence_samples += len(frame)
            if (
                self._speech_samples >= self.min_speech_samples
                and self._silence_samples >= self.silence_samples_required
            ):
                self.reset()
                return True
        return False


class LocalFunASRSession:
    """One authenticated WebSocket connection to the local ASR service."""

    def __init__(
        self,
        socket,
        request: ASRStreamRequest,
        *,
        timeout: float,
        detector: SilenceEndpointDetector,
    ):
        self.socket = socket
        self.request = request
        self.timeout = timeout
        self.detector = detector
        self.closed = False
        self.start_event = self._start()

    def _send_command(self, command: dict) -> None:
        self.socket.send(json.dumps(command, ensure_ascii=False))

    def _receive(self, timeout: float) -> TranscriptEvent:
        self.socket.settimeout(max(0.001, timeout))
        event = _parse_event(self.socket.recv())
        if event.event_type == TranscriptEventType.ERROR:
            raise RuntimeError(event.message or "本地 ASR 返回错误")
        return event

    def _start(self) -> TranscriptEvent:
        self._send_command(
            {
                "type": "start",
                "session_id": self.request.session_id,
                "sample_rate": 16000,
                "channels": 1,
                "encoding": "pcm_s16le",
                "language": self.request.language,
                "max_speakers": 8,
            }
        )
        event = self._receive(self.timeout)
        if event.event_type != TranscriptEventType.SESSION_STARTED:
            raise RuntimeError("本地 ASR 未确认会话启动")
        return event

    def _receive_available(self, wait_seconds: float = 0.25) -> list[TranscriptEvent]:
        events = []
        deadline = time.monotonic() + min(wait_seconds, self.timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                event = self._receive(remaining)
            except websocket.WebSocketTimeoutException:
                break
            events.append(event)
            deadline = min(deadline, time.monotonic() + 0.005)
        return events

    def _commit(self) -> list[TranscriptEvent]:
        self._send_command({"type": "commit"})
        events = []
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("等待本地 ASR 最终分段超时")
            event = self._receive(remaining)
            events.append(event)
            if event.segment is not None and event.segment.is_final:
                return events

    def feed_audio(self, pcm16le: bytes) -> list[TranscriptEvent]:
        if self.closed:
            raise RuntimeError("ASR 会话已经结束")
        if not pcm16le:
            return []
        self.socket.send_binary(pcm16le)
        events = self._receive_available()
        if self.detector.update(pcm16le):
            events.extend(self._commit())
        return events

    def finish(self) -> list[TranscriptEvent]:
        if self.closed:
            return []
        self._send_command({"type": "stop"})
        events = []
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("等待本地 ASR 结束会话超时")
                event = self._receive(remaining)
                events.append(event)
                if event.event_type == TranscriptEventType.SESSION_ENDED:
                    return events
        finally:
            self.closed = True
            self.socket.close()

    def abort(self) -> None:
        if not self.closed:
            self.closed = True
            self.socket.close()


class LocalFunASRProvider(ASRProvider):
    """Kotaemon adapter for the local FunASR HTTP and WebSocket API."""

    name = "local-funasr"

    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        timeout: float = 60.0,
        *,
        rms_threshold: float = 500.0,
        silence_ms: int = 700,
        min_speech_ms: int = 400,
        websocket_factory: Callable | None = None,
        http_session=None,
    ):
        self.api_base_url = _service_root(api_base_url)
        self.api_key = api_key or ""
        self.timeout = float(timeout)
        self.rms_threshold = float(rms_threshold)
        self.silence_ms = int(silence_ms)
        self.min_speech_ms = int(min_speech_ms)
        self.websocket_factory = websocket_factory or websocket.create_connection
        self.http = http_session or requests.Session()

    def healthcheck(self) -> None:
        response = self.http.get(
            f"{self.api_base_url}/health/ready",
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ready" or payload.get("backend") != "funasr":
            raise RuntimeError("本地 ASR 尚未加载真实 FunASR 模型")

    def open_live_session(self, request: ASRStreamRequest) -> LocalFunASRSession:
        headers = [f"X-ASR-API-Key: {self.api_key}"]
        socket = self.websocket_factory(
            _websocket_url(self.api_base_url),
            header=headers,
            timeout=self.timeout,
            enable_multithread=True,
        )
        detector = SilenceEndpointDetector(
            rms_threshold=self.rms_threshold,
            silence_ms=self.silence_ms,
            min_speech_ms=self.min_speech_ms,
        )
        try:
            return LocalFunASRSession(
                socket,
                request,
                timeout=self.timeout,
                detector=detector,
            )
        except Exception:
            socket.close()
            raise

    def stream(self, request: ASRStreamRequest) -> Iterator[TranscriptEvent]:
        if request.audio_stream is None:
            raise ValueError("真实 ASR 请求缺少音频流")
        session = self.open_live_session(request)
        yield session.start_event
        try:
            for chunk in request.audio_stream:
                pcm16le = (
                    chunk if isinstance(chunk, bytes) else audio_chunk_to_pcm16le(chunk)
                )
                yield from session.feed_audio(pcm16le)
            yield from session.finish()
        except Exception:
            session.abort()
            raise

    def register_voiceprint(
        self, display_name: str, audio_path: str
    ) -> ProviderVoiceprint:
        path = Path(audio_path)
        try:
            with path.open("rb") as audio_file:
                response = self.http.post(
                    f"{self.api_base_url}/v1/voiceprints",
                    headers={"X-ASR-API-Key": self.api_key},
                    data={"display_name": display_name},
                    files={"files": (path.name, audio_file, "audio/wav")},
                    timeout=self.timeout,
                )
        except OSError as exc:
            raise ValueError("无法读取声纹音频，请重新录制或上传") from exc
        except requests.RequestException as exc:
            raise RuntimeError("无法连接本地 ASR 声纹服务") from exc
        _voiceprint_error(response, "注册声纹")
        payload = response.json()
        return ProviderVoiceprint(
            provider_id=str(payload["id"]),
            sample_count=int(payload.get("sample_count", 1)),
        )

    def delete_voiceprint(self, provider_id: str) -> None:
        try:
            response = self.http.delete(
                f"{self.api_base_url}/v1/voiceprints/{provider_id}",
                headers={"X-ASR-API-Key": self.api_key},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError("无法连接本地 ASR 声纹服务") from exc
        _voiceprint_error(response, "删除声纹")
