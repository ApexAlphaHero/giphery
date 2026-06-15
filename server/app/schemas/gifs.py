"""GIF request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

# Tags are normalized lowercase; bound count and length to limit abuse.
TagName = Annotated[str, Field(min_length=1, max_length=64)]


class GifMeta(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str | None
    original_filename: str
    mime_type: str
    byte_size: int
    width: int
    height: int
    content_hash: str
    tags: list[str]
    raw_url: str
    created_at: datetime
    updated_at: datetime


class GifPage(BaseModel):
    items: list[GifMeta]
    next_cursor: str | None = None


class GifUpdate(BaseModel):
    # Explicit allow-list — owner_id/content cannot be changed via this route.
    title: str | None = Field(default=None, max_length=255)
    tags: list[TagName] | None = Field(default=None, max_length=50)


class TagAttach(BaseModel):
    name: TagName
