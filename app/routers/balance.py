"""Balance endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.cc_service import CCService
from app.services.common import SupabaseService
from supabase import Client

router = APIRouter()


@router.get("")
def get_balance(
    community_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return current user's CC balance for a community."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    balance = CCService(client).get_balance(user_id=user_id, community_id=community_id)
    return {"balance": balance}
