"""Incremental cosine clustering for stable session-local speaker labels."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def normalize_embedding(value: np.ndarray) -> np.ndarray:
    embedding = np.asarray(value, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(embedding))
    if not np.isfinite(norm) or norm <= 1e-8:
        raise ValueError("Speaker embedding is empty or invalid")
    return embedding / norm


@dataclass
class _Center:
    embedding: np.ndarray
    updates: int = 1


class OnlineSpeakerTracker:
    def __init__(self, *, threshold: float, max_speakers: int):
        self.threshold = threshold
        self.max_speakers = max_speakers
        self._centers: list[_Center] = []

    def assign(self, value: np.ndarray) -> tuple[str, float]:
        embedding = normalize_embedding(value)
        if not self._centers:
            self._centers.append(_Center(embedding))
            return "speaker_00", 1.0

        similarities = np.asarray(
            [float(np.dot(embedding, center.embedding)) for center in self._centers]
        )
        index = int(np.argmax(similarities))
        score = max(-1.0, min(1.0, float(similarities[index])))

        if score < self.threshold and len(self._centers) < self.max_speakers:
            index = len(self._centers)
            self._centers.append(_Center(embedding))
            return f"speaker_{index:02d}", 1.0

        center = self._centers[index]
        weight = 1.0 / min(center.updates + 1, 20)
        center.embedding = normalize_embedding(
            (1.0 - weight) * center.embedding + weight * embedding
        )
        center.updates += 1
        return f"speaker_{index:02d}", score
