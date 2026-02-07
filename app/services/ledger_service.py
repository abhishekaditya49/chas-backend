"""Ledger entry service."""

from __future__ import annotations

from typing import Any

from app.services.common import SupabaseService
from supabase import Client


class LedgerService:
    """Create and query ledger entries."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def create_entry(
        self,
        user_id: str,
        community_id: str,
        entry_type: str,
        amount: int,
        description: str,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a ledger entry row."""
        payload = {
            "user_id": user_id,
            "community_id": community_id,
            "type": entry_type,
            "amount": amount,
            "description": description,
            "reference_id": reference_id,
        }
        return self.db.insert_one("ledger_entries", payload)

    def list_entries(
        self,
        user_id: str,
        community_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return ledger entries with total count for pagination."""
        rows = self.db.select_many(
            "ledger_entries",
            filters={"user_id": user_id, "community_id": community_id},
            order_by="created_at",
            descending=True,
            limit=limit,
            offset=offset,
        )
        total = self.db.count("ledger_entries", {"user_id": user_id, "community_id": community_id})
        return rows, total

    def summary(self, user_id: str, community_id: str) -> dict[str, int]:
        """Return summary stats for the ledger page."""
        declaration_rows = self.db.select_many(
            "ledger_entries",
            filters={"user_id": user_id, "community_id": community_id, "type": "declaration"},
        )
        total_spent_all_time = sum(
            abs(int(row["amount"])) for row in declaration_rows if int(row["amount"]) < 0
        )

        balance = self.db.select_one(
            "cc_balances",
            {"user_id": user_id, "community_id": community_id},
            not_found_label="Balance",
        )
        return {
            "total_spent_all_time": total_spent_all_time,
            "remaining_today": int(balance["remaining"]),
            "spent_today": int(balance["spent_today"]),
        }
