from unittest.mock import MagicMock

from backend.limiter import _session_key


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
