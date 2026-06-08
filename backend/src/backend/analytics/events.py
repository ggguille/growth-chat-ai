import os
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AnalyticsEvent:
    name: str
    session_id: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)


async def emit_event(event: AnalyticsEvent) -> None:
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return
    try:
        from langfuse import get_client

        langfuse = get_client()
        with langfuse.start_as_current_span(
            name=event.name,
            input=event.payload,
            start_time=event.timestamp,
        ):
            langfuse.update_current_trace(session_id=event.session_id)
    except Exception:
        pass
