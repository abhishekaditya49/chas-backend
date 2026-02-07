"""Daily sunset scheduled job."""

from __future__ import annotations

import logging

from app.services.cc_service import CCService
from app.services.ledger_service import LedgerService
from app.utils.supabase_client import get_service_client
from app.utils.time import utc_today

logger = logging.getLogger(__name__)


async def daily_sunset() -> None:
    """Record and expire unspent CC at end-of-day."""
    client = get_service_client()
    cc_service = CCService(client)
    ledger = LedgerService(client)

    today = utc_today().isoformat()
    balances = cc_service.balances_with_remaining()
    processed = 0

    for balance in balances:
        user_id = str(balance["user_id"])
        community_id = str(balance["community_id"])
        remaining = int(balance["remaining"])
        if remaining <= 0:
            continue

        existing = (
            client.table("sunset_entries")
            .select("id")
            .eq("user_id", user_id)
            .eq("community_id", community_id)
            .eq("date", today)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            continue

        client.table("sunset_entries").insert(
            {
                "user_id": user_id,
                "community_id": community_id,
                "unspent_cc": remaining,
                "date": today,
            }
        ).execute()
        client.table("cc_balances").update(
            {
                "remaining": 0,
                "spent_today": int(balance["spent_today"]) + remaining,
            }
        ).eq("user_id", user_id).eq("community_id", community_id).execute()

        ledger.create_entry(
            user_id=user_id,
            community_id=community_id,
            entry_type="expired",
            amount=-remaining,
            description="Unspent CC returned to the void",
        )
        processed += 1

    logger.info("daily_sunset completed for %s balances", processed)
