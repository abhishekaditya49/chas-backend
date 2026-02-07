"""Election creation, voting, and closure logic."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from postgrest import APIError

from app.services.common import SupabaseService
from app.services.notification_service import NotificationService
from app.utils.errors import ConflictError, NotFoundError
from supabase import Client


class ElectionService:
    """Manage moderator election lifecycle."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)
        self.notifications = NotificationService(client)

    def _candidate_members(self, community_id: str) -> list[dict[str, Any]]:
        members = self.db.get_community_members_grouped(community_id)
        users = self.db.get_users_map([member["user_id"] for member in members])
        candidates = [
            member
            for member in members
            if set(member["roles"]).intersection({"council", "moderator"})
        ]
        for candidate in candidates:
            candidate["user"] = users.get(candidate["user_id"])
        return candidates

    def _votes(self, election_id: str) -> list[dict[str, Any]]:
        return self.db.select_many(
            "election_votes",
            filters={"election_id": election_id},
            order_by="created_at",
        )

    def _hydrate_election(self, election: dict[str, Any]) -> dict[str, Any]:
        payload = dict(election)
        payload["candidates"] = self._candidate_members(str(election["community_id"]))
        payload["votes"] = self._votes(str(election["id"]))
        return payload

    def active(self, community_id: str) -> dict[str, Any] | None:
        """Return active election if one exists."""
        rows = self.db.select_many(
            "elections",
            filters={"community_id": community_id, "status": "active"},
            order_by="created_at",
            descending=True,
            limit=1,
        )
        if not rows:
            return None
        return self._hydrate_election(rows[0])

    def create(
        self, actor_id: str, community_id: str, title: str, ends_at: datetime
    ) -> dict[str, Any]:
        """Create a new active election (moderator only)."""
        self.db.ensure_roles(
            user_id=actor_id,
            community_id=community_id,
            required={"moderator"},
            reason="Only moderators can create elections",
        )

        active = self.active(community_id)
        if active:
            raise ConflictError("An active election already exists")

        election = self.db.insert_one(
            "elections",
            {
                "community_id": community_id,
                "title": title,
                "status": "active",
                "ends_at": ends_at.isoformat(),
            },
        )
        return self._hydrate_election(election)

    def vote(
        self,
        actor_id: str,
        community_id: str,
        election_id: str,
        candidate_id: str,
    ) -> dict[str, Any]:
        """Cast one vote in an active election."""
        self.db.ensure_roles(
            user_id=actor_id,
            community_id=community_id,
            required={"council", "moderator"},
            reason="Only council members or moderators can vote",
        )

        election = self.db.select_one(
            "elections",
            {"id": election_id, "community_id": community_id},
            not_found_label="Election",
        )
        if election["status"] != "active":
            raise ConflictError("Election is closed", code="ELECTION_CLOSED")

        candidates = self._candidate_members(community_id)
        candidate_ids = {candidate["user_id"] for candidate in candidates}
        if candidate_id not in candidate_ids:
            raise NotFoundError("Candidate")

        existing_vote = self.db.select_many(
            "election_votes",
            filters={"election_id": election_id, "voter_id": actor_id},
            limit=1,
        )
        if existing_vote:
            raise ConflictError("You have already voted", code="ALREADY_VOTED")

        try:
            self.db.insert_one(
                "election_votes",
                {
                    "election_id": election_id,
                    "voter_id": actor_id,
                    "candidate_id": candidate_id,
                },
            )
        except APIError as exc:
            message = str(getattr(exc, "message", ""))
            if "duplicate" in message.lower() or "unique" in message.lower():
                raise ConflictError("You have already voted", code="ALREADY_VOTED") from exc
            raise

        return self._hydrate_election(election)

    def close(self, actor_id: str, community_id: str, election_id: str) -> dict[str, Any]:
        """Close election, compute winner, and update moderator role."""
        self.db.ensure_roles(
            user_id=actor_id,
            community_id=community_id,
            required={"moderator"},
            reason="Only moderators can close elections",
        )

        election = self.db.select_one(
            "elections",
            {"id": election_id, "community_id": community_id},
            not_found_label="Election",
        )
        if election["status"] != "active":
            return self._hydrate_election(election)

        votes = self._votes(election_id)
        if not votes:
            winner_id = None
        else:
            counts = Counter(str(vote["candidate_id"]) for vote in votes)
            max_votes = max(counts.values())
            tied = [candidate for candidate, total in counts.items() if total == max_votes]
            if len(tied) == 1:
                winner_id = tied[0]
            else:
                first_seen: dict[str, str] = {}
                for vote in votes:
                    candidate = str(vote["candidate_id"])
                    if candidate in tied and candidate not in first_seen:
                        first_seen[candidate] = str(vote["created_at"])
                winner_id = min(first_seen.items(), key=lambda item: item[1])[0]

        updated_rows = self.db.update(
            "elections",
            {"id": election_id},
            {"status": "completed", "winner_id": winner_id},
        )
        updated = updated_rows[0] if updated_rows else election

        if winner_id:
            existing_mod = self.db.select_many(
                "community_members",
                filters={"user_id": winner_id, "community_id": community_id, "role": "moderator"},
                limit=1,
            )
            if not existing_mod:
                self.db.insert_one(
                    "community_members",
                    {
                        "user_id": winner_id,
                        "community_id": community_id,
                        "role": "moderator",
                    },
                )

            winner = self.db.get_user(winner_id)
            announcement = f"Election closed: {winner['display_name']} is now moderator"
            self.db.insert_one(
                "chat_messages",
                {
                    "user_id": actor_id,
                    "community_id": community_id,
                    "type": "system",
                    "content": announcement,
                },
            )

            members = self.db.select_many(
                "community_members", filters={"community_id": community_id}
            )
            member_ids = sorted({str(member["user_id"]) for member in members})
            self.notifications.create_bulk(
                user_ids=member_ids,
                community_id=community_id,
                notification_type="election",
                title="Election result",
                body=announcement,
            )

        return self._hydrate_election(updated)
