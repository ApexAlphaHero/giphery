"""Rate limiting via slowapi (in-process, or Redis when REDIS_URL is set)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings

settings = get_settings()


def _client_key(request: Request) -> str:
    # Prefer the real client IP forwarded by SWAG so limits aren't all keyed
    # to the proxy address.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.redis_url or "memory://",
    default_limits=[],
)
