from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_API_KEY = "test-asr-api-key"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        backend="mock",
        api_key=TEST_API_KEY,
        data_dir=tmp_path / "data",
        voiceprint_threshold=0.95,
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-ASR-API-Key": TEST_API_KEY}


def make_wav(
    *,
    frequency: float = 220.0,
    duration_seconds: float = 1.2,
    sample_rate: int = 16000,
) -> tuple[bytes, bytes]:
    positions = np.arange(round(duration_seconds * sample_rate), dtype=np.float32)
    audio = 0.2 * np.sin(2 * np.pi * frequency * positions / sample_rate)
    pcm = np.clip(audio * 32767, -32768, 32767).astype("<i2").tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue(), pcm
