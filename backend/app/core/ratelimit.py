import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import AppError

_hits: dict[str, deque[float]] = defaultdict(deque)


def _limiter(setting: str):
    def check(request: Request) -> None:
        """Sliding window per client IP + path, limit read from settings.

        ponytail: in-process memory, so limits are per worker and reset on restart;
        move to Redis (INCR + EXPIRE) when running multiple backend workers.
        """
        now = time.monotonic()
        hits = _hits[f"{request.client.host if request.client else '?'}:{request.url.path}"]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= getattr(get_settings(), setting):
            raise AppError("Too many requests, try again later", 429)
        hits.append(now)

    return check


rate_limit = _limiter("rate_limit_per_minute")  # login, register, password reset: brute-force sensitive
rate_limit_refresh = _limiter("rate_limit_refresh_per_minute")  # every page load/tab refreshes a session, so it needs headroom
