"""Chamber/chat endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user, get_current_user_id, get_db_client
from app.schemas.chamber import (
    BorrowCreate,
    BorrowRespondRequest,
    DeclarationCreate,
    MessageCreate,
    TipToTipCreate,
    TipToTipVoteRequest,
)
from app.services.chamber_service import ChamberService
from supabase import Client

router = APIRouter()


@router.get("/messages")
def list_messages(
    community_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before: str | None = Query(default=None),
    after: str | None = Query(default=None),
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Get paginated chamber messages."""
    service = ChamberService(client)
    messages, has_more = service.list_messages(
        user_id=get_current_user_id(user),
        community_id=community_id,
        limit=limit,
        before_message_id=before,
        after_message_id=after,
    )
    return {"messages": messages, "has_more": has_more}


@router.get("/messages/{message_id}")
def get_message(
    community_id: str,
    message_id: str,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Get one hydrated chamber message by id."""
    service = ChamberService(client)
    message = service.get_message(
        user_id=get_current_user_id(user),
        community_id=community_id,
        message_id=message_id,
    )
    return {"message": message}


@router.post("/messages")
def send_message(
    community_id: str,
    payload: MessageCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Send a text message to chamber."""
    service = ChamberService(client)
    message = service.create_text_message(
        user_id=get_current_user_id(user),
        community_id=community_id,
        content=payload.content,
    )
    return {"message": message}


@router.post("/declare")
def declare_joy(
    community_id: str,
    payload: DeclarationCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Create a joy declaration."""
    service = ChamberService(client)
    declaration, message, balance = service.create_declaration_message(
        user_id=get_current_user_id(user),
        community_id=community_id,
        title=payload.title,
        description=payload.description,
        cc_spent=payload.cc_spent,
    )
    return {"declaration": declaration, "message": message, "balance": balance}


@router.post("/borrow")
def create_borrow(
    community_id: str,
    payload: BorrowCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Create borrow request message."""
    service = ChamberService(client)
    borrow_request, message = service.create_borrow_message(
        user_id=get_current_user_id(user),
        community_id=community_id,
        lender_id=payload.lender_id,
        amount=payload.amount,
        reason=payload.reason,
    )
    return {"borrow_request": borrow_request, "message": message}


@router.post("/borrow/{request_id}/respond")
def respond_borrow(
    community_id: str,
    request_id: str,
    payload: BorrowRespondRequest,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Approve or decline a borrow request."""
    service = ChamberService(client)
    borrow_request, system_message, balance = service.respond_borrow(
        user_id=get_current_user_id(user),
        community_id=community_id,
        request_id=request_id,
        action=payload.action,
    )
    return {
        "borrow_request": borrow_request,
        "system_message": system_message,
        "balance": balance,
    }


@router.post("/tip-to-tip")
def create_tip_to_tip(
    community_id: str,
    payload: TipToTipCreate,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Create a tip-to-tip proposal."""
    service = ChamberService(client)
    proposal, message, balance = service.create_tip_to_tip_message(
        user_id=get_current_user_id(user),
        community_id=community_id,
        title=payload.title,
        description=payload.description,
        stake_amount=payload.stake_amount,
    )
    return {"proposal": proposal, "message": message, "balance": balance}


@router.post("/tip-to-tip/{proposal_id}/vote")
def vote_tip_to_tip(
    community_id: str,
    proposal_id: str,
    payload: TipToTipVoteRequest,
    user: Any = Depends(get_current_user),
    client: Client = Depends(get_db_client),
) -> dict:
    """Vote on an active tip-to-tip proposal."""
    service = ChamberService(client)
    proposal, resolved, outcome = service.vote_tip_to_tip(
        user_id=get_current_user_id(user),
        community_id=community_id,
        proposal_id=proposal_id,
        vote=payload.vote,
    )
    return {"proposal": proposal, "resolved": resolved, "outcome": outcome}
