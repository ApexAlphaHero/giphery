"""First-run setup tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

GOOD_PASSWORD = "Sup3rSecret!"


@pytest.mark.asyncio
async def test_setup_pending_then_creates_admin(client: AsyncClient) -> None:
    status = await client.get("/api/v1/setup/status")
    assert status.json() == {"setup_pending": True}

    resp = await client.post(
        "/api/v1/setup",
        json={"username": "admin", "password": GOOD_PASSWORD},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["username"] == "admin"
    assert body["access_token"] and body["refresh_token"]
    # Never leak the hash.
    assert "password_hash" not in body["user"]

    status2 = await client.get("/api/v1/setup/status")
    assert status2.json() == {"setup_pending": False}


@pytest.mark.asyncio
async def test_second_setup_rejected(client: AsyncClient) -> None:
    await client.post("/api/v1/setup", json={"username": "admin", "password": GOOD_PASSWORD})
    resp = await client.post("/api/v1/setup", json={"username": "other", "password": GOOD_PASSWORD})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "setup_already_done"


@pytest.mark.asyncio
async def test_weak_password_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/setup", json={"username": "admin", "password": "short"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "weak_password"
