"""Weekly Jashn-e-Chas scheduled job."""

from __future__ import annotations

import logging

from app.services.leaderboard_service import LeaderboardService
from app.services.notification_service import NotificationService
from app.utils.supabase_client import get_service_client
from app.utils.time import last_completed_week_range

logger = logging.getLogger(__name__)


async def weekly_jashn() -> None:
    """Compute Jashn entries for each community and notify honorees."""
    client = get_service_client()
    leaderboard = LeaderboardService(client)
    notifications = NotificationService(client)

    communities = client.table("communities").select("id,name").execute().data or []
    week_start, _ = last_completed_week_range()

    processed = 0
    for community in communities:
        jashn = leaderboard.jashn(str(community["id"]), week_start=week_start)
        honored_user = jashn.get("honored_user")
        if honored_user:
            notifications.create_notification(
                user_id=str(honored_user["id"]),
                community_id=str(community["id"]),
                notification_type="jashn_e_chas",
                title="Jashn-e-Chas",
                body="You were honored for joyful restraint this week.",
            )
        processed += 1

    logger.info("weekly_jashn completed for %s communities", processed)
