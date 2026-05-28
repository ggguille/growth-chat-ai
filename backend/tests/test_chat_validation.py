import json
import uuid

import pytest

VALID_SESSION_ID = str(uuid.uuid4())
VALID_HEADERS = {
    "Accept": "text/event-stream",
    "ZGC-Session-ID": VALID_SESSION_ID,
    "ZGC-API-KEY": "",
}


async def test_missing_accept_header_returns_400(client):
    response = await client.post(
        "/chat",
        headers={"ZGC-Session-ID": VALID_SESSION_ID, "ZGC-API-KEY": ""},
        json={"message": "Hello"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "MISSING_ACCEPT_HEADER"


async def test_wrong_api_key_returns_401(client):
    response = await client.post(
        "/chat",
        headers={
            "Accept": "text/event-stream",
            "ZGC-Session-ID": VALID_SESSION_ID,
            "ZGC-API-KEY": "wrong-key",
        },
        json={"message": "Hello"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_API_KEY"


async def test_invalid_session_id_returns_400(client):
    response = await client.post(
        "/chat",
        headers={
            "Accept": "text/event-stream",
            "ZGC-Session-ID": "not-a-uuid",
            "ZGC-API-KEY": "",
        },
        json={"message": "Hello"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_MESSAGE"


async def test_empty_message_returns_400(client):
    response = await client.post(
        "/chat",
        headers=VALID_HEADERS,
        json={"message": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_MESSAGE"


async def test_valid_request_returns_sse_stream(client):
    async with client.stream(
        "POST",
        "/chat",
        headers=VALID_HEADERS,
        json={"message": "Hello"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] == "done"


async def test_valid_request_done_event_fields(client):
    async with client.stream(
        "POST",
        "/chat",
        headers=VALID_HEADERS,
        json={"message": "Hello"},
    ) as response:
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    done = next(e for e in events if e["type"] == "done")
    assert done["session_id"] == VALID_SESSION_ID
    assert done["lead_level"] == "cold"
    assert done["current_stage"] == 1
    assert done["turn_count"] == 1
    assert done["stage3_proposal_issued"] is False
