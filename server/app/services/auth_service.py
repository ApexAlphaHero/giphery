"""Auth service: token issuance, login, refresh rotation, device lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import needs_rehash, verify_password
from app.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from app.logging_config import audit
from app.models.device import Device
from app.models.user import User
from app.schemas.auth import TokenPair
from app.schemas.errors import ApiError
from app.services.users import get_by_username


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def issue_tokens_for_new_device(
    session: AsyncSession,
    user: User,
    *,
    device_name: str,
    platform: str | None = None,
) -> TokenPair:
    """Create a fresh device (session) and return an access+refresh pair."""
    refresh, refresh_jti = create_refresh_token(user.id)
    device = Device(
        user_id=user.id,
        name=device_name,
        refresh_jti=refresh_jti,
        refresh_token_hash=hash_refresh_token(refresh),
        platform=platform,
        last_seen_at=_now(),
    )
    session.add(device)
    await session.flush()  # assigns device.id

    # Bind the access token to this device so logout can target it precisely.
    access, _ = create_access_token(user.id, user.role, device_id=device.id)
    return TokenPair(access_token=access, refresh_token=refresh)


async def login(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    platform: str | None = None,
    client_ip: str | None = None,
) -> tuple[User, TokenPair]:
    """Authenticate and issue tokens. Generic errors prevent user enumeration."""
    user = await get_by_username(session, username)

    # Always run a hash verification to keep timing uniform whether or not the
    # user exists (mitigates user enumeration via response timing).
    candidate_hash = (
        user.password_hash
        if user is not None
        # A precomputed dummy Argon2id hash for the no-user branch.
        else "$argon2id$v=19$m=65536,t=3,p=2$c2FsdHNhbHRzYWx0$"
        "RdescE4i2u4z9rJpJ8u3o3Q1m3aQb8wq6dV0jWlO0aE"
    )
    password_ok = verify_password(password, candidate_hash)

    if user is None or not user.is_active or not password_ok:
        audit("login_failed", username=username, client_ip=client_ip)
        raise ApiError(401, "invalid_credentials", "Invalid username or password")

    if needs_rehash(user.password_hash):
        from app.auth.passwords import hash_password

        user.password_hash = hash_password(password)

    tokens = await issue_tokens_for_new_device(
        session, user, device_name=user.username, platform=platform
    )
    audit("login_success", user_id=str(user.id), client_ip=client_ip)
    return user, tokens


async def refresh(
    session: AsyncSession,
    *,
    refresh_token: str,
    client_ip: str | None = None,
) -> TokenPair:
    """Rotate a refresh token. Detects reuse of a rotated-out token."""
    try:
        data = decode_token(refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "invalid_token", "Invalid or expired refresh token") from exc

    # Reuse detection: a token whose jti is some device's *previous* jti means
    # the token was already rotated away — revoke the whole device.
    reused = (
        await session.execute(select(Device).where(Device.previous_refresh_jti == data.jti))
    ).scalar_one_or_none()
    if reused is not None and reused.revoked_at is None:
        reused.revoked_at = _now()
        # Persist the revocation before raising — the request fails (401) but the
        # device must stay revoked (otherwise the rollback would undo it).
        await session.commit()
        audit("refresh_reuse_detected", user_id=str(reused.user_id), client_ip=client_ip)
        raise ApiError(401, "token_reused", "Refresh token reuse detected; device revoked")

    device = (
        await session.execute(select(Device).where(Device.refresh_jti == data.jti))
    ).scalar_one_or_none()
    if (
        device is None
        or device.revoked_at is not None
        or device.refresh_token_hash != hash_refresh_token(refresh_token)
    ):
        raise ApiError(401, "invalid_token", "Invalid or expired refresh token")

    user = await session.get(User, device.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "invalid_token", "Invalid or expired refresh token")

    # Rotate.
    access, _ = create_access_token(user.id, user.role)
    new_refresh, new_jti = create_refresh_token(user.id)
    device.previous_refresh_jti = device.refresh_jti
    device.refresh_jti = new_jti
    device.refresh_token_hash = hash_refresh_token(new_refresh)
    device.last_seen_at = _now()
    audit("token_refreshed", user_id=str(user.id), client_ip=client_ip)
    return TokenPair(access_token=access, refresh_token=new_refresh)


async def logout_device(session: AsyncSession, device_id: uuid.UUID, *, user_id: uuid.UUID) -> None:
    """Revoke the current device (identified by the access token's `did`)."""
    device = await session.get(Device, device_id)
    if device is not None and device.user_id == user_id and device.revoked_at is None:
        device.revoked_at = _now()
        audit("logout", user_id=str(user_id), device_id=str(device.id))
