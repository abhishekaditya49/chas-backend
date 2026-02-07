"""Service package exports with lazy loading."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "BorrowService": "app.services.borrow_service",
    "CCService": "app.services.cc_service",
    "ChamberService": "app.services.chamber_service",
    "CommunityService": "app.services.community_service",
    "DeclarationService": "app.services.declaration_service",
    "ElectionService": "app.services.election_service",
    "InviteService": "app.services.invite_service",
    "LeaderboardService": "app.services.leaderboard_service",
    "LedgerService": "app.services.ledger_service",
    "MemberService": "app.services.member_service",
    "NotificationService": "app.services.notification_service",
    "SunsetService": "app.services.sunset_service",
    "SupabaseService": "app.services.common",
    "TipToTipService": "app.services.tip_to_tip_service",
}

__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    return getattr(module, name)
