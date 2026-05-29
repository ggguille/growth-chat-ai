from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.config import settings

_FALLBACK_TZ = "Europe/Madrid"


def _tz() -> ZoneInfo:
    tz_name = settings.business_hours_timezone or _FALLBACK_TZ
    return ZoneInfo(tz_name)


def is_business_hours(at: datetime | None = None, same_day_followup: bool = False) -> bool:
    """Mon–Fri 09:00–18:00 in the configured team timezone (default Europe/Madrid).

    When same_day_followup=True, applies an earlier 16:00 cutoff so the system
    never commits to same-day follow-up when the team cannot guarantee it (FR-22).
    """
    local = (at or datetime.now(UTC)).astimezone(_tz())
    if local.weekday() >= 5:
        return False
    if not (time(9, 0) <= local.time() < time(18, 0)):
        return False
    if same_day_followup and local.time() >= time(16, 0):
        return False
    return True


def next_business_day_opening(reference_dt: datetime | None = None) -> datetime:
    """Return the datetime of the next business day opening at 09:00 in the team timezone.

    If called before 09:00 on a weekday, returns today's opening. Otherwise returns
    the next weekday's opening. No public holiday awareness in v1.
    """
    tz = _tz()
    now_team = (reference_dt or datetime.now(UTC)).astimezone(tz)
    candidate = now_team.replace(hour=9, minute=0, second=0, microsecond=0)

    if now_team.weekday() < 5 and now_team < candidate:
        return candidate

    candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)

    return candidate
