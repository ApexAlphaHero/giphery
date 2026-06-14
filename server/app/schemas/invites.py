"""Invitation request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.auth import USERNAME_PATTERN, AuthResult

InviteStatus = Literal["active", "redeemed", "expired", "revoked"]


class InviteCreate(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_at: datetime | None = None


class InviteCreated(BaseModel):
    """Returned once at creation — includes the plaintext code."""

    id: uuid.UUID
    code: str
    label: str | None
    max_uses: int
    expires_at: datetime | None
    status: InviteStatus
    created_at: datetime


class InviteOut(BaseModel):
    """Admin list view — code is decrypted for display."""

    id: uuid.UUID
    code: str
    label: str | None
    status: InviteStatus
    max_uses: int
    uses_count: int
    redeemed_by: uuid.UUID | None
    redeemed_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class InviteRedeem(BaseModel):
    # Pairing is token-based: the user picks a username; no password is set
    # (regular users authenticate via device refresh tokens, not password login).
    code: str = Field(min_length=1, max_length=64)
    username: str = Field(pattern=USERNAME_PATTERN)
    display_name: str | None = Field(default=None, max_length=128)


# Redeem returns the same shape as other auth flows (tokens + user).
RedeemResult = AuthResult
