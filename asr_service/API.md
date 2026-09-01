# ASR API contract

## Authentication

REST requests use `X-ASR-API-Key`. WebSocket clients may use the same header or
the `token` query parameter. Production deployments should terminate TLS inside
the hospital network and should prefer short-lived WebSocket tokens.

## Realtime transcription

Connect to `WS /v1/asr/stream`, then send:

```json
{
  "type": "start",
  "session_id": "8eb2...",
  "sample_rate": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "language": "zh",
  "hotwords": ["心电图", "房颤"],
  "max_speakers": 4
}
```

After `session_started`, send binary mono PCM16LE frames. Frames of 60–600 ms
are recommended. The service emits partial `segment` events using the stable
`segment_id`; clients replace the previous partial with the newest revision.

Send `{"type":"commit"}` at an utterance boundary. The service runs offline
Paraformer correction, speaker embedding, online clustering and voiceprint
matching, then emits a final segment. Send `{"type":"stop"}` to commit pending
audio, receive `session_ended`, and close the socket.

```json
{
  "event_type": "segment",
  "session_id": "8eb2...",
  "segment": {
    "segment_id": "8eb2...-seg-0000",
    "text": "建议先做心电图检查。",
    "start_ms": 0,
    "end_ms": 3180,
    "speaker_id": "speaker_00",
    "speaker_name": "张医生",
    "verification_score": 0.86,
    "is_final": true
  }
}
```

The initial implementation uses client-driven `commit`. A browser VAD or the
stop button must create utterance boundaries. Server-side streaming FSMN-VAD is
the next pipeline extension; FSMN-VAD already participates in final correction.

## Voiceprints

- `POST /v1/voiceprints`: multipart `display_name` plus one or more `files`.
- `POST /v1/voiceprints/{id}/samples`: append enrollment WAV samples.
- `GET /v1/voiceprints`: list metadata; embeddings are never returned.
- `DELETE /v1/voiceprints/{id}`: remove identity and embedding.

Enrollment accepts uncompressed signed PCM16 WAV, mono or stereo, 8–96 kHz.
Audio is converted to mono 16 kHz. Each sample must be at least one second.

## Health

- `GET /health/live`: process is alive.
- `GET /health/ready`: all configured models are loaded and sessions may start.
