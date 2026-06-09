from classifier.engine import ClassificationEngine
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


def test_classifies_403():
    engine = ClassificationEngine()
    cats = engine.process(_entry(status=403, uri="/admin"))
    assert "auth_forbidden" in cats


def test_classifies_429():
    engine = ClassificationEngine()
    cats = engine.process(_entry(status=429, uri="/api/v1/products"))
    assert "rate_limited" in cats


def test_classifies_sqli_in_uri():
    engine = ClassificationEngine()
    cats = engine.process(_entry(uri="/api/v1/products/search?q=1' OR '1'='1"))
    assert "sqli_attempt" in cats
