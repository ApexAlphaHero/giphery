"""Invitation service: create, list, revoke, redeem."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.invite_codes import (
    decrypt_code,
    encrypt_code,
    generate_code,
    lookup_hash,
)
from app.logging_config import audit
from app.models.invitation import Invitation
from app.models.user import ROLE_USER, User
from app.schemas.auth import TokenPair
from app.schemas.errors import ApiError
from app.schemas.invites import InviteStatus
from app.services.auth_service import issue_tokens_for_new_device
from app.services.users import create_user

_GENERIC_INVITE_ERROR = ("invalid_invite", "Invalid or expired invitation code")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def derive_status(inv: Invitation) -> InviteStatus:
    if inv.revoked_at is not None:
        return "revoked"
    if inv.expires_at is not None and inv.expires_at < _now():
        return "expired"
    if inv.uses_count >= inv.max_uses:
        return "redeemed"
    return "active"


async def create_invite(
    session: AsyncSession,
    *,
    admin: User,
    label: str | None,
    max_uses: int,
    expires_at: datetime | None,
    target_user_id: uuid.UUID | None = None,
) -> tuple[Invitation, str]:
    """Create an invite; returns the row and the plaintext code (shown once).

    When ``target_user_id`` is set, this is a re-pair invite: redeeming it adds a
    device to that existing user instead of creating a new account.
    """
    # Avoid the astronomically unlikely lookup-hash collision.
    for _ in range(5):
        code = generate_code()
        lh = lookup_hash(code)
        exists = (
            await session.execute(select(Invitation.id).where(Invitation.code_lookup_hash == lh))
        ).first()
        if exists is None:
            break
    else:  # pragma: no cover - effectively unreachable
        raise ApiError(500, "code_generation_failed", "Could not allocate a code")

    invite = Invitation(
        code_encrypted=encrypt_code(code),
        code_lookup_hash=lh,
        label=label,
        created_by=admin.id,
        max_uses=max_uses,
        expires_at=expires_at,
        target_user_id=target_user_id,
    )
    session.add(invite)
    await session.flush()
    audit("invite_created", user_id=str(admin.id), invite_id=str(invite.id))
    return invite, code


async def list_invites(session: AsyncSession) -> list[Invitation]:
    result = await session.execute(select(Invitation).order_by(Invitation.created_at.desc()))
    return list(result.scalars().all())


def display_code(inv: Invitation) -> str:
    return decrypt_code(inv.code_encrypted) or "<undecryptable>"


async def revoke_invite(session: AsyncSession, invite_id: uuid.UUID, *, admin: User) -> None:
    invite = await session.get(Invitation, invite_id)
    if invite is None:
        raise ApiError(404, "invite_not_found", "Invitation not found")
    if invite.revoked_at is None:
        invite.revoked_at = _now()
        audit("invite_revoked", user_id=str(admin.id), invite_id=str(invite.id))


async def delete_invite(session: AsyncSession, invite_id: uuid.UUID, *, admin: User) -> None:
    """Permanently remove an invitation row (cleanup)."""
    invite = await session.get(Invitation, invite_id)
    if invite is not None:
        await session.delete(invite)
        audit("invite_deleted", user_id=str(admin.id), invite_id=str(invite_id))


async def clear_inactive_invites(session: AsyncSession, *, admin: User) -> int:
    """Delete all revoked/expired invites (keeps active + redeemed). Returns count."""
    invites = await list_invites(session)
    count = 0
    for inv in invites:
        if derive_status(inv) in ("revoked", "expired"):
            await session.delete(inv)
            count += 1
    audit("invites_cleared", user_id=str(admin.id), count=count)
    return count


async def redeem_invite(
    session: AsyncSession,
    *,
    code: str,
    username: str,
    display_name: str | None = None,
    platform: str | None = None,
    client_ip: str | None = None,
) -> tuple[User, TokenPair]:
    """Validate the code, create the user + device, return (user, TokenPair)."""
    invite = (
        await session.execute(
            select(Invitation).where(Invitation.code_lookup_hash == lookup_hash(code))
        )
    ).scalar_one_or_none()

    # Generic error for any invalid/expired/used/revoked code (no enumeration).
    if invite is None or derive_status(invite) != "active":
        audit("invite_redeem_failed", client_ip=client_ip)
        raise ApiError(400, *_GENERIC_INVITE_ERROR)

    if invite.target_user_id is not None:
        # Re-pair invite: add a device to the existing user (account recovery).
        # The submitted username is ignored; the bound user is authoritative.
        user = await session.get(User, invite.target_user_id)
        if user is None or not user.is_active:
            audit("invite_redeem_failed", client_ip=client_ip)
            raise ApiError(400, *_GENERIC_INVITE_ERROR)
    else:
        # Normal invite: create the user with a random, unknowable password —
        # regular users authenticate via device tokens, never password login.
        random_password = secrets.token_urlsafe(32)
        user = await create_user(
            session,
            username=username,
            password=random_password,
            role=ROLE_USER,
            display_name=display_name,
            enforce_strength=False,
        )

    invite.uses_count += 1
    invite.redeemed_by = user.id
    invite.redeemed_at = _now()

    tokens = await issue_tokens_for_new_device(
        session, user, device_name=user.username, platform=platform
    )
    audit(
        "invite_redeemed",
        user_id=str(user.id),
        invite_id=str(invite.id),
        client_ip=client_ip,
    )
    return user, tokens
