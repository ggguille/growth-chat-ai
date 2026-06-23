import contextlib
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


@contextlib.contextmanager
def generation_span(
    name: str,
    model: str = "unknown",
    input_messages: list[dict] | None = None,
    metadata: dict | None = None,
):
    from backend.analytics import analytics_provider  # late import avoids circular
    with analytics_provider.create_generation(
        name=name,
        model=model,
        input_messages=input_messages or [],
        metadata=metadata,
    ) as gen:
        yield gen


@contextlib.contextmanager
def embedding_span(
    name: str,
    model: str = "unknown",
    input_query: str = "",
    metadata: dict | None = None,
):
    from backend.analytics import analytics_provider  # late import avoids circular
    with analytics_provider.create_embedding_span(
        name=name,
        model=model,
        input_query=input_query,
        metadata=metadata,
    ) as obs:
        yield obs


@contextlib.contextmanager
def retriever_span(
    name: str,
    input_query: str = "",
    metadata: dict | None = None,
):
    from backend.analytics import analytics_provider  # late import avoids circular
    with analytics_provider.create_retriever_span(
        name=name,
        input_query=input_query,
        metadata=metadata,
    ) as obs:
        yield obs
