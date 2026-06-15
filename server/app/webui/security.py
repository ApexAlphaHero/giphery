"""Cookie-based session + CSRF helpers for the admin web console.

Tokens live in httpOnly cookies (never readable by JS). A double-submit CSRF
token guards state-changing form posts.
"""

from __future__ import annotations

import secrets

import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.auth.tokens import decode_token
from app.config import get_settings
from app.models.user import ROLE_ADMIN, User
from app.services import auth_service

settings = get_settings()

ACCESS_COOKIE = "gph_access"
REFRESH_COOKIE = "gph_refresh"
CSRF_COOKIE = "gph_csrf"
_REFRESH_MAX_AGE = settings.refresh_token_ttl_days * 24 * 3600


def _set_cookie(
    response: Response, name: str, value: str, *, http_only: bool, max_age: int
) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=http_only,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def set_session_cookies(response: Response, access: str, refresh: str) -> None:
    _set_cookie(response, ACCESS_COOKIE, access, http_only=True, max_age=_REFRESH_MAX_AGE)
    _set_cookie(response, REFRESH_COOKIE, refresh, http_only=True, max_age=_REFRESH_MAX_AGE)


def clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, path="/")


def issue_csrf(request: Request, response: Response) -> str:
    """Return the CSRF token, minting + setting one if absent."""
    token = request.cookies.get(CSRF_COOKIE)
    if not token:
        token = secrets.token_urlsafe(32)
        # Readable by the template (not httpOnly) for the double-submit field.
        _set_cookie(response, CSRF_COOKIE, token, http_only=False, max_age=_REFRESH_MAX_AGE)
    return token


def validate_csrf(request: Request, submitted: str | None) -> bool:
    cookie = request.cookies.get(CSRF_COOKIE)
    return bool(cookie and submitted and secrets.compare_digest(cookie, submitted))


async def current_admin(request: Request, response: Response, session: AsyncSession) -> User | None:
    """Resolve the logged-in admin from cookies, refreshing tokens if needed.

    Returns None when not authenticated/authorized (caller redirects to login).
    """
    access = request.cookies.get(ACCESS_COOKIE)
    if access:
        try:
            data = decode_token(access, expected_type="access")
            user = await session.get(User, data.sub)
            if user and user.is_active and user.role == ROLE_ADMIN:
                return user
        except jwt.InvalidTokenError:
            pass

    # Access missing/expired → try a refresh.
    refresh = request.cookies.get(REFRESH_COOKIE)
    if not refresh:
        return None
    try:
        tokens = await auth_service.refresh(session, refresh_token=refresh)
    except Exception:
        return None
    set_session_cookies(response, tokens.access_token, tokens.refresh_token)
    data = decode_token(tokens.access_token, expected_type="access")
    user = await session.get(User, data.sub)
    if user and user.is_active and user.role == ROLE_ADMIN:
        return user
    return None
