from __future__ import annotations

from river import anomaly

from classifier.config import settings
from classifier.parser import LogEntry


class AnomalyEngine:
    """Layer 2: unsupervised online anomaly detection (HalfSpaceTrees)."""

    def __init__(self) -> None:
        self._model = anomaly.HalfSpaceTrees(
            n_trees=25,
            height=8,
            window_size=250,
            seed=42,
        )
        self._samples = 0
        self._warmup = 50

    def _features(self, entry: LogEntry) -> dict[str, float]:
        uri_len = float(min(len(entry.uri), 512))
        return {
            "status": float(entry.status),
            "bytes": float(min(entry.bytes, 100000)),
            "uri_len": uri_len,
            "duration_us": float(min(entry.duration_us, 5_000_000)),
            "is_error": 1.0 if entry.status >= 500 else 0.0,
            "is_429": 1.0 if entry.status == 429 else 0.0,
        }

    def score(self, entry: LogEntry) -> float:
        features = self._features(entry)
        if self._samples < self._warmup:
            self._model.learn_one(features)
            self._samples += 1
            return 0.0
        score = float(self._model.score_one(features))
        self._model.learn_one(features)
        self._samples += 1
        # River anomaly scores: higher = more anomalous; normalize roughly to 0-1
        normalized = min(1.0, max(0.0, score / 10.0))
        return normalized

    def is_anomaly(self, entry: LogEntry) -> tuple[bool, float]:
        s = self.score(entry)
        return s >= settings.anomaly_threshold, s
