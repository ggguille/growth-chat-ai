import os
from dataclasses import dataclass, field
from datetime import datetime

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

log = get_logger("analytics")


@dataclass
class AnalyticsEvent:
    name: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)


async def emit_event(event: AnalyticsEvent) -> None:
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return
    try:
        from langfuse import get_client

        get_client().create_event(
            name=event.name,
            input=event.payload,
        )
    except Exception as exc:
        log.warning(tel_events.ANALYTICS_EMIT_FAILURE, error=sanitize_error(str(exc)))
