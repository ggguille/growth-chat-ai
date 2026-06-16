"""Functional validation for RAG integration paths.

Covers the four scenarios from the Phase 4 handoff:
  1. Relevant question  → chunk above threshold → answer grounded in KB content
  2. Irrelevant question → no retrieval result → [NO RELEVANT RESULTS] in prompt
  3. [NO RELEVANT RESULTS] path → forward path enforced even if LLM omits it
  4. Case study with high score → proactive_case_study=True → [proactive_case_study: true] in prompt

All tests are offline: no real DB, no real embedding API, no real LLM calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.knowledge.retrieval import RetrievedChunk, RetrievalResult
from backend.conversation.graph.messages import _format_retrieval_result


# ── Scenario 1 & 2: message formatting (pure function, no mocking needed) ─────

def test_no_result_formats_as_no_relevant_results_signal():
    result = RetrievalResult(status="no_result", reason="below_threshold")
    formatted = _format_retrieval_result("tool-1", result)
    assert len(formatted) == 1
    assert formatted[0]["content"] == "[NO RELEVANT RESULTS]"
    assert formatted[0]["tool_use_id"] == "tool-1"


def test_ok_result_formats_source_score_and_content():
    chunk = RetrievedChunk(
        chunk_id="c1",
        content="Zartis provides distributed engineering teams.",
        score=0.85,
        source="services-overview",
        chunk_index=0,
    )
    result = RetrievalResult(status="ok", chunks=[chunk])
    formatted = _format_retrieval_result("tool-2", result)
    content = formatted[0]["content"]
    assert "[Source: services-overview, score: 0.85]" in content
    assert "Zartis provides distributed engineering teams." in content
    assert "[proactive_case_study: true]" not in content


def test_proactive_case_study_flag_prepends_signal_to_content():
    chunk = RetrievedChunk(
        chunk_id="c2",
        content="We helped a fintech client reduce inference latency by 40%.",
        score=0.91,
        source="case-study-fintech",
        chunk_index=0,
    )
    result = RetrievalResult(status="ok", chunks=[chunk], proactive_case_study=True)
    formatted = _format_retrieval_result("tool-3", result)
    content = formatted[0]["content"]
    assert content.startswith("[proactive_case_study: true]")
    assert "case-study-fintech" in content


def test_error_result_also_returns_no_relevant_results():
    result = RetrievalResult(status="error", reason="embedding_failure")
    formatted = _format_retrieval_result("tool-4", result)
    assert formatted[0]["content"] == "[NO RELEVANT RESULTS]"


def test_multiple_chunks_separated_by_divider():
    chunks = [
        RetrievedChunk(chunk_id="a", content="Chunk A", score=0.80, source="src-a", chunk_index=0),
        RetrievedChunk(chunk_id="b", content="Chunk B", score=0.75, source="src-b", chunk_index=1),
    ]
    result = RetrievalResult(status="ok", chunks=chunks)
    formatted = _format_retrieval_result("tool-5", result)
    content = formatted[0]["content"]
    assert "---" in content
    assert "Chunk A" in content
    assert "Chunk B" in content


# ── Scenario 3: forward-path guard in generate_response node ─────────────────
#
# When retrieve_knowledge returns no results and the LLM response omits a
# forward path, the post-processing guard must append one.

@pytest.fixture(autouse=True)
def _mock_embed(monkeypatch):
    async def _fake(_query):
        return [0.1] * 5
    monkeypatch.setattr("backend.knowledge.retrieval._embed_query", _fake)


async def test_forward_path_appended_when_llm_omits_it(monkeypatch):
    """generate_response appends forward-path text when retrieval has no results
    and the LLM response does not offer to connect with an engineer."""
    from backend.conversation.graph.nodes.generate_response import _make_generate_response
    from backend.llm.base import LLMResponse
    from tests.conftest import FakeLLMClient

    # _vector_search returns no chunks → retrieve_knowledge → no_result
    async def _no_chunks(_embedding):
        return []
    monkeypatch.setattr("backend.knowledge.retrieval._vector_search", _no_chunks)

    class _ToolFake(FakeLLMClient):
        async def complete(self, system, messages, tools=None):
            return LLMResponse(
                content=None,
                tool_call={"name": "retrieve_knowledge", "input": {"query": "latency benchmarks"}, "id": "t0"},
            )

        async def stream(self, system, messages, on_token=None):
            return LLMResponse(content="I don't have specific latency figures for that deployment.")

    node = _make_generate_response(_ToolFake(), context_window=10)
    state = {
        "session_id": "fv-test",
        "messages": [{"role": "user", "content": "What latency do your RAG systems achieve?"}],
        "turn_counter": 1,
        "current_stage": 2,  # forward path guard only fires in Stage 2+
    }

    dispatched: list[str] = []

    async def _capture_event(event_name, data, **kwargs):
        if event_name == "token":
            dispatched.append(data["content"])

    with patch("backend.conversation.graph.nodes.generate_response.adispatch_custom_event", side_effect=_capture_event):
        with patch("backend.conversation.graph.nodes.generate_response.generation_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=None)
            mock_span.return_value.__exit__ = MagicMock(return_value=False)
            result = await node(state, config={})

    full_text = result["messages"][-1]["content"]
    assert "engineer" in full_text.lower(), f"Expected forward path in: {full_text!r}"


# ── Scenario 4: proactive case study path end-to-end ─────────────────────────
#
# When the top retrieved chunk is a case study with score ≥ proactive threshold,
# [proactive_case_study: true] is prepended to the tool result the LLM sees.

async def test_proactive_signal_passed_to_llm_when_case_study_top_chunk(monkeypatch):
    """When retrieve_knowledge returns proactive_case_study=True, the formatted
    tool result includes [proactive_case_study: true] at the start."""
    from backend.conversation.graph.nodes.generate_response import _make_generate_response
    from backend.llm.base import LLMResponse
    from tests.conftest import FakeLLMClient

    case_study_chunk = RetrievedChunk(
        chunk_id="cs1",
        content="We helped a healthcare startup deploy a HIPAA-compliant RAG pipeline.",
        score=0.92,
        source="case-study-healthcare",
        chunk_index=0,
    )

    async def _case_study_search(_embedding):
        return [case_study_chunk]

    monkeypatch.setattr("backend.knowledge.retrieval._vector_search", _case_study_search)
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.40)
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_proactive_threshold", 0.50)
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_top_k", 7)

    captured_messages: list[list[dict]] = []

    class _CaptureFake(FakeLLMClient):
        async def complete(self, system, messages, tools=None):
            return LLMResponse(
                content=None,
                tool_call={"name": "retrieve_knowledge", "input": {"query": "case studies"}, "id": "t0"},
            )

        async def stream(self, system, messages, on_token=None):
            captured_messages.append(messages)
            return LLMResponse(content="We have a case study on exactly this.")

    node = _make_generate_response(_CaptureFake(), context_window=10)
    state = {
        "session_id": "fv-proactive",
        "messages": [{"role": "user", "content": "Do you have case studies in healthcare AI?"}],
        "turn_counter": 1,
    }

    with patch("backend.conversation.graph.nodes.generate_response.adispatch_custom_event", new_callable=AsyncMock):
        with patch("backend.conversation.graph.nodes.generate_response.generation_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=None)
            mock_span.return_value.__exit__ = MagicMock(return_value=False)
            await node(state, config={})

    assert captured_messages, "stream() was never called"
    tool_result_msgs = [
        m for msgs in captured_messages for m in msgs if isinstance(m.get("content"), str) and "[proactive_case_study: true]" in m["content"]
    ]
    assert tool_result_msgs, "Expected [proactive_case_study: true] in messages passed to LLM for Pass 2"
