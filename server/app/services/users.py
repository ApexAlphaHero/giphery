"""User service: creation and lookup (case-insensitive username)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, validate_password_strength
from app.models.user import ROLE_USER, User
from app.schemas.errors import ApiError


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    # Case-insensitive match (CITEXT in Postgres; lower() keeps SQLite parity).
    stmt = select(User).where(func.lower(User.username) == username.strip().lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    role: str = ROLE_USER,
    display_name: str | None = None,
    enforce_strength: bool = True,
) -> User:
    username = username.strip()
    if await get_by_username(session, username) is not None:
        raise ApiError(409, "username_taken", "That username is already taken")

    if enforce_strength:
        validate_password_strength(password)
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        display_name=display_name,
    )
    session.add(user)
    await session.flush()
    return user
