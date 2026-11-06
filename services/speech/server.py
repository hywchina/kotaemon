"""Local streaming speech recognition and end-of-recording diarization."""

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

import numpy as np
import sherpa_onnx as sherpa
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

RATE = 16000
MAX_SECONDS = 300
MAX_FRAME_BYTES = 32000
LOGGER = logging.getLogger(__name__)


class SpeechModels:
    def __init__(self, directory: Path):
        zipformer = directory / "zipformer-zh"
        tokens = zipformer / "tokens.txt"
        transducer = {
            part: zipformer / f"{part}-epoch-99-avg-1.int8.onnx"
            for part in ("encoder", "decoder", "joiner")
        }
        segmentation = directory / "sherpa-onnx-pyannote-segmentation-3-0/model.onnx"
        embedding = (
            directory / "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
        )
        for path in (tokens, segmentation, embedding, *transducer.values()):
            if not path.is_file():
                raise FileNotFoundError(path)

        threads = int(os.getenv("SPEECH_THREADS", "2"))
        self.recognizer = sherpa.OnlineRecognizer.from_transducer(
            tokens=str(tokens),
            num_threads=threads,
            sample_rate=RATE,
            **{part: str(path) for part, path in transducer.items()},
        )
        self.cluster_threshold = float(os.getenv("SPEECH_CLUSTER_THRESHOLD", "0.55"))
        self.diarization_config = sherpa.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(segmentation)
                ),
                num_threads=threads,
            ),
            embedding=sherpa.SpeakerEmbeddingExtractorConfig(
                model=str(embedding), num_threads=threads
            ),
            clustering=sherpa.FastClusteringConfig(threshold=self.cluster_threshold),
            min_duration_on=0.2,
            min_duration_off=0.15,
        )
        self.diarizer = sherpa.OfflineSpeakerDiarization(self.diarization_config)
        self.recognition_lock = Lock()
        self.diarization_lock = Lock()

    def decode(self, stream, samples, *, final=False):
        with self.recognition_lock:
            stream.accept_waveform(RATE, samples)
            if final:
                stream.accept_waveform(RATE, np.zeros(RATE // 2, dtype=np.float32))
                stream.input_finished()
            while self.recognizer.is_ready(stream):
                self.recognizer.decode_stream(stream)
            return self.recognizer.get_result(stream).strip()

    def transcribe_turns(self, samples, full_text):
        if len(samples) < RATE // 5:
            return []
        with self.diarization_lock:
            turns = self.diarizer.process(samples).sort_by_start_time()
            if len({turn.speaker for turn in turns}) > 2:
                # First release supports one or two speakers. Merge spurious clusters
                # using the diarizer's embeddings while keeping single-speaker detection.
                self.diarization_config.clustering = sherpa.FastClusteringConfig(
                    num_clusters=2
                )
                try:
                    self.diarizer.set_config(self.diarization_config)
                    turns = self.diarizer.process(samples).sort_by_start_time()
                finally:
                    self.diarization_config.clustering = sherpa.FastClusteringConfig(
                        threshold=self.cluster_threshold
                    )
                    self.diarizer.set_config(self.diarization_config)

        speakers = {}
        segments = []
        for turn in turns:
            start = max(0, round(turn.start * RATE))
            end = min(len(samples), round(turn.end * RATE))
            if start >= end:
                continue
            text = self.decode(
                self.recognizer.create_stream(), samples[start:end], final=True
            )
            if text:
                number = speakers.setdefault(turn.speaker, len(speakers) + 1)
                segments.append(
                    {
                        "speaker": number,
                        "start": start / RATE,
                        "end": end / RATE,
                        "text": text,
                    }
                )

        if not segments and full_text:
            segments.append(
                {
                    "speaker": None,
                    "start": 0,
                    "end": len(samples) / RATE,
                    "text": full_text,
                }
            )
        return segments


@asynccontextmanager
async def lifespan(app):
    key = os.environ.get("SPEECH_API_KEY", "")
    if len(key) < 24:
        raise RuntimeError("SPEECH_API_KEY must contain at least 24 characters")
    app.state.key = key
    app.state.models = SpeechModels(Path(os.environ["SPEECH_MODEL_DIR"]))
    app.state.slots = asyncio.Semaphore(int(os.getenv("SPEECH_MAX_SESSIONS", "4")))
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health/ready")
async def ready():
    return {"ready": True}


@app.websocket("/recognize")
async def recognize(socket: WebSocket):
    auth = socket.headers.get("authorization", "")
    if not hmac.compare_digest(auth.encode(), f"Bearer {app.state.key}".encode()):
        await socket.close(code=1008)
        return

    slots = app.state.slots
    try:
        await asyncio.wait_for(slots.acquire(), timeout=0.2)
    except asyncio.TimeoutError:
        await socket.close(code=1013)
        return

    try:
        await socket.accept()
        await recognize_audio(socket, app.state.models)
    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        await socket.close(code=1008)
    except Exception:
        LOGGER.exception("Speech recognition failed")
        await socket.close(code=1011)
    finally:
        slots.release()


async def recognize_audio(socket: WebSocket, models: SpeechModels):
    stream = models.recognizer.create_stream()
    audio = bytearray()
    partial = ""
    while True:
        message = await asyncio.wait_for(socket.receive(), timeout=15)
        if message["type"] == "websocket.disconnect":
            return
        if message.get("text") == "stop":
            if audio:
                samples = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768
                full_text = await asyncio.to_thread(
                    models.decode, stream, np.empty(0, np.float32), final=True
                )
                segments = await asyncio.to_thread(
                    models.transcribe_turns, samples, full_text
                )
            else:
                segments = []
            await socket.send_json({"type": "final", "segments": segments})
            return

        chunk = message.get("bytes")
        if not chunk or len(chunk) % 2 or len(chunk) > MAX_FRAME_BYTES:
            await socket.close(code=1003)
            return
        if len(audio) + len(chunk) > MAX_SECONDS * RATE * 2:
            await socket.close(code=1009)
            return
        audio.extend(chunk)
        samples = np.frombuffer(chunk, dtype="<i2").astype(np.float32) / 32768
        text = await asyncio.to_thread(models.decode, stream, samples)
        if partial != text:
            partial = text
            await socket.send_json({"type": "partial", "text": text})
