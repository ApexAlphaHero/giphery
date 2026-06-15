"""Tag service: normalization, get-or-create, usage counts."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gif import Gif
from app.models.tag import Tag, gif_tags


def normalize_tag(name: str) -> str:
    return name.strip().lower()


async def get_or_create(session: AsyncSession, name: str) -> Tag:
    norm = normalize_tag(name)
    existing = (
        await session.execute(select(Tag).where(func.lower(Tag.name) == norm))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    tag = Tag(name=norm)
    session.add(tag)
    await session.flush()
    return tag


async def resolve_tags(session: AsyncSession, names: list[str]) -> list[Tag]:
    """Normalize + de-duplicate names into a list of (created-if-needed) tags."""
    seen: dict[str, None] = {}
    for n in names:
        norm = normalize_tag(n)
        if norm:
            seen.setdefault(norm, None)
    return [await get_or_create(session, n) for n in seen]


async def set_tags(session: AsyncSession, gif: Gif, names: list[str]) -> None:
    """Replace a (already tag-loaded) gif's tag set with the given names."""
    gif.tags = await resolve_tags(session, names)


async def list_with_counts(session: AsyncSession, q: str | None = None) -> list[tuple[str, int]]:
    stmt = (
        select(Tag.name, func.count(gif_tags.c.gif_id))
        .outerjoin(gif_tags, Tag.id == gif_tags.c.tag_id)
        .group_by(Tag.name)
        .order_by(func.count(gif_tags.c.gif_id).desc(), Tag.name)
    )
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{normalize_tag(q)}%"))
    rows = await session.execute(stmt)
    return [(name, count) for name, count in rows.all()]
