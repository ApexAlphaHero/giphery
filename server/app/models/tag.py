"""Tag model and the gif<->tag association table."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPkMixin

# Many-to-many association: composite PK (gif_id, tag_id).
gif_tags = Table(
    "gif_tags",
    Base.metadata,
    Column(
        "gif_id",
        ForeignKey("gifs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Tag(UUIDPkMixin, Base):
    __tablename__ = "tags"

    # Normalized lowercase/trimmed; CITEXT in Postgres for case-insensitive unique.
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
