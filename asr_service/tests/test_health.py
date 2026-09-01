from __future__ import annotations


def test_health_endpoints_report_mock_backend(client) -> None:
    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok", "backend": "mock", "models": {}}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["models"]["pipeline"] == "deterministic-mock"


def test_voiceprint_routes_require_api_key(client) -> None:
    response = client.get("/v1/voiceprints")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid ASR API key"
