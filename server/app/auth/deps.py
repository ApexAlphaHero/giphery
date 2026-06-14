"""FastAPI auth dependencies: current user, admin guard, RBAC helpers."""

from __future__ import annotations

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import decode_token
from app.db import get_session
from app.models.device import Device
from app.models.user import ROLE_ADMIN, User
from app.schemas.errors import ApiError


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "not_authenticated", "Missing or invalid Authorization header")
    return token


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _bearer_token(request)
    try:
        data = decode_token(token, expected_type="access")
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "invalid_token", "Invalid or expired token") from exc

    user = await session.get(User, data.sub)
    if user is None or not user.is_active:
        raise ApiError(401, "invalid_token", "Invalid or expired token")

    # If the token is bound to a device, ensure that device wasn't revoked
    # (logout / admin revocation takes effect immediately, not at token expiry).
    if data.device_id is not None:
        device = await session.get(Device, data.device_id)
        if device is None or device.revoked_at is not None:
            raise ApiError(401, "invalid_token", "Session has been revoked")

    # Expose for the access log.
    request.state.user_id = str(user.id)
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise ApiError(403, "forbidden", "Admin privileges required")
    return user


async def any_user_exists(session: AsyncSession) -> bool:
    result = await session.execute(select(User.id).limit(1))
    return result.first() is not None
