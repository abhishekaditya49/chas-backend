"""Member endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.common import SupabaseService
from app.services.member_service import MemberService
from supabase import Client

router = APIRouter()


@router.get("")
def list_members(
    community_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """List community members with aggregated roles."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = MemberService(client)
    members = service.list_members(community_id)
    return {"members": members}


@router.get("/{user_id}")
def get_member_profile(
    community_id: str,
    user_id: str,
    current_user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return detailed member profile stats."""
    viewer_id = get_current_user_id(current_user)
    common = SupabaseService(client)
    common.ensure_community_member(viewer_id, community_id)

    service = MemberService(client)
    profile = service.profile(
        viewer_id=viewer_id,
        community_id=community_id,
        target_user_id=user_id,
    )
    return {"profile": profile}
