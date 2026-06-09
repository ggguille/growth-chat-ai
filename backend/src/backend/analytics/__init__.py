from telemetry import get_logger

from .events import AnalyticsEvent  # re-export
from .provider import AnalyticsProvider, NullProvider

_log = get_logger("analytics")


def _build_provider() -> AnalyticsProvider:
    from backend.config import settings
    if settings.langfuse_public_key:
        from .langfuse_provider import LangfuseProvider
        _log.info("analytics_provider_built", provider="LangfuseProvider")
        return LangfuseProvider(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    _log.info("analytics_provider_built", provider="NullProvider")
    return NullProvider()


analytics_provider: AnalyticsProvider = _build_provider()
