import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import AppError

_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """Sliding window per client IP + path.

    ponytail: in-process memory, so limits are per worker and reset on restart;
    move to Redis (INCR + EXPIRE) when running multiple backend workers.
    """
    now = time.monotonic()
    hits = _hits[request.url.path]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= get_settings().rate_limit_per_minute:
        raise AppError("Too many requests, try again later", 429)
    hits.append(now)
