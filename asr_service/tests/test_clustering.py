from __future__ import annotations

import numpy as np

from app.clustering import OnlineSpeakerTracker


def test_online_tracker_reuses_and_creates_speaker_labels() -> None:
    tracker = OnlineSpeakerTracker(threshold=0.8, max_speakers=3)

    first, _ = tracker.assign(np.array([1.0, 0.0], dtype=np.float32))
    same, score = tracker.assign(np.array([0.99, 0.01], dtype=np.float32))
    second, _ = tracker.assign(np.array([0.0, 1.0], dtype=np.float32))

    assert first == "speaker_00"
    assert same == "speaker_00"
    assert score > 0.99
    assert second == "speaker_01"


def test_online_tracker_caps_number_of_speakers() -> None:
    tracker = OnlineSpeakerTracker(threshold=0.95, max_speakers=1)

    tracker.assign(np.array([1.0, 0.0], dtype=np.float32))
    label, _ = tracker.assign(np.array([0.0, 1.0], dtype=np.float32))

    assert label == "speaker_00"
