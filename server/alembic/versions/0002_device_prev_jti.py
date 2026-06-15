"""add devices.previous_refresh_jti for refresh-token reuse detection

Revision ID: 0002_device_prev_jti
Revises: 0001_initial
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_device_prev_jti"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("previous_refresh_jti", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("devices", "previous_refresh_jti")
