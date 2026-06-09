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
    from backend.analytics import analytics_provider  # late import avoids circular
    try:
        analytics_provider.create_event(name=event.name, payload=event.payload)
    except Exception as exc:
        log.warning(tel_events.ANALYTICS_EMIT_FAILURE, error=sanitize_error(str(exc)))
