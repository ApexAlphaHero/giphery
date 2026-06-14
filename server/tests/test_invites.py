"""Invitation create/list/revoke/redeem tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PASSWORD = "Sup3rSecret!"


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/setup", json={"username": "admin", "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_invite(client: AsyncClient, headers: dict[str, str], **body: object) -> dict:
    resp = await client.post("/api/v1/invites", headers=headers, json=body or {})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_create_and_list_invite_shows_code_and_status(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    created = await _create_invite(client, headers, label="For Alice")
    assert created["code"]
    assert created["status"] == "active"

    listed = await client.get("/api/v1/invites", headers=headers)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["label"] == "For Alice"
    # Code is decrypted for the admin view and matches what was issued.
    assert items[0]["code"] == created["code"]
    assert items[0]["status"] == "active"


@pytest.mark.asyncio
async def test_redeem_creates_user_and_marks_redeemed(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    created = await _create_invite(client, headers, label="For Bob")

    redeem = await client.post(
        "/api/v1/invites/redeem",
        json={"code": created["code"], "username": "bob"},
    )
    assert redeem.status_code == 201, redeem.text
    body = redeem.json()
    assert body["user"]["username"] == "bob"
    assert body["user"]["role"] == "user"
    assert body["access_token"] and body["refresh_token"]

    # Admin list now shows the invite redeemed by bob.
    listed = (await client.get("/api/v1/invites", headers=headers)).json()
    assert listed[0]["status"] == "redeemed"
    assert listed[0]["uses_count"] == 1
    assert listed[0]["redeemed_by"] == body["user"]["id"]


@pytest.mark.asyncio
async def test_single_use_code_cannot_be_redeemed_twice(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    created = await _create_invite(client, headers)
    code = created["code"]

    first = await client.post("/api/v1/invites/redeem", json={"code": code, "username": "user1"})
    assert first.status_code == 201
    second = await client.post("/api/v1/invites/redeem", json={"code": code, "username": "user2"})
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "invalid_invite"


@pytest.mark.asyncio
async def test_redeem_duplicate_username_rejected(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    c1 = await _create_invite(client, headers, max_uses=5)
    await client.post("/api/v1/invites/redeem", json={"code": c1["code"], "username": "dup"})
    again = await client.post(
        "/api/v1/invites/redeem", json={"code": c1["code"], "username": "DUP"}
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "username_taken"


@pytest.mark.asyncio
async def test_revoked_invite_cannot_be_redeemed(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    created = await _create_invite(client, headers)
    revoke = await client.delete(f"/api/v1/invites/{created['id']}", headers=headers)
    assert revoke.status_code == 204

    redeem = await client.post(
        "/api/v1/invites/redeem", json={"code": created["code"], "username": "xxx"}
    )
    assert redeem.status_code == 400


@pytest.mark.asyncio
async def test_invalid_code_generic_error(client: AsyncClient) -> None:
    redeem = await client.post(
        "/api/v1/invites/redeem", json={"code": "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE", "username": "zzz"}
    )
    assert redeem.status_code == 400
    assert redeem.json()["error"]["code"] == "invalid_invite"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_invite(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    created = await _create_invite(client, headers, max_uses=2)
    redeem = await client.post(
        "/api/v1/invites/redeem", json={"code": created["code"], "username": "regular"}
    )
    user_headers = {"Authorization": f"Bearer {redeem.json()['access_token']}"}
    resp = await client.post("/api/v1/invites", headers=user_headers, json={})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
