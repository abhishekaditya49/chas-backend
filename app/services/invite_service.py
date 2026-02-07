"""Invite code redemption service."""

from __future__ import annotations

from typing import Any

from app.services.common import SupabaseService
from app.utils.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from supabase import Client

DEFAULT_THEME = "dawn"
DEFAULT_WELCOME_TITLE = "Welcome to Chas"
DEFAULT_WELCOME_MESSAGE = (
    "Your invite has been redeemed. Step into the chamber and declare your first joy."
)


class InviteService:
    """Invite code lookup and redemption logic."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def redeem(self, user_id: str, email: str, invite_code: str) -> dict[str, Any]:
        """Redeem one invite code for a user and whitelist their account."""
        normalized_code = invite_code.strip().upper()
        if not normalized_code:
            raise InvalidInputError("Invite code is required")

        response_rows = self.db.execute(
            self.db.client.rpc(
                "redeem_invite_code",
                {
                    "p_user_id": user_id,
                    "p_email": email.strip().lower(),
                    "p_code": normalized_code,
                },
            ),
            default=[],
        )
        if not response_rows:
            raise InvalidInputError("Invite redemption failed")

        payload = response_rows[0]
        success = bool(payload.get("success"))
        reason = str(payload.get("reason") or "")
        if not success:
            self._raise_for_reason(reason)

        return {
            "whitelisted": True,
            "already_whitelisted": reason == "already_whitelisted",
            "invite_code": payload.get("invite_code"),
            "theme": payload.get("theme") or DEFAULT_THEME,
            "welcome_title": payload.get("welcome_title") or DEFAULT_WELCOME_TITLE,
            "welcome_message": payload.get("welcome_message") or DEFAULT_WELCOME_MESSAGE,
        }

    @staticmethod
    def _raise_for_reason(reason: str) -> None:
        if reason == "invalid_code":
            raise InvalidInputError("Invite code is invalid")
        if reason == "user_not_found":
            raise NotFoundError("User")
        if reason == "invite_not_found":
            raise NotFoundError("Invite code")
        if reason in {"invite_not_active", "invite_expired"}:
            raise ConflictError(
                "Invite code has already been redeemed or expired",
                code="INVITE_UNAVAILABLE",
            )
        if reason == "invite_email_mismatch":
            raise ForbiddenError("This invite code is assigned to a different email")
        raise InvalidInputError("Invite redemption failed")
