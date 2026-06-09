"""Tests for AnalyticsProvider protocol implementations and the emit_event bridge."""
import sys
import types
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.analytics.events import AnalyticsEvent, emit_event
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


def test_null_provider_request_context_is_valid_context_manager():
    with NullProvider().request_context("session-123"):
        pass


# ── LangfuseProvider ─────────────────────────────────────────────────────────

@pytest.fixture
def langfuse_provider():
    from backend.analytics.langfuse_provider import LangfuseProvider
    return LangfuseProvider()


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
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    from backend.analytics import _build_provider
    assert isinstance(_build_provider(), NullProvider)


def test_build_provider_returns_langfuse_provider_when_key_present(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
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
