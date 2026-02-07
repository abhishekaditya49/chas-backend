"""Chamber/chat service orchestration."""

from __future__ import annotations

from typing import Any

from app.services.borrow_service import BorrowService
from app.services.cc_service import CCService
from app.services.common import SupabaseService
from app.services.declaration_service import DeclarationService
from app.services.ledger_service import LedgerService
from app.services.tip_to_tip_service import TipToTipService
from app.utils.errors import InvalidInputError
from supabase import Client


class ChamberService:
    """Handle chamber message flow and side effects."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)
        self.cc = CCService(client)
        self.declarations = DeclarationService(client)
        self.ledger = LedgerService(client)
        self.borrows = BorrowService(client)
        self.tip_to_tip = TipToTipService(client)

    def _enrich_messages(
        self,
        messages: list[dict[str, Any]],
        current_user_id: str,
    ) -> list[dict[str, Any]]:
        if not messages:
            return []

        message_user_ids = {str(message["user_id"]) for message in messages}

        declaration_ids = [
            str(message["reference_id"])
            for message in messages
            if message["type"] == "declaration" and message.get("reference_id")
        ]
        borrow_ids = [
            str(message["reference_id"])
            for message in messages
            if message["type"] == "borrow_request" and message.get("reference_id")
        ]
        tip_ids = [
            str(message["reference_id"])
            for message in messages
            if message["type"] == "tip_to_tip" and message.get("reference_id")
        ]

        declaration_map = (
            {
                str(row["id"]): row
                for row in self.db.execute(
                    self.db.client.table("declarations").select("*").in_("id", declaration_ids),
                    default=[],
                )
            }
            if declaration_ids
            else {}
        )

        borrow_map = (
            {
                str(row["id"]): row
                for row in self.db.execute(
                    self.db.client.table("borrow_requests").select("*").in_("id", borrow_ids),
                    default=[],
                )
            }
            if borrow_ids
            else {}
        )

        tip_map = (
            {
                str(row["id"]): row
                for row in self.db.execute(
                    self.db.client.table("tip_to_tip_proposals").select("*").in_("id", tip_ids),
                    default=[],
                )
            }
            if tip_ids
            else {}
        )

        votes_by_id: dict[str, list[dict[str, Any]]] = {}
        if tip_map:
            votes = self.db.execute(
                self.db.client.table("tip_to_tip_votes")
                .select("*")
                .in_("proposal_id", list(tip_map.keys())),
                default=[],
            )
            for vote in votes:
                proposal_id = str(vote["proposal_id"])
                votes_by_id.setdefault(proposal_id, []).append(vote)

        related_user_ids = set(message_user_ids)
        related_user_ids.update(str(item["user_id"]) for item in declaration_map.values())
        for borrow in borrow_map.values():
            related_user_ids.add(str(borrow["borrower_id"]))
            related_user_ids.add(str(borrow["lender_id"]))
        for proposal in tip_map.values():
            related_user_ids.add(str(proposal["proposer_id"]))
        for votes in votes_by_id.values():
            for vote in votes:
                related_user_ids.add(str(vote["user_id"]))

        user_map = self.db.get_users_map(related_user_ids)

        if declaration_map:
            decl_witnesses = self.db.execute(
                self.db.client.table("witnesses")
                .select("declaration_id,user_id")
                .in_("declaration_id", list(declaration_map.keys())),
                default=[],
            )
            counts: dict[str, int] = {}
            witnessed_by_user: set[str] = set()
            for row in decl_witnesses:
                declaration_id = str(row["declaration_id"])
                counts[declaration_id] = counts.get(declaration_id, 0) + 1
                if str(row["user_id"]) == current_user_id:
                    witnessed_by_user.add(declaration_id)

            for declaration in declaration_map.values():
                declaration_id = str(declaration["id"])
                declaration["witnessed_count"] = counts.get(declaration_id, 0)
                declaration["has_witnessed"] = declaration_id in witnessed_by_user
                declaration["user"] = user_map.get(str(declaration["user_id"]))

        if borrow_map:
            for borrow in borrow_map.values():
                borrow["borrower"] = user_map.get(str(borrow["borrower_id"]))
                borrow["lender"] = user_map.get(str(borrow["lender_id"]))

        if tip_map:
            for proposal_id, proposal in tip_map.items():
                sorted_votes = sorted(
                    votes_by_id.get(proposal_id, []),
                    key=lambda row: str(row.get("created_at", "")),
                )
                proposal["proposer"] = user_map.get(str(proposal["proposer_id"]))
                proposal["votes"] = [
                    {
                        **vote,
                        "user": user_map.get(str(vote["user_id"])),
                    }
                    for vote in sorted_votes
                ]

        payload: list[dict[str, Any]] = []
        for message in messages:
            item = dict(message)
            reference_id = (
                str(message.get("reference_id")) if message.get("reference_id") else None
            )
            item["user"] = user_map.get(str(message["user_id"]))
            item["declaration"] = declaration_map.get(reference_id) if reference_id else None
            item["borrow_request"] = borrow_map.get(reference_id) if reference_id else None
            item["tip_to_tip"] = tip_map.get(reference_id) if reference_id else None
            payload.append(item)
        return payload

    def list_messages(
        self,
        user_id: str,
        community_id: str,
        limit: int = 50,
        before_message_id: str | None = None,
        after_message_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return paginated chamber messages enriched with nested objects."""
        self.db.ensure_community_member(user_id, community_id)
        if before_message_id and after_message_id:
            raise InvalidInputError("Use either before or after, not both")

        query = (
            self.db.client.table("chat_messages")
            .select("*")
            .eq("community_id", community_id)
            .order("created_at", desc=False)
        )
        if before_message_id:
            anchor = self.db.select_one(
                "chat_messages",
                {"id": before_message_id, "community_id": community_id},
                not_found_label="Message",
            )
            query = query.lt("created_at", anchor["created_at"])
        if after_message_id:
            anchor = self.db.select_one(
                "chat_messages",
                {"id": after_message_id, "community_id": community_id},
                not_found_label="Message",
            )
            query = query.gt("created_at", anchor["created_at"])

        rows = self.db.execute(query.limit(limit + 1), default=[])
        has_more = len(rows) > limit
        messages = rows[:limit]
        return self._enrich_messages(messages, current_user_id=user_id), has_more

    def get_message(self, user_id: str, community_id: str, message_id: str) -> dict[str, Any]:
        """Return one message with full nested payload."""
        self.db.ensure_community_member(user_id, community_id)
        message = self.db.select_one(
            "chat_messages",
            {"id": message_id, "community_id": community_id},
            not_found_label="Message",
        )
        enriched = self._enrich_messages([message], current_user_id=user_id)
        return enriched[0]

    def create_text_message(self, user_id: str, community_id: str, content: str) -> dict[str, Any]:
        """Insert a plain text message."""
        self.db.ensure_community_member(user_id, community_id)
        message = self.db.insert_one(
            "chat_messages",
            {
                "user_id": user_id,
                "community_id": community_id,
                "content": content,
                "type": "message",
            },
        )
        return self.get_message(
            user_id=user_id, community_id=community_id, message_id=str(message["id"])
        )

    def create_declaration_message(
        self,
        user_id: str,
        community_id: str,
        title: str,
        description: str,
        cc_spent: int,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Create declaration + chamber message + ledger side effects."""
        self.db.ensure_community_member(user_id, community_id)
        balance = self.cc.spend_cc(user_id, community_id, cc_spent)
        declaration = self.declarations.create_declaration(
            user_id=user_id,
            community_id=community_id,
            title=title,
            description=description,
            cc_spent=cc_spent,
        )

        message = self.db.insert_one(
            "chat_messages",
            {
                "user_id": user_id,
                "community_id": community_id,
                "type": "declaration",
                "reference_id": declaration["id"],
                "content": None,
            },
        )
        self.ledger.create_entry(
            user_id=user_id,
            community_id=community_id,
            entry_type="declaration",
            amount=-cc_spent,
            description=f"Declared joy: {title}",
            reference_id=str(declaration["id"]),
        )

        full_message = self.get_message(
            user_id=user_id, community_id=community_id, message_id=str(message["id"])
        )
        full_declaration = self.declarations.declaration_with_author(
            declaration_id=str(declaration["id"]),
            current_user_id=user_id,
        )
        return full_declaration, full_message, balance

    def create_borrow_message(
        self,
        user_id: str,
        community_id: str,
        lender_id: str,
        amount: int,
        reason: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create borrow request and matching chamber message."""
        borrow = self.borrows.create_request(
            borrower_id=user_id,
            community_id=community_id,
            lender_id=lender_id,
            amount=amount,
            reason=reason,
        )
        message = self.db.insert_one(
            "chat_messages",
            {
                "user_id": user_id,
                "community_id": community_id,
                "type": "borrow_request",
                "reference_id": borrow["id"],
                "content": None,
            },
        )
        full_message = self.get_message(
            user_id=user_id, community_id=community_id, message_id=str(message["id"])
        )
        return borrow, full_message

    def respond_borrow(
        self,
        user_id: str,
        community_id: str,
        request_id: str,
        action: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        """Resolve borrow request and emit a system chamber message."""
        updated, system_content, balance = self.borrows.respond(
            request_id=request_id,
            community_id=community_id,
            actor_id=user_id,
            action=action,
        )
        system_message = self.db.insert_one(
            "chat_messages",
            {
                "user_id": user_id,
                "community_id": community_id,
                "type": "system",
                "content": system_content,
            },
        )
        full_system = self.get_message(
            user_id=user_id, community_id=community_id, message_id=str(system_message["id"])
        )
        return updated, full_system, balance

    def create_tip_to_tip_message(
        self,
        user_id: str,
        community_id: str,
        title: str,
        description: str,
        stake_amount: int,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Create tip-to-tip proposal and matching chamber message."""
        proposal, balance = self.tip_to_tip.create(
            proposer_id=user_id,
            community_id=community_id,
            title=title,
            description=description,
            stake_amount=stake_amount,
        )
        message = self.db.insert_one(
            "chat_messages",
            {
                "user_id": user_id,
                "community_id": community_id,
                "type": "tip_to_tip",
                "reference_id": proposal["id"],
                "content": None,
            },
        )
        full_message = self.get_message(
            user_id=user_id, community_id=community_id, message_id=str(message["id"])
        )
        return proposal, full_message, balance

    def vote_tip_to_tip(
        self,
        user_id: str,
        community_id: str,
        proposal_id: str,
        vote: str,
    ) -> tuple[dict[str, Any], bool, str | None]:
        """Vote on a tip-to-tip proposal and return updated state."""
        self.db.ensure_community_member(user_id, community_id)
        return self.tip_to_tip.vote(
            proposal_id=proposal_id,
            community_id=community_id,
            voter_id=user_id,
            vote=vote,
        )
