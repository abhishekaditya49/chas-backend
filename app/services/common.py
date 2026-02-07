"""Shared Supabase data access helpers."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from postgrest import APIError

from app.config import settings
from app.utils.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from supabase import Client

ROLE_PRIORITY = {"moderator": 0, "council": 1, "member": 2}
logger = logging.getLogger(__name__)
_membership_cache: dict[tuple[str, str], tuple[float, bool]] = {}
_user_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _cache_get(cache: dict[Any, tuple[float, Any]], key: Any) -> Any | None:
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
) -> None:
    if ttl_seconds <= 0:
        return

    with _cache_lock:
        max_entries = max(100, settings.data_cache_max_entries)
        if len(cache) >= max_entries:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)
        cache[key] = (time.monotonic() + ttl_seconds, value)


class SupabaseService:
    """Thin helper wrapper around a Supabase client."""

    def __init__(self, client: Client) -> None:
        self.client = client

    def execute(self, query, default: Any = None) -> Any:
        """Execute a Supabase query and normalize API errors."""
        started = time.perf_counter()
        try:
            response = query.execute()
            elapsed_ms = (time.perf_counter() - started) * 1000
            threshold_ms = settings.slow_query_log_threshold_ms
            if threshold_ms > 0 and elapsed_ms >= threshold_ms:
                logger.warning("Slow Supabase query %.1fms", elapsed_ms)
            data = response.data
            return default if data is None and default is not None else data
        except APIError as exc:
            message = getattr(exc, "message", "Database request failed")
            raise InvalidInputError(str(message)) from exc

    def select_one(
        self,
        table: str,
        filters: dict[str, Any],
        columns: str = "*",
        not_found_label: str | None = None,
    ) -> dict[str, Any]:
        """Select a single row and raise NotFoundError when missing."""
        query = self.client.table(table).select(columns)
        for key, value in filters.items():
            query = query.eq(key, value)
        rows = self.execute(query.limit(1), default=[])
        if not rows:
            label = not_found_label or table
            raise NotFoundError(label)
        return rows[0]

    def select_many(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        columns: str = "*",
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Select many rows from a table with optional filters and paging."""
        query = self.client.table(table).select(columns)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        if order_by:
            query = query.order(order_by, desc=descending)
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return self.execute(query, default=[])

    def count(self, table: str, filters: dict[str, Any] | None = None) -> int:
        """Count rows in a table with optional equality filters."""
        # Use head-only count so this works for tables without an `id` column
        # (for example, composite-key join tables like `witnesses`).
        query = self.client.table(table).select("*", count="exact", head=True)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        try:
            response = query.execute()
            return response.count or 0
        except APIError as exc:
            message = getattr(exc, "message", "Database request failed")
            raise InvalidInputError(str(message)) from exc

    def insert_one(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one row and return the created object."""
        rows = self.execute(self.client.table(table).insert(payload), default=[])
        if not rows:
            raise InvalidInputError(f"Failed to insert into {table}")
        return rows[0]

    def insert_many(self, table: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert many rows and return inserted rows."""
        if not payloads:
            return []
        return self.execute(self.client.table(table).insert(payloads), default=[])

    def update(
        self,
        table: str,
        filters: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Update rows by equality filters and return the updated rows."""
        query = self.client.table(table).update(payload)
        for key, value in filters.items():
            query = query.eq(key, value)
        return self.execute(query, default=[])

    def delete(self, table: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Delete rows by equality filters and return removed rows."""
        query = self.client.table(table).delete()
        for key, value in filters.items():
            query = query.eq(key, value)
        return self.execute(query, default=[])

    def get_user(self, user_id: str) -> dict[str, Any]:
        """Return a public user record."""
        cache_key = str(user_id)
        cached_user = _cache_get(_user_cache, cache_key)
        if cached_user is not None:
            return dict(cached_user)

        user = self.select_one("users", {"id": user_id}, not_found_label="User")
        _cache_set(_user_cache, cache_key, dict(user), settings.user_cache_ttl_seconds)
        return user

    def get_users_map(self, user_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Fetch multiple users and return an id-keyed mapping."""
        ids = list({str(uid) for uid in user_ids})
        if not ids:
            return {}

        result: dict[str, dict[str, Any]] = {}
        missing_ids: list[str] = []
        for user_id in ids:
            cached_user = _cache_get(_user_cache, user_id)
            if cached_user is None:
                missing_ids.append(user_id)
                continue
            result[user_id] = dict(cached_user)

        if missing_ids:
            rows = self.execute(
                self.client.table("users").select("*").in_("id", missing_ids),
                default=[],
            )
            for row in rows:
                user_key = str(row["id"])
                user_payload = dict(row)
                result[user_key] = user_payload
                _cache_set(_user_cache, user_key, user_payload, settings.user_cache_ttl_seconds)

        return result

    def is_community_member(self, user_id: str, community_id: str) -> bool:
        """Check if a user belongs to a community in any role."""
        membership_key = (str(user_id), str(community_id))
        cached_member = _cache_get(_membership_cache, membership_key)
        if cached_member is not None:
            return bool(cached_member)

        rows = self.execute(
            self.client.table("community_members")
            .select("user_id")
            .eq("user_id", user_id)
            .eq("community_id", community_id)
            .limit(1),
            default=[],
        )
        is_member = bool(rows)
        _cache_set(
            _membership_cache,
            membership_key,
            is_member,
            settings.membership_cache_ttl_seconds,
        )
        return is_member

    def set_community_membership_cache(
        self,
        user_id: str,
        community_id: str,
        is_member: bool,
    ) -> None:
        """Seed or override membership cache for immediate follow-up requests."""
        _cache_set(
            _membership_cache,
            (str(user_id), str(community_id)),
            bool(is_member),
            settings.membership_cache_ttl_seconds,
        )

    def ensure_community_member(self, user_id: str, community_id: str) -> None:
        """Raise ForbiddenError when the user is not in the community."""
        if not self.is_community_member(user_id, community_id):
            raise ForbiddenError("You are not a member of this community")

    def get_roles(self, user_id: str, community_id: str) -> list[str]:
        """Return all roles a user has in a community."""
        rows = self.execute(
            self.client.table("community_members")
            .select("role")
            .eq("user_id", user_id)
            .eq("community_id", community_id),
            default=[],
        )
        roles = [row["role"] for row in rows]
        return sorted(roles, key=lambda value: ROLE_PRIORITY.get(value, 99))

    def ensure_roles(
        self,
        user_id: str,
        community_id: str,
        required: set[str],
        reason: str,
    ) -> None:
        """Ensure user has at least one role in ``required``."""
        roles = set(self.get_roles(user_id, community_id))
        if not roles.intersection(required):
            raise ForbiddenError(reason)

    def get_community_members_grouped(self, community_id: str) -> list[dict[str, Any]]:
        """Return community members grouped by user id with aggregated roles."""
        rows = self.execute(
            self.client.table("community_members")
            .select("user_id,community_id,role,joined_at")
            .eq("community_id", community_id),
            default=[],
        )

        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            user_id = str(row["user_id"])
            current = grouped.get(user_id)
            if not current:
                grouped[user_id] = {
                    "user_id": user_id,
                    "community_id": str(row["community_id"]),
                    "roles": [row["role"]],
                    "joined_at": row["joined_at"],
                }
                continue

            current["roles"].append(row["role"])
            if str(row["joined_at"]) < str(current["joined_at"]):
                current["joined_at"] = row["joined_at"]

        members = list(grouped.values())
        for member in members:
            member["roles"] = sorted(
                member["roles"], key=lambda value: ROLE_PRIORITY.get(value, 99)
            )

        members.sort(key=lambda item: item["joined_at"])
        return members

    def unique_conflict(self, message: str) -> ConflictError:
        """Return a standardized conflict error instance."""
        return ConflictError(message)


def map_users_on_field(
    rows: list[dict[str, Any]],
    users: dict[str, dict[str, Any]],
    user_key: str = "user_id",
    out_key: str = "user",
) -> list[dict[str, Any]]:
    """Attach user records to rows based on ``user_key``."""
    enriched: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload[out_key] = users.get(str(row[user_key]))
        enriched.append(payload)
    return enriched


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    """Group rows by an arbitrary key."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return grouped
