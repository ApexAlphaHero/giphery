"""Auth router: login, refresh (rotating), logout. Rate-limited."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.rate_limit import limiter
from app.auth.tokens import decode_token
from app.config import get_settings
from app.db import get_session
from app.models.user import User
from app.schemas.auth import AuthResult, LoginRequest, RefreshRequest, TokenPair
from app.schemas.users import UserOut
from app.services import auth_service

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/login", response_model=AuthResult)
@limiter.limit(settings.rate_limit_login)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResult:
    user, tokens = await auth_service.login(
        session,
        username=payload.username,
        password=payload.password,
        platform=request.headers.get("user-agent"),
        client_ip=_client_ip(request),
    )
    return AuthResult(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(settings.rate_limit_login)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    return await auth_service.refresh(
        session,
        refresh_token=payload.refresh_token,
        client_ip=_client_ip(request),
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    # Identify the device from the access token's `did` claim and revoke it.
    header = request.headers.get("authorization", "")
    token = header.partition(" ")[2]
    data = decode_token(token, expected_type="access")
    if data.device_id is not None:
        await auth_service.logout_device(session, data.device_id, user_id=user.id)
    return Response(status_code=204)
