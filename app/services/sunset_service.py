"""Sunset reporting service."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.common import SupabaseService
from app.utils.time import utc_today
from supabase import Client


class SunsetService:
    """Read sunset entries for community pages."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def list_entries(self, community_id: str, target_date: date | None = None) -> dict[str, Any]:
        """Return sunset entries for a community/date with totals."""
        date_value = target_date or (utc_today() - timedelta(days=1))
        rows = self.db.select_many(
            "sunset_entries",
            filters={"community_id": community_id, "date": date_value.isoformat()},
            order_by="unspent_cc",
            descending=True,
        )
        users = self.db.get_users_map([str(row["user_id"]) for row in rows])

        entries = []
        total = 0
        for row in rows:
            unspent = int(row["unspent_cc"])
            total += unspent
            entries.append(
                {
                    "user": users.get(str(row["user_id"])),
                    "unspent_cc": unspent,
                    "date": str(row["date"]),
                }
            )

        return {
            "entries": entries,
            "date": date_value.isoformat(),
            "total_expired": total,
        }
