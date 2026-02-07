"""Notification schemas."""

from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Notification representation."""

    id: str
    user_id: str
    community_id: str
    type: str
    title: str
    body: str
    read: bool
    created_at: datetime
