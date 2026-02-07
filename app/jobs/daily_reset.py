"""Daily CC reset scheduled job."""

from __future__ import annotations

import logging

from app.services.cc_service import CCService
from app.services.ledger_service import LedgerService
from app.utils.supabase_client import get_service_client

logger = logging.getLogger(__name__)


async def daily_cc_reset() -> None:
    """Reset every user's daily balance and apply debt repayments."""
    client = get_service_client()
    cc_service = CCService(client)
    ledger = LedgerService(client)

    balances = cc_service.list_balances()
    for balance in balances:
        updated = cc_service.reset_balance_with_debt(balance)
        credited_amount = int(updated["remaining"])
        ledger.create_entry(
            user_id=str(updated["user_id"]),
            community_id=str(updated["community_id"]),
            entry_type="daily_reset",
            amount=credited_amount,
            description="Daily CC reset",
        )

    logger.info("daily_cc_reset completed for %s balances", len(balances))
