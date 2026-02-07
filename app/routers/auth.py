"""Authentication endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.dependencies import (
    get_authenticated_user,
    get_current_user_email,
    get_current_user_id,
    get_db_client,
    is_user_whitelisted,
    set_user_whitelist_cache,
)
from app.schemas.invite import AccessStatusResponse, InviteRedeemRequest, InviteRedeemResponse
from app.services.invite_service import InviteService
from app.utils.supabase_client import get_supabase_client
from supabase import Client

router = APIRouter()


class AuthCallbackRequest(BaseModel):
    """Request body for auth callback endpoint."""

    access_token: str
    refresh_token: str


@router.post("/callback")
def auth_callback(payload: AuthCallbackRequest) -> dict:
    """Validate tokens from frontend callback and return the authenticated user."""
    supabase = get_supabase_client()
    supabase.auth.set_session(payload.access_token, payload.refresh_token)
    user_response = supabase.auth.get_user(payload.access_token)
    return {"user": user_response.user}


@router.get("/session")
def auth_session(user: Any = Depends(get_authenticated_user)) -> dict:
    """Return the currently authenticated user."""
    return {"user": user}


@router.get("/access", response_model=AccessStatusResponse)
def auth_access(
    user: Any = Depends(get_authenticated_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return whitelist access status for invite-gated onboarding."""
    user_id = get_current_user_id(user)
    whitelisted = is_user_whitelisted(user_id, client=client)
    return {
        "whitelisted": whitelisted,
        "whitelist_required": settings.enforce_invite_whitelist,
    }


@router.post("/invite/redeem", response_model=InviteRedeemResponse)
def redeem_invite(
    payload: InviteRedeemRequest,
    user: Any = Depends(get_authenticated_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Redeem one invite code and whitelist the authenticated user."""
    service = InviteService(client)
    result = service.redeem(
        user_id=get_current_user_id(user),
        email=get_current_user_email(user),
        invite_code=payload.invite_code,
    )
    set_user_whitelist_cache(get_current_user_id(user), bool(result.get("whitelisted")))
    return result


@router.post("/signout")
def auth_signout() -> dict:
    """Return success for stateless sign-out handling."""
    return {"success": True}
