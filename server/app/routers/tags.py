"""Tags router: list with usage counts (for autocomplete)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.tags import TagOut
from app.services import tags as tag_service

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
async def list_tags(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None, max_length=64),
) -> list[TagOut]:
    rows = await tag_service.list_with_counts(session, q=q)
    return [TagOut(name=name, usage_count=count) for name, count in rows]
