"""Election schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.community import MemberResponse


class ElectionCreate(BaseModel):
    """Request body for creating an election."""

    title: str = Field(..., min_length=1)
    ends_at: datetime


class VoteCreate(BaseModel):
    """Request body for casting a vote."""

    candidate_id: str


class ElectionVote(BaseModel):
    """A single vote in an election."""

    election_id: str
    voter_id: str
    candidate_id: str
    created_at: datetime


class ElectionResponse(BaseModel):
    """Election representation."""

    id: str
    community_id: str
    title: str
    candidates: list[MemberResponse] = Field(default_factory=list)
    votes: list[ElectionVote] = Field(default_factory=list)
    status: str
    winner_id: str | None = None
    created_at: datetime
    ends_at: datetime
