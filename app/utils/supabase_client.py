"""Supabase client singletons (anon + service-role)."""

from functools import lru_cache

import httpx
from supabase.lib.client_options import SyncClientOptions

from app.config import settings
from supabase import Client, create_client


def _build_sync_options() -> SyncClientOptions:
    max_connections = max(10, settings.supabase_http_max_connections)
    max_keepalive_connections = max(
        5,
        min(max_connections, settings.supabase_http_max_keepalive_connections),
    )
    timeout_seconds = max(1, settings.supabase_postgrest_timeout_seconds)

    httpx_client = httpx.Client(
        timeout=httpx.Timeout(timeout_seconds),
        limits=httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        ),
    )

    return SyncClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        postgrest_client_timeout=timeout_seconds,
        storage_client_timeout=timeout_seconds,
        function_client_timeout=min(timeout_seconds, 30),
        httpx_client=httpx_client,
    )


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return the anon-key Supabase client (RLS enforced)."""
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=_build_sync_options(),
    )


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """Return the service-role Supabase client (bypasses RLS).

    Use this only for scheduled jobs and admin operations.
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key,
        options=_build_sync_options(),
    )
