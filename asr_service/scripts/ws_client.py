"""Send a PCM16 WAV file through the realtime WebSocket contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
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


async def run(url: str, api_key: str, path: Path) -> None:
    pcm = read_pcm16(path)
    separator = "&" if "?" in url else "?"
    async with websockets.connect(f"{url}{separator}token={api_key}") as socket:
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
        print(await socket.recv())
        chunk_bytes = 16000 * 2 * 600 // 1000
        for offset in range(0, len(pcm), chunk_bytes):
            await socket.send(pcm[offset : offset + chunk_bytes])
            try:
                print(await asyncio.wait_for(socket.recv(), timeout=0.05))
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(0.06)
        await socket.send(json.dumps({"type": "commit"}))
        print(await socket.recv())
        await socket.send(json.dumps({"type": "stop"}))
        print(await socket.recv())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("--url", default="ws://127.0.0.1:8002/v1/asr/stream")
    args = parser.parse_args()
    api_key = os.getenv("ASR_API_KEY", "")
    if not api_key:
        raise SystemExit("Set ASR_API_KEY in the environment")
    asyncio.run(run(args.url, api_key, args.wav))


if __name__ == "__main__":
    main()
