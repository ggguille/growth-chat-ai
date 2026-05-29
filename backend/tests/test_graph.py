"""Tests for the 6-node conversation graph.

Uses FakeLLMClient so no real LLM calls are made.
"""
import json

import pytest
from langgraph.checkpoint.memory import MemorySaver

from backend.conversation.graph import build_graph
from backend.qualification.models import QualificationState
from tests.conftest import FakeLLMClient


def _make_graph(fake_client: FakeLLMClient | None = None):
    return build_graph(MemorySaver(), fake_client or FakeLLMClient())


# ── Basic graph plumbing ─────────────────────────────────────────────────────

async def test_first_turn_returns_assistant_message():
    graph = _make_graph()
    result = await graph.ainvoke(
        {"session_id": "t0", "messages": [{"role": "user", "content": "Hello"}]},
        config={"configurable": {"thread_id": "t0"}},
    )
    messages = result.get("messages", [])
    assert messages, "no messages in result"
    last = messages[-1]
    content = last.content if hasattr(last, "content") else last.get("content", "")
    assert content == "Test response"


async def test_turn_counter_increments_after_each_turn():
    graph = _make_graph()
    cfg = {"configurable": {"thread_id": "t1"}}
    await graph.ainvoke(
        {"session_id": "t1", "messages": [{"role": "user", "content": "Hi"}]},
        config=cfg,
    )
    result = await graph.ainvoke(
        {"session_id": "t1", "messages": [{"role": "user", "content": "More"}]},
        config=cfg,
    )
    assert result.get("turn_counter", 0) == 2


async def test_different_threads_are_isolated():
    graph = _make_graph()
    r1 = await graph.ainvoke(
        {"session_id": "ta", "messages": [{"role": "user", "content": "A"}]},
        config={"configurable": {"thread_id": "ta"}},
    )
    r2 = await graph.ainvoke(
        {"session_id": "tb", "messages": [{"role": "user", "content": "B"}]},
        config={"configurable": {"thread_id": "tb"}},
    )
    assert r1.get("turn_counter", 0) == r2.get("turn_counter", 0) == 1


# ── score_router routing logic ───────────────────────────────────────────────

async def test_score_router_does_not_escalate_cold_lead():
    graph = _make_graph()
    result = await graph.ainvoke(
        {"session_id": "cold", "messages": [{"role": "user", "content": "Just browsing"}]},
        config={"configurable": {"thread_id": "cold"}},
    )
    assert result.get("handoff_reason") is None or result.get("handoff_reason") != "hot_lead"
    assert result.get("stage3_proposals_issued", 0) == 0


async def test_score_router_escalates_hot_lead():
    """When qualification state is already hot, score_router should route to propose_handoff."""
    hot_qual = QualificationState(
        problem_fit="confirmed",
        authority_fit="confirmed",
        company_fit="partially_confirmed",
    )

    class _StructuredFake(FakeLLMClient):
        async def structured_complete(self, system, messages, schema):
            # Return empty delta — no new signals; hot lead already set
            return {}

    graph = _make_graph(_StructuredFake())
    result = await graph.ainvoke(
        {
            "session_id": "hot",
            "messages": [{"role": "user", "content": "I'm ready to move forward"}],
            "qualification": hot_qual,
        },
        config={"configurable": {"thread_id": "hot"}},
    )
    assert result.get("stage3_proposals_issued", 0) >= 1
    assert result.get("handoff_reason") == "hot_lead"


async def test_score_router_does_not_escalate_negative_persona():
    """N1 visitors with hot-looking signals must not route to propose_handoff."""
    negative_qual = QualificationState(
        problem_fit="confirmed",
        authority_fit="confirmed",
        company_fit="confirmed",
        is_negative_persona=True,
    )

    class _StructuredFake(FakeLLMClient):
        async def structured_complete(self, system, messages, schema):
            return {}

    graph = _make_graph(_StructuredFake())
    result = await graph.ainvoke(
        {
            "session_id": "n1",
            "messages": [{"role": "user", "content": "What are your day rates?"}],
            "qualification": negative_qual,
        },
        config={"configurable": {"thread_id": "n1"}},
    )
    assert result.get("stage3_proposals_issued", 0) == 0


# ── stall_check ───────────────────────────────────────────────────────────────

async def test_stall_triggers_at_threshold():
    """After STALL_TURN_THRESHOLD turns with no Stage 3, propose_handoff fires."""
    from backend.config import settings

    threshold = settings.stall_turn_threshold
    graph = _make_graph()
    cfg = {"configurable": {"thread_id": "stall_test"}}

    state: dict = {"session_id": "stall_test", "messages": []}
    result = None
    for i in range(threshold):
        state = {"session_id": "stall_test", "messages": [{"role": "user", "content": f"Turn {i}"}]}
        result = await graph.ainvoke(state, config=cfg)

    assert result is not None
    assert result.get("stage3_proposals_issued", 0) >= 1


async def test_explicit_human_request_escalates_immediately():
    """explicit_human_request=True must route to propose_handoff regardless of qualification."""

    class _ExplicitRequestFake(FakeLLMClient):
        async def structured_complete(self, system, messages, schema):
            return {"explicit_human_request": True}

    graph = _make_graph(_ExplicitRequestFake())
    result = await graph.ainvoke(
        {
            "session_id": "explicit",
            "messages": [{"role": "user", "content": "I'd like to speak with someone"}],
        },
        config={"configurable": {"thread_id": "explicit"}},
    )
    assert result.get("handoff_reason") == "explicit_request"
    assert result.get("stage3_proposals_issued", 0) >= 1
