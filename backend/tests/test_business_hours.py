"""Unit tests for is_business_hours() and next_business_day_opening().

Reference dates (Europe/Madrid timezone):
  2026-06-08 = Monday   2026-06-12 = Friday
  2026-06-09 = Tuesday  2026-06-13 = Saturday
  2026-06-15 = Monday   2026-06-14 = Sunday
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.handoff.business_hours import is_business_hours, next_business_day_opening

_TZ = ZoneInfo("Europe/Madrid")


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=_TZ)


# ── is_business_hours ─────────────────────────────────────────────────────────

def test_monday_morning_is_business_hours():
    assert is_business_hours(_dt(2026, 6, 8, 10)) is True


def test_saturday_is_not_business_hours():
    assert is_business_hours(_dt(2026, 6, 13, 12)) is False


def test_sunday_is_not_business_hours():
    assert is_business_hours(_dt(2026, 6, 14, 10)) is False


def test_before_open_is_not_business_hours():
    assert is_business_hours(_dt(2026, 6, 8, 8, 59)) is False


def test_after_close_is_not_business_hours():
    # 18:00 is the exclusive upper boundary
    assert is_business_hours(_dt(2026, 6, 8, 18, 0)) is False


def test_at_open_is_business_hours():
    # 09:00 is the inclusive lower boundary
    assert is_business_hours(_dt(2026, 6, 8, 9, 0)) is True


def test_same_day_followup_cuts_off_at_1600():
    # FR-22: 16:00+ with same_day_followup=True → False
    assert is_business_hours(_dt(2026, 6, 8, 16, 30), same_day_followup=True) is False


def test_same_day_followup_before_cutoff():
    assert is_business_hours(_dt(2026, 6, 8, 15, 59), same_day_followup=True) is True


# ── next_business_day_opening ─────────────────────────────────────────────────

def test_next_business_day_from_friday_evening():
    # Friday 19:00 → next Monday 09:00
    result = next_business_day_opening(_dt(2026, 6, 12, 19))
    assert result.date() == _dt(2026, 6, 15, 9).date()
    assert result.hour == 9
    assert result.minute == 0


def test_next_business_day_from_saturday():
    # Saturday 12:00 → next Monday 09:00
    result = next_business_day_opening(_dt(2026, 6, 13, 12))
    assert result.date() == _dt(2026, 6, 15, 9).date()
    assert result.hour == 9


def test_next_business_day_before_open():
    # Monday 07:00 → today (Monday) 09:00
    mon_early = _dt(2026, 6, 8, 7)
    result = next_business_day_opening(mon_early)
    assert result.date() == mon_early.date()
    assert result.hour == 9


def test_next_business_day_after_open():
    # Monday 11:00 → Tuesday 09:00
    result = next_business_day_opening(_dt(2026, 6, 8, 11))
    assert result.date() == _dt(2026, 6, 9, 9).date()
    assert result.hour == 9
