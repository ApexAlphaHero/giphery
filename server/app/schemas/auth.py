"""Auth & setup request/response schemas with explicit field allow-lists."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.users import UserOut

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,64}$"


class SetupStatus(BaseModel):
    setup_pending: bool


class SetupRequest(BaseModel):
    # Explicit allow-list: role can NOT be supplied (first user is always admin).
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth token_type literal, not a secret


class AuthResult(TokenPair):
    user: UserOut
