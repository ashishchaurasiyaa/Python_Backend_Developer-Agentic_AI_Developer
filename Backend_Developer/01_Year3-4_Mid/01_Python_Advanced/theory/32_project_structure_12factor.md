# Project Structure + 12-Factor App

## Quick Concepts

**WHAT:**
- **Project structure** = How to organize code files/folders
- **12-Factor App** = Methodology for cloud-native apps
- **src/ layout** = Code in src/ folder (vs flat)
- **Application factory** = Function that creates app instance
- **Settings management** = Config separate from code

**WHY structure matters:**
- Easy to navigate
- Easy to test
- Easy to deploy
- Easy to onboard

**HOW typical layers:**
```
Project/
├── src/                  # Application code
├── tests/                # Tests
├── docs/                 # Documentation
├── scripts/              # Build/deploy scripts
├── pyproject.toml        # Project config
├── README.md
└── .gitignore
```

---

## Interview Questions & Answers

### Q1: Project structure for web app?

**Answer:**

**HOW — FastAPI app structure (recommended):**

```
myapp/
├── src/
│   └── myapp/
│       ├── __init__.py
│       ├── main.py                # FastAPI app
│       ├── config.py              # Settings
│       │
│       ├── api/                   # API routes
│       │   ├── __init__.py
│       │   ├── deps.py            # Dependencies
│       │   ├── v1/
│       │   │   ├── __init__.py
│       │   │   ├── users.py       # User routes
│       │   │   ├── orders.py
│       │   │   └── auth.py
│       │   └── v2/                # New version
│       │
│       ├── core/                  # Business logic
│       │   ├── __init__.py
│       │   ├── security.py
│       │   └── exceptions.py
│       │
│       ├── domain/                # Domain models
│       │   ├── __init__.py
│       │   ├── user.py
│       │   └── order.py
│       │
│       ├── services/              # Service layer
│       │   ├── __init__.py
│       │   ├── user_service.py
│       │   ├── order_service.py
│       │   └── email_service.py
│       │
│       ├── repositories/          # Data access
│       │   ├── __init__.py
│       │   ├── user_repo.py
│       │   └── order_repo.py
│       │
│       ├── db/                    # Database
│       │   ├── __init__.py
│       │   ├── session.py
│       │   ├── base.py            # Base ORM class
│       │   └── models/
│       │       ├── user.py
│       │       └── order.py
│       │
│       ├── schemas/               # Pydantic models
│       │   ├── __init__.py
│       │   ├── user.py
│       │   └── order.py
│       │
│       ├── workers/               # Background tasks
│       │   ├── __init__.py
│       │   └── email_worker.py
│       │
│       └── utils/                 # Utilities
│           ├── __init__.py
│           └── logger.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   └── test_services.py
│   ├── integration/
│   │   └── test_api.py
│   └── e2e/
│       └── test_full_flow.py
│
├── migrations/                    # Alembic
│   ├── env.py
│   └── versions/
│
├── scripts/                       # Utility scripts
│   ├── seed_db.py
│   └── deploy.sh
│
├── docs/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
└── Makefile
```

---

### Q2: 12-Factor App principles?

**Answer:**

**WHAT:** Methodology for SaaS apps (Heroku, 2011).

**HOW — 12 principles:**

**1. Codebase — One codebase, many deploys**
```
Same code: dev, staging, prod
Different config per env
```

**2. Dependencies — Explicitly declared**
```python
# pyproject.toml — explicit deps
[project]
dependencies = [
    "fastapi==0.100.0",     # Pinned versions
    "pydantic==2.0.0",
]
```

**3. Config — Store in environment**
```python
# ❌ BAD
DATABASE_URL = "postgresql://prod-server/db"  # Hardcoded

# ✅ GOOD
import os
DATABASE_URL = os.environ["DATABASE_URL"]


# Better: pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

**4. Backing Services — Treat as attached resources**
```python
# Switch DB without code change
# DATABASE_URL=postgresql://local/db
# DATABASE_URL=postgresql://prod.aws.com/db
# Same code, different URL
```

**5. Build, Release, Run — Strict separation**
```
1. Build:   Code + deps → artifact (Docker image)
2. Release: Artifact + config = release
3. Run:     Execute release in environment
```

**6. Processes — Stateless**
```python
# ❌ Local file storage
def save_upload(file):
    file.save("/tmp/uploads/")  # ⚠️ Lost on restart!


