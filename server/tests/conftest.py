"""Shared test fixtures. Runs the app against an in-process SQLite database.

Environment is configured *before* any app import so pydantic-settings and the
module-level async engine pick up the test DSN.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

# --- configure environment before importing the app ---
_TMP = tempfile.mkdtemp(prefix="giphery-test-")
os.environ.setdefault("GIPHERY_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef")
os.environ.setdefault("INVITE_ENC_KEY", "dGVzdC1pbnZpdGUtZW5jLWtleS0zMmJ5dGVzLWxvbmchIQ==")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/test.db")
os.environ.setdefault("LOG_DIR", str(Path(_TMP) / "logs"))
os.environ.setdefault("MEDIA_ROOT", str(Path(_TMP) / "media"))
os.environ.setdefault("ENABLE_DOCS", "true")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from app.auth.rate_limit import limiter  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    # Isolate rate-limit counters between tests.
    with contextlib.suppress(Exception):
        limiter._storage.reset()


@pytest_asyncio.fixture(autouse=True)
async def _create_schema() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
