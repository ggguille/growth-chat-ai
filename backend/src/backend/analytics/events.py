from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AnalyticsEvent:
    name: str
    session_id: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)


async def emit_event(event: AnalyticsEvent) -> None:
    pass  # Phase 3: implement analytics pipeline
