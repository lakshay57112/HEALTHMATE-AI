from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def tz_for(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or get_settings().default_timezone)
    except Exception:  # noqa: BLE001
        return ZoneInfo(get_settings().default_timezone)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def local_now(tz_name: str | None) -> datetime:
    return now_utc().astimezone(tz_for(tz_name))


def local_today(tz_name: str | None) -> date:
    return local_now(tz_name).date()


def parse_hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def fmt_hhmm(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def shift_hhmm(value: str, minutes: int) -> str:
    base = datetime.combine(date(2000, 1, 1), parse_hhmm(value)) + timedelta(minutes=minutes)
    # Clamp within the same day so a dose never silently moves to another date.
    if base.date() < date(2000, 1, 1):
        return "00:00"
    if base.date() > date(2000, 1, 1):
        return "23:59"
    return fmt_hhmm(base.time())


def local_dt(day: date, hhmm: str, tz_name: str | None) -> datetime:
    """Aware datetime for a local wall-clock time, returned in UTC."""
    return datetime.combine(day, parse_hhmm(hhmm), tzinfo=tz_for(tz_name)).astimezone(timezone.utc)


def minutes_between(a: str, b: str) -> int:
    ta, tb = parse_hhmm(a), parse_hhmm(b)
    return (tb.hour * 60 + tb.minute) - (ta.hour * 60 + ta.minute)


def ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
