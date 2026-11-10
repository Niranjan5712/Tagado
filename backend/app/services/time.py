from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def today_ist(now: datetime | None = None) -> date:
    current = now or now_utc()
    return current.astimezone(IST).date()


def format_today_ist(now: datetime | None = None) -> str:
    return today_ist(now).isoformat()


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite often returns naive datetimes; treat naive values as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def combine_ist_date_time(day: date, hour: int, minute: int) -> datetime:
    return datetime(
        day.year,
        day.month,
        day.day,
        hour,
        minute,
        tzinfo=IST,
    )


def is_sunday(day: date) -> bool:
    return day.weekday() == 6


def next_non_sunday(day: date) -> date:
    while is_sunday(day):
        day += timedelta(days=1)
    return day


def shift_sunday_to_monday(day: date) -> date:
    if is_sunday(day):
        return day + timedelta(days=1)
    return day


def is_within_send_window_ist(dt_ist: datetime) -> bool:
    if dt_ist.weekday() == 6:
        return False
    minutes = dt_ist.hour * 60 + dt_ist.minute
    return 9 * 60 <= minutes <= 19 * 60


def next_valid_send_slot(
    from_utc: datetime,
    *,
    hour_ist: int,
    minute_ist: int,
) -> datetime:
    """Next Mon–Sat slot at workspace send time, not before from_utc, within 09:00–19:00 IST."""
    cursor = from_utc.astimezone(IST)
    day = cursor.date()

    for _ in range(14):
        day = next_non_sunday(day)
        candidate_ist = combine_ist_date_time(day, hour_ist, minute_ist)
        if not is_within_send_window_ist(candidate_ist):
            # Workspace defaults are 10:30; if misconfigured, clamp into window.
            clamped_hour = min(max(hour_ist, 9), 19)
            candidate_ist = combine_ist_date_time(day, clamped_hour, minute_ist if clamped_hour < 19 else 0)
        if candidate_ist >= cursor and is_within_send_window_ist(candidate_ist):
            return to_utc(candidate_ist)
        day += timedelta(days=1)

    raise RuntimeError("Unable to find a valid send slot")


def send_at_for_date(
    send_on: date,
    *,
    hour_ist: int,
    minute_ist: int,
) -> tuple[datetime, date | None]:
    """Return UTC send_at and the shifted calendar date if Sunday moved to Monday."""
    shifted = shift_sunday_to_monday(send_on)
    shifted_from = None if shifted == send_on else shifted
    send_at = to_utc(combine_ist_date_time(shifted, hour_ist, minute_ist))
    return send_at, shifted_from
