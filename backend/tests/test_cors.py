import pytest

from backend.main import app

ALLOWED = "http://localhost:3000"
DISALLOWED = "https://evil.example.com"

PREFLIGHT_HEADERS = {
    "Origin": ALLOWED,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "Content-Type,Accept,ZGC-Session-ID,ZGC-API-KEY",
}


@pytest.fixture(autouse=True)
def set_allowed_origin(monkeypatch):
    from backend import config
    monkeypatch.setattr(config.settings, "allowed_origin", ALLOWED)
    # Re-add middleware with the patched origin so the running app picks it up.
    # The app instance is module-level, so we patch the settings attribute that
    # CORSMiddleware reads from settings at startup.  Because the middleware is
    # instantiated once at import time we need to replace it for these tests.
    from fastapi.middleware.cors import CORSMiddleware
    app.middleware_stack = None  # force rebuild on next request
    # Remove stale CORS middleware and add a fresh one with the test origin.
    app.user_middleware = [
        m for m in app.user_middleware
        if not (hasattr(m, "cls") and m.cls is CORSMiddleware)
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED],
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type", "Accept", "ZGC-Session-ID", "ZGC-API-KEY"],
        allow_credentials=False,
    )


async def test_preflight_allowed_origin_returns_200(client):
    response = await client.options("/chat", headers=PREFLIGHT_HEADERS)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED
    assert "POST" in response.headers.get("access-control-allow-methods", "")


async def test_preflight_disallowed_origin_returns_400(client):
    headers = {**PREFLIGHT_HEADERS, "Origin": DISALLOWED}
    response = await client.options("/chat", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_post_allowed_origin_includes_cors_header(client):
    import uuid
    session_id = str(uuid.uuid4())
    response = await client.post(
        "/chat",
        headers={
            "Origin": ALLOWED,
            "Accept": "text/event-stream",
            "ZGC-Session-ID": session_id,
            "ZGC-API-KEY": "",
        },
        json={"message": "Hello"},
    )
    assert response.headers.get("access-control-allow-origin") == ALLOWED
