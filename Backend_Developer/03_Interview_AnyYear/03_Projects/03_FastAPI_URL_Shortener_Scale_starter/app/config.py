"""Application configuration — single source of truth, loaded from env / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "URL Shortener at Scale"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://shortener:dev@localhost:5432/shortenerdb"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-dev-only"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    base_domain: str = "shrt.ly"

    # Worker ID for Snowflake ID generation — MUST be unique per running
    # instance in a real multi-node deployment (spec section 5), or two
    # instances can mint colliding IDs in the same millisecond.
    worker_id: int = 0

    # Rate limiting
    anon_shorten_per_minute: int = 5
    auth_shorten_per_minute: int = 60

    # Redirect cache TTL (spec section 8 — "cache for next 1 hour")
    redirect_cache_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
