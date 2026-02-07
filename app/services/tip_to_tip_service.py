"""Tip-to-tip proposal and voting logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from postgrest import APIError

from app.services.cc_service import CCService
from app.services.common import SupabaseService
from app.services.ledger_service import LedgerService
from app.services.notification_service import NotificationService
from app.utils.errors import ConflictError, InvalidInputError, NotFoundError
from app.utils.time import now_utc
from supabase import Client


class TipToTipService:
    """Create, vote, resolve, and expire tip-to-tip proposals."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)
        self.cc = CCService(client)
        self.ledger = LedgerService(client)
        self.notifications = NotificationService(client)

    def get_proposal(self, proposal_id: str, community_id: str | None = None) -> dict[str, Any]:
        """Return one tip-to-tip proposal by id."""
        filters = {"id": proposal_id}
        if community_id:
            filters["community_id"] = community_id
        rows = self.db.select_many("tip_to_tip_proposals", filters=filters, limit=1)
        if not rows:
            raise NotFoundError("Tip-to-tip proposal")
        proposal = rows[0]
        proposal["votes"] = self.votes_for_proposal(proposal_id)
        return proposal

    def votes_for_proposal(self, proposal_id: str) -> list[dict[str, Any]]:
        """Return all votes on a proposal."""
        return self.db.select_many(
            "tip_to_tip_votes",
            filters={"proposal_id": proposal_id},
            order_by="created_at",
        )

    def create(
        self,
        proposer_id: str,
        community_id: str,
        title: str,
        description: str,
        stake_amount: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a new active proposal and auto-cast proposer's accept vote."""
        if stake_amount < 50:
            raise InvalidInputError("Tip-to-tip stake must be at least 50 CC")

        self.db.ensure_community_member(proposer_id, community_id)
        balance = self.cc.spend_cc(proposer_id, community_id, stake_amount)

        proposal = self.db.insert_one(
            "tip_to_tip_proposals",
            {
                "proposer_id": proposer_id,
                "community_id": community_id,
                "title": title,
                "description": description,
                "stake_amount": stake_amount,
                "deadline": (now_utc() + timedelta(hours=24)).isoformat(),
                "status": "active",
            },
        )

        self.db.insert_one(
            "tip_to_tip_votes",
            {
                "proposal_id": proposal["id"],
                "user_id": proposer_id,
                "vote": "accept",
            },
        )

        self.ledger.create_entry(
            user_id=proposer_id,
            community_id=community_id,
            entry_type="tip_to_tip",
            amount=-stake_amount,
            description=f"Proposed Tip-to-Tip '{title}'",
            reference_id=str(proposal["id"]),
        )

        members = self.db.select_many("community_members", filters={"community_id": community_id})
        member_ids = sorted(
            {str(row["user_id"]) for row in members if str(row["user_id"]) != proposer_id}
        )
        proposer = self.db.get_user(proposer_id)
        self.notifications.create_bulk(
            user_ids=member_ids,
            community_id=community_id,
            notification_type="tip_to_tip",
            title="New Tip-to-Tip proposal",
            body=f"{proposer['display_name']} proposed '{title}'",
        )

        proposal["votes"] = self.votes_for_proposal(str(proposal["id"]))
        return proposal, balance

    def vote(
        self,
        proposal_id: str,
        community_id: str,
        voter_id: str,
        vote: str,
    ) -> tuple[dict[str, Any], bool, str | None]:
        """Cast a vote and resolve the proposal when all members have voted."""
        proposal = self.get_proposal(proposal_id, community_id=community_id)
        if proposal["status"] != "active":
            raise ConflictError("Proposal is not active", code="PROPOSAL_EXPIRED")

        deadline = str(proposal["deadline"]).replace("Z", "+00:00")
        if now_utc() > datetime.fromisoformat(deadline):
            self.db.update("tip_to_tip_proposals", {"id": proposal_id}, {"status": "expired"})
            raise ConflictError("Proposal deadline passed", code="PROPOSAL_EXPIRED")

        self.db.ensure_community_member(voter_id, community_id)
        existing = self.db.select_many(
            "tip_to_tip_votes",
            filters={"proposal_id": proposal_id, "user_id": voter_id},
            limit=1,
        )
        if existing:
            raise ConflictError("You have already voted", code="ALREADY_VOTED")

        try:
            self.db.insert_one(
                "tip_to_tip_votes",
                {"proposal_id": proposal_id, "user_id": voter_id, "vote": vote},
            )
        except APIError as exc:
            message = str(getattr(exc, "message", ""))
            if "duplicate" in message.lower() or "unique" in message.lower():
                raise ConflictError("You have already voted", code="ALREADY_VOTED") from exc
            raise

        resolved, outcome = self._resolve_if_complete(proposal_id, community_id)
        updated = self.get_proposal(proposal_id, community_id=community_id)
        return updated, resolved, outcome

    def _resolve_if_complete(self, proposal_id: str, community_id: str) -> tuple[bool, str | None]:
        """Check if all members voted, then resolve proposal outcome."""
        proposal = self.get_proposal(proposal_id, community_id=community_id)
        votes = proposal["votes"]
        members = self.db.select_many("community_members", filters={"community_id": community_id})
        total_members = len({str(row["user_id"]) for row in members})

        if len(votes) < total_members:
            return False, None

        declined = any(str(vote_row["vote"]) == "decline" for vote_row in votes)
        if declined:
            self.db.update("tip_to_tip_proposals", {"id": proposal_id}, {"status": "expired"})
            return True, "expired"

        self.db.update("tip_to_tip_proposals", {"id": proposal_id}, {"status": "completed"})
        self.cc.refund_tip_to_tip(
            user_id=str(proposal["proposer_id"]),
            community_id=community_id,
            amount=int(proposal["stake_amount"]),
        )
        self.ledger.create_entry(
            user_id=str(proposal["proposer_id"]),
            community_id=community_id,
            entry_type="tip_to_tip",
            amount=int(proposal["stake_amount"]),
            description=(
                f"Tip-to-Tip '{proposal['title']}' unanimously accepted - stake refunded"
            ),
            reference_id=proposal_id,
        )
        return True, "completed"

    def expire_overdue(self) -> list[dict[str, Any]]:
        """Expire proposals with deadlines in the past and return affected rows."""
        now = now_utc().isoformat()
        overdue = self.db.execute(
            self.db.client.table("tip_to_tip_proposals")
            .select("*")
            .eq("status", "active")
            .lt("deadline", now),
            default=[],
        )
        expired_rows: list[dict[str, Any]] = []
        for proposal in overdue:
            updated = self.db.update(
                "tip_to_tip_proposals",
                {"id": proposal["id"]},
                {"status": "expired"},
            )
            if updated:
                expired_rows.append(updated[0])
        return expired_rows
