"""add invitations.target_user_id for re-pair invites

Revision ID: 0003_invite_target_user
Revises: 0002_device_prev_jti
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_invite_target_user"
down_revision: str | None = "0002_device_prev_jti"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invites_target_user",
        "invitations",
        "users",
        ["target_user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_invites_target_user", "invitations", type_="foreignkey")
    op.drop_column("invitations", "target_user_id")
