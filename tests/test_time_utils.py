"""Time helper tests."""

from __future__ import annotations

from app.utils.time import parse_iso_date


def test_parse_iso_date_with_default() -> None:
    """Missing input should return default value when provided."""
    default = parse_iso_date("2026-02-01")
    assert parse_iso_date(None, default=default) == default


def test_parse_iso_date_valid_input() -> None:
    """ISO date parsing should return exact date."""
    result = parse_iso_date("2026-02-07")
    assert result.isoformat() == "2026-02-07"
