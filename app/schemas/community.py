"""Community and membership schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class CommunityCreate(BaseModel):
    """Request body for creating a community."""

    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field("", max_length=200)


class CommunityResponse(BaseModel):
    """Community representation."""

    id: str
    name: str
    description: str
    invite_code: str
    daily_cc_budget: int
    created_by: str
    created_at: datetime
    member_count: int = 0
    last_activity: str = "new"


class JoinCommunityRequest(BaseModel):
    """Request body for joining via invite code."""

    invite_code: str


class MemberResponse(BaseModel):
    """Community member with aggregated roles."""

    user_id: str
    community_id: str
    roles: list[str]
    joined_at: datetime
    user: UserResponse


class CCBalanceResponse(BaseModel):
    """CC balance for a user in a community."""

    user_id: str
    community_id: str
    daily_budget: int
    spent_today: int
    remaining: int
    last_reset: datetime
    debt: int = 0
