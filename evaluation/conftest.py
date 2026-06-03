from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv()

_API_URL = os.getenv("EVAL_API_URL", "http://localhost:8000")
_API_KEY = os.getenv("ZGC_API_KEY", "dev-key")


@dataclass
class ChatResponse:
    text: str
    lead_level: str
    current_stage: int
    stage3_proposal_issued: bool
    handoff_reason: str | None
    turn_count: int

    def __str__(self) -> str:
        return self.text


class ChatSession:
    def __init__(self, client: httpx.AsyncClient, session_id: str, api_key: str) -> None:
        self._client = client
        self._session_id = session_id
        self._api_key = api_key

    async def send(self, message: str) -> ChatResponse:
        try:
            return await self._send_once(message)
        except httpx.RemoteProtocolError:
            await asyncio.sleep(1.0)
            return await self._send_once(message)

    async def _send_once(self, message: str) -> ChatResponse:
        tokens: list[str] = []
        done_data: dict = {}
        async with self._client.stream(
            "POST",
            "/chat",
            json={"message": message},
            headers={
                "ZGC-Session-ID": self._session_id,
                "ZGC-API-KEY": self._api_key,
                "Accept": "text/event-stream",
            },
            timeout=httpx.Timeout(10.0, read=120.0),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                if payload.get("type") == "token":
                    tokens.append(payload["content"])
                elif payload.get("type") == "done":
                    done_data = payload
        return ChatResponse(
            text="".join(tokens),
            lead_level=done_data.get("lead_level", "cold"),
            current_stage=done_data.get("current_stage", 1),
            stage3_proposal_issued=done_data.get("stage3_proposal_issued", False),
            handoff_reason=done_data.get("handoff_reason"),
            turn_count=done_data.get("turn_count", 0),
        )


@pytest_asyncio.fixture
async def chat_session():
    async with httpx.AsyncClient(base_url=_API_URL) as client:
        try:
            resp = await client.get("/ready", timeout=10.0)
            if resp.status_code != 200:
                pytest.skip(
                    f"Backend not ready at {_API_URL} (status {resp.status_code}) — is the graph initialised?"
                )
                return
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip(f"Backend not reachable at {_API_URL} — set EVAL_API_URL to a running instance")
            return
        session_id = str(uuid.uuid4())
        yield ChatSession(client, session_id, _API_KEY)
