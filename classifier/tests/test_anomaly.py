from classifier.anomaly import AnomalyEngine
from classifier.parser import LogEntry


def _entry(status: int = 200, uri: str = "/products") -> LogEntry:
    return LogEntry(
        time="2026-06-03T12:00:00",
        ip="10.0.0.1",
        method="GET",
        uri=uri,
        status=status,
        bytes=100,
        referer="-",
        ua="test",
        duration_us=1000,
    )


def test_anomaly_warmup_returns_low_score():
    engine = AnomalyEngine()
    score = engine.score(_entry())
    assert 0.0 <= score <= 1.0
