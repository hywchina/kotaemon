"""Strict audio decoding helpers used at the API boundary."""

from __future__ import annotations

import io
import wave

import numpy as np


class AudioFormatError(ValueError):
    pass


def pcm16le_to_float(payload: bytes) -> np.ndarray:
    if len(payload) % 2:
        raise AudioFormatError("PCM16 payload length must be even")
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def _resample_linear(
    audio: np.ndarray, source_rate: int, target_rate: int
) -> np.ndarray:
    if source_rate == target_rate or not len(audio):
        return audio.astype(np.float32, copy=False)
    target_length = max(1, round(len(audio) * target_rate / source_rate))
    source_positions = np.arange(len(audio), dtype=np.float64)
    target_positions = np.linspace(0, len(audio) - 1, target_length)
    return np.interp(target_positions, source_positions, audio).astype(np.float32)


def decode_wav(
    payload: bytes, *, target_rate: int = 16000, max_seconds: int = 60
) -> np.ndarray:
    try:
        with wave.open(io.BytesIO(payload), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            compression = wav.getcomptype()
            frames = wav.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise AudioFormatError("Invalid WAV file") from exc

    if compression != "NONE":
        raise AudioFormatError("Compressed WAV files are not supported")
    if sample_width != 2:
        raise AudioFormatError("Voiceprint WAV must use signed 16-bit PCM")
    if channels not in {1, 2}:
        raise AudioFormatError("Voiceprint WAV must be mono or stereo")
    if sample_rate < 8000 or sample_rate > 96000:
        raise AudioFormatError("Unsupported WAV sample rate")
    if frame_count / sample_rate > max_seconds:
        raise AudioFormatError(f"Voiceprint sample exceeds {max_seconds} seconds")

    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    if channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)
    audio /= 32768.0
    return _resample_linear(audio, sample_rate, target_rate)
