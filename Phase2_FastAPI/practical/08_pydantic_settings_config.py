"""
PHASE 2 FastAPI — Practical 08: pydantic-settings + Config Management
Run: uvicorn 08_pydantic_settings_config:app --reload
Docs: http://127.0.0.1:8000/docs

Install: pip install pydantic-settings python-dotenv

Topics:
  - BaseSettings — env vars auto-loaded
  - .env file loading
  - Multiple environments (dev / staging / prod)
  - Nested settings (DatabaseSettings, RedisSettings)
  - @lru_cache singleton — settings loaded once
  - get_settings() as FastAPI dependency
  - Secrets from files (Docker secrets)
  - Settings validation with @field_validator
  - Dynamic config override in tests
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI
from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ═══════════════════════════════════════════════════════
# SECTION 1: Environment Enum
# ═══════════════════════════════════════════════════════

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING     = "staging"
    PRODUCTION  = "production"
    TESTING     = "testing"


# ═══════════════════════════════════════════════════════
# SECTION 2: Nested Settings Models
# ═══════════════════════════════════════════════════════

class DatabaseSettings(BaseSettings):
    """All DB-related config grouped together."""
    host:     str = "localhost"
    port:     int = 5432
    name:     str = "myapp"
    user:     str = "postgres"
    password: str = "password"
    pool_size: int = 10
    max_overflow: int = 20
    echo_sql: bool = False

    model_config = SettingsConfigDict(env_prefix="DB_")

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    host:     str = "localhost"
    port:     int = 6379
    db:       int = 0
    password: Optional[str] = None
    ttl_seconds: int = 300

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class JWTSettings(BaseSettings):
    secret_key: str = "change-me-in-production-256-bit-secret"
    algorithm:  str = "HS256"
    access_token_expire_minutes:  int = 15
    refresh_token_expire_days:    int = 7

    model_config = SettingsConfigDict(env_prefix="JWT_")

    @field_validator("secret_key")
    @classmethod
    def secret_key_length(cls, v: str, info) -> str:
        # Only enforce in production
        if len(v) < 32 and os.getenv("APP_ENVIRONMENT") == "production":
            raise ValueError("JWT secret_key must be at least 32 characters in production")
        return v


# ═══════════════════════════════════════════════════════
# SECTION 3: Main Application Settings
# ═══════════════════════════════════════════════════════

class Settings(BaseSettings):
    """
    Central config class.
    Reads from environment variables and .env file.
    Priority: env vars > .env file > defaults
    """
    model_config = SettingsConfigDict(
        env_file=".env",              # load from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,         # APP_NAME == app_name
        extra="ignore",               # ignore unknown env vars
    )

    # ─── App Info ───
    app_name:        str = "My FastAPI App"
    app_version:     str = "1.0.0"
    app_description: str = "Production FastAPI Application"
    environment:     Environment = Environment.DEVELOPMENT
    debug:           bool = False

    # ─── Server ───
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = True

    # ─── CORS ───
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    allowed_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    # ─── Nested settings (auto-populated from env prefix) ───
    # DB_HOST, DB_PORT, DB_NAME, etc.
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis:    RedisSettings    = Field(default_factory=RedisSettings)
    jwt:      JWTSettings      = Field(default_factory=JWTSettings)

    # ─── Feature Flags ───
    enable_docs:       bool = True    # False in prod to hide Swagger
    enable_cache:      bool = True
    enable_rate_limit: bool = True
    max_upload_size_mb: int = 10

    # ─── External APIs ───
    openai_api_key:    Optional[str] = None
    anthropic_api_key: Optional[str] = None
    sendgrid_api_key:  Optional[str] = None
    sentry_dsn:        Optional[str] = None

    # ─── Validators ───
    @field_validator("workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        import os
        cpu = os.cpu_count() or 1
        if v > cpu * 2:
            raise ValueError(f"workers={v} too high. CPU count={cpu}")
        return v

    @model_validator(mode="after")
    def production_checks(self) -> "Settings":
        """Enforce production requirements."""
        if self.environment == Environment.PRODUCTION:
            if self.debug:
                raise ValueError("debug must be False in production")
            if self.enable_docs:
                raise ValueError("Disable Swagger docs in production (enable_docs=False)")
            if not self.sentry_dsn:
                import warnings
                warnings.warn("No SENTRY_DSN set for production!", stacklevel=2)
        return self

    # ─── Convenience properties ───
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def docs_url(self) -> Optional[str]:
        return "/docs" if self.enable_docs else None

    @property
    def redoc_url(self) -> Optional[str]:
        return "/redoc" if self.enable_docs else None


# ═══════════════════════════════════════════════════════
# SECTION 4: Settings Singleton with @lru_cache
# ═══════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load settings ONCE and cache.
    @lru_cache ensures settings are not reloaded on every request.

    To override in tests:
        app.dependency_overrides[get_settings] = lambda: Settings(debug=True, ...)
        # OR
        get_settings.cache_clear()  # force reload after os.environ changes
    """
    return Settings()


