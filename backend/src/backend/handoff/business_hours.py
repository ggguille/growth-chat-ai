from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Europe/Madrid")


def is_business_hours(at: datetime | None = None) -> bool:
    """Mon–Fri 09:00–18:00 CET/CEST (Europe/Madrid). No public holiday awareness (v1)."""
    local = (at or datetime.now(UTC)).astimezone(_TZ)
    return local.weekday() < 5 and time(9, 0) <= local.time() < time(18, 0)
