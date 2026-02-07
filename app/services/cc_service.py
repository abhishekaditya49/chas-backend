"""CC balance and accounting operations."""

from __future__ import annotations

from typing import Any

from app.services.common import SupabaseService
from app.utils.errors import InsufficientCCError
from app.utils.time import now_utc
from supabase import Client


class CCService:
    """Business logic for Chas Coin balances and debt."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def get_balance(self, user_id: str, community_id: str) -> dict[str, Any]:
        """Return the balance row for a user/community pair."""
        return self.db.select_one(
            "cc_balances",
            {"user_id": user_id, "community_id": community_id},
            not_found_label="Balance",
        )

    def ensure_balance(
        self, user_id: str, community_id: str, daily_budget: int = 100
    ) -> dict[str, Any]:
        """Create a balance row if absent, otherwise return the existing balance."""
        rows = self.db.select_many(
            "cc_balances",
            filters={"user_id": user_id, "community_id": community_id},
            limit=1,
        )
        if rows:
            return rows[0]

        return self.db.insert_one(
            "cc_balances",
            {
                "user_id": user_id,
                "community_id": community_id,
                "daily_budget": daily_budget,
                "spent_today": 0,
                "remaining": daily_budget,
                "debt": 0,
                "last_reset": now_utc().isoformat(),
            },
        )

    def spend_cc(self, user_id: str, community_id: str, amount: int) -> dict[str, Any]:
        """Deduct CC from a user and return updated balance."""
        balance = self.get_balance(user_id, community_id)
        remaining = int(balance["remaining"])
        if remaining < amount:
            raise InsufficientCCError(required=amount, available=remaining)

        spent_today = int(balance["spent_today"]) + amount
        new_remaining = remaining - amount
        rows = self.db.update(
            "cc_balances",
            {"user_id": user_id, "community_id": community_id},
            {"spent_today": spent_today, "remaining": new_remaining},
        )
        return rows[0] if rows else self.get_balance(user_id, community_id)

    def transfer(
        self,
        lender_id: str,
        borrower_id: str,
        community_id: str,
        amount: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Transfer CC from lender to borrower and track debt on borrower."""
        lender = self.get_balance(lender_id, community_id)
        borrower = self.get_balance(borrower_id, community_id)

        lender_remaining = int(lender["remaining"])
        if lender_remaining < amount:
            raise InsufficientCCError(required=amount, available=lender_remaining)

        lender_payload = {
            "remaining": lender_remaining - amount,
            "spent_today": int(lender["spent_today"]) + amount,
        }
        borrower_payload = {
            "remaining": int(borrower["remaining"]) + amount,
            "debt": int(borrower.get("debt", 0)) + amount,
        }

        lender_rows = self.db.update(
            "cc_balances",
            {"user_id": lender_id, "community_id": community_id},
            lender_payload,
        )
        borrower_rows = self.db.update(
            "cc_balances",
            {"user_id": borrower_id, "community_id": community_id},
            borrower_payload,
        )
        return (
            lender_rows[0] if lender_rows else self.get_balance(lender_id, community_id),
            borrower_rows[0] if borrower_rows else self.get_balance(borrower_id, community_id),
        )

    def refund_tip_to_tip(self, user_id: str, community_id: str, amount: int) -> dict[str, Any]:
        """Refund stake amount to proposer after unanimous acceptance."""
        balance = self.get_balance(user_id, community_id)
        payload = {
            "remaining": int(balance["remaining"]) + amount,
            "spent_today": max(0, int(balance["spent_today"]) - amount),
        }
        rows = self.db.update(
            "cc_balances",
            {"user_id": user_id, "community_id": community_id},
            payload,
        )
        return rows[0] if rows else self.get_balance(user_id, community_id)

    def reset_balance_with_debt(self, balance: dict[str, Any]) -> dict[str, Any]:
        """Apply daily reset and automatically repay debt from new allocation."""
        debt = int(balance.get("debt", 0))
        daily_budget = int(balance["daily_budget"])
        if debt > 0:
            repayment = min(daily_budget, debt)
            payload = {
                "debt": debt - repayment,
                "remaining": daily_budget - repayment,
                "spent_today": repayment,
                "last_reset": now_utc().isoformat(),
            }
        else:
            payload = {
                "remaining": daily_budget,
                "spent_today": 0,
                "last_reset": now_utc().isoformat(),
            }

        rows = self.db.update(
            "cc_balances",
            {
                "user_id": str(balance["user_id"]),
                "community_id": str(balance["community_id"]),
            },
            payload,
        )
        return (
            rows[0]
            if rows
            else self.get_balance(str(balance["user_id"]), str(balance["community_id"]))
        )

    def list_balances(self) -> list[dict[str, Any]]:
        """Return all balance rows for scheduled jobs."""
        return self.db.select_many("cc_balances", order_by="community_id")

    def balances_with_remaining(self) -> list[dict[str, Any]]:
        """Return balances where remaining CC is greater than zero."""
        return self.db.execute(
            self.db.client.table("cc_balances").select("*").gt("remaining", 0),
            default=[],
        )
