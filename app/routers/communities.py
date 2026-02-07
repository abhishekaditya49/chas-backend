"""Community endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.schemas.community import CommunityCreate, JoinCommunityRequest
from app.services.community_service import CommunityService
from supabase import Client

router = APIRouter()


@router.get("")
def list_communities(
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """List communities and balances for current user."""
    service = CommunityService(client)
    communities, balances = service.list_for_user(get_current_user_id(user))
    return {"communities": communities, "balances": balances}


@router.post("")
def create_community(
    payload: CommunityCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Create a new community."""
    service = CommunityService(client)
    community = service.create(
        user_id=get_current_user_id(user),
        name=payload.name,
        description=payload.description,
    )
    return {"community": community}


@router.post("/join")
def join_community(
    payload: JoinCommunityRequest,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Join an existing community using invite code."""
    service = CommunityService(client)
    community, member = service.join(
        user_id=get_current_user_id(user),
        invite_code=payload.invite_code,
    )
    return {"community": community, "member": member}


@router.get("/{community_id}")
def get_community(
    community_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return community details with aggregated members."""
    service = CommunityService(client)
    # Permission check: caller must be a member.
    service.db.ensure_community_member(get_current_user_id(user), community_id)
    community, members = service.get_with_members(community_id)
    return {"community": community, "members": members}
