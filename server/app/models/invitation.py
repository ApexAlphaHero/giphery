"""Invitation model. Code is encrypted at rest; an HMAC enables O(1) lookup."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPkMixin


class Invitation(UUIDPkMixin, Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("max_uses >= 1", name="ck_invites_max_uses"),
        CheckConstraint("uses_count >= 0", name="ck_invites_uses_count"),
    )

    # Fernet-encrypted plaintext code (admin can decrypt-and-view).
    code_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # HMAC-SHA256(code) for constant-time redeem lookup without decrypting rows.
    code_lookup_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
