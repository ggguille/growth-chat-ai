import asyncio
import time

from fastapi import HTTPException, Request
from slowapi.util import get_remote_address


def _session_key(request: Request) -> str:
    return request.headers.get("ZGC-Session-ID", get_remote_address(request))


class _FixedWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def hit(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            count, window_start = self._buckets.get(key, (0, now))
            if now - window_start >= self._window:
                self._buckets[key] = (1, now)
                return True
            if count >= self._limit:
                return False
            self._buckets[key] = (count + 1, window_start)
            return True


_rate_limiter = _FixedWindowLimiter(limit=20, window_seconds=300)


async def check_rate_limit(request: Request) -> None:
    if not await _rate_limiter.hit(_session_key(request)):
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Rate limit exceeded. Try again in 5 minutes.",
                    "retry_after_seconds": 300,
                }
            },
            headers={"Retry-After": "300"},
        )
