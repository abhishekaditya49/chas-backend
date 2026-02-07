"""Notification endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.services.notification_service import NotificationService
from supabase import Client

router = APIRouter()


@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Return notifications for current user."""
    service = NotificationService(client)
    notifications = service.list_notifications(
        user_id=get_current_user_id(user),
        unread_only=unread_only,
        limit=limit,
    )
    return {"notifications": notifications}


@router.put("/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Mark a single notification as read."""
    service = NotificationService(client)
    notification = service.mark_read(
        user_id=get_current_user_id(user),
        notification_id=notification_id,
    )
    return {"notification": notification}


@router.put("/read-all")
def mark_all_read(
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Mark all notifications as read for current user."""
    service = NotificationService(client)
    count = service.mark_all_read(user_id=get_current_user_id(user))
    return {"count": count}
