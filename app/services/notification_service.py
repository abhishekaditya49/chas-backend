"""Notification service."""

from __future__ import annotations

from typing import Any

from app.services.common import SupabaseService
from app.utils.errors import NotFoundError
from supabase import Client


class NotificationService:
    """Create and manage user notifications."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def create_notification(
        self,
        user_id: str,
        community_id: str,
        notification_type: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """Create a notification row."""
        return self.db.insert_one(
            "notifications",
            {
                "user_id": user_id,
                "community_id": community_id,
                "type": notification_type,
                "title": title,
                "body": body,
            },
        )

    def create_bulk(
        self,
        user_ids: list[str],
        community_id: str,
        notification_type: str,
        title: str,
        body: str,
    ) -> list[dict[str, Any]]:
        """Create one notification per user."""
        payloads = [
            {
                "user_id": user_id,
                "community_id": community_id,
                "type": notification_type,
                "title": title,
                "body": body,
            }
            for user_id in user_ids
        ]
        return self.db.insert_many("notifications", payloads)

    def list_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return notifications for a user in reverse chronological order."""
        query = (
            self.db.client.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if unread_only:
            query = query.eq("read", False)
        return self.db.execute(query, default=[])

    def mark_read(self, user_id: str, notification_id: str) -> dict[str, Any]:
        """Mark a single notification as read."""
        rows = self.db.update(
            "notifications",
            {"id": notification_id, "user_id": user_id},
            {"read": True},
        )
        if not rows:
            raise NotFoundError("Notification")
        return rows[0]

    def mark_all_read(self, user_id: str) -> int:
        """Mark all unread notifications as read and return affected count."""
        unread = self.db.execute(
            self.db.client.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("read", False),
            default=[],
        )
        if not unread:
            return 0

        self.db.execute(
            self.db.client.table("notifications")
            .update({"read": True})
            .eq("user_id", user_id)
            .eq("read", False),
            default=[],
        )
        return len(unread)
