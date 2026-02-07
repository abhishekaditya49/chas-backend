"""Leaderboard and Jashn-e-Chas service."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from app.services.common import SupabaseService
from app.utils.errors import NotFoundError
from app.utils.time import last_completed_week_range, this_week_monday
from supabase import Client


class LeaderboardService:
    """Compute weekly rankings and Jashn celebration payloads."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    @staticmethod
    def _range_start_end(week_start: date) -> tuple[datetime, datetime, date]:
        start_dt = datetime.combine(week_start, time.min, tzinfo=UTC)
        end_dt = start_dt + timedelta(days=7)
        week_end = week_start + timedelta(days=6)
        return start_dt, end_dt, week_end

    def _declarations_for_week(self, community_id: str, week_start: date) -> list[dict[str, Any]]:
        start_dt, end_dt, _ = self._range_start_end(week_start)
        return self.db.execute(
            self.db.client.table("declarations")
            .select("*")
            .eq("community_id", community_id)
            .gte("created_at", start_dt.isoformat())
            .lt("created_at", end_dt.isoformat()),
            default=[],
        )

    def leaderboard(self, community_id: str, week_start: date | None = None) -> dict[str, Any]:
        """Return weekly leaderboard payload."""
        week_start_date = week_start or this_week_monday()
        _, _, week_end = self._range_start_end(week_start_date)

        members = self.db.get_community_members_grouped(community_id)
        member_ids = sorted({member["user_id"] for member in members})
        users = self.db.get_users_map(member_ids)
        declarations = self._declarations_for_week(community_id, week_start_date)

        declaration_ids = [str(row["id"]) for row in declarations]
        witness_rows = (
            self.db.execute(
                self.db.client.table("witnesses")
                .select("declaration_id")
                .in_("declaration_id", declaration_ids),
                default=[],
            )
            if declaration_ids
            else []
        )

        witness_count_by_declaration: dict[str, int] = {}
        for witness in witness_rows:
            declaration_id = str(witness["declaration_id"])
            witness_count_by_declaration[declaration_id] = (
                witness_count_by_declaration.get(declaration_id, 0) + 1
            )

        per_user: dict[str, dict[str, Any]] = {
            user_id: {
                "user": users.get(user_id),
                "total_declarations": 0,
                "total_cc_spent": 0,
                "avg_cc_per_declaration": 0.0,
                "witnessed_received": 0,
                "rank": 0,
                "streak_days": 0,
                "_dates": set(),
            }
            for user_id in member_ids
        }

        for declaration in declarations:
            user_id = str(declaration["user_id"])
            if user_id not in per_user:
                continue
            cc_spent = int(declaration["cc_spent"])
            per_user[user_id]["total_declarations"] += 1
            per_user[user_id]["total_cc_spent"] += cc_spent
            per_user[user_id]["witnessed_received"] += witness_count_by_declaration.get(
                str(declaration["id"]), 0
            )
            created = str(declaration["created_at"]).replace("Z", "+00:00")
            per_user[user_id]["_dates"].add(date.fromisoformat(created[:10]))

        entries = list(per_user.values())
        for entry in entries:
            total_declarations = entry["total_declarations"]
            if total_declarations > 0:
                entry["avg_cc_per_declaration"] = round(
                    entry["total_cc_spent"] / total_declarations,
                    2,
                )
            entry["streak_days"] = len(entry["_dates"])
            del entry["_dates"]

        entries.sort(
            key=lambda row: (
                -int(row["total_cc_spent"]),
                -int(row["total_declarations"]),
                str(row["user"]["display_name"] if row.get("user") else ""),
            )
        )
        for index, entry in enumerate(entries, start=1):
            entry["rank"] = index

        most_restrained = None
        if entries:
            restrained = sorted(
                entries,
                key=lambda row: (
                    int(row["total_cc_spent"]),
                    -int(row["total_declarations"]),
                    str(row["user"]["display_name"] if row.get("user") else ""),
                ),
            )[0]
            most_restrained = restrained.get("user")

        return {
            "week_start": week_start_date.isoformat(),
            "week_end": week_end.isoformat(),
            "entries": entries,
            "most_restrained": most_restrained,
        }

    def _ensure_jashn(self, community_id: str, week_start: date) -> dict[str, Any]:
        rows = self.db.select_many(
            "jashn_e_chas",
            filters={"community_id": community_id, "week_start": week_start.isoformat()},
            limit=1,
        )
        if rows:
            return rows[0]

        board = self.leaderboard(community_id=community_id, week_start=week_start)
        entries = board["entries"]
        if entries:
            restrained = min(entries, key=lambda row: int(row["total_cc_spent"]))
            honored_user_id = restrained["user"]["id"] if restrained.get("user") else None
            total_declarations = int(restrained["total_declarations"])
            total_cc_spent = int(restrained["total_cc_spent"])
        else:
            honored_user_id = None
            total_declarations = 0
            total_cc_spent = 0

        return self.db.insert_one(
            "jashn_e_chas",
            {
                "community_id": community_id,
                "week_start": board["week_start"],
                "week_end": board["week_end"],
                "honored_user_id": honored_user_id,
                "total_declarations": total_declarations,
                "total_cc_spent": total_cc_spent,
            },
        )

    def jashn(self, community_id: str, week_start: date | None = None) -> dict[str, Any]:
        """Return Jashn-e-Chas payload for a target week."""
        if week_start is None:
            week_start, _ = last_completed_week_range()

        jashn = self._ensure_jashn(community_id, week_start)
        celebrations = self.db.select_many(
            "jashn_celebrations",
            filters={"jashn_id": str(jashn["id"])},
            order_by="created_at",
        )
        users = self.db.get_users_map([str(row["user_id"]) for row in celebrations])
        celebrations_payload = []
        for celebration in celebrations:
            celebrations_payload.append(
                {
                    "user": users.get(str(celebration["user_id"])),
                    "message": celebration["message"],
                }
            )

        honored_user = (
            self.db.get_user(str(jashn["honored_user_id"]))
            if jashn.get("honored_user_id")
            else None
        )

        return {
            "id": str(jashn["id"]),
            "community_id": str(jashn["community_id"]),
            "week_start": str(jashn["week_start"]),
            "week_end": str(jashn["week_end"]),
            "honored_user": honored_user,
            "total_declarations": int(jashn["total_declarations"]),
            "total_cc_spent": int(jashn["total_cc_spent"]),
            "celebrations": celebrations_payload,
        }

    def celebrate(
        self, community_id: str, jashn_id: str, user_id: str, message: str
    ) -> dict[str, Any]:
        """Create a celebration message for a Jashn record."""
        jashn_rows = self.db.select_many(
            "jashn_e_chas",
            filters={"id": jashn_id, "community_id": community_id},
            limit=1,
        )
        if not jashn_rows:
            raise NotFoundError("Jashn")

        self.db.insert_one(
            "jashn_celebrations",
            {
                "jashn_id": jashn_id,
                "user_id": user_id,
                "message": message,
            },
        )
        user = self.db.get_user(user_id)
        return {"user": user, "message": message}
