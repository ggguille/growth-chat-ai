from __future__ import annotations

import contextlib
import os
from typing import Any

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

log = get_logger("analytics")


class LangfuseProvider:
    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._host = host

    def initialize(self) -> None:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", self._public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", self._secret_key)
        if self._host:
            os.environ.setdefault("LANGFUSE_HOST", self._host)
        try:
            from langfuse import get_client
            get_client()
        except Exception as exc:
            log.warning(tel_events.LANGFUSE_CLIENT_FAILURE, error=str(exc))

    def flush(self) -> None:
        try:
            from langfuse import get_client
            get_client().flush()
        except Exception:
            pass

    @contextlib.contextmanager
    def request_context(self, session_id: str):
        from langfuse import Langfuse, get_client, propagate_attributes
        lf = get_client()
        trace_id = Langfuse.create_trace_id(seed=session_id)
        with lf.start_as_current_observation(
            as_type="span",
            name="chat_request",
            trace_context={"trace_id": trace_id},
        ):
            with propagate_attributes(session_id=session_id):
                yield

    def get_callback_handler(self) -> Any | None:
        try:
            from langfuse.langchain import CallbackHandler
            return CallbackHandler()
        except Exception as exc:
            log.warning(tel_events.LANGFUSE_CLIENT_FAILURE, error=str(exc))
            return None

    def create_event(self, name: str, payload: dict) -> None:
        try:
            from langfuse import get_client
            get_client().create_event(name=name, input=payload)
        except Exception as exc:
            log.warning(tel_events.ANALYTICS_EMIT_FAILURE, error=sanitize_error(str(exc)))
