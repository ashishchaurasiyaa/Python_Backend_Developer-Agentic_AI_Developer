"""
Application configuration — single source of truth, loaded from env / .env.

Uses pydantic-settings so every value is typed and validated at startup.
Env var names are the UPPER_SNAKE_CASE of each field (e.g. DATABASE_URL -> database_url).
Never hard-code secrets here — real values live in .env (gitignored) or the
deploy platform's secret store.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "RAG Backend (Multi-Tenant)"
    environment: str = "development"
    debug: bool = True

    # --- Datastores ---
    database_url: str = "postgresql+asyncpg://rag:dev@localhost:5432/ragdb"
    redis_url: str = "redis://localhost:6379/0"

    # --- Auth (Day 2) ---
    jwt_secret: str = "change-me-dev-only"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- LLM / providers (optional Day 1; needed Week 1 D6 onward) ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_api_key: str = ""

    # --- Models ---
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "claude-sonnet-5"  # configurable via LLM_MODEL env


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so .env is parsed once per process."""
    return Settings()
