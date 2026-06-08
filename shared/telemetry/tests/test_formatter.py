import json
import logging
from datetime import datetime

import pytest

from telemetry import configure_logging, get_logger, sanitize_error
from telemetry import events


def _capture(log_fn, *args, **kwargs) -> dict:
    """Call log_fn and return the parsed JSON from the handler's last record."""
    import io
    from telemetry._formatter import JSONFormatter

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)

    try:
        log_fn(*args, **kwargs)
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)

    return json.loads(buf.getvalue().strip())


def test_mandatory_fields_present():
    log = get_logger("orchestrator")
    data = _capture(log.error, events.LLM_GENERATION_FAILURE, session_id="abc-123", turn_index=1, error="boom")

    assert data["timestamp"]
    assert data["level"] == "ERROR"
    assert data["event"] == events.LLM_GENERATION_FAILURE
    assert data["session_id"] == "abc-123"
    assert data["component"] == "orchestrator"


def test_warning_maps_to_warn():
    log = get_logger("rag")
    data = _capture(log.warn, events.EMBEDDING_API_FAILURE, session_id=None, turn_index=0, error="timeout")
    assert data["level"] == "WARN"


def test_extra_fields_pass_through():
    log = get_logger("orchestrator")
    data = _capture(log.error, events.LLM_GENERATION_FAILURE, session_id="s1", turn_index=3, error="oops")
    assert data["turn_index"] == 3
    assert data["error"] == "oops"


def test_null_session_id_serialized_as_null():
    log = get_logger("rag")
    data = _capture(log.warn, events.VECTOR_SEARCH_FAILURE, session_id=None, error="db gone")
    assert data["session_id"] is None


def test_sanitize_error_redacts_email():
    result = sanitize_error("Error for user@example.com in request")
    assert "user@example.com" not in result
    assert "[REDACTED]" in result


def test_sanitize_error_passthrough_safe_string():
    msg = "connection refused on port 5432"
    assert sanitize_error(msg) == msg


def test_configure_logging_idempotent():
    configure_logging()
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) == 1


def test_json_output_is_valid():
    log = get_logger("api")
    data = _capture(log.info, "health_check", session_id=None)
    assert isinstance(data, dict)


def test_timestamp_is_iso8601():
    log = get_logger("orchestrator")
    data = _capture(log.info, "llm_backend_selected", session_id=None, backend="anthropic")
    ts = data["timestamp"]
    datetime.fromisoformat(ts)  # raises if not valid ISO 8601


def test_component_values_match_trd():
    assert events.COMPONENT_ORCHESTRATOR == "orchestrator"
    assert events.COMPONENT_RAG == "rag"
    assert events.COMPONENT_HANDOFF == "handoff"
    assert events.COMPONENT_API == "api"
    assert events.COMPONENT_BACKUP == "backup"
