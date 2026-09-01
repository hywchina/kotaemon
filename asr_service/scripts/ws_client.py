"""Send a PCM16 WAV file through the realtime WebSocket contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
import wave
from pathlib import Path

import websockets


def read_pcm16(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("Input must be mono PCM16 WAV")
        if wav.getframerate() != 16000:
            raise ValueError("Input must use 16000 Hz sample rate")
        return wav.readframes(wav.getnframes())


async def receive_until(socket, predicate, *, timeout: float) -> dict:
    """Print events until the expected protocol boundary is received."""

    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for the expected ASR event")
        payload = await asyncio.wait_for(socket.recv(), timeout=remaining)
        print(payload)
        event = json.loads(payload)
        if event.get("event_type") == "error":
            raise RuntimeError(event.get("message", "ASR service returned an error"))
        if predicate(event):
            return event


async def drain_available(socket, *, timeout: float = 0.05) -> None:
    """Print partials already available without delaying the audio sender."""

    while True:
        try:
            payload = await asyncio.wait_for(socket.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            return
        print(payload)
        event = json.loads(payload)
        if event.get("event_type") == "error":
            raise RuntimeError(event.get("message", "ASR service returned an error"))


async def run(url: str, api_key: str, path: Path, timeout: float) -> None:
    pcm = read_pcm16(path)
    async with websockets.connect(
        url,
        additional_headers={"X-ASR-API-Key": api_key},
    ) as socket:
        await socket.send(
            json.dumps(
                {
                    "type": "start",
                    "session_id": uuid.uuid4().hex,
                    "sample_rate": 16000,
                    "channels": 1,
                    "encoding": "pcm_s16le",
                    "language": "zh",
                }
            )
        )
        await receive_until(
            socket,
            lambda event: event.get("event_type") == "session_started",
            timeout=timeout,
        )
        chunk_bytes = 16000 * 2 * 600 // 1000
        for offset in range(0, len(pcm), chunk_bytes):
            await socket.send(pcm[offset : offset + chunk_bytes])
            await drain_available(socket)
            await asyncio.sleep(0.06)
        await socket.send(json.dumps({"type": "commit"}))
        await receive_until(
            socket,
            lambda event: bool((event.get("segment") or {}).get("is_final")),
            timeout=timeout,
        )
        await socket.send(json.dumps({"type": "stop"}))
        await receive_until(
            socket,
            lambda event: event.get("event_type") == "session_ended",
            timeout=timeout,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("--url", default="ws://127.0.0.1:8002/v1/asr/stream")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    api_key = os.getenv("ASR_API_KEY", "")
    if not api_key:
        raise SystemExit("Set ASR_API_KEY in the environment")
    asyncio.run(run(args.url, api_key, args.wav, args.timeout))


if __name__ == "__main__":
    main()
