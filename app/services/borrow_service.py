"""Borrow request business logic."""

from __future__ import annotations

from typing import Any

from app.services.cc_service import CCService
from app.services.common import SupabaseService
from app.services.ledger_service import LedgerService
from app.services.notification_service import NotificationService
from app.utils.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from supabase import Client


class BorrowService:
    """Create and resolve borrow requests."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)
        self.cc = CCService(client)
        self.ledger = LedgerService(client)
        self.notifications = NotificationService(client)

    def create_request(
        self,
        borrower_id: str,
        community_id: str,
        lender_id: str,
        amount: int,
        reason: str,
    ) -> dict[str, Any]:
        """Create a pending borrow request with basic validation."""
        if borrower_id == lender_id:
            raise InvalidInputError("Borrower and lender cannot be the same user")
        if amount < 1:
            raise InvalidInputError("Amount must be at least 1")

        self.db.ensure_community_member(borrower_id, community_id)
        self.db.ensure_community_member(lender_id, community_id)

        request = self.db.insert_one(
            "borrow_requests",
            {
                "borrower_id": borrower_id,
                "lender_id": lender_id,
                "community_id": community_id,
                "amount": amount,
                "reason": reason,
                "status": "pending",
            },
        )

        borrower = self.db.get_user(borrower_id)
        self.notifications.create_notification(
            user_id=lender_id,
            community_id=community_id,
            notification_type="borrow_request",
            title="New borrow request",
            body=f"{borrower['display_name']} requested {amount} CC",
        )
        return request

    def get_request(self, request_id: str, community_id: str) -> dict[str, Any]:
        """Return one borrow request in a community."""
        rows = self.db.select_many(
            "borrow_requests",
            filters={"id": request_id, "community_id": community_id},
            limit=1,
        )
        if not rows:
            raise NotFoundError("Borrow request")
        return rows[0]

    def respond(
        self,
        request_id: str,
        community_id: str,
        actor_id: str,
        action: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
        """Approve or decline a pending borrow request."""
        request = self.get_request(request_id, community_id)

        if str(request["lender_id"]) != actor_id:
            raise ForbiddenError("Only the lender can respond to this request")
        if request["status"] != "pending":
            raise ConflictError("Borrow request already resolved")

        lender = self.db.get_user(str(request["lender_id"]))
        borrower = self.db.get_user(str(request["borrower_id"]))
        amount = int(request["amount"])

        if action == "approved":
            lender_balance, _ = self.cc.transfer(
                lender_id=str(request["lender_id"]),
                borrower_id=str(request["borrower_id"]),
                community_id=community_id,
                amount=amount,
            )
            updated = self.db.update(
                "borrow_requests",
                {"id": request_id},
                {"status": "approved"},
            )[0]
            self.ledger.create_entry(
                user_id=str(request["lender_id"]),
                community_id=community_id,
                entry_type="borrow_given",
                amount=-amount,
                description=f"Borrowed {amount} CC to {borrower['display_name']}",
                reference_id=request_id,
            )
            self.ledger.create_entry(
                user_id=str(request["borrower_id"]),
                community_id=community_id,
                entry_type="borrow_received",
                amount=amount,
                description=f"Borrowed {amount} CC from {lender['display_name']}",
                reference_id=request_id,
            )
            self.notifications.create_notification(
                user_id=str(request["borrower_id"]),
                community_id=community_id,
                notification_type="borrow_approved",
                title="Borrow request approved",
                body=f"{lender['display_name']} approved your request for {amount} CC",
            )
            message = (
                f"{lender['display_name']} fulfilled "
                f"{borrower['display_name']}'s request for {amount} cc"
            )
            return updated, message, lender_balance

        if action == "declined":
            updated = self.db.update(
                "borrow_requests",
                {"id": request_id},
                {"status": "declined"},
            )[0]
            self.notifications.create_notification(
                user_id=str(request["borrower_id"]),
                community_id=community_id,
                notification_type="borrow_declined",
                title="Borrow request declined",
                body=f"{lender['display_name']} declined your request",
            )
            message = (
                f"{lender['display_name']} declined {borrower['display_name']}'s borrow request"
            )
            return updated, message, None

        raise InvalidInputError("Action must be 'approved' or 'declined'")
