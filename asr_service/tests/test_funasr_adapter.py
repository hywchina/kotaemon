from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np

from app.backends.base import SessionOptions
from app.backends.funasr import FunASRSession, _merge_text
from app.config import Settings
from app.voiceprints import VoiceprintStore


class FakeRuntime:
    def stream_decode(self, audio, cache, *, is_final):
        del audio, cache, is_final
        return "胸闷"

    def offline_decode(self, audio, hotwords):
        del audio, hotwords
        return "患者主诉胸闷。"

    def speaker_embedding(self, audio):
        del audio
        return np.array([1.0, 0.0], dtype=np.float32)


def test_partial_text_merge_does_not_repeat_overlap() -> None:
    assert _merge_text("患者胸", "胸闷两天") == "患者胸闷两天"
    assert _merge_text("患者胸闷", "患者胸闷两天") == "患者胸闷两天"


def test_funasr_session_maps_partial_and_final_events(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, voiceprint_threshold=0.7)
    store = VoiceprintStore(settings.database_path)
    store.create("张医生", np.array([1.0, 0.0], dtype=np.float32))
    session = FunASRSession(
        FakeRuntime(),
        settings,
        SessionOptions(
            session_id="real-adapter-test",
            sample_rate=16000,
            language="zh",
            hotwords=("胸闷",),
            max_speakers=4,
        ),
        store,
    )

    pcm = np.zeros(16000, dtype="<i2").tobytes()

    async def exercise_session():
        partial = await session.feed_audio(pcm)
        final = await session.commit()
        return partial, final

    partial, final = asyncio.run(exercise_session())

    assert partial[0].segment.text == "胸闷"
    assert partial[0].segment.is_final is False
    assert final[0].segment.text == "患者主诉胸闷。"
    assert final[0].segment.speaker_id == "speaker_00"
    assert final[0].segment.speaker_name == "张医生"
