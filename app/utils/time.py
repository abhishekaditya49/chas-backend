"""Time utility helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def now_utc() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(tz=UTC)


def utc_today() -> date:
    """Return current UTC date."""
    return now_utc().date()


def parse_iso_date(value: str | None, default: date | None = None) -> date:
    """Parse an ISO date string with an optional fallback default."""
    if not value:
        if default is None:
            raise ValueError("Missing required date value")
        return default
    return date.fromisoformat(value)


def this_week_monday(base: date | None = None) -> date:
    """Return Monday for the week containing ``base`` (or today)."""
    target = base or utc_today()
    return target - timedelta(days=target.weekday())


def last_completed_week_range(base: date | None = None) -> tuple[date, date]:
    """Return Monday-Sunday range for the most recently completed week."""
    target = base or utc_today()
    current_monday = this_week_monday(target)
    week_end = current_monday - timedelta(days=1)
    week_start = week_end - timedelta(days=6)
    return week_start, week_end


def humanize_relative_time(last_activity: str | datetime | None) -> str:
    """Format a timestamp into compact relative form used by the frontend."""
    if not last_activity:
        return "new"

    if isinstance(last_activity, str):
        normalized = last_activity.replace("Z", "+00:00")
        value = datetime.fromisoformat(normalized)
    else:
        value = last_activity

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    delta = now_utc() - value
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return "now"
    if total_minutes < 60:
        return f"{total_minutes}m"

    total_hours = total_minutes // 60
    if total_hours < 24:
        return f"{total_hours}h"

    total_days = total_hours // 24
    return f"{total_days}d"
