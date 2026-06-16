"""Admin user management: list, revoke devices, delete."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import audit
from app.models.device import Device
from app.models.gif import Gif
from app.models.user import ROLE_ADMIN, User
from app.schemas.errors import ApiError


@dataclass
class UserSummary:
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime
    device_count: int
    active_device_count: int
    gif_count: int


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def list_users(session: AsyncSession) -> list[UserSummary]:
    users = list((await session.execute(select(User).order_by(User.created_at))).scalars())
    summaries: list[UserSummary] = []
    for u in users:
        devices = list(
            (await session.execute(select(Device).where(Device.user_id == u.id))).scalars()
        )
        gif_count = (
            await session.scalar(select(func.count()).select_from(Gif).where(Gif.owner_id == u.id))
            or 0
        )
        summaries.append(
            UserSummary(
                id=u.id,
                username=u.username,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                device_count=len(devices),
                active_device_count=sum(1 for d in devices if d.revoked_at is None),
                gif_count=int(gif_count),
            )
        )
    return summaries


async def revoke_devices(session: AsyncSession, user_id: uuid.UUID, *, admin: User) -> int:
    """Revoke all of a user's devices (forces re-pair). Returns count revoked."""
    devices = list(
        (
            await session.execute(
                select(Device).where(Device.user_id == user_id, Device.revoked_at.is_(None))
            )
        ).scalars()
    )
    for d in devices:
        d.revoked_at = _now()
    audit(
        "user_devices_revoked",
        user_id=str(admin.id),
        target_user_id=str(user_id),
        count=len(devices),
    )
    return len(devices)


async def delete_user(session: AsyncSession, user_id: uuid.UUID, *, admin: User) -> None:
    """Delete a user and (via FK cascade) their devices and GIFs."""
    if user_id == admin.id:
        raise ApiError(400, "cannot_delete_self", "You cannot delete your own account")

    user = await session.get(User, user_id)
    if user is None:
        raise ApiError(404, "user_not_found", "User not found")

    # Don't allow deleting the last remaining admin.
    if user.role == ROLE_ADMIN:
        other_admins = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == ROLE_ADMIN, User.id != user_id)
        )
        if not other_admins:
            raise ApiError(400, "last_admin", "Cannot delete the only admin")

    await session.delete(user)
    audit("user_deleted", user_id=str(admin.id), target_user_id=str(user_id))
