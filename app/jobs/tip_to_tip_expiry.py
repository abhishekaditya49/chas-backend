"""Tip-to-tip expiry checker job."""

from __future__ import annotations

import logging

from app.services.notification_service import NotificationService
from app.services.tip_to_tip_service import TipToTipService
from app.utils.supabase_client import get_service_client

logger = logging.getLogger(__name__)


async def tip_to_tip_expiry() -> None:
    """Expire overdue tip-to-tip proposals and emit system events."""
    client = get_service_client()
    tip_service = TipToTipService(client)
    notifications = NotificationService(client)

    expired = tip_service.expire_overdue()
    for proposal in expired:
        proposer = (
            client.table("users")
            .select("display_name")
            .eq("id", str(proposal["proposer_id"]))
            .limit(1)
            .execute()
            .data
        )
        proposer_name = proposer[0]["display_name"] if proposer else "Proposer"
        message = f"Tip-to-Tip '{proposal['title']}' expired - {proposer_name} bears the cost"
        client.table("chat_messages").insert(
            {
                "user_id": str(proposal["proposer_id"]),
                "community_id": str(proposal["community_id"]),
                "type": "system",
                "content": message,
            }
        ).execute()
        notifications.create_notification(
            user_id=str(proposal["proposer_id"]),
            community_id=str(proposal["community_id"]),
            notification_type="system",
            title="Tip-to-Tip expired",
            body=message,
        )

    logger.info("tip_to_tip_expiry completed with %s expired proposals", len(expired))
