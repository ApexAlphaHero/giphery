"""GIF upload/validate/store, search, tagging, raw-serve, delete, ownership."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from PIL import Image

PASSWORD = "Sup3rSecret!"


def make_gif(color: tuple[int, int, int] = (255, 0, 0), size: int = 8) -> bytes:
    buf = io.BytesIO()
    frame1 = Image.new("RGB", (size, size), color)
    frame2 = Image.new("RGB", (size, size), (0, 0, 255))
    frame1.save(buf, format="GIF", save_all=True, append_images=[frame2], duration=100)
    return buf.getvalue()


def make_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (0, 255, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def _admin_token(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/setup", json={"username": "admin", "password": PASSWORD})
    return resp.json()["access_token"]


async def _paired_user_token(client: AsyncClient, admin_h: dict, username: str) -> str:
    created = await client.post("/api/v1/invites", headers=admin_h, json={})
    redeem = await client.post(
        "/api/v1/invites/redeem",
        json={"code": created.json()["code"], "username": username},
    )
    return redeem.json()["access_token"]


async def _upload(client: AsyncClient, headers: dict, data: bytes, **fields: str):
    return await client.post(
        "/api/v1/gifs",
        headers=headers,
        files={"file": ("anim.gif", data, "image/gif")},
        data=fields,
    )


@pytest.mark.asyncio
async def test_upload_validate_and_get(client: AsyncClient) -> None:
    token = await _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}

    resp = await _upload(client, h, make_gif(), title="Hello", tags="funny, cat")
    assert resp.status_code == 201, resp.text
    meta = resp.json()
    assert meta["mime_type"] == "image/gif"
    assert meta["width"] == 8 and meta["height"] == 8
    assert sorted(meta["tags"]) == ["cat", "funny"]
    assert meta["raw_url"].endswith(f"/gifs/{meta['id']}/raw")

    got = await client.get(f"/api/v1/gifs/{meta['id']}", headers=h)
    assert got.status_code == 200
    assert got.json()["title"] == "Hello"


@pytest.mark.asyncio
async def test_reject_non_gif(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    resp = await _upload(client, h, make_png())
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "not_a_gif"


@pytest.mark.asyncio
async def test_raw_serve_returns_gif_bytes(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    data = make_gif()
    meta = (await _upload(client, h, data)).json()

    raw = await client.get(f"/api/v1/gifs/{meta['id']}/raw", headers=h)
    assert raw.status_code == 200
    assert raw.headers["content-type"] == "image/gif"
    assert raw.headers["x-content-type-options"] == "nosniff"
    assert raw.content == data


@pytest.mark.asyncio
async def test_dedupe_same_bytes_same_owner(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    data = make_gif()
    first = await _upload(client, h, data)
    second = await _upload(client, h, data)
    assert first.status_code == 201
    assert second.status_code == 200  # dedupe → existing row
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_search_by_title_and_tag(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _upload(client, h, make_gif((255, 0, 0)), title="Red Cat", tags="cat")
    await _upload(client, h, make_gif((0, 255, 0)), title="Green Dog", tags="dog")

    by_title = await client.get("/api/v1/gifs?q=cat", headers=h)
    assert {g["title"] for g in by_title.json()["items"]} == {"Red Cat"}

    by_tag = await client.get("/api/v1/gifs?tag=dog", headers=h)
    assert {g["title"] for g in by_tag.json()["items"]} == {"Green Dog"}


@pytest.mark.asyncio
async def test_edit_title_and_tags(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    meta = (await _upload(client, h, make_gif(), title="Old", tags="a")).json()

    patched = await client.patch(
        f"/api/v1/gifs/{meta['id']}",
        headers=h,
        json={"title": "New", "tags": ["b", "c"]},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "New"
    assert sorted(patched.json()["tags"]) == ["b", "c"]


@pytest.mark.asyncio
async def test_attach_and_detach_tag(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    meta = (await _upload(client, h, make_gif())).json()

    attached = await client.post(f"/api/v1/gifs/{meta['id']}/tags", headers=h, json={"name": "wow"})
    assert "wow" in attached.json()["tags"]

    detached = await client.delete(f"/api/v1/gifs/{meta['id']}/tags/wow", headers=h)
    assert "wow" not in detached.json()["tags"]


@pytest.mark.asyncio
async def test_delete_removes_row_and_file(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    meta = (await _upload(client, h, make_gif())).json()

    deleted = await client.delete(f"/api/v1/gifs/{meta['id']}", headers=h)
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/gifs/{meta['id']}", headers=h)
    assert gone.status_code == 404
    raw = await client.get(f"/api/v1/gifs/{meta['id']}/raw", headers=h)
    assert raw.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_others_gif(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    alice_token = await _paired_user_token(client, admin_h, "alice")
    bob_token = await _paired_user_token(client, admin_h, "bob")

    alice_h = {"Authorization": f"Bearer {alice_token}"}
    bob_h = {"Authorization": f"Bearer {bob_token}"}

    meta = (await _upload(client, alice_h, make_gif())).json()
    # Bob cannot see Alice's gif (404, no existence disclosure).
    assert (await client.get(f"/api/v1/gifs/{meta['id']}", headers=bob_h)).status_code == 404
    # Bob's listing is empty; Alice sees her own.
    assert (await client.get("/api/v1/gifs", headers=bob_h)).json()["items"] == []
    assert len((await client.get("/api/v1/gifs", headers=alice_h)).json()["items"]) == 1


@pytest.mark.asyncio
async def test_tags_endpoint_usage_counts(client: AsyncClient) -> None:
    h = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _upload(client, h, make_gif((1, 2, 3)), tags="shared")
    await _upload(client, h, make_gif((4, 5, 6)), tags="shared, unique")

    resp = await client.get("/api/v1/tags", headers=h)
    counts = {t["name"]: t["usage_count"] for t in resp.json()}
    assert counts["shared"] == 2
    assert counts["unique"] == 1