# ✅ Use S3 / object storage
def save_upload(file):
    s3.upload_fileobj(file, "my-bucket", "uploads/...")
```

**7. Port binding — Self-contained**
```python
# App brings its own server
# Not behind Apache/IIS
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

**8. Concurrency — Scale via processes**
```bash
# Horizontal scale: more processes
# Vertical: bigger machines

# Production: gunicorn workers
gunicorn app:app --workers 4
```

**9. Disposability — Fast startup + graceful shutdown**
```python
# Quick boot
# Handle SIGTERM properly
import signal
import sys

def shutdown(signum, frame):
    print("Cleaning up...")
    # Close connections, finish requests
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
```

**10. Dev/Prod Parity — Keep similar**
```
Same database (PostgreSQL)
Same Redis
Same Python version
Use Docker for consistency
```

**11. Logs — Stream to stdout**
```python
# ❌ Don't write to files
log.handler = FileHandler("/var/log/app.log")

# ✅ Stream to stdout
import logging
log.addHandler(logging.StreamHandler())
# Let infrastructure handle aggregation (CloudWatch, etc.)
```

**12. Admin Processes — One-off tasks**
```bash
# Same release, run admin task
docker run myapp:1.0 python manage.py migrate
docker run myapp:1.0 python manage.py shell
```

---

### Q3: Application Factory pattern?

**Answer:**

**WHAT:** Function that creates app instance.

**WHY:**
- Multiple instances (testing)
- Different configs
- Lazy initialization

**HOW — FastAPI factory:**

```python
# src/myapp/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from myapp.config import Settings
from myapp.api.v1 import users, orders
from myapp.core.middleware import RequestIDMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    settings = settings or Settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
    )

    # Middleware
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins)
    app.add_middleware(RequestIDMiddleware)

    # Routes
    app.include_router(users.router, prefix="/api/v1/users")
    app.include_router(orders.router, prefix="/api/v1/orders")

    # Startup/shutdown
    @app.on_event("startup")
    async def startup():
        # Initialize DB pool, Redis, etc.
        pass

    @app.on_event("shutdown")
    async def shutdown():
        # Cleanup
        pass

    return app


# Default app instance
app = create_app()
```

**HOW — Use in tests:**

```python
# tests/conftest.py
import pytest
from myapp.main import create_app
from myapp.config import Settings


@pytest.fixture
def app():
    """Test app with overridden settings."""
    test_settings = Settings(
        database_url="sqlite:///:memory:",
        debug=True,
        testing=True,
    )
    return create_app(settings=test_settings)


@pytest.fixture
async def client(app):
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

---

### Q4: Configuration management?

**Answer:**

**HOW — pydantic-settings (recommended):**

```python
# src/myapp/config.py
from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings — type-safe + auto from env."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "My App"
    version: str = "1.0.0"
    debug: bool = False
    environment: Literal["dev", "staging", "production"] = "dev"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: PostgresDsn

    # Redis
    redis_url: RedisDsn

    # JWT
    secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list[str] = Field(default_factory=list)

    # External services
    sentry_dsn: str | None = None
    aws_access_key: str | None = None
    aws_secret_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Singleton
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**HOW — Use:**

```python
from myapp.config import get_settings

settings = get_settings()
print(settings.database_url)

# In FastAPI dependency
from fastapi import Depends

@app.get("/info")
def info(settings: Settings = Depends(get_settings)):
    return {"app": settings.app_name, "env": settings.environment}
```

**HOW — .env file:**

```bash
# .env
DEBUG=true
ENVIRONMENT=dev

DATABASE_URL=postgresql://user:pass@localhost/myapp
REDIS_URL=redis://localhost:6379/0

SECRET_KEY=your-secret-here
CORS_ORIGINS=["http://localhost:3000","https://app.example.com"]

SENTRY_DSN=https://abc@sentry.io/123
```

