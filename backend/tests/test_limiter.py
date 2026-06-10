import pytest
from unittest.mock import MagicMock

from backend.limiter import _FixedWindowLimiter, _session_key


def test_uses_session_id_header_when_present():
    req = MagicMock()
    req.headers = {"ZGC-Session-ID": "abc-123"}
    assert _session_key(req) == "abc-123"


def test_falls_back_to_ip_when_no_header():
    req = MagicMock()
    req.headers = {}
    req.client.host = "127.0.0.1"
    # get_remote_address reads request.client.host
    result = _session_key(req)
    assert result == "127.0.0.1"


async def test_rate_limiter_blocks_after_limit():
    limiter = _FixedWindowLimiter(limit=3, window_seconds=60)
    assert await limiter.hit("k") is True
    assert await limiter.hit("k") is True
    assert await limiter.hit("k") is True
    assert await limiter.hit("k") is False


async def test_rate_limiter_separate_keys_are_independent():
    limiter = _FixedWindowLimiter(limit=1, window_seconds=60)
    assert await limiter.hit("a") is True
    assert await limiter.hit("b") is True
    assert await limiter.hit("a") is False
