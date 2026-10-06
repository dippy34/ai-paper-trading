"""Time helpers. The competition runs on New York (exchange) time."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001 - no tz database on this machine
    ET = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _us_eastern_offset(dt_utc: datetime) -> timedelta:
    """Fallback DST rule (2nd Sunday of March to 1st Sunday of November, 2am local)."""
    y = dt_utc.year
    march = datetime(y, 3, 8, 7, tzinfo=timezone.utc)  # 2am EST = 7:00 UTC
    dst_start = march + timedelta(days=(6 - march.weekday()) % 7)
    nov = datetime(y, 11, 1, 6, tzinfo=timezone.utc)  # 2am EDT = 6:00 UTC
    dst_end = nov + timedelta(days=(6 - nov.weekday()) % 7)
    return timedelta(hours=-4) if dst_start <= dt_utc < dst_end else timedelta(hours=-5)


def to_et(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    if ET is not None:
        return dt.astimezone(ET)
    return dt.astimezone(timezone(_us_eastern_offset(dt)))


def et_date(dt: datetime) -> date:
    return to_et(dt).date()


def et_close_utc(d: date) -> datetime:
    """4:00 PM New York time (the closing bell) on date d, in UTC."""
    if ET is not None:
        return datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET).astimezone(timezone.utc)
    approx = datetime(d.year, d.month, d.day, 20, 0, tzinfo=timezone.utc)
    return datetime(d.year, d.month, d.day, 16, 0, tzinfo=timezone.utc) - _us_eastern_offset(approx)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def weekdays_between(start: date, end: date) -> int:
    """Count Mon-Fri dates in [start, end]."""
    if end < start:
        return 0
    n = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n