**HOW — .env.example (committed):**

```bash
# .env.example — template (commit this, don't commit .env)
DATABASE_URL=postgresql://user:pass@host/dbname
REDIS_URL=redis://host:6379/0
SECRET_KEY=
```

---

### Q5: Settings per environment?

**Answer:**

**HOW — Environment-specific settings:**

```python
# src/myapp/config.py
from pydantic_settings import BaseSettings


class BaseAppSettings(BaseSettings):
    """Base settings shared across envs."""
    app_name: str = "My App"
    database_url: str
    secret_key: str


class DevSettings(BaseAppSettings):
    debug: bool = True
    environment: str = "dev"
    cors_origins: list[str] = ["http://localhost:3000"]


class StagingSettings(BaseAppSettings):
    debug: bool = False
    environment: str = "staging"
    cors_origins: list[str] = ["https://staging.example.com"]


class ProductionSettings(BaseAppSettings):
    debug: bool = False
    environment: str = "production"
    cors_origins: list[str] = ["https://app.example.com"]


# Pick based on env var
import os

def get_settings():
    env = os.getenv("ENVIRONMENT", "dev").lower()
    if env == "production":
        return ProductionSettings()
    elif env == "staging":
        return StagingSettings()
    return DevSettings()
```

---

### Q6: Service layer pattern?

**Answer:**

**WHAT:** Layer between API and database with business logic.

**WHY:**
- Separate concerns (API vs business vs data)
- Reusable (multiple endpoints can call)
- Testable in isolation

**HOW:**

```python
# src/myapp/api/v1/users.py (API layer — thin)
from fastapi import APIRouter, Depends, HTTPException
from myapp.schemas.user import UserCreate, UserResponse
from myapp.services.user_service import UserService

router = APIRouter()


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    service: UserService = Depends(),
):
    """API endpoint — delegates to service."""
    try:
        user = await service.create_user(user_data)
        return user
    except UserAlreadyExistsError as e:
        raise HTTPException(409, str(e))


# src/myapp/services/user_service.py (business logic)
from myapp.domain.user import User
from myapp.repositories.user_repo import UserRepository
from myapp.services.email_service import EmailService


class UserService:
    """Business logic for users."""

    def __init__(
        self,
        repo: UserRepository = Depends(),
        email_service: EmailService = Depends(),
    ):
        self.repo = repo
        self.email_service = email_service

    async def create_user(self, data: UserCreate) -> User:
        # Business rules
        if await self.repo.email_exists(data.email):
            raise UserAlreadyExistsError(data.email)

        # Hash password
        password_hash = hash_password(data.password)

        # Create user
        user = await self.repo.create(
            email=data.email,
            password_hash=password_hash,
            name=data.name,
        )

        # Side effect: send welcome email
        await self.email_service.send_welcome(user)

        return user


# src/myapp/repositories/user_repo.py (data access)
class UserRepository:
    """Database access — no business logic."""

    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def create(self, email: str, password_hash: str, name: str) -> User:
        user = User(email=email, password_hash=password_hash, name=name)
        self.db.add(user)
        await self.db.commit()
        return user

    async def email_exists(self, email: str) -> bool:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none() is not None
```

---

### Q7: Domain models vs DB models?

**Answer:**

**WHY separate:**
- Domain = business concepts (User, Order)
- DB = persistence concerns
- Decouple → can change DB without touching business

**HOW:**

```python
# src/myapp/domain/user.py (pure Python, no DB)
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    """Domain model — business logic only."""
    id: int
    email: str
    name: str
    created_at: datetime

    def can_edit(self, other: "User") -> bool:
        """Business rule."""
        return self.id == other.id


# src/myapp/db/models/user.py (DB-specific)
from sqlalchemy import Column, Integer, String, DateTime
from myapp.db.base import Base

class UserORM(Base):
    """Database model — ORM-specific."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    password_hash = Column(String)
    created_at = Column(DateTime)


# Repository converts between them
class UserRepository:
    async def get(self, user_id: int) -> User:
        # Fetch DB model
        orm = await self.db.get(UserORM, user_id)

        # Convert to domain
        return User(
            id=orm.id,
            email=orm.email,
            name=orm.name,
            created_at=orm.created_at,
        )
```

