"""Invite service error mapping tests."""

from __future__ import annotations

import pytest

from app.services.invite_service import InviteService
from app.utils.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError


@pytest.mark.parametrize(
    ("reason", "exc_type"),
    [
        ("invalid_code", InvalidInputError),
        ("user_not_found", NotFoundError),
        ("invite_not_found", NotFoundError),
        ("invite_not_active", ConflictError),
        ("invite_expired", ConflictError),
        ("invite_email_mismatch", ForbiddenError),
    ],
)
def test_raise_for_reason_maps_known_errors(reason: str, exc_type: type[Exception]) -> None:
    """Known RPC failure reasons should map to stable API exceptions."""
    with pytest.raises(exc_type):
        InviteService._raise_for_reason(reason)


def test_raise_for_reason_falls_back_to_invalid_input() -> None:
    """Unexpected failure reasons should still produce a client-safe error."""
    with pytest.raises(InvalidInputError):
        InviteService._raise_for_reason("unexpected")
