"""Tests for AnalyticsProvider protocol implementations and the emit_event bridge."""
import sys
import types
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.analytics.events import AnalyticsEvent, emit_event, embedding_span, generation_span, retriever_span
from backend.analytics.provider import NullProvider


# ── NullProvider ──────────────────────────────────────────────────────────────

def test_null_provider_initialize_does_not_raise():
    NullProvider().initialize()


def test_null_provider_flush_does_not_raise():
    NullProvider().flush()


def test_null_provider_get_callback_handler_returns_none():
    assert NullProvider().get_callback_handler() is None


def test_null_provider_create_event_does_not_raise():
    NullProvider().create_event("test_event", {"key": "value"})


def test_null_provider_create_generation_is_context_manager():
    with NullProvider().create_generation(
        name="test_gen",
        model="test-model",
        input_messages=[{"role": "user", "content": "hi"}],
    ) as gen:
        assert gen is None


def test_null_provider_request_context_is_valid_context_manager():
    with NullProvider().request_context("session-123"):
        pass


# ── LangfuseProvider ─────────────────────────────────────────────────────────

@pytest.fixture
def langfuse_provider():
    from backend.analytics.langfuse_provider import LangfuseProvider
    return LangfuseProvider(public_key="pk-test", secret_key="sk-test", host="")


def test_langfuse_provider_initialize_calls_get_client(langfuse_provider):
    mock_client = MagicMock()
    with patch("langfuse.get_client", return_value=mock_client) as mock_get:
        langfuse_provider.initialize()
    mock_get.assert_called_once()


def test_langfuse_provider_initialize_silences_errors(langfuse_provider):
    with patch("langfuse.get_client", side_effect=RuntimeError("sdk unavailable")):
        langfuse_provider.initialize()  # must not raise


def test_langfuse_provider_flush_calls_client_flush(langfuse_provider):
    mock_client = MagicMock()
    with patch("langfuse.get_client", return_value=mock_client):
        langfuse_provider.flush()
    mock_client.flush.assert_called_once()


def test_langfuse_provider_flush_silences_errors(langfuse_provider):
    with patch("langfuse.get_client", side_effect=RuntimeError("sdk unavailable")):
        langfuse_provider.flush()  # must not raise


def test_langfuse_provider_get_callback_handler_returns_handler(langfuse_provider):
    mock_handler = MagicMock()
    mock_langchain = types.ModuleType("langfuse.langchain")
    mock_langchain.CallbackHandler = MagicMock(return_value=mock_handler)
    with patch.dict(sys.modules, {"langfuse.langchain": mock_langchain}):
        result = langfuse_provider.get_callback_handler()
    assert result is mock_handler


def test_langfuse_provider_get_callback_handler_returns_none_on_error(langfuse_provider):
    mock_langchain = types.ModuleType("langfuse.langchain")
    mock_langchain.CallbackHandler = MagicMock(side_effect=RuntimeError("handler init failed"))
    with patch.dict(sys.modules, {"langfuse.langchain": mock_langchain}):
        result = langfuse_provider.get_callback_handler()
    assert result is None


def test_langfuse_provider_create_event_calls_client(langfuse_provider):
    mock_client = MagicMock()
    with patch("langfuse.get_client", return_value=mock_client):
        langfuse_provider.create_event("my_event", {"key": "val"})
    mock_client.create_event.assert_called_once_with(name="my_event", input={"key": "val"})


def test_langfuse_provider_create_event_silences_errors(langfuse_provider):
    with patch("langfuse.get_client", side_effect=RuntimeError("sdk unavailable")):
        langfuse_provider.create_event("event", {})  # must not raise


def test_langfuse_provider_create_generation_enters_observation(langfuse_provider):
    mock_client = MagicMock()
    mock_gen = MagicMock()
    mock_obs_ctx = MagicMock()
    mock_obs_ctx.__enter__ = MagicMock(return_value=mock_gen)
    mock_obs_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_obs_ctx
    input_msgs = [{"role": "user", "content": "hello"}]
    with patch("langfuse.get_client", return_value=mock_client):
        with langfuse_provider.create_generation(
            name="test_gen",
            model="claude-3-5-haiku",
            input_messages=input_msgs,
            metadata={"session_id": "abc"},
        ) as gen:
            assert gen is mock_gen
            gen.update(output="world", usage_details={"input": 20, "output": 10})
    mock_client.start_as_current_observation.assert_called_once_with(
        as_type="generation",
        name="test_gen",
        model="claude-3-5-haiku",
        input=input_msgs,
        metadata={"session_id": "abc"},
    )
    mock_obs_ctx.__exit__.assert_called_once_with(None, None, None)


def test_langfuse_provider_create_generation_silences_errors(langfuse_provider):
    with patch("langfuse.get_client", side_effect=RuntimeError("sdk unavailable")):
        with langfuse_provider.create_generation(
            name="g", model="m", input_messages=[],
        ) as gen:
            assert gen is None  # must not raise; yields None on setup failure


def test_langfuse_provider_request_context_creates_trace(langfuse_provider):
    mock_client = MagicMock()
    mock_pa_ctx = MagicMock()

    with patch("langfuse.get_client", return_value=mock_client), \
         patch("langfuse.Langfuse") as mock_lf_class, \
         patch("langfuse.propagate_attributes", return_value=mock_pa_ctx):
        mock_lf_class.create_trace_id.return_value = "trace-abc"
        with langfuse_provider.request_context("session-xyz"):
            pass

    mock_lf_class.create_trace_id.assert_called_once_with(seed="session-xyz")
    mock_client.start_as_current_observation.assert_called_once_with(
        as_type="span",
        name="chat_request",
        trace_context={"trace_id": "trace-abc"},
    )


