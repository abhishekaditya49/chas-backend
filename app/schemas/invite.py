"""Invite code and whitelist schemas."""

from pydantic import BaseModel, Field


class InviteRedeemRequest(BaseModel):
    """Request body for redeeming one invite code."""

    invite_code: str = Field(..., min_length=4, max_length=64)


class InviteRedeemResponse(BaseModel):
    """Result of redeeming an invite code."""

    whitelisted: bool
    already_whitelisted: bool = False
    invite_code: str | None = None
    theme: str = "dawn"
    welcome_title: str
    welcome_message: str


class AccessStatusResponse(BaseModel):
    """Whitelist access status for current user."""

    whitelisted: bool
    whitelist_required: bool
