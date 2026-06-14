"""FastAPI application entrypoint: middleware, error handling, routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.auth.rate_limit import limiter
from app.config import get_settings
from app.logging_config import app_logger, configure_logging
from app.middleware import access_log_middleware
from app.routers import auth, health, invites, setup
from app.schemas.errors import ApiError, ErrorBody, ErrorResponse

settings = get_settings()
API_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings)
    app_logger.info(
        "startup",
        extra={"env": settings.giphery_env, "version": __version__},
    )
    yield
    app_logger.info("shutdown")


def _envelope(status_code: int, code: str, message: str, details: object = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def create_app() -> FastAPI:
    # In production, never expose docs unless explicitly enabled.
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None

    app = FastAPI(
        title="Giphery API",
        version=__version__,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Rate limiting (slowapi reads app.state.limiter).
    app.state.limiter = limiter

    # CORS — reject wildcard in production.
    origins = settings.cors_origins_list
    if settings.is_production and "*" in origins:
        raise RuntimeError("Wildcard CORS origin is not allowed in production")
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Access logging / request-id (24h rolling stream).
    app.middleware("http")(access_log_middleware)

    # --- Error handlers: uniform envelope, no internal leakage ---
    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(422, "validation_error", "Invalid request", exc.errors())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_req: Request, exc: RateLimitExceeded) -> JSONResponse:
        return _envelope(429, "rate_limited", "Too many requests; please slow down")

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception) -> JSONResponse:
        app_logger.exception("unhandled_exception")
        # Never leak internals to the client.
        return _envelope(500, "internal_error", "An unexpected error occurred")

    # --- Routers ---
    app.include_router(health.router, prefix=API_V1)
    app.include_router(setup.router, prefix=API_V1)
    app.include_router(auth.router, prefix=API_V1)
    app.include_router(invites.router, prefix=API_V1)

    return app


app = create_app()
