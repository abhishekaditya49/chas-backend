"""APScheduler setup and job registration."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.jobs.daily_reset import daily_cc_reset
from app.jobs.daily_sunset import daily_sunset
from app.jobs.tip_to_tip_expiry import tip_to_tip_expiry
from app.jobs.weekly_jashn import weekly_jashn

scheduler = AsyncIOScheduler(timezone=settings.timezone)


def register_jobs() -> None:
    """Register all periodic jobs if not already present."""
    if scheduler.get_job("daily_reset") is None:
        scheduler.add_job(
            daily_cc_reset,
            CronTrigger(hour=0, minute=0, timezone=settings.timezone),
            id="daily_reset",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if scheduler.get_job("daily_sunset") is None:
        scheduler.add_job(
            daily_sunset,
            CronTrigger(hour=23, minute=59, timezone=settings.timezone),
            id="daily_sunset",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if scheduler.get_job("weekly_jashn") is None:
        scheduler.add_job(
            weekly_jashn,
            CronTrigger(day_of_week="sun", hour=0, minute=5, timezone=settings.timezone),
            id="weekly_jashn",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if scheduler.get_job("tip_to_tip_expiry") is None:
        scheduler.add_job(
            tip_to_tip_expiry,
            CronTrigger(minute="*/15", timezone=settings.timezone),
            id="tip_to_tip_expiry",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
