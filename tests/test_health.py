"""Basic app health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    """Health endpoint should return status and version."""
    response = client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["version"], str)
