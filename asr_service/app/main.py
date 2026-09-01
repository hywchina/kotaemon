"""FastAPI entry point for the standalone realtime ASR service."""

from __future__ import annotations

import hmac
import json
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError

from .audio import AudioFormatError, decode_wav
from .backends import create_backend
from .backends.base import ASRBackend, SessionOptions, StreamingSession
from .config import Settings
from .schemas import (
    EventType,
    HealthResponse,
    StartMessage,
    TranscriptEvent,
    VoiceprintResponse,
)
from .voiceprints import VoiceprintRecord, VoiceprintStore


def _voiceprint_response(item: VoiceprintRecord) -> VoiceprintResponse:
    return VoiceprintResponse.model_validate(item)


def _event_payload(event: TranscriptEvent) -> dict:
    return event.model_dump(mode="json", exclude_none=True)


def create_app(
    settings: Settings | None = None,
    backend: ASRBackend | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    backend = backend or create_backend(settings)
    voiceprints = VoiceprintStore(settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await backend.startup()
        try:
            yield
        finally:
            await backend.shutdown()

    app = FastAPI(
        title="Kotaemon Realtime ASR Service",
        version="0.1.0",
        description=(
            "Standalone FunASR and 3D-Speaker gateway for realtime transcription, "
            "speaker diarization and voiceprint identification."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.backend = backend
    app.state.voiceprints = voiceprints

    def require_api_key(
        x_asr_api_key: Annotated[str | None, Header()] = None,
    ) -> None:
        if not x_asr_api_key or not hmac.compare_digest(
            x_asr_api_key, settings.api_key
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ASR API key",
            )

    @app.get("/health/live", response_model=HealthResponse)
    async def health_live() -> HealthResponse:
        return HealthResponse(status="ok", backend=backend.name)

    @app.get("/health/ready", response_model=HealthResponse)
    async def health_ready() -> HealthResponse:
        if not backend.is_ready():
            raise HTTPException(status_code=503, detail="Models are not ready")
        return HealthResponse(
            status="ready",
            backend=backend.name,
            models=backend.model_info(),
        )

    @app.get(
        "/v1/voiceprints",
        response_model=list[VoiceprintResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def list_voiceprints() -> list[VoiceprintResponse]:
        return [_voiceprint_response(item) for item in voiceprints.list()]

    async def embeddings_from_uploads(files: list[UploadFile]):
        if not files:
            raise HTTPException(
                status_code=422, detail="At least one WAV file is required"
            )
        embeddings = []
        for upload in files:
            payload = await upload.read()
            try:
                audio = decode_wav(
                    payload,
                    target_rate=settings.sample_rate,
                    max_seconds=settings.max_voiceprint_seconds,
                )
            except AudioFormatError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"{upload.filename or 'audio'}: {exc}",
                ) from exc
            if len(audio) < settings.sample_rate:
                filename = upload.filename or "audio"
                raise HTTPException(
                    status_code=422,
                    detail=f"{filename}: sample must be at least 1 second",
                )
            embeddings.append(await backend.embed_audio(audio))
        return embeddings

    @app.post(
        "/v1/voiceprints",
        response_model=VoiceprintResponse,
        status_code=201,
        dependencies=[Depends(require_api_key)],
    )
    async def create_voiceprint(
        display_name: Annotated[str, Form(min_length=1, max_length=128)],
        files: Annotated[list[UploadFile], File()],
    ) -> VoiceprintResponse:
        embeddings = await embeddings_from_uploads(files)
        try:
            item = voiceprints.create(display_name, embeddings[0])
            for embedding in embeddings[1:]:
                item = voiceprints.add_sample(item.id, embedding)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _voiceprint_response(item)

    @app.post(
        "/v1/voiceprints/{voiceprint_id}/samples",
        response_model=VoiceprintResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def add_voiceprint_samples(
        voiceprint_id: str,
        files: Annotated[list[UploadFile], File()],
    ) -> VoiceprintResponse:
        embeddings = await embeddings_from_uploads(files)
        try:
            item = voiceprints.get(voiceprint_id)
            for embedding in embeddings:
                item = voiceprints.add_sample(item.id, embedding)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Voiceprint not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _voiceprint_response(item)

    @app.delete(
        "/v1/voiceprints/{voiceprint_id}",
        status_code=204,
        response_class=Response,
        response_model=None,
        dependencies=[Depends(require_api_key)],
    )
    async def delete_voiceprint(
        voiceprint_id: str,
    ) -> Response:
        try:
            voiceprints.delete(voiceprint_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Voiceprint not found") from exc
        return Response(status_code=204)

    async def send_events(websocket: WebSocket, events: list[TranscriptEvent]) -> None:
        for event in events:
            await websocket.send_json(_event_payload(event))

    @app.websocket("/v1/asr/stream")
    async def stream_asr(websocket: WebSocket) -> None:
        supplied_key = websocket.query_params.get("token") or websocket.headers.get(
            "x-asr-api-key"
        )
        if not supplied_key or not hmac.compare_digest(supplied_key, settings.api_key):
            await websocket.close(code=4401, reason="Invalid ASR API key")
            return
        if not backend.is_ready():
            await websocket.close(code=1013, reason="Models are not ready")
            return

        await websocket.accept()
        session: StreamingSession | None = None
        session_id = "unknown"
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break

                payload_bytes = message.get("bytes")
                if payload_bytes is not None:
                    if session is None:
                        await websocket.send_json(
                            _event_payload(
                                TranscriptEvent(
                                    event_type=EventType.ERROR,
                                    session_id=session_id,
                                    message="Send a start message before audio",
                                )
                            )
                        )
                        continue
                    if len(payload_bytes) > settings.max_audio_chunk_bytes:
                        raise ValueError("Audio chunk exceeds configured size limit")
                    await send_events(
                        websocket, await session.feed_audio(payload_bytes)
                    )
                    continue

                payload_text = message.get("text")
                if payload_text is None:
                    continue
                try:
                    command = json.loads(payload_text)
                except (TypeError, ValueError) as exc:
                    raise ValueError("WebSocket text frames must contain JSON") from exc

                command_type = command.get("type")
                if command_type == "start":
                    if session is not None:
                        raise ValueError("Session has already started")
                    start = StartMessage.model_validate(command)
                    if start.sample_rate != settings.sample_rate:
                        raise ValueError(
                            f"sample_rate must be {settings.sample_rate} Hz"
                        )
                    if start.channels != 1 or start.encoding != "pcm_s16le":
                        raise ValueError("Audio must be mono pcm_s16le")
                    session_id = start.session_id
                    session = backend.create_session(
                        SessionOptions(
                            session_id=start.session_id,
                            sample_rate=start.sample_rate,
                            language=start.language,
                            hotwords=tuple(start.hotwords),
                            max_speakers=min(
                                start.max_speakers or settings.max_speakers,
                                settings.max_speakers,
                            ),
                        ),
                        voiceprints,
                    )
                    await websocket.send_json(
                        _event_payload(
                            TranscriptEvent(
                                event_type=EventType.SESSION_STARTED,
                                session_id=session_id,
                            )
                        )
                    )
                elif command_type == "commit":
                    if session is None:
                        raise ValueError("Session has not started")
                    await send_events(websocket, await session.commit())
                elif command_type in {"stop", "end"}:
                    if session is None:
                        raise ValueError("Session has not started")
                    await send_events(websocket, await session.close())
                    await websocket.send_json(
                        _event_payload(
                            TranscriptEvent(
                                event_type=EventType.SESSION_ENDED,
                                session_id=session_id,
                            )
                        )
                    )
                    await websocket.close(code=1000)
                    return
                else:
                    raise ValueError(f"Unsupported command: {command_type!r}")
        except WebSocketDisconnect:
            pass
        except (ValidationError, ValueError, RuntimeError) as exc:
            try:
                await websocket.send_json(
                    _event_payload(
                        TranscriptEvent(
                            event_type=EventType.ERROR,
                            session_id=session_id,
                            message=str(exc),
                        )
                    )
                )
                await websocket.close(code=1003)
            except RuntimeError:
                pass
        finally:
            if session is not None:
                try:
                    await session.close()
                except Exception:
                    pass

    return app


app = create_app()
