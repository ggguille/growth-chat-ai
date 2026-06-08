import contextvars
import logging
import re
import sys
from typing import Any, MutableMapping

from telemetry._formatter import JSONFormatter

_session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_session_id", default=None
)


def set_session_id(session_id: str | None) -> None:
    _session_id_var.set(session_id)


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "session_id"):
            record.session_id = _session_id_var.get()
        if not hasattr(record, "component"):
            record.component = record.name
        return True


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_NAME_RE = re.compile(r"(name\s*[=:]\s*[\"']?)([A-Za-z ]{2,40})([\"']?)", re.IGNORECASE)


def sanitize_error(msg: str) -> str:
    """Strip email and name= PII patterns from external API error strings."""
    msg = _EMAIL_RE.sub("[REDACTED]", msg)
    msg = _NAME_RE.sub(r"\1[REDACTED]\3", msg)
    return msg


class _StructuredAdapter(logging.LoggerAdapter):
    """LoggerAdapter that binds component and accepts per-call kwargs as extra fields."""

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        merged = dict(self.extra)
        merged.update(kwargs.pop("extra", {}) or {})
        kwargs["extra"] = merged
        return msg, kwargs

    def info(self, event: str, **kw: Any) -> None:  # type: ignore[override]
        super().info(event, extra=kw)

    def warn(self, event: str, **kw: Any) -> None:
        super().warning(event, extra=kw)

    def warning(self, event: str, **kw: Any) -> None:  # type: ignore[override]
        super().warning(event, extra=kw)

    def error(self, event: str, **kw: Any) -> None:  # type: ignore[override]
        super().error(event, extra=kw)


def get_logger(component: str) -> _StructuredAdapter:
    """Return a component-bound structured logger.

    Usage::

        log = get_logger("orchestrator")
        log.error(events.LLM_GENERATION_FAILURE, session_id=sid, turn_index=t, error=str(exc))
    """
    logger = logging.getLogger(f"telemetry.{component}")
    return _StructuredAdapter(logger, extra={"component": component})


def configure_logging() -> None:
    """Set up a JSON stdout handler on the root logger.

    Call once at module level in main.py before app = FastAPI(...).
    Routes uvicorn loggers through the same JSON handler to prevent duplicate lines.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(_RequestContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True
