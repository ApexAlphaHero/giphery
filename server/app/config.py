"""Application configuration via pydantic-settings (env-driven)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config. Loaded from environment / .env (never hard-coded)."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---
    giphery_env: Literal["development", "production"] = "production"
    public_base_url: str = "http://localhost:8000"
    app_port: int = 8000
    log_level: str = "info"

    # --- Security / crypto ---
    secret_key: str = Field(min_length=16)
    invite_enc_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "giphery"
    jwt_audience: str = "giphery-clients"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 60

    # --- Database ---
    database_url: str | None = None
    postgres_user: str = "giphery"
    postgres_password: str = "giphery"
    postgres_db: str = "giphery"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # --- Storage ---
    media_root: str = "/data/media"
    max_upload_bytes: int = 16 * 1024 * 1024

    # --- CORS ---
    cors_allowed_origins: str = ""

    # --- Rate limiting ---
    redis_url: str | None = None
    rate_limit_login: str = "5/minute"
    rate_limit_redeem: str = "5/minute"

    # --- Docs ---
    enable_docs: bool = False

    # --- Logging (24h rolling) ---
    log_dir: str = "/data/logs"
    log_retention_hours: int = 24
    log_json: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.giphery_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
