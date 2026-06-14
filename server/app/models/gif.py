"""GIF model. Files live on disk; this row holds validated metadata."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPkMixin
from app.models.tag import Tag, gif_tags


class Gif(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "gifs"
    __table_args__ = (
        # Per-owner dedupe on identical bytes.
        UniqueConstraint("owner_id", "content_hash", name="uq_gifs_owner_hash"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stored_path: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tags: Mapped[list[Tag]] = relationship(
        secondary=gif_tags,
        lazy="selectin",
    )
