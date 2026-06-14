"""Invitations router: admin CRUD + public redeem (used by the Android app)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin
from app.auth.rate_limit import limiter
from app.config import get_settings
from app.db import get_session
from app.models.user import User
from app.schemas.invites import (
    InviteCreate,
    InviteCreated,
    InviteOut,
    InviteRedeem,
    RedeemResult,
)
from app.schemas.users import UserOut
from app.services import invites as invite_service

settings = get_settings()
router = APIRouter(prefix="/invites", tags=["invites"])


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("", response_model=InviteCreated, status_code=201)
async def create_invite(
    payload: InviteCreate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteCreated:
    invite, code = await invite_service.create_invite(
        session,
        admin=admin,
        label=payload.label,
        max_uses=payload.max_uses,
        expires_at=payload.expires_at,
    )
    return InviteCreated(
        id=invite.id,
        code=code,
        label=invite.label,
        max_uses=invite.max_uses,
        expires_at=invite.expires_at,
        status=invite_service.derive_status(invite),
        created_at=invite.created_at,
    )


@router.get("", response_model=list[InviteOut])
async def list_invites(
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[InviteOut]:
    invites = await invite_service.list_invites(session)
    return [
        InviteOut(
            id=inv.id,
            code=invite_service.display_code(inv),
            label=inv.label,
            status=invite_service.derive_status(inv),
            max_uses=inv.max_uses,
            uses_count=inv.uses_count,
            redeemed_by=inv.redeemed_by,
            redeemed_at=inv.redeemed_at,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
        )
        for inv in invites
    ]


@router.delete("/{invite_id}", status_code=204)
async def revoke_invite(
    invite_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await invite_service.revoke_invite(session, invite_id, admin=admin)
    return Response(status_code=204)


@router.post("/redeem", response_model=RedeemResult, status_code=201)
@limiter.limit(settings.rate_limit_redeem)
async def redeem_invite(
    payload: InviteRedeem,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedeemResult:
    user, tokens = await invite_service.redeem_invite(
        session,
        code=payload.code,
        username=payload.username,
        display_name=payload.display_name,
        platform=request.headers.get("user-agent"),
        client_ip=_client_ip(request),
    )
    return RedeemResult(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserOut.model_validate(user),
    )
