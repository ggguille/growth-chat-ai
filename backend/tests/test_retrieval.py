"""Tests for retrieve_knowledge() — exercises every branch including AnalyticsEvent calls.

_embed_query and _vector_search are patched so no database or embedding API is needed.
"""
from unittest.mock import AsyncMock, patch

import pytest

from backend.knowledge.retrieval import RetrievedChunk, retrieve_knowledge


_FAKE_EMBEDDING = [0.1] * 5


def _chunk(score: float = 0.9, source: str = "services") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="abc123",
        content="Zartis builds distributed engineering teams.",
        score=score,
        source=source,
        chunk_index=0,
    )


@pytest.fixture(autouse=True)
def _mock_embed(monkeypatch):
    async def _fake(_query):
        return _FAKE_EMBEDDING

    monkeypatch.setattr("backend.knowledge.retrieval._embed_query", _fake)


@pytest.fixture
def mock_search(monkeypatch):
    """Factory: call mock_search([chunk, ...]) to stub _vector_search for a test."""
    def _setup(chunks):
        async def _fake(_embedding):
            return chunks

        monkeypatch.setattr("backend.knowledge.retrieval._vector_search", _fake)

    return _setup


# ── happy path ────────────────────────────────────────────────────────────────

async def test_ok_status_when_chunks_above_threshold(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    mock_search([_chunk(score=0.9)])
    result = await retrieve_knowledge("What is Zartis?")
    assert result.status == "ok"
    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_id == "abc123"


async def test_rag_retrieved_event_emitted_with_correct_payload(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    mock_search([_chunk(score=0.9)])
    with patch("backend.knowledge.retrieval.emit_event", new_callable=AsyncMock) as mock_emit:
        await retrieve_knowledge("What is Zartis?", turn_index=3)
    mock_emit.assert_called_once()
    event = mock_emit.call_args[0][0]
    assert event.name == "rag_retrieved"
    assert event.payload["chunks_returned"] == 1
    assert event.payload["turn_index"] == 3
    assert "top_score" in event.payload


async def test_proactive_flag_set_for_high_scoring_case_study(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    mock_search([_chunk(score=0.9, source="case-study-fintech")])
    result = await retrieve_knowledge("client story")
    assert result.proactive_case_study is True


async def test_proactive_flag_not_set_for_non_case_study_source(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    mock_search([_chunk(score=0.9, source="services")])
    result = await retrieve_knowledge("services info")
    assert result.proactive_case_study is False


async def test_proactive_flag_not_set_when_score_below_proactive_threshold(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_proactive_threshold", 0.60)
    mock_search([_chunk(score=0.55, source="case-study-fintech")])  # above relevance but below proactive 0.60
    result = await retrieve_knowledge("client story")
    assert result.proactive_case_study is False


async def test_proactive_flag_uses_custom_proactive_threshold(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_proactive_threshold", 0.80)
    # score 0.75: above relevance (0.5) but below custom proactive threshold (0.80)
    mock_search([_chunk(score=0.75, source="case-study-fintech")])
    result = await retrieve_knowledge("client story")
    assert result.proactive_case_study is False


# ── no-result path ────────────────────────────────────────────────────────────

async def test_no_result_when_chunks_below_threshold(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.8)
    mock_search([_chunk(score=0.5)])
    result = await retrieve_knowledge("obscure query")
    assert result.status == "no_result"
    assert result.reason == "below_threshold"


async def test_rag_no_result_event_emitted_with_correct_payload(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.8)
    mock_search([_chunk(score=0.5)])
    with patch("backend.knowledge.retrieval.emit_event", new_callable=AsyncMock) as mock_emit:
        await retrieve_knowledge("obscure query", turn_index=1)
    mock_emit.assert_called_once()
    event = mock_emit.call_args[0][0]
    assert event.name == "rag_no_result"
    assert event.payload["turn_index"] == 1


async def test_no_result_when_search_returns_empty_list(mock_search, monkeypatch):
    monkeypatch.setattr("backend.knowledge.retrieval.settings.rag_relevance_threshold", 0.5)
    mock_search([])
    result = await retrieve_knowledge("anything")
    assert result.status == "no_result"


# ── error paths ───────────────────────────────────────────────────────────────

async def test_error_on_embedding_failure(monkeypatch):
    async def _fail(_query):
        raise RuntimeError("embedding API down")

    monkeypatch.setattr("backend.knowledge.retrieval._embed_query", _fail)
    result = await retrieve_knowledge("test")
    assert result.status == "error"
    assert result.reason == "embedding_failure"


async def test_error_on_search_failure(monkeypatch):
    async def _fail(_embedding):
        raise RuntimeError("db down")

    monkeypatch.setattr("backend.knowledge.retrieval._vector_search", _fail)
    result = await retrieve_knowledge("test")
    assert result.status == "error"
    assert result.reason == "search_failure"
