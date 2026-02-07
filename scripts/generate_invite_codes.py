"""Generate random invite codes and insert them into Supabase."""

from __future__ import annotations

import argparse
import secrets
import string
import sys
from collections.abc import Sequence
from pathlib import Path

from postgrest import APIError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ALPHABET = string.ascii_uppercase + string.digits


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Create random invite codes in public.invite_codes.",
    )
    parser.add_argument(
        "count",
        type=int,
        help="How many invite codes to generate.",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=8,
        help="Code length (default: 8).",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default="dawn",
        choices=["dawn", "sunset", "mint", "ink"],
        help="Default welcome theme saved with the code.",
    )
    parser.add_argument(
        "--welcome-title",
        type=str,
        default="Welcome to Chas",
        help="Welcome title stored on each code.",
    )
    parser.add_argument(
        "--welcome-message",
        type=str,
        default=(
            "Your invite has been redeemed. Step into the chamber and declare your first joy."
        ),
        help="Welcome message stored on each code.",
    )
    return parser.parse_args()


def random_code(length: int) -> str:
    """Return an uppercase alphanumeric code."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_unique_violation(exc: APIError) -> bool:
    """Return True when an insert failed due to duplicate code."""
    message = str(getattr(exc, "message", "")).lower()
    code = str(getattr(exc, "code", "")).lower()
    return "duplicate key value" in message or code == "23505"


def create_codes(
    count: int,
    length: int,
    theme: str,
    welcome_title: str,
    welcome_message: str,
) -> list[str]:
    """Insert ``count`` unique invite codes and return them."""
    if count <= 0:
        raise ValueError("count must be >= 1")
    if length < 4:
        raise ValueError("length must be >= 4")

    from app.utils.supabase_client import get_service_client

    client = get_service_client()
    generated: list[str] = []

    for _ in range(count):
        created = False
        for _attempt in range(100):
            code = random_code(length)
            try:
                client.table("invite_codes").insert(
                    {
                        "code": code,
                        "theme": theme,
                        "welcome_title": welcome_title,
                        "welcome_message": welcome_message,
                    }
                ).execute()
                generated.append(code)
                created = True
                break
            except APIError as exc:
                if is_unique_violation(exc):
                    continue
                raise

        if not created:
            raise RuntimeError("Failed to generate a unique invite code after 100 attempts")

    return generated


def print_codes(codes: Sequence[str]) -> None:
    """Print generated codes in copy-friendly form."""
    print(f"Generated {len(codes)} invite code(s):")
    for code in codes:
        print(code)


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    codes = create_codes(
        count=args.count,
        length=args.length,
        theme=args.theme,
        welcome_title=args.welcome_title,
        welcome_message=args.welcome_message,
    )
    print_codes(codes)


if __name__ == "__main__":
    main()
