"""
Redis-backed rate limiting with in-memory fallback.

Used to protect authentication endpoints from brute-force and abuse.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, DefaultDict

from fastapi import Request, status

from app.core.config import settings
from app.core.exceptions import AppException
from app.db.redis import RedisManager

logger = logging.getLogger(__name__)

_memory_buckets: DefaultDict[str, Deque[float]] = defaultdict(deque)
_memory_lock = Lock()


def _client_key(request: Request, scope: str) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"rl:{scope}:{ip}"


async def enforce_rate_limit(
    request: Request,
    *,
    scope: str = "auth",
    limit: int | None = None,
    window_seconds: int | None = None,
) -> None:
    """
    Raise ``AppException`` (429) when the client exceeds the configured budget.

    Tries Redis first; falls back to a process-local sliding window.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    max_requests = limit if limit is not None else settings.RATE_LIMIT_AUTH_PER_MINUTE
    window = window_seconds if window_seconds is not None else settings.RATE_LIMIT_WINDOW_SECONDS
    key = _client_key(request, scope)

    try:
        client = RedisManager.get_client()
        pipe = client.pipeline()
        now = time.time()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {f"{now}:{id(request)}": now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = int(results[2])
        if count > max_requests:
            raise AppException(
                "Too many requests. Please try again later.",
                code="RATE_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return
    except AppException:
        raise
    except Exception:  # noqa: BLE001 — fall back when Redis is unavailable
        logger.debug("Rate limit using in-memory fallback for key=%s", key)

    now = time.time()
    with _memory_lock:
        bucket = _memory_buckets[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= max_requests:
            raise AppException(
                "Too many requests. Please try again later.",
                code="RATE_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        bucket.append(now)