# ── _build_provider factory ───────────────────────────────────────────────────

def test_build_provider_returns_null_provider_when_key_absent(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    from backend.analytics import _build_provider
    assert isinstance(_build_provider(), NullProvider)


def test_build_provider_returns_langfuse_provider_when_key_present(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test-123")
    from backend.analytics import _build_provider
    from backend.analytics.langfuse_provider import LangfuseProvider
    assert isinstance(_build_provider(), LangfuseProvider)


# ── emit_event bridge ─────────────────────────────────────────────────────────

async def test_emit_event_delegates_to_provider(monkeypatch):
    from backend.analytics import analytics_provider
    mock_create = MagicMock()
    monkeypatch.setattr(analytics_provider, "create_event", mock_create)

    event = AnalyticsEvent(name="test_event", timestamp=datetime.now(UTC), payload={"k": "v"})
    await emit_event(event)

    mock_create.assert_called_once_with(name="test_event", payload={"k": "v"})


async def test_emit_event_silences_provider_exceptions(monkeypatch):
    from backend.analytics import analytics_provider
    monkeypatch.setattr(analytics_provider, "create_event", MagicMock(side_effect=RuntimeError("boom")))

    event = AnalyticsEvent(name="test_event", timestamp=datetime.now(UTC), payload={})
    await emit_event(event)  # must not raise


# ── generation_span bridge ────────────────────────────────────────────────────

def test_generation_span_delegates_to_provider(monkeypatch):
    from backend.analytics import analytics_provider
    mock_gen = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_gen)
    mock_cm.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(analytics_provider, "create_generation", MagicMock(return_value=mock_cm))

    with generation_span(name="test_gen", model="m", input_messages=[{"role": "user", "content": "hi"}]) as gen:
        assert gen is mock_gen


# ── NullProvider — new span types ────────────────────────────────────────────

def test_null_provider_create_embedding_span_is_context_manager():
    with NullProvider().create_embedding_span(
        name="embed_query",
        model="text-embedding-3-small",
        input_query="What is Zartis?",
    ) as obs:
        assert obs is None


def test_null_provider_create_retriever_span_is_context_manager():
    with NullProvider().create_retriever_span(
        name="vector_search",
        input_query="What is Zartis?",
    ) as obs:
        assert obs is None


# ── LangfuseProvider — embedding span ────────────────────────────────────────

def test_langfuse_provider_create_embedding_span_enters_generation_observation(langfuse_provider):
    mock_client = MagicMock()
    mock_obs = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_obs)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_ctx

    with patch("langfuse.get_client", return_value=mock_client):
        with langfuse_provider.create_embedding_span(
            name="embed_query",
            model="text-embedding-3-small",
            input_query="What is Zartis?",
            metadata={"session_id": "s1"},
        ) as obs:
            assert obs is mock_obs
            obs.update(output={"vector_dim": 1536})

    mock_client.start_as_current_observation.assert_called_once_with(
        as_type="embedding",
        name="embed_query",
        model="text-embedding-3-small",
        input="What is Zartis?",
        metadata={"session_id": "s1"},
    )
    mock_ctx.__exit__.assert_called_once_with(None, None, None)


def test_langfuse_provider_create_embedding_span_silences_errors(langfuse_provider):
    with patch("langfuse.get_client", side_effect=RuntimeError("sdk unavailable")):
        with langfuse_provider.create_embedding_span(
            name="e", model="m", input_query="q",
        ) as obs:
            assert obs is None


# ── LangfuseProvider — retriever span ────────────────────────────────────────

def test_langfuse_provider_create_retriever_span_enters_span_observation(langfuse_provider):
    mock_client = MagicMock()
    mock_obs = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_obs)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_ctx

    with patch("langfuse.get_client", return_value=mock_client):
        with langfuse_provider.create_retriever_span(
            name="vector_search",
            input_query="What is Zartis?",
            metadata={"threshold": 0.7, "top_k": 7},
        ) as obs:
            assert obs is mock_obs

    mock_client.start_as_current_observation.assert_called_once_with(
        as_type="retriever",
        name="vector_search",
        input="What is Zartis?",
        metadata={"threshold": 0.7, "top_k": 7},
    )
    mock_ctx.__exit__.assert_called_once_with(None, None, None)


def test_langfuse_provider_create_retriever_span_silences_errors(langfuse_provider):
    with patch("langfuse.get_client", side_effect=RuntimeError("sdk unavailable")):
        with langfuse_provider.create_retriever_span(
            name="r", input_query="q",
        ) as obs:
            assert obs is None


# ── events.py — embedding_span and retriever_span bridges ────────────────────

def test_embedding_span_delegates_to_provider(monkeypatch):
    from backend.analytics import analytics_provider
    mock_obs = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_obs)
    mock_cm.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(analytics_provider, "create_embedding_span", MagicMock(return_value=mock_cm))

    with embedding_span(name="embed_query", model="text-embedding-3-small", input_query="hi") as obs:
        assert obs is mock_obs


def test_retriever_span_delegates_to_provider(monkeypatch):
    from backend.analytics import analytics_provider
    mock_obs = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_obs)
    mock_cm.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(analytics_provider, "create_retriever_span", MagicMock(return_value=mock_cm))

    with retriever_span(name="vector_search", input_query="hi", metadata={"top_k": 7}) as obs:
        assert obs is mock_obs
