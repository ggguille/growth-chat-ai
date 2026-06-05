import json
import os
import uuid

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("ZGC_API_KEY", "")


def _new_session_id() -> str:
    return str(uuid.uuid4())


async def _stream_chat(session_id: str, message: str) -> list[dict]:
    events: list[dict] = []
    async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
        async with client.stream(
            "POST",
            "/chat",
            headers={
                "Accept": "text/event-stream",
                "ZGC-Session-ID": session_id,
                "ZGC-API-KEY": API_KEY,
            },
            json={"message": message},
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    return events


async def test_health():
    async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_ready():
    async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
        r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


async def test_chat_returns_token_and_done_events():
    events = await _stream_chat(_new_session_id(), "Hello")
    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] == "done"


async def test_done_event_has_required_fields():
    sid = _new_session_id()
    events = await _stream_chat(sid, "Hello")
    done = next(e for e in events if e["type"] == "done")
    assert done["session_id"] == sid
    assert done["lead_level"] in ("hot", "warm", "cold")
    assert done["current_stage"] in (1, 2, 3)
    assert done["turn_count"] >= 1
    assert isinstance(done["stage3_proposal_issued"], bool)


async def test_session_continuity_turn_count_increments():
    sid = _new_session_id()
    events1 = await _stream_chat(sid, "Hello")
    events2 = await _stream_chat(sid, "Tell me more")
    done1 = next(e for e in events1 if e["type"] == "done")
    done2 = next(e for e in events2 if e["type"] == "done")
    assert done2["turn_count"] > done1["turn_count"]


async def test_rate_limit_fires_after_20_requests():
    sid = _new_session_id()
    status_codes: list[int] = []

    async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
        for _ in range(21):
            async with client.stream(
                "POST",
                "/chat",
                headers={
                    "Accept": "text/event-stream",
                    "ZGC-Session-ID": sid,
                    "ZGC-API-KEY": API_KEY,
                },
                json={"message": "ping"},
                timeout=60.0,
            ) as r:
                status_codes.append(r.status_code)
                # status code available on headers — no body drain needed for rate-limit check

    assert 429 in status_codes, "Expected HTTP 429 after 20 requests within 5 minutes"

    async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
        r = await client.post(
            "/chat",
            headers={
                "Accept": "text/event-stream",
                "ZGC-Session-ID": sid,
                "ZGC-API-KEY": API_KEY,
            },
            json={"message": "ping"},
            timeout=15.0,
        )
    if r.status_code == 429:
        body = r.json()
        assert body["error"]["code"] == "RATE_LIMITED"
