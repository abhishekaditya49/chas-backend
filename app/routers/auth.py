"""Authentication endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.utils.supabase_client import get_supabase_client

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
def auth_session(user: Any = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user."""
    return {"user": user}


@router.post("/signout")
def auth_signout() -> dict:
    """Return success for stateless sign-out handling."""
    return {"success": True}
