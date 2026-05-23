# FastAPI — Pydantic Settings + Alembic Migrations

## Quick Concepts
- **pydantic-settings** = `.env` file → Python class — type-safe config
- **BaseSettings** = environment variables ko Pydantic model mein load karo
- **`@lru_cache`** = settings ko cache karo — har request par re-read nahi
- **Alembic** = SQLAlchemy ka database migration tool
- **autogenerate** = models se migration script auto-generate
- **`env.py`** = Alembic ka heart — DB connection + migration run logic

---

## Interview Questions & Answers

### Q1: Pydantic Settings kya hai? `os.environ.get()` se better kyu hai?

**Answer:**
```python
# BAD — os.environ (no type safety, no validation, no defaults)
import os
DATABASE_URL = os.environ.get("DATABASE_URL")  # str | None — koi guarantee nahi
SECRET_KEY   = os.environ.get("SECRET_KEY", "")  # default empty string → insecure

# GOOD — pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, field_validator
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Required — app will CRASH at startup if missing (fail-fast)
    secret_key: str
    database_url: PostgresDsn       # validates PostgreSQL URL format

    # Optional with defaults
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int   = 7

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

@lru_cache(maxsize=1)   # singleton — load once, reuse everywhere
def get_settings() -> Settings:
    return Settings()

# FastAPI Dependency
from typing import Annotated
from fastapi import Depends
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Route mein use
@app.get("/info")
async def info(settings: SettingsDep):
    return {"debug": settings.debug, "version": "1.0"}
```

**Advantages:**
- Type safety — `database_url: PostgresDsn` validates format
- Fail-fast — missing required vars crash at startup, not runtime
- IDE autocomplete
- Nested config — `DatabaseSettings`, `RedisSettings` as sub-models

---

### Q2: Nested Settings kaise banate hain? Multiple `.env` prefix?

**Answer:**
```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://localhost/mydb"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False           # True = print all SQL queries

class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"
    max_connections: int = 20

class JWTSettings(BaseModel):
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_expire_minutes: int = 30
    refresh_expire_days: int = 7

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__")
    #  env_nested_delimiter="__" means:
    #  DATABASE__URL=... → settings.database.url
    #  REDIS__URL=...    → settings.redis.url

    app_name: str = "MyAPI"
    debug: bool   = False

    database: DatabaseSettings = DatabaseSettings()
    redis:    RedisSettings    = RedisSettings()
    jwt:      JWTSettings      = JWTSettings()

# .env file:
# DATABASE__URL=postgresql+asyncpg://user:pass@localhost/mydb
# DATABASE__POOL_SIZE=20
# REDIS__URL=redis://redis:6379/0
# JWT__SECRET_KEY=super-secret-key-min-32-chars

# Environment-specific
class ProductionSettings(Settings):
    debug: bool = False

    @field_validator("jwt")
    @classmethod
    def validate_jwt_prod(cls, v):
        if v.secret_key == "change-me":
            raise ValueError("Change JWT secret key in production!")
        return v
```

---

### Q3: Alembic kya hai? Manual migration vs autogenerate fark?

**Answer:**
```
Alembic = database schema version control
  - SQLAlchemy models change karoge → DB schema automatically update
  - Rollback possible — down() function
  - Migration history — har change tracked

Manual migration:
  op.add_column("users", sa.Column("phone", sa.String(20)))
  → apne aap likhna parta hai

Autogenerate (recommended):
  alembic revision --autogenerate -m "add phone to users"
  → Alembic compares current models vs DB → migration script generate
```

```python
# alembic/env.py — async setup
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool
from alembic import context
from app.models import Base  # sabhi models import

config = context.config

def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=NullPool,   # NullPool: migration ke liye — connection reuse nahi
    )

    async def do_run_migrations(connection):
        context.configure(connection=connection, target_metadata=Base.metadata)
        async with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(run_async_migrations())

run_migrations_online()
```

**CLI Commands:**
```bash
alembic init alembic                         # project setup
alembic revision --autogenerate -m "message" # create migration
alembic upgrade head                         # apply all
alembic upgrade +1                           # apply next one
alembic downgrade -1                         # rollback one
alembic history --verbose                    # show all migrations
alembic current                              # current DB version
```

---

### Q4: Migration mein data migration (backfill) kaise karte hain?

**Answer:**
```python
# migrations/versions/003_backfill_slug.py

def upgrade():
    # Step 1: Add column (nullable first)
    op.add_column("posts", sa.Column("slug", sa.String(300), nullable=True))

    # Step 2: Backfill — data migrate karo
    connection = op.get_bind()
    posts = connection.execute(sa.text("SELECT id, title FROM posts")).fetchall()
    for post_id, title in posts:
        slug = title.lower().replace(" ", "-")[:280]
        connection.execute(
            sa.text("UPDATE posts SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": post_id}
        )

    # Step 3: Make NOT NULL after backfill
    op.alter_column("posts", "slug", nullable=False)

    # Step 4: Add unique constraint
    op.create_unique_constraint("uq_posts_slug", "posts", ["slug"])

def downgrade():
    op.drop_constraint("uq_posts_slug", "posts")
    op.drop_column("posts", "slug")
```

**INTERVIEW: Migration best practices?**
1. Schema change + data migration = 2 separate migrations
2. Add column nullable → backfill → make not null (zero-downtime)
3. Never edit old migration files (already applied in production)
4. Test migrations: `alembic upgrade head` + `alembic downgrade base`

---

### Q5: Alembic ko FastAPI lifespan mein integrate kaise karte hain?

**Answer:**
```python
from contextlib import asynccontextmanager
from alembic.config import Config
from alembic import command

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run pending migrations at startup
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")  # blocking — ok in lifespan

    yield

    # Cleanup on shutdown
    await engine.dispose()
```

**INTERVIEW: Production mein lifespan migration theek hai kya?**
- Single instance: OK
- Multiple instances (K8s, load balancer): Use init container ya CI/CD migration step
- Race condition possible — dono instances simultaneously migrate karne ki koshish karen

---

## Summary Table

| Feature | pydantic-settings | os.environ |
|---------|------------------|------------|
| Type safety | ✅ | ❌ |
| Validation | ✅ field_validator | ❌ |
| Fail-fast (startup) | ✅ | ❌ (runtime) |
| Nested config | ✅ `__` delimiter | ❌ |
| `.env` file support | ✅ built-in | ❌ need python-dotenv |
| IDE autocomplete | ✅ | ❌ |
| Caching (`@lru_cache`) | ✅ | N/A |

| Alembic Command | Effect |
|----------------|--------|
| `revision --autogenerate` | Model diff se migration create |
| `upgrade head` | All pending migrations apply |
| `downgrade -1` | Last migration rollback |
| `history` | All migrations list |
| `current` | DB ka current version |
