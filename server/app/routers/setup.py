"""First-run setup: detect pending state and create the initial admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import any_user_exists
from app.auth.passwords import validate_password_strength
from app.db import get_session
from app.logging_config import audit
from app.models.user import ROLE_ADMIN
from app.schemas.auth import AuthResult, SetupRequest, SetupStatus
from app.schemas.errors import ApiError
from app.schemas.users import UserOut
from app.services.auth_service import issue_tokens_for_new_device
from app.services.users import create_user

router = APIRouter(tags=["setup"])


@router.get("/setup/status", response_model=SetupStatus)
async def setup_status(session: AsyncSession = Depends(get_session)) -> SetupStatus:
    return SetupStatus(setup_pending=not await any_user_exists(session))


@router.post("/setup", response_model=AuthResult, status_code=201)
async def create_first_admin(
    payload: SetupRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResult:
    # Hard-fail once any user exists — setup is a one-time, first-run operation.
    if await any_user_exists(session):
        raise ApiError(409, "setup_already_done", "Setup has already been completed")

    validate_password_strength(payload.password)
    user = await create_user(
        session,
        username=payload.username,
        password=payload.password,
        role=ROLE_ADMIN,
        display_name=payload.display_name,
    )
    tokens = await issue_tokens_for_new_device(
        session, user, device_name=user.username, platform="web"
    )
    client_ip = request.client.host if request.client else None
    audit("setup_completed", user_id=str(user.id), client_ip=client_ip)
    return AuthResult(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserOut.model_validate(user),
    )
