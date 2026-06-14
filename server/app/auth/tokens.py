"""JWT creation and verification (access + refresh) with full claim validation."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenData:
    sub: uuid.UUID
    jti: uuid.UUID
    typ: TokenType
    role: str | None
    device_id: uuid.UUID | None = None


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _encode(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(
    user_id: uuid.UUID, role: str, device_id: uuid.UUID | None = None
) -> tuple[str, uuid.UUID]:
    jti = uuid.uuid4()
    now = _now()
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "jti": str(jti),
        "typ": "access",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    if device_id is not None:
        claims["did"] = str(device_id)
    return _encode(claims), jti


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    jti = uuid.uuid4()
    now = _now()
    claims = {
        "sub": str(user_id),
        "jti": str(jti),
        "typ": "refresh",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(days=settings.refresh_token_ttl_days),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return _encode(claims), jti


def decode_token(token: str, expected_type: TokenType) -> TokenData:
    """Decode + validate signature, exp/iat/nbf, iss, aud, and token type.

    Raises ``jwt.InvalidTokenError`` (or subclass) on any failure.
    """
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["exp", "iat", "nbf", "sub", "jti", "iss", "aud"]},
    )
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    did = payload.get("did")
    return TokenData(
        sub=uuid.UUID(payload["sub"]),
        jti=uuid.UUID(payload["jti"]),
        typ=expected_type,
        role=payload.get("role"),
        device_id=uuid.UUID(did) if did else None,
    )


def hash_refresh_token(token: str) -> str:
    """SHA-256 of a refresh token, stored server-side for verification."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
