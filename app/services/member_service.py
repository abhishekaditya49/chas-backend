"""Member listing and profile statistics service."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.common import SupabaseService, map_users_on_field
from app.utils.errors import NotFoundError
from supabase import Client


def compute_streaks(dates: list[date]) -> tuple[int, int]:
    """Compute current and longest declaration streaks from unique dates."""
    if not dates:
        return 0, 0

    ordered = sorted(set(dates))
    longest = 1
    current = 1
    for idx in range(1, len(ordered)):
        if (ordered[idx] - ordered[idx - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    # Current streak is based on trailing consecutive dates up to last declaration.
    trailing = 1
    for idx in range(len(ordered) - 1, 0, -1):
        if (ordered[idx] - ordered[idx - 1]).days == 1:
            trailing += 1
        else:
            break

    return trailing, longest


class MemberService:
    """Member directory and profile aggregation logic."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def list_members(self, community_id: str) -> list[dict[str, Any]]:
        """Return members grouped by user with role arrays."""
        members = self.db.get_community_members_grouped(community_id)
        users = self.db.get_users_map([member["user_id"] for member in members])
        return map_users_on_field(members, users, user_key="user_id")

    def profile(self, viewer_id: str, community_id: str, target_user_id: str) -> dict[str, Any]:
        """Compute profile stats for one target member in a community."""
        member_rows = self.db.select_many(
            "community_members",
            filters={"community_id": community_id, "user_id": target_user_id},
        )
        if not member_rows:
            raise NotFoundError("Community member")

        joined_at = min(str(row["joined_at"]) for row in member_rows)
        target_user = self.db.get_user(target_user_id)

        viewer_communities = {
            str(row["community_id"])
            for row in self.db.select_many("community_members", filters={"user_id": viewer_id})
        }
        target_communities = {
            str(row["community_id"])
            for row in self.db.select_many(
                "community_members", filters={"user_id": target_user_id}
            )
        }
        communities_shared = len(viewer_communities.intersection(target_communities))

        declarations = self.db.select_many(
            "declarations",
            filters={"community_id": community_id, "user_id": target_user_id},
            order_by="created_at",
        )
        total_declarations = len(declarations)
        total_cc_spent = sum(int(row["cc_spent"]) for row in declarations)
        avg_cc = float(total_cc_spent / total_declarations) if total_declarations else 0.0
        most_expensive = (
            max(declarations, key=lambda row: int(row["cc_spent"])) if declarations else None
        )

        declaration_dates: list[date] = []
        for declaration in declarations:
            created = str(declaration["created_at"]).replace("Z", "+00:00")
            declaration_dates.append(date.fromisoformat(created[:10]))

        current_streak, longest_streak = compute_streaks(declaration_dates)

        witnessed_given = self.db.count("witnesses", {"user_id": target_user_id})
        declaration_ids = [str(row["id"]) for row in declarations]
        if declaration_ids:
            witness_on_declarations = self.db.execute(
                self.db.client.table("witnesses")
                .select("user_id")
                .in_("declaration_id", declaration_ids),
                default=[],
            )
            witnessed_received = len(witness_on_declarations)
        else:
            witnessed_received = 0

        payload: dict[str, Any] = {
            "user": target_user,
            "communities_shared": communities_shared,
            "total_declarations": total_declarations,
            "total_cc_spent": total_cc_spent,
            "avg_cc_per_declaration": round(avg_cc, 2),
            "most_expensive_declaration": most_expensive,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "witnessed_given": witnessed_given,
            "witnessed_received": witnessed_received,
            "joined_at": joined_at,
        }

        if most_expensive:
            payload["most_expensive_declaration"]["user"] = target_user

        return payload
