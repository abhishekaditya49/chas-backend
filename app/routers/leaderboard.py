"""Leaderboard and Jashn endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.common import SupabaseService
from app.services.leaderboard_service import LeaderboardService
from app.utils.time import parse_iso_date
from supabase import Client

router = APIRouter()


class CelebrateRequest(BaseModel):
    """Request body for Jashn celebration messages."""

    message: str = Field(..., min_length=1)


@router.get("/leaderboard")
def get_leaderboard(
    community_id: str,
    week_start: str | None = Query(default=None),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return weekly leaderboard for community."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = LeaderboardService(client)
    week_start_date = parse_iso_date(week_start) if week_start else None
    leaderboard = service.leaderboard(community_id=community_id, week_start=week_start_date)
    return {"leaderboard": leaderboard}


@router.get("/jashn")
def get_jashn(
    community_id: str,
    week_start: str | None = Query(default=None),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return Jashn-e-Chas payload for week."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = LeaderboardService(client)
    week_start_date = parse_iso_date(week_start) if week_start else None
    jashn = service.jashn(community_id=community_id, week_start=week_start_date)
    return {"jashn": jashn}


@router.post("/jashn/{jashn_id}/celebrate")
def celebrate_jashn(
    community_id: str,
    jashn_id: str,
    payload: CelebrateRequest,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Add a celebration message for honored user."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = LeaderboardService(client)
    celebration = service.celebrate(
        community_id=community_id,
        jashn_id=jashn_id,
        user_id=user_id,
        message=payload.message,
    )
    return {"celebration": celebration}
