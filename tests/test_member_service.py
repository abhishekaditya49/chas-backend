"""Member service utility tests."""

from __future__ import annotations

from datetime import date

from app.services.member_service import compute_streaks


def test_compute_streaks_empty() -> None:
    """Empty history should produce zero streaks."""
    assert compute_streaks([]) == (0, 0)


def test_compute_streaks_consecutive_and_gap() -> None:
    """Current and longest streaks should be calculated from sorted unique dates."""
    dates = [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
    ]
    current, longest = compute_streaks(dates)
    assert current == 3
    assert longest == 3
