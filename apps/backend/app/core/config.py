"""Application settings — loaded from env vars via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Read once at startup, cached via `get_settings()`. Never mutate.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Arxiu Institut la Ferreria"
    log_level: str = "INFO"
    tz: str = "Europe/Madrid"

    # --- Backend ---
    backend_host: str = "0.0.0.0"  # noqa: S104 — bound inside container, exposed only via reverse proxy
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"

    # --- JWT ---
    jwt_private_key_path: Path = Path("/run/secrets/jwt_private.pem")
    jwt_public_key_path: Path = Path("/run/secrets/jwt_public.pem")
    jwt_algorithm: str = "RS256"
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 604_800

    # --- Database ---
    database_url: str = Field(
        default="mysql+asyncmy://arxiu:changeme@mysql:3306/arxiu?charset=utf8mb4",
        description="SQLAlchemy async DSN",
    )

    # --- Redis / ARQ ---
    redis_url: str = "redis://redis:6379/0"

    # --- Google OAuth (optional) ---
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    google_oauth_allowed_domain: str = "inslaferreria.cat"

    # --- SMTP ---
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_address: str = "no-reply@inslaferreria.cat"
    smtp_from_name: str = "Arxiu Institut la Ferreria"

    # --- Storage ---
    storage_root: Path = Path("/var/arxiu/storage")

    # --- Security ---
    password_bcrypt_rounds: int = 12
    password_min_length: int = 12
    admin_password_reveal_ttl_seconds: int = 300
    rate_limit_login_per_minute: int = 5
    rate_limit_write_per_minute: int = 60

    # --- Observability ---
    sentry_dsn: str = ""
    prometheus_enabled: bool = True

    # --- Computed -----------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — call inside dependencies, not at import time."""
    return Settings()
