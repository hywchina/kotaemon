"""Deployment policy helpers for hospital network environments."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

VALID_DEPLOYMENT_MODES = {
    "standard",
    "hospital-external",
    "hospital-offline",
}


def normalize_deployment_mode(value: str) -> str:
    """Validate and normalize a deployment mode."""

    mode = value.strip().lower()
    if mode not in VALID_DEPLOYMENT_MODES:
        choices = ", ".join(sorted(VALID_DEPLOYMENT_MODES))
        raise ValueError(f"KH_DEPLOYMENT_MODE must be one of: {choices}")
    return mode


def is_hospital_mode(mode: str) -> bool:
    return normalize_deployment_mode(mode).startswith("hospital-")


def _is_internal_hostname(hostname: str) -> bool:
    normalized = hostname.rstrip(".").lower()
    if normalized in {"localhost", "host.docker.internal"}:
        return True
    if normalized.endswith((".local", ".internal", ".lan")):
        return True
    if "." not in normalized:
        return True
    try:
        return ipaddress.ip_address(normalized).is_private
    except ValueError:
        return False


def validate_model_endpoint(
    mode: str,
    endpoint: str,
    *,
    external_hosts: set[str] | None = None,
) -> str:
    """Validate a model endpoint against the selected hospital egress policy."""

    deployment_mode = normalize_deployment_mode(mode)
    if deployment_mode == "standard":
        return endpoint

    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Invalid model endpoint: {endpoint}")
    if parsed.username or parsed.password:
        raise ValueError("Model endpoint credentials must not be embedded in the URL")

    hostname = parsed.hostname.lower()
    if deployment_mode == "hospital-offline":
        if not _is_internal_hostname(hostname):
            raise ValueError(
                "hospital-offline only permits localhost, private IPs, single-label "
                "service names, and .local/.internal/.lan model hosts"
            )
    else:
        if _is_internal_hostname(hostname):
            return endpoint
        allowed = {host.lower() for host in external_hosts or set()}
        if parsed.scheme != "https":
            raise ValueError("hospital-external model endpoints must use HTTPS")
        if hostname not in allowed:
            raise ValueError(
                f"Model endpoint host '{hostname}' is not in KH_MODEL_HOST_ALLOWLIST"
            )
    return endpoint


def validate_model_spec(
    mode: str,
    spec: dict,
    *,
    external_hosts: set[str] | None = None,
) -> dict:
    """Validate every endpoint field in a serialized model specification."""

    for key in ("base_url", "endpoint_url", "azure_endpoint"):
        endpoint = spec.get(key)
        if endpoint:
            validate_model_endpoint(
                mode,
                str(endpoint),
                external_hosts=external_hosts,
            )
    return spec
