"""Invitation-code crypto: high-entropy generation, encryption at rest, HMAC lookup.

Codes are stored **encrypted** (Fernet) so the admin UI can decrypt-and-display
them, plus an HMAC-SHA256 lookup hash for O(1) redeem without decrypting rows.
Plaintext codes never touch the database.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

settings = get_settings()

# Unambiguous alphabet (no 0/O/1/I/L) for human-typed codes.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_GROUPS = 5
_GROUP_LEN = 5  # 25 chars over a 31-symbol alphabet ≈ 123 bits of entropy


def _fernet() -> Fernet:
    # Derive a valid 32-byte urlsafe Fernet key from the configured secret so
    # any sufficiently long INVITE_ENC_KEY string works.
    digest = hashlib.sha256(settings.invite_enc_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _hmac_key() -> bytes:
    return settings.secret_key.encode("utf-8")


def generate_code() -> str:
    """Return a high-entropy, human-friendly invitation code."""
    groups = ["".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LEN)) for _ in range(_GROUPS)]
    return "-".join(groups)


def normalize_code(code: str) -> str:
    """Canonicalize user-entered codes (uppercase, strip spaces)."""
    return code.strip().upper().replace(" ", "")


def encrypt_code(code: str) -> bytes:
    return _fernet().encrypt(code.encode("utf-8"))


def decrypt_code(token: bytes) -> str | None:
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        return None


def lookup_hash(code: str) -> bytes:
    """Deterministic HMAC of the normalized code for indexed lookup."""
    return hmac.new(_hmac_key(), normalize_code(code).encode("utf-8"), hashlib.sha256).digest()
