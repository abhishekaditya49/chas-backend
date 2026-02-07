"""Ledger endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.common import SupabaseService
from app.services.ledger_service import LedgerService
from supabase import Client

router = APIRouter()


@router.get("")
def get_ledger(
    community_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return current user's ledger entries and summary."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = LedgerService(client)
    entries, total = service.list_entries(
        user_id=user_id, community_id=community_id, limit=limit, offset=offset
    )
    summary = service.summary(user_id=user_id, community_id=community_id)
    return {"entries": entries, "total": total, "summary": summary}
