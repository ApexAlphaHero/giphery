"""Argon2id password hashing and password-strength enforcement."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exc

from app.schemas.errors import ApiError

# Argon2id with sane interactive params (argon2-cffi defaults are Argon2id).
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=2,
)

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128  # bound work; Argon2 has no practical max but cap input


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except argon2_exc.VerifyMismatchError:
        return False
    except argon2_exc.VerificationError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_password_strength(password: str) -> None:
    """Raise ApiError(422) if the password is too weak."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"must be at most {MAX_PASSWORD_LENGTH} characters")
    if not any(c.isalpha() for c in password):
        problems.append("must contain a letter")
    if not any(c.isdigit() for c in password):
        problems.append("must contain a digit")
    if len(set(password)) < 4:
        problems.append("is too repetitive")
    if problems:
        raise ApiError(
            422,
            "weak_password",
            "Password does not meet strength requirements",
            details=problems,
        )
