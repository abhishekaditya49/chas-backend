"""Community and member aggregation service."""

from __future__ import annotations

from typing import Any

from app.services.cc_service import CCService
from app.services.common import SupabaseService, map_users_on_field
from app.services.ledger_service import LedgerService
from app.utils.errors import ConflictError, NotFoundError
from app.utils.time import humanize_relative_time
from supabase import Client


class CommunityService:
    """Community creation, lookup, join, and member listing logic."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)
        self.cc = CCService(client)
        self.ledger = LedgerService(client)

    def list_for_user(
        self, user_id: str
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Return communities and balances for a user dashboard."""
        member_rows = self.db.select_many(
            "community_members",
            filters={"user_id": user_id},
            columns="community_id",
        )
        community_ids = sorted({str(row["community_id"]) for row in member_rows})
        if not community_ids:
            return [], {}

        communities = self.db.execute(
            self.db.client.table("communities").select("*").in_("id", community_ids),
            default=[],
        )

        balances = self.db.execute(
            self.db.client.table("cc_balances")
            .select("*")
            .eq("user_id", user_id)
            .in_("community_id", community_ids),
            default=[],
        )
        balances_map = {str(balance["community_id"]): balance for balance in balances}

        community_members = self.db.execute(
            self.db.client.table("community_members")
            .select("community_id,user_id")
            .in_("community_id", community_ids),
            default=[],
        )
        member_count_by_community: dict[str, int] = {}
        unique_members: dict[str, set[str]] = {}
        for row in community_members:
            community_key = str(row["community_id"])
            user_key = str(row["user_id"])
            unique_members.setdefault(community_key, set()).add(user_key)
        for community_key, user_ids in unique_members.items():
            member_count_by_community[community_key] = len(user_ids)

        recent_limit = min(5000, max(200, len(community_ids) * 40))
        recent_messages = self.db.execute(
            self.db.client.table("chat_messages")
            .select("community_id,created_at")
            .in_("community_id", community_ids)
            .order("created_at", desc=True)
            .limit(recent_limit),
            default=[],
        )
        last_activity_by_community: dict[str, Any] = {}
        for row in recent_messages:
            community_key = str(row["community_id"])
            if community_key not in last_activity_by_community:
                last_activity_by_community[community_key] = row["created_at"]

        for community in communities:
            cid = str(community["id"])
            community["member_count"] = member_count_by_community.get(cid, 0)
            community["last_activity"] = humanize_relative_time(
                last_activity_by_community.get(cid) or community.get("created_at")
            )

        communities.sort(key=lambda item: str(item.get("created_at")), reverse=True)
        return communities, balances_map

    def create(self, user_id: str, name: str, description: str) -> dict[str, Any]:
        """Create a community and seed creator membership/balance."""
        community = self.db.insert_one(
            "communities",
            {
                "name": name,
                "description": description,
                "created_by": user_id,
            },
        )

        community_id = str(community["id"])
        self.db.insert_one(
            "community_members",
            {
                "user_id": user_id,
                "community_id": community_id,
                "role": "moderator",
            },
        )
        self.db.set_community_membership_cache(user_id, community_id, True)

        balance = self.cc.ensure_balance(
            user_id, community_id, daily_budget=int(community["daily_cc_budget"])
        )
        self.ledger.create_entry(
            user_id=user_id,
            community_id=community_id,
            entry_type="daily_reset",
            amount=int(balance["daily_budget"]),
            description="Initial daily CC allocation",
        )
        return community

    def join(self, user_id: str, invite_code: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Join a community by invite code."""
        rows = self.db.execute(
            self.db.client.table("communities")
            .select("*")
            .ilike("invite_code", invite_code.strip().lower())
            .limit(1),
            default=[],
        )
        if not rows:
            raise NotFoundError("Community")

        community = rows[0]
        community_id = str(community["id"])
        existing = self.db.select_many(
            "community_members",
            filters={"user_id": user_id, "community_id": community_id},
            limit=1,
        )
        if existing:
            raise ConflictError("Already a member of this community")

        member = self.db.insert_one(
            "community_members",
            {
                "user_id": user_id,
                "community_id": community_id,
                "role": "member",
            },
        )
        self.db.set_community_membership_cache(user_id, community_id, True)
        balance = self.cc.ensure_balance(
            user_id, community_id, daily_budget=int(community["daily_cc_budget"])
        )
        self.ledger.create_entry(
            user_id=user_id,
            community_id=community_id,
            entry_type="daily_reset",
            amount=int(balance["daily_budget"]),
            description="Community join daily CC allocation",
        )
        return community, member

    def get_with_members(self, community_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Return one community and all members with aggregated roles."""
        community = self.db.select_one(
            "communities", {"id": community_id}, not_found_label="Community"
        )
        members = self.db.get_community_members_grouped(community_id)
        users = self.db.get_users_map([member["user_id"] for member in members])
        return community, map_users_on_field(members, users, user_key="user_id")

    def get_member(self, user_id: str, community_id: str) -> dict[str, Any]:
        """Return one member aggregate row for a user/community."""
        all_members = self.db.get_community_members_grouped(community_id)
        for member in all_members:
            if member["user_id"] == user_id:
                member["user"] = self.db.get_user(user_id)
                return member
        raise NotFoundError("Community member")
