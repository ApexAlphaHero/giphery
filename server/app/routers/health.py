"""Liveness/readiness endpoint (no auth)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.errors import ApiError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Return 200 when the app and DB are reachable, else 503."""
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        raise ApiError(503, "not_ready", "Database is not reachable") from exc

    return {
        "status": "ok",
        "db": "ok" if db_ok else "down",
        "time": datetime.now(tz=UTC).isoformat(),
    }