---

### Q8: Makefile for project tasks?

**Answer:**

**WHY:** Standard commands across projects.

**HOW:**

```makefile
# Makefile
.PHONY: install dev test lint format clean docker

install:
	uv pip install -e ".[dev]"

dev:
	uvicorn src.myapp.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/

clean:
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker build -t myapp:latest -f docker/Dockerfile .

docker-up:
	docker-compose -f docker/docker-compose.yml up

docker-down:
	docker-compose -f docker/docker-compose.yml down

migrate:
	alembic upgrade head

migrate-create:
	@read -p "Migration name: " name; \
	alembic revision --autogenerate -m "$$name"

deploy-staging:
	./scripts/deploy.sh staging

deploy-prod:
	./scripts/deploy.sh production

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Run dev server"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code"
```

**Usage:**

```bash
make install
make dev
make test
make lint
```

---

### Q9: Pre-commit hooks?

**Answer:**

**WHAT:** Run checks before git commit.

**HOW — Install:**

```bash
pip install pre-commit
```

**HOW — .pre-commit-config.yaml:**

```yaml
# .pre-commit-config.yaml
repos:
  # General
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key
      - id: debug-statements

  # Python linting + formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-redis]

  # Security
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']
```

**HOW — Install hooks:**

```bash
pre-commit install
# Now runs on every git commit

# Run manually
pre-commit run --all-files
```

---

### Q10: GitHub Actions CI/CD template?

**Answer:**

**HOW — Complete CI/CD:**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ["5432:5432"]
        options: --health-cmd=pg_isready

      redis:
        image: redis:7
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv pip install -e ".[dev]"

      - name: Lint
        run: |
          ruff check src/ tests/
          ruff format --check src/ tests/

      - name: Type check
        run: mypy src/

      - name: Test
        env:
          DATABASE_URL: postgresql://postgres:test@localhost/test
          REDIS_URL: redis://localhost:6379
        run: pytest --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Project Setup Checklist

```markdown
### Initial
- [ ] pyproject.toml (modern)
- [ ] src/ layout
- [ ] README.md
- [ ] LICENSE
- [ ] .gitignore (Python.gitignore template)
- [ ] .env.example
- [ ] Makefile

### Config
- [ ] pydantic-settings
- [ ] Environment-specific
- [ ] Secrets from env vars
- [ ] .env not committed

### Code Organization
- [ ] Layered (api/services/repos)
- [ ] Application factory
- [ ] Domain models separate from DB
- [ ] Dependency injection (FastAPI Depends)

### Quality
- [ ] ruff + mypy configured
- [ ] pre-commit hooks
- [ ] pytest with coverage
- [ ] CI on GitHub Actions
- [ ] Conventional commits

### Documentation
- [ ] README with quickstart
- [ ] CHANGELOG
- [ ] CONTRIBUTING (if OSS)
- [ ] API docs (MkDocs/Sphinx)
- [ ] Architecture diagram

### Deployment
- [ ] Dockerfile
- [ ] docker-compose for local dev
- [ ] Production-ready settings
- [ ] Health check endpoint
- [ ] Structured logging
- [ ] Error tracking (Sentry)
```

---

## Production-Ready Template Stack

```
Modern Python Project 2024+:

Code Quality:    ruff + mypy + pre-commit
Package Mgmt:    uv (or poetry)
Build Backend:   hatchling
Test:            pytest + pytest-asyncio + pytest-cov
API:             FastAPI + Pydantic v2
ORM:             SQLAlchemy 2.0 async + Alembic
DB:              PostgreSQL (asyncpg) + Redis
Async Tasks:     ARQ or Celery
Logging:         structlog
Config:          pydantic-settings
Auth:            python-jose (JWT)
HTTP Client:     httpx
JSON:            orjson
Docs:            MkDocs Material
CI/CD:           GitHub Actions
Container:       Docker + docker-compose
Deploy:          Kubernetes / ECS / Lambda
Monitoring:      Sentry + OpenTelemetry
Secrets:         AWS Secrets Manager / Vault
```
