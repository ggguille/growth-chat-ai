"""Tests for context_packet.py — ContextPacket generation and summary builder."""
from datetime import UTC, datetime

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.handoff.context_packet import (
    ContextPacketGenerationError,
    build_summary,
    generate_context_packet,
)
from backend.handoff.models import HandoffRequest
from backend.qualification.models import QualificationState, SignalEntry


def _make_state(**kwargs) -> dict:
    base = {
        "session_id": "sess-001",
        "qualification": QualificationState(),
        "visitor_email": None,
        "visitor_name": None,
        "visitor_company": None,
        "visitor_role": None,
        "is_consultant": False,
        "referral_mentioned": False,
        "turn_counter": 0,
        "stage3_proposals_issued": 0,
        "messages": [],
        "handoff_triggered": False,
        "handoff_reason": None,
    }
    base.update(kwargs)
    return base


def _make_request(**kwargs) -> HandoffRequest:
    defaults = {
        "session_id": "sess-001",
        "handoff_reason": "hot_lead",
        "lead_level": "hot",
        "business_hours": True,
        "session_state": {},
        "triggered_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return HandoffRequest(**defaults)


# ── ContextPacket generation ─────────────────────────────────────────────────

def test_generate_context_packet_happy_path():
    state = _make_state(
        visitor_email="alice@example.com",
        visitor_name="Alice",
        visitor_company="Acme",
        visitor_role="CTO",
        messages=[HumanMessage(content="Hi"), AIMessage(content="Hello")],
        qualification=QualificationState(problem_fit="confirmed", authority_fit="confirmed"),
    )
    request = _make_request()
    packet = generate_context_packet(state, request)

    assert packet.session_id == "sess-001"
    assert packet.lead_level == "hot"
    assert packet.handoff_reason == "hot_lead"
    assert packet.visitor.email == "alice@example.com"
    assert packet.visitor.company == "Acme"
    assert packet.qualification.problem_fit == "confirmed"
    assert packet.turn_count == 1  # 1 human message


def test_generate_context_packet_counts_only_human_messages():
    messages = [
        HumanMessage(content="Q1"),
        AIMessage(content="A1"),
        HumanMessage(content="Q2"),
        AIMessage(content="A2"),
    ]
    state = _make_state(messages=messages)
    packet = generate_context_packet(state, _make_request())
    assert packet.turn_count == 2


def test_generate_context_packet_missing_session_id_raises():
    state = _make_state(session_id="")
    with pytest.raises(ContextPacketGenerationError, match="session_id"):
        generate_context_packet(state, _make_request())


def test_generate_context_packet_invalid_lead_level_raises():
    state = _make_state()
    request = _make_request(lead_level="ultra")  # type: ignore[arg-type]
    with pytest.raises(ContextPacketGenerationError, match="lead_level"):
        generate_context_packet(state, request)


def test_generate_context_packet_missing_visitor_fields_uses_none():
    state = _make_state()
    packet = generate_context_packet(state, _make_request())
    assert packet.visitor.email is None
    assert packet.visitor.name is None
    assert packet.visitor.company is None
    assert packet.visitor.role is None


def test_generate_context_packet_includes_signals_observed():
    signal = SignalEntry(dimension="problem_fit", signal_type="explicit", evidence="needs RAG", turn_index=1)
    qual = QualificationState(problem_fit="confirmed", signals_observed=[signal])
    state = _make_state(qualification=qual)
    packet = generate_context_packet(state, _make_request())
    assert len(packet.signals_observed) == 1
    assert packet.signals_observed[0].evidence == "needs RAG"


# ── build_summary ────────────────────────────────────────────────────────────

def test_build_summary_produces_non_empty_string():
    state = _make_state()
    summary = build_summary(state)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_build_summary_mentions_company():
    state = _make_state(visitor_company="TechCorp")
    summary = build_summary(state)
    assert "TechCorp" in summary


def test_build_summary_mentions_role():
    state = _make_state(visitor_role="VP Engineering")
    summary = build_summary(state)
    assert "VP Engineering" in summary


def test_build_summary_says_consultant_when_is_consultant():
    state = _make_state(is_consultant=True)
    summary = build_summary(state)
    assert "consultant" in summary.lower()


def test_build_summary_includes_turn_count():
    state = _make_state(messages=[HumanMessage(content="Hi"), AIMessage(content="Hey")])
    summary = build_summary(state)
    assert "1" in summary  # 1 human message → 1 turn


def test_build_summary_includes_qualification_signals():
    qual = QualificationState(problem_fit="confirmed", authority_fit="confirmed")
    state = _make_state(qualification=qual)
    summary = build_summary(state)
    assert "problem fit confirmed" in summary
    assert "decision authority confirmed" in summary


def test_build_summary_fallback_on_exception(monkeypatch):
    """Summary failure inside generate_context_packet uses fallback string."""
    import backend.handoff.context_packet as cp_module
    monkeypatch.setattr(cp_module, "build_summary", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    state = _make_state()
    packet = generate_context_packet(state, _make_request())
    assert "session signals" in packet.conversation_summary
