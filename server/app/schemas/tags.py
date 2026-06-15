"""Tag response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class TagOut(BaseModel):
    name: str
    usage_count: int
