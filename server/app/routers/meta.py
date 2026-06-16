"""Server metadata + database stats (authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.auth.deps import get_current_user
from app.db import get_session
from app.models.device import Device
from app.models.gif import Gif
from app.models.tag import Tag
from app.models.user import ROLE_ADMIN, User
from app.schemas.meta import MetaOut

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaOut)
async def meta(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MetaOut:
    is_admin = user.role == ROLE_ADMIN

    gif_count_stmt = select(func.count()).select_from(Gif)
    storage_stmt = select(func.coalesce(func.sum(Gif.byte_size), 0))
    if not is_admin:
        gif_count_stmt = gif_count_stmt.where(Gif.owner_id == user.id)
        storage_stmt = storage_stmt.where(Gif.owner_id == user.id)

    gifs = await session.scalar(gif_count_stmt) or 0
    storage = await session.scalar(storage_stmt) or 0
    tags = await session.scalar(select(func.count()).select_from(Tag)) or 0

    users = devices = None
    if is_admin:
        users = await session.scalar(select(func.count()).select_from(User)) or 0
        devices = await session.scalar(select(func.count()).select_from(Device)) or 0

    return MetaOut(
        server_version=__version__,
        role=user.role,
        gifs=int(gifs),
        storage_bytes=int(storage),
        tags=int(tags),
        users=users,
        devices=devices,
    )
