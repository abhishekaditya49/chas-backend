"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    Values are read from environment variables (or a `.env` file).
    """

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_http_max_connections: int = 100
    supabase_http_max_keepalive_connections: int = 50
    supabase_postgrest_timeout_seconds: int = 30

    # App
    app_name: str = "CHAS API"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000"
    enable_scheduler: bool = True

    # Scheduling
    timezone: str = "UTC"

    # Performance tuning
    auth_token_cache_ttl_seconds: int = 15
    auth_token_cache_max_entries: int = 1024
    slow_request_log_threshold_ms: int = 0
    slow_query_log_threshold_ms: int = 0
    membership_cache_ttl_seconds: int = 20
    user_cache_ttl_seconds: int = 30
    data_cache_max_entries: int = 5000
    enforce_invite_whitelist: bool = True
    whitelist_cache_ttl_seconds: int = 300

    @property
    def is_production(self) -> bool:
        """Return True when running in production."""
        return self.environment == "production"

    @property
    def origins_list(self) -> list[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()  # type: ignore[call-arg]