# Type alias for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]


# ═══════════════════════════════════════════════════════
# SECTION 5: Environment-specific .env files
# ═══════════════════════════════════════════════════════

# Typically you have:
#
# .env                  ← local development (gitignored)
# .env.example          ← template committed to git
# .env.staging          ← staging environment
# .env.production       ← production (managed via secrets manager)
#
# Load the right file based on ENVIRONMENT:
#
# def get_settings() -> Settings:
#     env = os.getenv("ENVIRONMENT", "development")
#     env_file = f".env.{env}" if env != "development" else ".env"
#     return Settings(_env_file=env_file)

# Example .env file content (create this file):
ENV_FILE_EXAMPLE = """
# .env — copy this to .env and fill in values
# Never commit .env with real secrets!

APP_NAME=My FastAPI App
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=true
ENABLE_DOCS=true

DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp_dev
DB_USER=postgres
DB_PASSWORD=secret
DB_POOL_SIZE=5

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_TTL_SECONDS=300

JWT_SECRET_KEY=my-dev-secret-key-at-least-32-chars
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
SENTRY_DSN=https://...@sentry.io/...
"""

# Write example .env if it doesn't exist
env_example_path = Path(".env.example")
if not env_example_path.exists():
    env_example_path.write_text(ENV_FILE_EXAMPLE.strip())
    print("✅ Created .env.example")


# ═══════════════════════════════════════════════════════
# SECTION 6: Docker Secrets Pattern
# ═══════════════════════════════════════════════════════

