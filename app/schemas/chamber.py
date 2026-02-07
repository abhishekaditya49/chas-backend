"""Chamber (chat) related schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class MessageCreate(BaseModel):
    """Request body for sending a chat message."""

    content: str = Field(..., min_length=1)


class DeclarationCreate(BaseModel):
    """Request body for creating a declaration."""

    title: str = Field(..., min_length=1)
    description: str = ""
    cc_spent: int = Field(..., ge=1, le=20)


class DeclarationResponse(BaseModel):
    """Declaration representation."""

    id: str
    user_id: str
    community_id: str
    title: str
    description: str
    cc_spent: int
    image_url: str | None = None
    witnessed_count: int = 0
    has_witnessed: bool = False
    created_at: datetime
    user: UserResponse | None = None


class BorrowCreate(BaseModel):
    """Request body for creating a borrow request."""

    lender_id: str
    amount: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1)


class BorrowRespondRequest(BaseModel):
    """Request body for responding to a borrow request."""

    action: str = Field(..., pattern="^(approved|declined)$")


class BorrowRequestResponse(BaseModel):
    """Borrow request representation."""

    id: str
    borrower_id: str
    lender_id: str
    community_id: str
    amount: int
    reason: str
    status: str
    created_at: datetime


class TipToTipCreate(BaseModel):
    """Request body for creating a tip-to-tip proposal."""

    title: str = Field(..., min_length=1)
    description: str = ""
    stake_amount: int = Field(..., ge=50)


class TipToTipVoteRequest(BaseModel):
    """Request body for voting on a tip-to-tip proposal."""

    vote: str = Field(..., pattern="^(accept|decline)$")


class TipToTipResponse(BaseModel):
    """Tip-to-tip proposal representation."""

    id: str
    proposer_id: str
    community_id: str
    title: str
    description: str
    stake_amount: int
    deadline: datetime
    status: str
    votes: list[dict] = Field(default_factory=list)
    created_at: datetime


class ChatMessageResponse(BaseModel):
    """Chat message with embedded references."""

    id: str
    user_id: str
    community_id: str
    content: str | None = None
    type: str
    declaration: DeclarationResponse | None = None
    borrow_request: BorrowRequestResponse | None = None
    tip_to_tip: TipToTipResponse | None = None
    created_at: datetime
    user: UserResponse | None = None
