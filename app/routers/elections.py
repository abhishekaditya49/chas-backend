"""Election endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.schemas.election import ElectionCreate, VoteCreate
from app.services.common import SupabaseService
from app.services.election_service import ElectionService
from supabase import Client

router = APIRouter()


@router.get("/active")
def get_active_election(
    community_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return active election for community if present."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = ElectionService(client)
    election = service.active(community_id)
    return {"election": election}


@router.post("")
def create_election(
    community_id: str,
    payload: ElectionCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Create a new election."""
    service = ElectionService(client)
    election = service.create(
        actor_id=get_current_user_id(user),
        community_id=community_id,
        title=payload.title,
        ends_at=payload.ends_at,
    )
    return {"election": election}


@router.post("/{election_id}/vote")
def vote_election(
    community_id: str,
    election_id: str,
    payload: VoteCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Cast election vote."""
    service = ElectionService(client)
    election = service.vote(
        actor_id=get_current_user_id(user),
        community_id=community_id,
        election_id=election_id,
        candidate_id=payload.candidate_id,
    )
    return {"election": election}


@router.post("/{election_id}/close")
def close_election(
    community_id: str,
    election_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Close an election and assign winner as moderator."""
    service = ElectionService(client)
    election = service.close(
        actor_id=get_current_user_id(user),
        community_id=community_id,
        election_id=election_id,
    )
    return {"election": election}
