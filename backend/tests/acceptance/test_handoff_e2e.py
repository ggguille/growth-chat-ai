"""Acceptance tests for Phase 3 exit gate: propose_handoff fires → leads row + handoff_records row.

Requires:
  - Backend running at BACKEND_URL (auto-skipped by require_backend fixture in conftest.py)
  - CHECKPOINT_DB_URL set (auto-skipped by require_db_url fixture below)

Trigger strategy: send the qualifying hot-lead message first. With Claude Haiku (CI) it
fires on turn 1 via rule-based hot-lead detection. With a local Ollama model that returns
"partially_confirmed" instead of None for problem_fit (blocking the rule-based override),
the stall check fires deterministically at turn 6 — no LLM involvement. Either way,
propose_handoff runs, the leads row is written, and the handoff_records row is written.
"""
import json
import os
import uuid

import httpx
import psycopg
import pytest

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CHECKPOINT_DB_URL = os.getenv("CHECKPOINT_DB_URL", "")
API_KEY = os.getenv("ZGC_API_KEY", "")

_HOT_LEAD_MESSAGE = (
    "Hi, I'm the CTO at a fintech startup with 50 engineers. "
    "We're building a RAG pipeline to automate document processing "
    "and need to complete the first version by Q3. "
    "Would love to learn more about how your team could help."
)

_FALLBACK_TURNS = [
    "Tell me more about your team.",
    "What technologies do you typically use?",
    "How long does a typical engagement take?",
    "Can you share some case studies?",
    "What would the next steps look like?",
]


@pytest.fixture(scope="session", autouse=True)
async def require_db_url():
    if not CHECKPOINT_DB_URL:
        pytest.skip("CHECKPOINT_DB_URL not set — skipping Phase 3 handoff e2e tests")


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
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    return events


async def _drive_to_stage3(session_id: str) -> dict:
    """Send messages until propose_handoff fires (hot-lead or stall) and return the done event.

    Turn 1: qualifying hot-lead message — exits immediately with capable models (Claude Haiku).
    Turns 2-6: neutral follow-ups — stall fires deterministically at turn 6 with any model.
    Raises AssertionError if no proposal after 6 turns (genuine infrastructure failure).
    """
    events = await _stream_chat(session_id, _HOT_LEAD_MESSAGE)
    done = next(e for e in events if e.get("type") == "done")
    if done.get("stage3_proposal_issued"):
        return done
    for msg in _FALLBACK_TURNS:
        events = await _stream_chat(session_id, msg)
        done = next(e for e in events if e.get("type") == "done")
        if done.get("stage3_proposal_issued"):
            return done
    raise AssertionError(f"propose_handoff did not fire after 6 turns: last done={done}")


async def test_hot_lead_creates_leads_row():
    """propose_handoff fires → leads table row with non-empty summary."""
    sid = _new_session_id()
    await _drive_to_stage3(sid)

    with psycopg.connect(CHECKPOINT_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT lead_level, conversation_summary, signals_observed FROM leads WHERE session_id = %s",
                (sid,),
            )
            row = cur.fetchone()

    assert row is not None, f"No row in leads for session_id={sid}"
    lead_level, summary, signals = row
    assert lead_level in ("hot", "warm", "cold")
    assert summary, "conversation_summary is empty"
    assert isinstance(signals, list)


async def test_hot_lead_creates_handoff_record():
    """propose_handoff fires → handoff_records row with outcome=complete (both channels ok)."""
    sid = _new_session_id()
    await _drive_to_stage3(sid)

    with psycopg.connect(CHECKPOINT_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT outcome, crm_status, slack_status FROM handoff_records WHERE session_id = %s",
                (sid,),
            )
            row = cur.fetchone()

    assert row is not None, f"No row in handoff_records for session_id={sid}"
    outcome, crm_status, slack_status = row
    assert crm_status == "ok", f"CRM delivery failed: crm_status={crm_status}"
    assert slack_status == "ok", f"Slack delivery failed (NullNotifier should always succeed): {slack_status}"
    assert outcome == "complete"
