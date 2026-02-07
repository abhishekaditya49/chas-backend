"""Ledger schemas."""

from datetime import datetime

from pydantic import BaseModel


class LedgerEntryResponse(BaseModel):
    """A single ledger entry."""

    id: str
    user_id: str
    community_id: str
    type: str
    amount: int
    description: str
    reference_id: str | None = None
    created_at: datetime


class LedgerSummary(BaseModel):
    """Pre-computed ledger summary stats."""

    total_spent_all_time: int = 0
    remaining_today: int = 0
    spent_today: int = 0
