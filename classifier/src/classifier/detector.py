from __future__ import annotations

import time

import redis

from classifier.config import settings


class StatefulDetector:
    """Layer 3: Redis sorted-set sliding windows per IP."""

    def __init__(self, client: redis.Redis) -> None:
        self._redis = client
        self._recon_paths = [p.strip() for p in settings.recon_paths.split(",") if p.strip()]

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

        key = f"window:{ip}:{event}"
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_sec)
        pipe.zadd(key, {f"{now}": now})
        pipe.zcard(key)
        pipe.expire(key, window_sec + 5)
        _, _, count, _ = pipe.execute()
        return int(count) >= threshold

    def track_recon(self, ip: str, path: str) -> bool:
        key = f"recon:{ip}"
        self._redis.sadd(key, path)
        self._redis.expire(key, settings.ddos_window_sec)
        count = self._redis.scard(key)
        return int(count) >= settings.recon_min_paths

    def flag_ip(self, ip: str, reason: str) -> None:
        self._redis.sadd(f"flagged:{reason}", ip)
        self._redis.expire(f"flagged:{reason}", 3600)

    def count_flagged(self, reason: str) -> int:
        return int(self._redis.scard(f"flagged:{reason}") or 0)
