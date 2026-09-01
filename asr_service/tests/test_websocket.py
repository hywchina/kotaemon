from __future__ import annotations

from starlette.websockets import WebSocketDisconnect

from .conftest import TEST_API_KEY, make_wav


def _start_message(session_id: str = "session-1") -> dict:
    return {
        "type": "start",
        "session_id": session_id,
        "sample_rate": 16000,
        "channels": 1,
        "encoding": "pcm_s16le",
        "language": "zh",
        "hotwords": ["心电图", "心率"],
        "max_speakers": 4,
    }


def test_websocket_streams_partial_final_and_end_events(client) -> None:
    _, pcm = make_wav()

    with client.websocket_connect(f"/v1/asr/stream?token={TEST_API_KEY}") as websocket:
        websocket.send_json(_start_message())
        assert websocket.receive_json()["event_type"] == "session_started"

        websocket.send_bytes(pcm)
        partial = websocket.receive_json()
        assert partial["event_type"] == "segment"
        assert partial["segment"]["is_final"] is False
        assert partial["segment"]["speaker_id"] == "speaker_pending"

        websocket.send_json({"type": "commit"})
        final = websocket.receive_json()
        assert final["segment"]["is_final"] is True
        assert final["segment"]["speaker_id"] == "speaker_00"
        assert final["segment"]["segment_id"] == partial["segment"]["segment_id"]

        websocket.send_json({"type": "stop"})
        assert websocket.receive_json()["event_type"] == "session_ended"


def test_registered_voiceprint_is_attached_to_final_segment(
    client, auth_headers
) -> None:
    wav_payload, pcm = make_wav(frequency=330)
    enrolled = client.post(
        "/v1/voiceprints",
        headers=auth_headers,
        data={"display_name": "李医生"},
        files=[("files", ("doctor.wav", wav_payload, "audio/wav"))],
    )
    assert enrolled.status_code == 201

    with client.websocket_connect(f"/v1/asr/stream?token={TEST_API_KEY}") as websocket:
        websocket.send_json(_start_message("identified-session"))
        websocket.receive_json()
        websocket.send_bytes(pcm)
        websocket.receive_json()
        websocket.send_json({"type": "commit"})
        final = websocket.receive_json()["segment"]

    assert final["speaker_name"] == "李医生"
    assert final["verification_score"] > 0.99


def test_websocket_rejects_invalid_key(client) -> None:
    try:
        with client.websocket_connect("/v1/asr/stream?token=wrong"):
            raise AssertionError("connection should not be accepted")
    except WebSocketDisconnect as exc:
        assert exc.code == 4401
