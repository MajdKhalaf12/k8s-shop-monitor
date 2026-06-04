from __future__ import annotations

import time

from classifier.config import settings


class StatefulDetector:
    """Layer 3: in-process sliding windows per IP (single classifier sidecar)."""

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = {}
        self._recon_sets: dict[str, set[str]] = {}
        self._recon_expiry: dict[str, float] = {}
        self._flagged: dict[str, set[str]] = {}
        self._flagged_expiry: dict[str, float] = {}

    def record_and_check(
        self,
        ip: str,
        event: str,
        window_sec: int | None = None,
        threshold: int | None = None,
    ) -> bool:
        window_sec = window_sec or settings.ddos_window_sec
        thresholds = {
            "request": settings.ddos_threshold,
            "auth_401": settings.auth_threshold,
        }
        threshold = threshold or thresholds.get(event, settings.ddos_threshold)

        key = f"{ip}:{event}"
        now = time.time()
        events = self._windows.setdefault(key, [])
        cutoff = now - window_sec
        events[:] = [t for t in events if t > cutoff]
        events.append(now)
        return len(events) >= threshold

    def track_recon(self, ip: str, path: str) -> bool:
        now = time.time()
        if self._recon_expiry.get(ip, 0) < now:
            self._recon_sets[ip] = set()
        self._recon_expiry[ip] = now + settings.ddos_window_sec
        self._recon_sets.setdefault(ip, set()).add(path)
        return len(self._recon_sets[ip]) >= settings.recon_min_paths

    def flag_ip(self, ip: str, reason: str) -> None:
        now = time.time()
        key = f"flagged:{reason}"
        if self._flagged_expiry.get(key, 0) < now:
            self._flagged[key] = set()
        self._flagged_expiry[key] = now + 3600
        self._flagged.setdefault(key, set()).add(ip)

    def count_flagged(self, reason: str) -> int:
        key = f"flagged:{reason}"
        if self._flagged_expiry.get(key, 0) < time.time():
            return 0
        return len(self._flagged.get(key, set()))
