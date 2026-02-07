"""FastAPI dependency injection helpers."""

from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import Depends, Header

from app.config import settings
from app.services.common import SupabaseService
from app.utils.errors import InviteRequiredError, UnauthorizedError
from app.utils.supabase_client import get_service_client, get_supabase_client
from supabase import Client

_token_cache: dict[str, tuple[float, Any]] = {}
_whitelist_cache: dict[str, tuple[float, bool]] = {}
_cache_lock = threading.Lock()


def _cache_get(cache: dict[Any, tuple[float, Any]], key: Any) -> Any | None:
    """Return a cache value when present and not expired."""
    now = time.monotonic()
    with _cache_lock:
        entry = cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at <= now:
            cache.pop(key, None)
            return None
        return value


def _cache_set(
    cache: dict[Any, tuple[float, Any]],
    key: Any,
    value: Any,
    ttl_seconds: int,
    max_entries: int,
) -> None:
    """Store a bounded cache value with TTL."""
    if ttl_seconds <= 0:
        return

    with _cache_lock:
        bounded_max_entries = max(1, max_entries)
        if len(cache) >= bounded_max_entries:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)
        cache[key] = (time.monotonic() + ttl_seconds, value)


def get_authenticated_user(authorization: str = Header(None)) -> Any:
    """Extract and validate a Supabase JWT from the Authorization header.

    Raises:
        UnauthorizedError: 401 if the header is missing, malformed, or
            the token cannot be validated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing authorization header")

    token = authorization.split(" ", 1)[1]
    cached_user = _cache_get(_token_cache, token)
    if cached_user is not None:
        return cached_user

    supabase = get_supabase_client()

    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise UnauthorizedError("Invalid token")
        _cache_set(
            _token_cache,
            token,
            response.user,
            settings.auth_token_cache_ttl_seconds,
            settings.auth_token_cache_max_entries,
        )
        return response.user
    except UnauthorizedError:
        raise
    except Exception as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


def get_current_user(user: Any = Depends(get_authenticated_user)) -> Any:
    """Return authenticated + invite-whitelisted user for protected routes."""
    user_id = get_current_user_id(user)
    if not is_user_whitelisted(user_id):
        raise InviteRequiredError()
    return user


def get_current_user_id(user: Any) -> str:
    """Extract a stable user id string from the Supabase user object."""
    return str(user.id)


def get_current_user_email(user: Any) -> str:
    """Extract and normalize the authenticated user's email."""
    raw_email = getattr(user, "email", None)
    if not isinstance(raw_email, str) or not raw_email.strip():
        raise UnauthorizedError("Authenticated user email is required")
    return raw_email.strip().lower()


def is_user_whitelisted(user_id: str, client: Client | None = None) -> bool:
    """Return whether a user has redeemed an invite and can access CHAS."""
    if not settings.enforce_invite_whitelist:
        return True

    cache_key = str(user_id)
    cached = _cache_get(_whitelist_cache, cache_key)
    if cached is not None:
        return bool(cached)

    db_client = client or get_service_client()
    db = SupabaseService(db_client)
    rows = db.execute(
        db.client.table("users").select("is_whitelisted").eq("id", cache_key).limit(1),
        default=[],
    )
    is_whitelisted = bool(rows and rows[0].get("is_whitelisted"))
    _cache_set(
        _whitelist_cache,
        cache_key,
        is_whitelisted,
        settings.whitelist_cache_ttl_seconds,
        settings.data_cache_max_entries,
    )
    return is_whitelisted


def set_user_whitelist_cache(user_id: str, is_whitelisted: bool) -> None:
    """Seed whitelist cache after invite redemption or admin updates."""
    _cache_set(
        _whitelist_cache,
        str(user_id),
        bool(is_whitelisted),
        settings.whitelist_cache_ttl_seconds,
        settings.data_cache_max_entries,
    )


def get_db_client() -> Client:
    """Return the privileged Supabase client used by backend services."""
    return get_service_client()
