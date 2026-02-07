"""User-related schemas."""

from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Public user representation."""

    id: str
    email: str
    display_name: str
    avatar_url: str | None = None
    created_at: datetime
