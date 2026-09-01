"""Audio conversion helpers for browser microphone chunks."""

from __future__ import annotations

import numpy as np


def audio_chunk_to_pcm16le(
    audio_chunk: tuple[int, np.ndarray], *, target_sample_rate: int = 16000
) -> bytes:
    """Convert a Gradio audio chunk to mono, 16 kHz, signed PCM16LE."""

    if not audio_chunk or len(audio_chunk) != 2:
        raise ValueError("麦克风音频块格式无效")
    sample_rate, values = audio_chunk
    if sample_rate <= 0:
        raise ValueError("麦克风采样率无效")

    samples = np.asarray(values)
    if samples.size == 0:
        return b""
    if samples.ndim == 2:
        samples = samples.astype(np.float32).mean(axis=1)
    elif samples.ndim != 1:
        raise ValueError("麦克风音频必须是单声道或双声道")

    samples = samples.astype(np.float32)
    if np.issubdtype(np.asarray(values).dtype, np.floating):
        peak = float(np.max(np.abs(samples)))
        if peak <= 1.5:
            samples *= 32767.0

    if sample_rate != target_sample_rate:
        output_size = max(
            1,
            round(len(samples) * target_sample_rate / sample_rate),
        )
        source_positions = np.arange(output_size, dtype=np.float64) * (
            sample_rate / target_sample_rate
        )
        samples = np.interp(
            source_positions,
            np.arange(len(samples), dtype=np.float64),
            samples,
        ).astype(np.float32)

    return np.clip(np.rint(samples), -32768, 32767).astype("<i2").tobytes()
