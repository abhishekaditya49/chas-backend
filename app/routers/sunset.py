"""Sunset endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.common import SupabaseService
from app.services.sunset_service import SunsetService
from app.utils.time import parse_iso_date
from supabase import Client

router = APIRouter()


@router.get("")
def get_sunset(
    community_id: str,
    date: str | None = Query(default=None),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return sunset rows and total expired for a date."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    target_date = parse_iso_date(date, default=None) if date else None
    service = SunsetService(client)
    return service.list_entries(community_id=community_id, target_date=target_date)
