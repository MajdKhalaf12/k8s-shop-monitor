import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

WINDOW_SEC = float(os.environ.get("RATE_LIMIT_WINDOW_SEC", "1"))
MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX", "30"))
_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _client_ip(request)
        now = time.time()
        hits = _hits[ip]
        hits[:] = [t for t in hits if now - t < WINDOW_SEC]
        hits.append(now)
        if len(hits) > MAX_REQUESTS:
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
        return await call_next(request)
