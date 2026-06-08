import json
import logging
from datetime import UTC, datetime

_STDLIB_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "taskName", "message",
})


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level = "WARN" if record.levelno == logging.WARNING else record.levelname
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        payload: dict = {
            "timestamp": ts,
            "level": level,
            "event": record.msg,
            "session_id": getattr(record, "session_id", None),
            "component": getattr(record, "component", "unknown"),
        }

        for key, val in record.__dict__.items():
            if key not in _STDLIB_ATTRS and key not in payload:
                payload[key] = val

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
