"""FastAPI dependency injection helpers."""

from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import Header

from app.config import settings
from app.utils.errors import UnauthorizedError
from app.utils.supabase_client import get_service_client, get_supabase_client

_token_cache: dict[str, tuple[float, Any]] = {}
_token_cache_lock = threading.Lock()


def _get_cached_user(token: str) -> Any | None:
    ttl = settings.auth_token_cache_ttl_seconds
    if ttl <= 0:
        return None

    now = time.monotonic()
    with _token_cache_lock:
        cached = _token_cache.get(token)
        if not cached:
            return None

        expires_at, user = cached
        if expires_at <= now:
            _token_cache.pop(token, None)
            return None
        return user


def _cache_user(token: str, user: Any) -> None:
    ttl = settings.auth_token_cache_ttl_seconds
    if ttl <= 0:
        return

    with _token_cache_lock:
        max_entries = max(1, settings.auth_token_cache_max_entries)
        if len(_token_cache) >= max_entries:
            # Drop the oldest inserted entry to bound memory usage.
            oldest_key = next(iter(_token_cache))
            _token_cache.pop(oldest_key, None)
        _token_cache[token] = (time.monotonic() + ttl, user)


def get_current_user(authorization: str = Header(None)) -> Any:
    """Extract and validate a Supabase JWT from the Authorization header.

    Raises:
        UnauthorizedError: 401 if the header is missing, malformed, or
            the token cannot be validated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing authorization header")

    token = authorization.split(" ", 1)[1]
    cached_user = _get_cached_user(token)
    if cached_user is not None:
        return cached_user

    supabase = get_supabase_client()

    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise UnauthorizedError("Invalid token")
        _cache_user(token, response.user)
        return response.user
    except UnauthorizedError:
        raise
    except Exception as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


def get_current_user_id(user: Any) -> str:
    """Extract a stable user id string from the Supabase user object."""
    return str(user.id)


def get_db_client():
    """Return the privileged Supabase client used by backend services."""
    return get_service_client()
