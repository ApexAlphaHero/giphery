"""Admin web console tests: setup, login, invite create/revoke, CSRF."""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

PASSWORD = "Sup3rSecret!"
_CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf(html: str) -> str:
    m = _CSRF_RE.search(html)
    assert m, "no csrf token in page"
    return m.group(1)


async def _setup_admin(client: AsyncClient) -> None:
    page = await client.get("/setup")
    token = _csrf(page.text)
    resp = await client.post(
        "/setup",
        data={"username": "admin", "password": PASSWORD, "csrf_token": token},
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


@pytest.mark.asyncio
async def test_index_redirects_to_setup_when_empty(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/setup"


@pytest.mark.asyncio
async def test_setup_creates_admin_and_dashboard_loads(client: AsyncClient) -> None:
    await _setup_admin(client)
    # Cookies from the redirect are stored by the client → dashboard renders.
    dash = await client.get("/")
    assert dash.status_code == 200
    assert "Invitations" in dash.text
    assert "admin" in dash.text


@pytest.mark.asyncio
async def test_second_setup_redirects_to_login(client: AsyncClient) -> None:
    await _setup_admin(client)
    page = await client.get("/setup")
    assert page.status_code == 303
    assert page.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_create_and_revoke_invite_via_web(client: AsyncClient) -> None:
    await _setup_admin(client)
    dash = await client.get("/")
    token = _csrf(dash.text)

    # Create uses Post/Redirect/Get → 303 to "/" (refresh-safe, no duplicates).
    created = await client.post(
        "/invites",
        data={"label": "Alice", "max_uses": "1", "expires_at": "", "csrf_token": token},
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/"

    # The new invite (with its code) shows in the list on the follow-up GET.
    listing = await client.get("/")
    assert "Alice" in listing.text
    assert "active" in listing.text

    # Grab the invite id from a revoke form and revoke it.
    m = re.search(r"/invites/([0-9a-f-]+)/revoke", listing.text)
    assert m
    revoke = await client.post(f"/invites/{m.group(1)}/revoke", data={"csrf_token": token})
    assert revoke.status_code == 303
    after = await client.get("/")
    assert "revoked" in after.text


@pytest.mark.asyncio
async def test_create_invite_bad_csrf_rejected(client: AsyncClient) -> None:
    await _setup_admin(client)
    await client.get("/")
    resp = await client.post(
        "/invites",
        data={"label": "x", "max_uses": "1", "csrf_token": "wrong-token"},
    )
    # Bad CSRF → dashboard re-rendered with an error, no invite created.
    assert resp.status_code == 200
    assert "Invalid session" in resp.text


@pytest.mark.asyncio
async def test_login_logout_cycle(client: AsyncClient) -> None:
    await _setup_admin(client)
    # Log out, then the index should send us to login.
    dash = await client.get("/")
    token = _csrf(dash.text)
    await client.post("/logout", data={"csrf_token": token})
    idx = await client.get("/")
    assert idx.status_code == 303
    assert idx.headers["location"] == "/login"

    # Log back in.
    login_page = await client.get("/login")
    ltoken = _csrf(login_page.text)
    resp = await client.post(
        "/login",
        data={"username": "admin", "password": PASSWORD, "csrf_token": ltoken},
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
