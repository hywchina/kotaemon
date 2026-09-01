"""Evaluate the running ASR API with the official 3D-Speaker 2-speaker sample."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import websockets
from scipy.optimize import linear_sum_assignment
from websockets.exceptions import ConnectionClosedOK

SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WAV = SERVICE_ROOT / "test-data/3d-speaker-2spk/2speakers_example.wav"
DEFAULT_RTTM = SERVICE_ROOT / "test-data/3d-speaker-2spk/2speakers_example.rttm"


@dataclass(frozen=True)
class ReferenceTurn:
    start: float
    duration: float
    speaker: str


def read_rttm(path: Path) -> list[ReferenceTurn]:
    turns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields or fields[0] != "SPEAKER":
            continue
        turns.append(
            ReferenceTurn(
                start=float(fields[3]),
                duration=float(fields[4]),
                speaker=fields[7],
            )
        )
    if not turns:
        raise ValueError(f"No RTTM speaker turns found in {path}")
    return sorted(turns, key=lambda item: item.start)


def read_pcm(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("Evaluation audio must be mono PCM16 WAV")
        return wav.readframes(wav.getnframes()), wav.getframerate()


async def receive_events(websocket, queue: asyncio.Queue) -> None:
    try:
        async for payload in websocket:
            await queue.put(json.loads(payload))
    except ConnectionClosedOK:
        pass


async def wait_for_event(queue: asyncio.Queue, predicate, timeout: float = 120):
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=timeout)
        if predicate(event):
            return event


def clustering_metrics(rows: list[dict]) -> dict:
    references = sorted({row["reference_speaker"] for row in rows})
    predictions = sorted({row["predicted_speaker"] for row in rows})
    durations = np.zeros((len(references), len(predictions)), dtype=np.float64)
    for row in rows:
        ref_index = references.index(row["reference_speaker"])
        pred_index = predictions.index(row["predicted_speaker"])
        durations[ref_index, pred_index] += row["duration_seconds"]

    ref_indices, pred_indices = linear_sum_assignment(-durations)
    mapping = {
        predictions[pred]: references[ref]
        for ref, pred in zip(ref_indices, pred_indices, strict=True)
    }
    total = float(durations.sum())
    correct = float(durations[ref_indices, pred_indices].sum())
    return {
        "reference_speaker_count": len(references),
        "predicted_speaker_count": len(predictions),
        "one_to_one_mapping": mapping,
        "duration_weighted_speaker_accuracy": correct / total if total else 0.0,
    }


async def evaluate(url: str, api_key: str, wav_path: Path, rttm_path: Path) -> dict:
    pcm, sample_rate = read_pcm(wav_path)
    turns = read_rttm(rttm_path)
    bytes_per_second = sample_rate * 2
    queue: asyncio.Queue = asyncio.Queue()
    headers = {"X-ASR-API-Key": api_key}

    async with websockets.connect(
        url,
        additional_headers=headers,
        max_size=2**22,
    ) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "type": "start",
                    "session_id": "3d-speaker-2spk-evaluation",
                    "sample_rate": sample_rate,
                    "channels": 1,
                    "encoding": "pcm_s16le",
                    "language": "zh",
                    "max_speakers": 4,
                }
            )
        )
        started = json.loads(await asyncio.wait_for(websocket.recv(), timeout=30))
        if started.get("event_type") != "session_started":
            raise RuntimeError(f"Unexpected start response: {started}")
        receiver = asyncio.create_task(receive_events(websocket, queue))

        results = []
        for index, turn in enumerate(turns):
            byte_start = round(turn.start * bytes_per_second)
            byte_end = round((turn.start + turn.duration) * bytes_per_second)
            utterance = pcm[byte_start:byte_end]
            started_at = time.perf_counter()
            for offset in range(0, len(utterance), 19200):
                await websocket.send(utterance[offset : offset + 19200])
            await websocket.send(json.dumps({"type": "commit"}))

            partial_count = 0
            while True:
                event = await wait_for_event(
                    queue, lambda item: item.get("event_type") in {"segment", "error"}
                )
                if event.get("event_type") == "error":
                    raise RuntimeError(event.get("message", "ASR API error"))
                segment = event["segment"]
                if segment["is_final"]:
                    break
                partial_count += 1
            results.append(
                {
                    "turn": index + 1,
                    "source_start_seconds": turn.start,
                    "duration_seconds": turn.duration,
                    "reference_speaker": turn.speaker,
                    "predicted_speaker": segment["speaker_id"],
                    "text": segment["text"],
                    "partial_count": partial_count,
                    "processing_seconds": round(time.perf_counter() - started_at, 3),
                }
            )

        await websocket.send(json.dumps({"type": "stop"}))
        await wait_for_event(
            queue, lambda item: item.get("event_type") == "session_ended", timeout=30
        )
        await receiver

    metrics = clustering_metrics(results)
    metrics["non_empty_transcript_rate"] = sum(
        bool(row["text"].strip()) for row in results
    ) / len(results)
    return {
        "source": {
            "wav": str(wav_path),
            "rttm": str(rttm_path),
            "sample_rate": sample_rate,
            "reference_turn_count": len(turns),
            "evaluated_speech_seconds": round(sum(turn.duration for turn in turns), 3),
        },
        "boundary_mode": "reference_rttm_turn_boundaries",
        "metrics": metrics,
        "turns": results,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8002/v1/asr/stream")
    parser.add_argument("--wav", type=Path, default=DEFAULT_WAV)
    parser.add_argument("--rttm", type=Path, default=DEFAULT_RTTM)
    args = parser.parse_args()
    api_key = os.getenv("ASR_API_KEY")
    if not api_key:
        parser.error("ASR_API_KEY is required; run with `uv run --env-file .env ...`")
    report = await evaluate(args.url, api_key, args.wav, args.rttm)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
