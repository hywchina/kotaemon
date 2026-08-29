import pytest
from ktem.utils.deployment import (
    normalize_deployment_mode,
    validate_model_endpoint,
    validate_model_spec,
)


def test_invalid_deployment_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="KH_DEPLOYMENT_MODE"):
        normalize_deployment_mode("unknown")


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://127.0.0.1:8000/v1",
        "http://model-gateway:8000/v1",
        "https://models.hospital.internal/v1",
        "http://10.20.30.40:8000/v1",
    ),
)
def test_offline_mode_accepts_internal_model_endpoints(endpoint: str) -> None:
    assert validate_model_endpoint("hospital-offline", endpoint) == endpoint


def test_offline_mode_rejects_public_model_endpoint() -> None:
    with pytest.raises(ValueError, match="hospital-offline"):
        validate_model_endpoint("hospital-offline", "https://api.openai.com/v1")


def test_external_mode_requires_https_allowlist() -> None:
    endpoint = "https://geekai.co/api/v1"
    assert (
        validate_model_endpoint(
            "hospital-external",
            endpoint,
            external_hosts={"geekai.co"},
        )
        == endpoint
    )
    with pytest.raises(ValueError, match="HTTPS"):
        validate_model_endpoint(
            "hospital-external",
            "http://geekai.co/api/v1",
            external_hosts={"geekai.co"},
        )


def test_external_mode_also_accepts_internal_fallback() -> None:
    endpoint = "http://model-gateway:8000/v1"
    assert validate_model_endpoint("hospital-external", endpoint) == endpoint


def test_model_spec_rejects_hidden_public_endpoint() -> None:
    with pytest.raises(ValueError, match="not in KH_MODEL_HOST_ALLOWLIST"):
        validate_model_spec(
            "hospital-external",
            {"endpoint_url": "https://other-provider.example/v1/rerank"},
            external_hosts={"geekai.co"},
        )
