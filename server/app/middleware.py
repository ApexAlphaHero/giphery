"""Request-id + access-log middleware feeding the 24h rolling access stream."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import access_logger

RequestIdHeader = "X-Request-ID"


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For's first hop (set by SWAG); fall back to peer.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def access_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get(RequestIdHeader) or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": _client_ip(request),
                "latency_ms": elapsed_ms,
            },
        )
        raise

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    user_id = getattr(request.state, "user_id", None)
    response.headers[RequestIdHeader] = request_id
    access_logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": elapsed_ms,
            "client_ip": _client_ip(request),
            "user_id": str(user_id) if user_id else None,
        },
    )
    return response
