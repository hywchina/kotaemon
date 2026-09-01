"""Inference backend factory."""

from __future__ import annotations

from ..config import Settings
from .base import ASRBackend
from .mock import MockBackend


def create_backend(settings: Settings) -> ASRBackend:
    if settings.backend == "mock":
        return MockBackend(settings)
    if settings.backend == "funasr":
        from .funasr import FunASRBackend

        return FunASRBackend(settings)
    raise ValueError(f"Unsupported backend: {settings.backend}")


__all__ = ["ASRBackend", "create_backend"]
