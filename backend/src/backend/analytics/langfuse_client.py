from __future__ import annotations

import os

from telemetry import get_logger
from telemetry import events as tel_events

log = get_logger("analytics")


def _is_configured() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY"))


def initialize_langfuse() -> None:
    """Force singleton initialisation at startup so OTEL resource attributes are read correctly."""
    if not _is_configured():
        return
    try:
        from langfuse import get_client
        get_client()
    except Exception as exc:
        log.warning(tel_events.LANGFUSE_CLIENT_FAILURE, error=str(exc))


def get_callback_handler(session_id: str | None = None):
    """Return a LangGraph-compatible Langfuse CallbackHandler, or None if not configured."""
    if not _is_configured():
        return None
    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler(session_id=session_id)
    except Exception as exc:
        log.warning(tel_events.LANGFUSE_CLIENT_FAILURE, session_id=session_id, error=str(exc))
        return None


def get_langfuse_client():
    """Return the Langfuse singleton client for explicit span instrumentation, or None if not configured."""
    if not _is_configured():
        return None
    try:
        from langfuse import get_client
        return get_client()
    except Exception as exc:
        log.warning(tel_events.LANGFUSE_CLIENT_FAILURE, error=str(exc))
        return None
