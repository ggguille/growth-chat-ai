from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _session_key(request: Request) -> str:
    return request.headers.get("ZGC-Session-ID", get_remote_address(request))


limiter = Limiter(key_func=_session_key)
