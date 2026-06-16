"""Re-pair invites and admin user management."""

from __future__ import annotations

import uuid

import pytest
from app.db import SessionLocal
from app.models.user import User
from app.schemas.errors import ApiError
from app.services import invites as invite_service
from app.services import users_admin
from httpx import AsyncClient
from sqlalchemy import select

PASSWORD = "Sup3rSecret!"


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/api/v1/setup", json={"username": "admin", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _redeem_new(client: AsyncClient, admin_h: dict[str, str], username: str):
    inv = await client.post("/api/v1/invites", headers=admin_h, json={})
    return await client.post(
        "/api/v1/invites/redeem", json={"code": inv.json()["code"], "username": username}
    )


async def _admin_user() -> User:
    async with SessionLocal() as s:
        return (await s.execute(select(User).where(User.username == "admin"))).scalar_one()


@pytest.mark.asyncio
async def test_repair_invite_recovers_existing_user(client: AsyncClient) -> None:
    admin_h = await _admin_headers(client)
    red = await _redeem_new(client, admin_h, "alice")
    assert red.status_code == 201
    alice_id = red.json()["user"]["id"]

    # Admin issues a re-pair invite bound to alice.
    async with SessionLocal() as s:
        admin = (await s.execute(select(User).where(User.username == "admin"))).scalar_one()
        _inv, code = await invite_service.create_invite(
            s,
            admin=admin,
            label="re-pair",
            max_uses=1,
            expires_at=None,
            target_user_id=uuid.UUID(alice_id),
        )
        await s.commit()

    # Redeeming it returns alice again (no username_taken), same id.
    again = await client.post(
        "/api/v1/invites/redeem", json={"code": code, "username": "ignored-name"}
    )
    assert again.status_code == 201, again.text
    assert again.json()["user"]["id"] == alice_id
    assert again.json()["user"]["username"] == "alice"


@pytest.mark.asyncio
async def test_delete_user_frees_username(client: AsyncClient) -> None:
    admin_h = await _admin_headers(client)
    red = await _redeem_new(client, admin_h, "bob")
    bob_id = red.json()["user"]["id"]

    async with SessionLocal() as s:
        admin = (await s.execute(select(User).where(User.username == "admin"))).scalar_one()
        await users_admin.delete_user(s, uuid.UUID(bob_id), admin=admin)
        await s.commit()

    # Username is freed → a fresh invite can recreate "bob".
    again = await _redeem_new(client, admin_h, "bob")
    assert again.status_code == 201


@pytest.mark.asyncio
async def test_cannot_delete_self_or_last_admin(client: AsyncClient) -> None:
    await _admin_headers(client)
    async with SessionLocal() as s:
        admin = (await s.execute(select(User).where(User.username == "admin"))).scalar_one()
        with pytest.raises(ApiError):
            await users_admin.delete_user(s, admin.id, admin=admin)


@pytest.mark.asyncio
async def test_delete_and_clear_inactive_invites(client: AsyncClient) -> None:
    admin_h = await _admin_headers(client)
    # Two invites: one we'll revoke, one we'll delete directly.
    a = await client.post("/api/v1/invites", headers=admin_h, json={})
    b = await client.post("/api/v1/invites", headers=admin_h, json={})
    a_id = uuid.UUID(a.json()["id"])
    b_id = uuid.UUID(b.json()["id"])

    async with SessionLocal() as s:
        admin = (await s.execute(select(User).where(User.username == "admin"))).scalar_one()
        await invite_service.revoke_invite(s, a_id, admin=admin)  # a -> revoked
        await invite_service.delete_invite(s, b_id, admin=admin)  # b -> gone
        await s.commit()

    async with SessionLocal() as s:
        admin = (await s.execute(select(User).where(User.username == "admin"))).scalar_one()
        cleared = await invite_service.clear_inactive_invites(s, admin=admin)
        await s.commit()
    assert cleared == 1  # the revoked one

    listed = await client.get("/api/v1/invites", headers=admin_h)
    assert listed.json() == []  # all cleaned up


@pytest.mark.asyncio
async def test_revoke_devices_counts(client: AsyncClient) -> None:
    admin_h = await _admin_headers(client)
    red = await _redeem_new(client, admin_h, "carol")
    carol_id = red.json()["user"]["id"]

    async with SessionLocal() as s:
        admin = (await s.execute(select(User).where(User.username == "admin"))).scalar_one()
        revoked = await users_admin.revoke_devices(s, uuid.UUID(carol_id), admin=admin)
        await s.commit()
    assert revoked == 1  # carol's single paired device

    # The old refresh token is now dead.
    refresh = red.json()["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401
