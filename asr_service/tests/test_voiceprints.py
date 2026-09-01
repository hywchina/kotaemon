from __future__ import annotations

from .conftest import make_wav


def _upload(client, headers, name: str, wav_payload: bytes):
    return client.post(
        "/v1/voiceprints",
        headers=headers,
        data={"display_name": name},
        files=[("files", ("sample.wav", wav_payload, "audio/wav"))],
    )


def test_voiceprint_crud_and_multiple_samples(client, auth_headers) -> None:
    first_wav, _ = make_wav(frequency=220)
    second_wav, _ = make_wav(frequency=225)

    created = _upload(client, auth_headers, "张医生", first_wav)
    assert created.status_code == 201, created.text
    voiceprint_id = created.json()["id"]
    assert created.json()["sample_count"] == 1

    updated = client.post(
        f"/v1/voiceprints/{voiceprint_id}/samples",
        headers=auth_headers,
        files=[("files", ("sample-2.wav", second_wav, "audio/wav"))],
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sample_count"] == 2

    listed = client.get("/v1/voiceprints", headers=auth_headers)
    assert listed.status_code == 200
    assert [(item["display_name"], item["sample_count"]) for item in listed.json()] == [
        ("张医生", 2)
    ]

    deleted = client.delete(f"/v1/voiceprints/{voiceprint_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/v1/voiceprints", headers=auth_headers).json() == []


def test_duplicate_voiceprint_name_is_rejected(client, auth_headers) -> None:
    wav_payload, _ = make_wav()
    assert _upload(client, auth_headers, "张医生", wav_payload).status_code == 201

    duplicate = _upload(client, auth_headers, "张医生", wav_payload)

    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_invalid_or_short_voiceprint_audio_is_rejected(client, auth_headers) -> None:
    invalid = _upload(client, auth_headers, "无效样本", b"not-a-wave")
    short_wav, _ = make_wav(duration_seconds=0.2)
    short = _upload(client, auth_headers, "过短样本", short_wav)

    assert invalid.status_code == 422
    assert short.status_code == 422
    assert "at least 1 second" in short.json()["detail"]
