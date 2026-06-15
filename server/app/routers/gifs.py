"""GIFs router: upload, search, metadata, raw bytes, edit, delete, tagging."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models.gif import Gif
from app.models.user import User
from app.schemas.errors import ApiError
from app.schemas.gifs import GifMeta, GifPage, GifUpdate, TagAttach
from app.services import gifs as gif_service
from app.services import tags as tag_service
from app.storage import read_file

router = APIRouter(prefix="/gifs", tags=["gifs"])


def to_meta(gif: Gif) -> GifMeta:
    return GifMeta(
        id=gif.id,
        owner_id=gif.owner_id,
        title=gif.title,
        original_filename=gif.original_filename,
        mime_type=gif.mime_type,
        byte_size=gif.byte_size,
        width=gif.width,
        height=gif.height,
        content_hash=gif.content_hash,
        tags=sorted(t.name for t in gif.tags),
        raw_url=gif_service.raw_url(gif.id),
        created_at=gif.created_at,
        updated_at=gif.updated_at,
    )


@router.get("", response_model=GifPage)
async def list_gifs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None, max_length=128),
    tag: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=30, ge=1, le=100),
    cursor: uuid.UUID | None = Query(default=None),
) -> GifPage:
    items, next_cursor = await gif_service.search_gifs(
        session, user=user, q=q, tag=tag, limit=limit, cursor=cursor
    )
    return GifPage(
        items=[to_meta(g) for g in items],
        next_cursor=str(next_cursor) if next_cursor else None,
    )


@router.post("", response_model=GifMeta, status_code=201)
async def upload_gif(
    response: Response,
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=255),
    tags: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GifMeta:
    data = await file.read()
    tag_names = [t for t in (tags or "").split(",") if t.strip()] or None
    gif, created = await gif_service.create_gif(
        session,
        owner=user,
        data=data,
        original_filename=file.filename or "upload.gif",
        title=title,
        tag_names=tag_names,
    )
    # Dedupe returns the existing row with 200 instead of 201.
    response.status_code = 201 if created else 200
    return to_meta(gif)


@router.get("/{gif_id}", response_model=GifMeta)
async def get_gif(
    gif_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GifMeta:
    gif = await gif_service.get_gif(session, gif_id, user)
    return to_meta(gif)


@router.get("/{gif_id}/raw")
async def get_gif_raw(
    gif_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Serve the raw GIF bytes. This is the stable endpoint a future IME hits."""
    gif = await gif_service.get_gif(session, gif_id, user)
    try:
        data = read_file(gif.stored_path)
    except FileNotFoundError as exc:
        raise ApiError(404, "gif_file_missing", "GIF file is missing") from exc
    return Response(
        content=data,
        media_type="image/gif",
        headers={
            # Safe, non-executable inline disposition with a sanitized name.
            "Content-Disposition": f'inline; filename="{gif.content_hash}.gif"',
            "Cache-Control": "private, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{gif_id}", response_model=GifMeta)
async def update_gif(
    gif_id: uuid.UUID,
    payload: GifUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GifMeta:
    gif = await gif_service.update_gif(
        session,
        gif_id,
        user,
        title=payload.title,
        title_set="title" in payload.model_fields_set,
        tag_names=payload.tags,
    )
    return to_meta(gif)


@router.delete("/{gif_id}", status_code=204)
async def delete_gif(
    gif_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await gif_service.delete_gif(session, gif_id, user)
    return Response(status_code=204)


@router.post("/{gif_id}/tags", response_model=GifMeta)
async def attach_tag(
    gif_id: uuid.UUID,
    payload: TagAttach,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GifMeta:
    gif = await gif_service.get_gif(session, gif_id, user)
    names = sorted({*(t.name for t in gif.tags), tag_service.normalize_tag(payload.name)})
    gif = await gif_service.replace_tags(session, gif_id, user, names)
    return to_meta(gif)


@router.delete("/{gif_id}/tags/{tag}", response_model=GifMeta)
async def detach_tag(
    gif_id: uuid.UUID,
    tag: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GifMeta:
    gif = await gif_service.get_gif(session, gif_id, user)
    target = tag_service.normalize_tag(tag)
    names = [t.name for t in gif.tags if t.name != target]
    gif = await gif_service.replace_tags(session, gif_id, user, names)
    return to_meta(gif)
