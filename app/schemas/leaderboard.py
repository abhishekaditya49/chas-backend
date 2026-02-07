"""Leaderboard and Jashn-e-Chas schemas."""

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class LeaderboardEntry(BaseModel):
    """Single entry in the weekly leaderboard."""

    user: UserResponse
    total_declarations: int
    total_cc_spent: int
    avg_cc_per_declaration: float
    witnessed_received: int
    rank: int
    streak_days: int


class LeaderboardResponse(BaseModel):
    """Weekly leaderboard."""

    week_start: str
    week_end: str
    entries: list[LeaderboardEntry]
    most_restrained: UserResponse | None = None


class JashnCelebration(BaseModel):
    """A celebration message for Jashn-e-Chas."""

    user: UserResponse
    message: str


class JashnResponse(BaseModel):
    """Jashn-e-Chas celebration data."""

    id: str
    community_id: str
    week_start: str
    week_end: str
    honored_user: UserResponse | None = None
    total_declarations: int
    total_cc_spent: int
    celebrations: list[JashnCelebration] = Field(default_factory=list)


class CelebrateRequest(BaseModel):
    """Request body for adding a celebration message."""

    message: str = Field(..., min_length=1)
