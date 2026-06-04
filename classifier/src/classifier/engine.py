from __future__ import annotations

from classifier.anomaly import AnomalyEngine
from classifier.config import settings
from classifier.detector import StatefulDetector
from classifier import metrics
from classifier.parser import LogEntry
from classifier import patterns


class ClassificationEngine:
    def __init__(self) -> None:
        self._detector = StatefulDetector()
        self._anomaly = AnomalyEngine()

    def process(self, entry: LogEntry) -> list[str]:
        categories: list[str] = []
        ip = entry.ip
        uri = entry.uri

        if entry.status >= 500:
            categories.append("error_5xx")

        if entry.status == 429:
            categories.append("rate_limited")

        if patterns.check_sqli(uri):
            categories.append("sqli_attempt")

        if patterns.check_xss(uri):
            categories.append("xss_attempt")

        recon_hit = patterns.check_recon_path(uri)
        if recon_hit:
            if self._detector.track_recon(ip, recon_hit):
                categories.append("recon")

        if entry.status == 401:
            if self._detector.record_and_check(
                ip, "auth_401", settings.auth_window_sec, settings.auth_threshold
            ):
                categories.append("auth_attack")
                self._detector.flag_ip(ip, "auth_attack")

        if self._detector.record_and_check(ip, "request"):
            categories.append("ddos_suspect")
            self._detector.flag_ip(ip, "ddos_suspect")

        is_anom, score = self._anomaly.is_anomaly(entry)
        metrics.ML_ANOMALY_SCORE.set(score)
        if is_anom:
            categories.append("ml_anomaly")

        for cat in categories:
            metrics.inc_category(cat)

        for reason in ("ddos_suspect", "auth_attack"):
            metrics.FLAGGED_IPS.labels(reason=reason).set(
                self._detector.count_flagged(reason)
            )

        metrics.LOGS_PROCESSED.inc()
        return categories
