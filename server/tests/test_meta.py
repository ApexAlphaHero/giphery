"""Server metadata / stats endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PASSWORD = "Sup3rSecret!"


@pytest.mark.asyncio
async def test_meta_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/meta")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_meta_reports_version_and_admin_stats(client: AsyncClient) -> None:
    boot = await client.post("/api/v1/setup", json={"username": "admin", "password": PASSWORD})
    headers = {"Authorization": f"Bearer {boot.json()['access_token']}"}

    resp = await client.get("/api/v1/meta", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_version"]  # non-empty
    assert body["role"] == "admin"
    assert body["gifs"] == 0
    assert body["storage_bytes"] == 0
    assert body["tags"] == 0
    # Admin sees global counts (at least the admin user itself).
    assert body["users"] == 1
    assert body["devices"] >= 1


@pytest.mark.asyncio
async def test_meta_user_scoped_hides_admin_counts(client: AsyncClient) -> None:
    boot = await client.post("/api/v1/setup", json={"username": "admin", "password": PASSWORD})
    admin_h = {"Authorization": f"Bearer {boot.json()['access_token']}"}
    inv = await client.post("/api/v1/invites", headers=admin_h, json={})
    redeem = await client.post(
        "/api/v1/invites/redeem",
        json={"code": inv.json()["code"], "username": "alice"},
    )
    user_h = {"Authorization": f"Bearer {redeem.json()['access_token']}"}

    resp = await client.get("/api/v1/meta", headers=user_h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "user"
    assert body["users"] is None
    assert body["devices"] is None