def read_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read from Docker secret file or environment variable.
    Docker mounts secrets at /run/secrets/<name>.
    """
    secret_file = Path(f"/run/secrets/{name}")
    if secret_file.exists():
        return secret_file.read_text().strip()
    return os.getenv(name.upper(), default)

# Usage:
# db_password = read_secret("db_password")
# jwt_secret  = read_secret("jwt_secret_key")


# ═══════════════════════════════════════════════════════
# SECTION 7: FastAPI App using Settings
# ═══════════════════════════════════════════════════════

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    print(f"🚀 Starting '{s.app_name}' v{s.app_version}")
    print(f"   Environment: {s.environment.value}")
    print(f"   Debug: {s.debug}")
    print(f"   DB: {s.database.host}:{s.database.port}/{s.database.name}")
    print(f"   Redis: {s.redis.host}:{s.redis.port}")
    print(f"   Docs: {s.docs_url}")
    yield
    print(f"🛑 '{s.app_name}' shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    docs_url=settings.docs_url,         # None = disabled
    redoc_url=settings.redoc_url,
    lifespan=lifespan,
)


# ─── Routes that USE settings via dependency ───

@app.get("/", tags=["Root"])
async def root(s: SettingsDep):
    return {
        "app": s.app_name,
        "version": s.app_version,
        "environment": s.environment.value,
        "debug": s.debug,
    }


@app.get("/config", tags=["Config"])
async def show_config(s: SettingsDep):
    """Show non-sensitive config (never show secrets in production)."""
    if s.is_production:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Config endpoint disabled in production")

    return {
        "environment": s.environment.value,
        "debug": s.debug,
        "docs_enabled": s.enable_docs,
        "cache_enabled": s.enable_cache,
        "rate_limit_enabled": s.enable_rate_limit,
        "max_upload_mb": s.max_upload_size_mb,
        "database": {
            "host": s.database.host,
            "port": s.database.port,
            "name": s.database.name,
            "pool_size": s.database.pool_size,
        },
        "redis": {
            "host": s.redis.host,
            "port": s.redis.port,
            "ttl_seconds": s.redis.ttl_seconds,
        },
        "jwt": {
            "algorithm": s.jwt.algorithm,
            "access_expire_minutes": s.jwt.access_token_expire_minutes,
            "refresh_expire_days": s.jwt.refresh_token_expire_days,
        },
        "cors_origins": s.allowed_origins,
    }


@app.get("/feature-flags", tags=["Config"])
async def feature_flags(s: SettingsDep):
    return {
        "docs": s.enable_docs,
        "cache": s.enable_cache,
        "rate_limit": s.enable_rate_limit,
        "is_production": s.is_production,
        "has_openai": bool(s.openai_api_key),
        "has_anthropic": bool(s.anthropic_api_key),
        "has_sentry": bool(s.sentry_dsn),
    }


# ─── Settings override in tests ───
# In conftest.py:
#
# from 08_pydantic_settings_config import app, get_settings, Settings
#
# def override_settings():
#     return Settings(
#         environment=Environment.TESTING,
#         debug=True,
#         enable_docs=True,
#         database=DatabaseSettings(name="test_db"),
#         jwt=JWTSettings(secret_key="test-secret-key-32-characters-long"),
#     )
#
# app.dependency_overrides[get_settings] = override_settings
# # OR use monkeypatch:
# def test_with_env(monkeypatch):
#     monkeypatch.setenv("DEBUG", "true")
#     monkeypatch.setenv("APP_NAME", "Test App")
#     get_settings.cache_clear()     # force reload
#     settings = get_settings()
#     assert settings.debug is True


# ═══════════════════════════════════════════════════════
# SECTION 8: Interview Q&A
# ═══════════════════════════════════════════════════════

"""
Q1: pydantic-settings kya hai? BaseSettings kab use karte hain?
    pydantic-settings: env vars ko type-safe config objects mein load karta hai.
    BaseSettings = BaseModel + env var reading.
    Use karo jab: app config, DB urls, API keys, feature flags .env se read karne ho.

Q2: @lru_cache(maxsize=1) settings pe kyun lagate hain?
    Settings ko ek baar load karna chahiye — har request pe nahi.
    @lru_cache ensures single instance throughout app lifetime.
    Tests mein: get_settings.cache_clear() se force reload karo.

Q3: env vars priority kya hai?
    1. Environment variables (highest)
    2. .env file
    3. Default values in Settings class (lowest)
    Real env vars always override .env file values.

Q4: Production mein secrets kaise manage karte hain?
    Options: AWS Secrets Manager, HashiCorp Vault, Docker secrets, K8s secrets.
    Never commit .env with real secrets — use .env.example as template.
    Read from /run/secrets/<name> for Docker secrets.

Q5: Multiple environments kaise handle karte hain?
    ENVIRONMENT=production python command set karo.
    Settings mein @model_validator se production checks enforce karo.
    .env.production, .env.staging, .env.development separate files raho.

Q6: Nested settings kaise kaam kati hain?
    Separate BaseSettings class with env_prefix banao.
    DB_HOST, DB_PORT etc. → DatabaseSettings(env_prefix="DB_").
    Main Settings mein Field(default_factory=DatabaseSettings) se nest karo.
"""


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "08_pydantic_settings_config:app",
        host=s.host,
        port=8007,
        reload=s.reload and s.is_development,
    )
