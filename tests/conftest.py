"""Pytest fixtures for backend tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


def _set_default_env() -> None:
    os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
    os.environ.setdefault("SUPABASE_ANON_KEY", "anon-key")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service-key")
    os.environ.setdefault("ENABLE_SCHEDULER", "false")


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Create a FastAPI test client."""
    _set_default_env()
    from app.main import app

    return TestClient(app)
