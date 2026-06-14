"""Login, refresh rotation/reuse, logout, and rate-limiting tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PASSWORD = "Sup3rSecret!"


async def _bootstrap_admin(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/setup", json={"username": "admin", "password": PASSWORD})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    await _bootstrap_admin(client)
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_and_unknown_user_same_error(
    client: AsyncClient,
) -> None:
    await _bootstrap_admin(client)
    wrong = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "nope-nope-1"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "nope-nope-1"}
    )
    assert wrong.status_code == unknown.status_code == 401
    # No user enumeration: identical error code/message.
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"]


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection(client: AsyncClient) -> None:
    boot = await _bootstrap_admin(client)
    old_refresh = boot["refresh_token"]

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Reusing the now-rotated-out token must fail and revoke the device.
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "token_reused"

    # The new refresh token is also dead now (device revoked).
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session(client: AsyncClient) -> None:
    boot = await _bootstrap_admin(client)
    headers = {"Authorization": f"Bearer {boot['access_token']}"}

    out = await client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 204

    # The access token's device is revoked → subsequent auth'd calls fail.
    again = await client.post("/api/v1/auth/logout", headers=headers)
    assert again.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limited(client: AsyncClient) -> None:
    await _bootstrap_admin(client)
    # Default test limit is 5/minute; the 6th attempt must be throttled.
    statuses = []
    for _ in range(6):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-pass-1"},
        )
        statuses.append(r.status_code)
    assert statuses[-1] == 429
    assert statuses.count(401) == 5
