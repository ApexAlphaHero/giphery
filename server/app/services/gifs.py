"""GIF service: upload/validate/store, search, get, update, delete."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.logging_config import audit
from app.models.gif import Gif
from app.models.tag import Tag, gif_tags
from app.models.user import ROLE_ADMIN, User
from app.schemas.errors import ApiError
from app.services import tags as tag_service
from app.services.gif_validation import GIF_MIME, validate_gif
from app.storage import delete_file, sanitize_filename, store_bytes

settings = get_settings()
MAX_PAGE_SIZE = 100


def raw_url(gif_id: uuid.UUID) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/api/v1/gifs/{gif_id}/raw"


def can_access(user: User, gif: Gif) -> bool:
    return user.role == ROLE_ADMIN or gif.owner_id == user.id


async def _require_gif(session: AsyncSession, gif_id: uuid.UUID, user: User) -> Gif:
    # Eager-load tags so serialization never triggers a sync lazy-load.
    stmt = select(Gif).options(selectinload(Gif.tags)).where(Gif.id == gif_id)
    gif = (await session.execute(stmt)).scalar_one_or_none()
    if gif is None or not can_access(user, gif):
        # Same response whether missing or not-owned (no existence disclosure).
        raise ApiError(404, "gif_not_found", "GIF not found")
    return gif


async def create_gif(
    session: AsyncSession,
    *,
    owner: User,
    data: bytes,
    original_filename: str,
    title: str | None,
    tag_names: list[str] | None,
) -> tuple[Gif, bool]:
    """Validate + store a GIF. Returns (gif, created) — created=False on dedupe."""
    width, height, content_hash = validate_gif(data)

    # Per-owner dedupe: identical bytes return the existing row idempotently.
    existing = (
        await session.execute(
            select(Gif).where(Gif.owner_id == owner.id, Gif.content_hash == content_hash)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    stored_path = store_bytes(content_hash, data)
    gif = Gif(
        owner_id=owner.id,
        stored_path=stored_path,
        original_filename=sanitize_filename(original_filename),
        content_hash=content_hash,
        mime_type=GIF_MIME,
        byte_size=len(data),
        width=width,
        height=height,
        title=title,
    )
    # Resolve + assign tags while the gif is still transient so the assignment
    # never triggers a sync lazy-load of an unloaded collection.
    gif.tags = await tag_service.resolve_tags(session, tag_names or [])
    session.add(gif)
    await session.flush()
    audit("gif_uploaded", user_id=str(owner.id), gif_id=str(gif.id))
    return gif, True


async def search_gifs(
    session: AsyncSession,
    *,
    user: User,
    q: str | None,
    tag: str | None,
    limit: int,
    cursor: uuid.UUID | None,
) -> tuple[list[Gif], uuid.UUID | None]:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    stmt = select(Gif)

    # Ownership scoping: admins see all, users see their own.
    if user.role != ROLE_ADMIN:
        stmt = stmt.where(Gif.owner_id == user.id)

    if q:
        stmt = stmt.where(Gif.title.ilike(f"%{q.strip()}%"))
    if tag:
        norm = tag_service.normalize_tag(tag)
        stmt = stmt.where(
            Gif.id.in_(
                select(gif_tags.c.gif_id)
                .join(Tag, Tag.id == gif_tags.c.tag_id)
                .where(Tag.name == norm)
            )
        )

    # UUIDv7 ids are time-ordered → ordering by id desc is newest-first.
    if cursor is not None:
        stmt = stmt.where(Gif.id < cursor)
    stmt = stmt.order_by(Gif.id.desc()).limit(limit + 1)

    rows = list((await session.execute(stmt)).scalars().all())
    next_cursor = rows[limit - 1].id if len(rows) > limit else None
    return rows[:limit], next_cursor


async def get_gif(session: AsyncSession, gif_id: uuid.UUID, user: User) -> Gif:
    return await _require_gif(session, gif_id, user)


async def update_gif(
    session: AsyncSession,
    gif_id: uuid.UUID,
    user: User,
    *,
    title: str | None,
    title_set: bool,
    tag_names: list[str] | None,
) -> Gif:
    gif = await _require_gif(session, gif_id, user)
    if title_set:
        gif.title = title
    if tag_names is not None:
        await tag_service.set_tags(session, gif, tag_names)
    await session.flush()
    audit("gif_updated", user_id=str(user.id), gif_id=str(gif.id))
    # Re-fetch with tags eagerly loaded so serialization never lazy-loads.
    return await _require_gif(session, gif_id, user)


async def replace_tags(
    session: AsyncSession, gif_id: uuid.UUID, user: User, names: list[str]
) -> Gif:
    """Set a gif's tag set to ``names`` and return it with tags loaded."""
    gif = await _require_gif(session, gif_id, user)
    await tag_service.set_tags(session, gif, names)
    await session.flush()
    return await _require_gif(session, gif_id, user)


async def delete_gif(session: AsyncSession, gif_id: uuid.UUID, user: User) -> None:
    gif = await _require_gif(session, gif_id, user)
    stored_path = gif.stored_path
    content_hash = gif.content_hash
    owner_id = gif.owner_id
    await session.delete(gif)
    await session.flush()

    # Only remove the file if no other row references the same content.
    still_used = (
        await session.execute(select(Gif.id).where(Gif.content_hash == content_hash).limit(1))
    ).first()
    if still_used is None:
        delete_file(stored_path)
    audit("gif_deleted", user_id=str(user.id), gif_id=str(gif_id), owner_id=str(owner_id))
