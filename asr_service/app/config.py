"""Environment-backed configuration for the standalone ASR service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _service_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (SERVICE_ROOT / path).resolve()


def _model_reference(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if value.startswith(("./", "../", "/", "~")):
        return str(_service_path(value))
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings. All paths default inside ``asr_service``."""

    backend: str = "mock"
    api_key: str = "local-development-key"
    host: str = "0.0.0.0"
    port: int = 8002
    data_dir: Path = SERVICE_ROOT / "data"
    sample_rate: int = 16000
    max_audio_chunk_bytes: int = 1024 * 1024
    max_voiceprint_seconds: int = 60
    max_speakers: int = 8
    cluster_threshold: float = 0.62
    voiceprint_threshold: float = 0.72
    device: str = "cpu"
    offline: bool = True
    streaming_model: str = "paraformer-zh-streaming"
    offline_model: str = "paraformer-zh"
    vad_model: str = "fsmn-vad"
    punctuation_model: str = "ct-punc"
    speaker_model: str = "cam++"
    encoder_chunk_look_back: int = 4
    decoder_chunk_look_back: int = 1

    @property
    def database_path(self) -> Path:
        return self.data_dir / "voiceprints.sqlite3"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            backend=os.getenv("ASR_BACKEND", "mock").strip().lower(),
            api_key=os.getenv("ASR_API_KEY", "local-development-key"),
            host=os.getenv("ASR_HOST", "0.0.0.0"),
            port=_env_int("ASR_PORT", 8002),
            data_dir=_service_path(
                os.getenv("ASR_DATA_DIR", str(SERVICE_ROOT / "data"))
            ),
            sample_rate=_env_int("ASR_SAMPLE_RATE", 16000),
            max_audio_chunk_bytes=_env_int("ASR_MAX_AUDIO_CHUNK_BYTES", 1024 * 1024),
            max_voiceprint_seconds=_env_int("ASR_MAX_VOICEPRINT_SECONDS", 60),
            max_speakers=_env_int("ASR_MAX_SPEAKERS", 8),
            cluster_threshold=_env_float("ASR_CLUSTER_THRESHOLD", 0.62),
            voiceprint_threshold=_env_float("ASR_VOICEPRINT_THRESHOLD", 0.72),
            device=os.getenv("ASR_DEVICE", "cpu"),
            offline=_env_bool("ASR_OFFLINE", True),
            streaming_model=_model_reference(
                "ASR_STREAMING_MODEL", "paraformer-zh-streaming"
            ),
            offline_model=_model_reference("ASR_OFFLINE_MODEL", "paraformer-zh"),
            vad_model=_model_reference("ASR_VAD_MODEL", "fsmn-vad"),
            punctuation_model=_model_reference("ASR_PUNCTUATION_MODEL", "ct-punc"),
            speaker_model=_model_reference("ASR_SPEAKER_MODEL", "cam++"),
            encoder_chunk_look_back=_env_int("ASR_ENCODER_CHUNK_LOOK_BACK", 4),
            decoder_chunk_look_back=_env_int("ASR_DECODER_CHUNK_LOOK_BACK", 1),
        )

    def validate(self) -> None:
        if self.backend not in {"mock", "funasr"}:
            raise ValueError("ASR_BACKEND must be 'mock' or 'funasr'")
        if not self.api_key:
            raise ValueError("ASR_API_KEY must not be empty")
        if self.sample_rate != 16000:
            raise ValueError("The current model pipeline requires 16000 Hz audio")
        if self.port < 1 or self.port > 65535:
            raise ValueError("ASR_PORT must be between 1 and 65535")
        if self.max_speakers < 1:
            raise ValueError("ASR_MAX_SPEAKERS must be positive")
        if self.backend == "funasr" and self.offline:
            model_paths = {
                "ASR_STREAMING_MODEL": self.streaming_model,
                "ASR_OFFLINE_MODEL": self.offline_model,
                "ASR_VAD_MODEL": self.vad_model,
                "ASR_PUNCTUATION_MODEL": self.punctuation_model,
                "ASR_SPEAKER_MODEL": self.speaker_model,
            }
            missing = [
                name for name, value in model_paths.items() if not Path(value).is_dir()
            ]
            if missing:
                names = ", ".join(missing)
                raise ValueError(
                    f"Offline model directories are missing ({names}); "
                    "run `uv run python scripts/preload_models.py` first"
                )
