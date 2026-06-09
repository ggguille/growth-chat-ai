import os

from telemetry import get_logger

from .events import AnalyticsEvent  # re-export
from .provider import AnalyticsProvider, NullProvider

_log = get_logger("analytics")


def _build_provider() -> AnalyticsProvider:
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        from .langfuse_provider import LangfuseProvider
        _log.info("analytics_provider_built", provider="LangfuseProvider")
        return LangfuseProvider()
    _log.info("analytics_provider_built", provider="NullProvider")
    return NullProvider()


analytics_provider: AnalyticsProvider = _build_provider()
