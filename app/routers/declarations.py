"""Gazette declaration endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.common import SupabaseService
from app.services.declaration_service import DeclarationService
from app.services.notification_service import NotificationService
from supabase import Client

router = APIRouter()


@router.get("")
def list_declarations(
    community_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return community declarations for gazette page."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = DeclarationService(client)
    declarations, total = service.list_for_gazette(
        community_id=community_id,
        current_user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return {"declarations": declarations, "total": total}


@router.post("/{declaration_id}/witness")
def witness_declaration(
    community_id: str,
    declaration_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Witness a declaration exactly once."""
    user_id = get_current_user_id(user)
    common = SupabaseService(client)
    common.ensure_community_member(user_id, community_id)

    service = DeclarationService(client)
    witness_count = service.witness(user_id=user_id, declaration_id=declaration_id)

    author_id = service.get_author_id(declaration_id)
    if author_id != user_id:
        notifier = NotificationService(client)
        actor = common.get_user(user_id)
        notifier.create_notification(
            user_id=author_id,
            community_id=community_id,
            notification_type="witnessed",
            title="Your declaration was witnessed",
            body=f"{actor['display_name']} bore witness to your declaration.",
        )

    return {"witnessed": True, "witnessed_count": witness_count}
