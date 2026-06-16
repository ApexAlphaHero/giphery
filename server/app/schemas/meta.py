"""Server metadata + database stats schema."""

from __future__ import annotations

from pydantic import BaseModel


class MetaOut(BaseModel):
    server_version: str
    role: str
    # Scoped to the caller: own GIFs for a user, all GIFs for an admin.
    gifs: int
    storage_bytes: int
    tags: int
    # Admin-only global counts (null for regular users).
    users: int | None = None
    devices: int | None = None
