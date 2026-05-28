# Library Comparisons — Which to Use for What

## Quick Concepts

**WHY know library options:**
- Interview: "Why X over Y?"
- Right tool = 10x productivity
- Avoid trends (boring tech often best)

**HOW evaluate:**
- Maintenance status (last commit, issues, contributors)
- Performance
- Ecosystem compatibility
- Learning curve
- Documentation quality

---

## Library Comparisons by Category

### HTTP Clients

| Library | Sync | Async | HTTP/2 | Use Case |
|---|---|---|---|---|
| **requests** | ✅ | ❌ | ❌ | Simple sync scripts |
| **httpx** ⭐ | ✅ | ✅ | ✅ | Modern (FastAPI default) |
| **aiohttp** | ❌ | ✅ | Limited | Async server + client |
| **urllib3** | ✅ | ❌ | ❌ | Low-level (rarely direct use) |

**Recommendation:** Use **httpx** for new projects.

```python
# requests (sync, legacy)
import requests
r = requests.get("https://api.example.com")

# httpx (modern, sync OR async)
import httpx
# Sync
r = httpx.get("https://api.example.com")
# Async
async with httpx.AsyncClient() as client:
    r = await client.get("https://api.example.com")
```

---

### JSON Libraries

| Library | Speed | Features | Use Case |
|---|---|---|---|
| **json** (stdlib) | Slow | Basic | Default, no deps |
| **orjson** ⭐ | Fastest | Native datetime, dataclass | Modern apps |
| **ujson** | Fast | Simple | Legacy |
| **msgpack** | Fast | Binary, smaller | Internal services |
| **simplejson** | Slow | Extra features | Decimal handling |

**Recommendation:** Use **orjson** for speed, **msgpack** for binary.

```python
# orjson (3-5x faster than json)
import orjson
data = orjson.dumps({"key": "value", "now": datetime.now()})  # bytes
parsed = orjson.loads(data)
```

---

### Async ORMs

| ORM | Async | Style | Use Case |
|---|---|---|---|
| **SQLAlchemy 2.0** ⭐ | ✅ | Most flexible | Production standard |
| **Tortoise ORM** | ✅ | Django-like | Familiar Django users |
| **Beanie** | ✅ | Pydantic-based | MongoDB |
| **Prisma** | ✅ | Schema-first | TypeScript-like |
| **encode/databases** | ✅ | Low-level | Raw SQL with async |

**Recommendation:** **SQLAlchemy 2.0** for SQL, **Beanie** for MongoDB.

```python
# SQLAlchemy 2.0 async
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select

engine = create_async_engine("postgresql+asyncpg://...")

async with AsyncSession(engine) as session:
    result = await session.execute(select(User).where(User.id == 1))
    user = result.scalar_one()
```

---

### Data Validation

| Library | Speed | Use Case |
|---|---|---|
| **Pydantic v2** ⭐ | Rust-fast | Modern (FastAPI standard) |
| **Pydantic v1** | Slower | Legacy |
| **marshmallow** | Slower | Flask ecosystem |
| **attrs** | Fast | Internal classes |
| **dataclasses** (stdlib) | Fast | Simple cases |
| **msgspec** | Fastest | Performance critical |

**Recommendation:** **Pydantic v2** for APIs, **dataclasses** for internal.

```python
# Pydantic v2 (best for APIs)
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    id: int
    email: EmailStr
    name: str

user = User(id=1, email="a@x.com", name="Alice")
user.model_dump_json()
```

---

### Dates / Time

| Library | Style | Pros | Cons |
|---|---|---|---|
| **datetime** (stdlib) | Verbose | No deps | Awkward API |
| **dateutil** | Helpful | Parse anything | Stdlib + this |
| **arrow** | Friendly | Easier API | Extra dep |
| **pendulum** ⭐ | Best | Timezone-aware, fast | Active maintenance |
| **whenever** | Modern | Type-safe | New (2024) |

**Recommendation:** Use **datetime + dateutil** for stdlib; **pendulum** if you want better API.

```python
# Pendulum (cleaner)
import pendulum

now = pendulum.now("UTC")
ist = now.in_timezone("Asia/Kolkata")
tomorrow = now.add(days=1)
duration = now.diff_for_humans()  # "in 1 day"
```

---

### Background Tasks

| Library | Use Case | Pros | Cons |
|---|---|---|---|
| **Celery** | Heavy production | Mature, features | Complex |
| **ARQ** ⭐ (FastAPI) | Async-native | Simple, Redis | Less features |
| **RQ** | Simple Redis | Easy setup | Sync only |
| **Dramatiq** | Modern | Good defaults | Smaller community |
| **Huey** | Lightweight | Minimal | Limited |
| **APScheduler** | Cron jobs | Simple scheduling | Not distributed |

**Recommendation:** **ARQ** for async, **Celery** for complex workflows.

```python
# ARQ (async, Redis-based)
from arq import create_pool, Worker
from arq.connections import RedisSettings

async def send_email(ctx, to: str):
    # Task implementation
    pass

class WorkerSettings:
    functions = [send_email]
    redis_settings = RedisSettings()

# Run: arq myapp.WorkerSettings
```

---

### Testing

| Library | Use Case |
|---|---|
| **pytest** ⭐ | Industry standard |
| **unittest** (stdlib) | Classic |
| **pytest-asyncio** | Async tests |
| **pytest-cov** | Coverage |
| **pytest-mock** | Easier mocking |
| **hypothesis** | Property testing |
| **factory-boy** | Test data factories |
| **respx** | Mock httpx |
| **freezegun** | Freeze time |

**Recommendation:** **pytest + pytest-asyncio + pytest-cov** baseline.

```python
# pytest async
import pytest

@pytest.mark.asyncio
async def test_endpoint(client):
    response = await client.get("/users/1")
    assert response.status_code == 200
```

---

### Logging

| Library | Use Case |
|---|---|
| **logging** (stdlib) | Default |
| **structlog** ⭐ | Structured production |
| **loguru** | Simple, beautiful |
| **picologging** | Faster (drop-in) |

**Recommendation:** **structlog** for production, **loguru** for scripts.

```python
# structlog (structured)
import structlog

log = structlog.get_logger()
log.info("user_login", user_id=42, ip="1.2.3.4")
# {"event": "user_login", "user_id": 42, "ip": "1.2.3.4"}
```

---

### Configuration

| Library | Use Case |
|---|---|
| **os.environ** | Simple env vars |
| **python-dotenv** | .env files |
| **pydantic-settings** ⭐ | Typed config |
| **dynaconf** | Complex multi-env |
| **hydra** | ML/research |

**Recommendation:** **pydantic-settings** for typed config.

```python
# Pydantic Settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()  # Reads from env / .env
```

---

### Dependency Injection

| Library | Use Case |
|---|---|
| **manual** | Simple projects |
| **dependency-injector** | Complex DI |
| **wired** | Lightweight |
| **FastAPI's Depends** ⭐ | FastAPI apps |

**Recommendation:** Use **FastAPI's Depends** for FastAPI; manual otherwise.

```python
# FastAPI dependency injection
from fastapi import Depends, FastAPI

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

@app.get("/users/{id}")
async def get_user(id: int, db: AsyncSession = Depends(get_db)):
    return await db.get(User, id)
```

---

### Caching

| Library | Use Case |
|---|---|
| **functools.lru_cache** | In-memory, single process |
| **functools.cache** (3.9+) | Unbounded cache |
| **cachetools** | TTL cache |
| **redis** ⭐ | Distributed |
| **diskcache** | Persistent local |
| **aiocache** | Async multi-backend |

**Recommendation:** **lru_cache** for local; **redis** for distributed.

```python
# Local cache
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive(x):
    return x * x

# Distributed (Redis)
import redis
r = redis.Redis()
r.setex("key", 300, "value")  # 5 min TTL
```

---

### Web Frameworks

| Framework | Use Case |
|---|---|
| **FastAPI** ⭐ | Modern async APIs |
| **Django** | Full-stack monolith |
| **Flask** | Simple APIs |
| **Starlette** | Lightweight ASGI |
| **Sanic** | Performance focus |
| **aiohttp** | Async server |
| **Litestar** | Modern FastAPI alternative |
| **Quart** | Async Flask |

**Recommendation:** **FastAPI** for APIs, **Django** for full-stack.

---

### CLI Frameworks

| Framework | Use Case |
|---|---|
| **argparse** (stdlib) | Simple |
| **Click** | Mature decorator-based |
| **Typer** ⭐ | Modern type-based |
| **Fire** | Auto-CLI from class |
| **docopt** | Help-text first |

**Recommendation:** **Typer** for new projects.

---

### Image Processing

| Library | Use Case |
|---|---|
| **Pillow** ⭐ | General purpose |
| **OpenCV** | Computer vision |
| **scikit-image** | Scientific |
| **wand** | ImageMagick wrapper |

**Recommendation:** **Pillow** for basic, **OpenCV** for CV.

```python
from PIL import Image

img = Image.open("photo.jpg")
img.thumbnail((300, 300))
img.save("thumb.jpg")
```

---

### Markdown / Templating

| Library | Use Case |
|---|---|
| **markdown** | Basic Markdown |
| **markdown-it-py** ⭐ | Fast, CommonMark |
| **Jinja2** | HTML templating |
| **mako** | Alternative templates |
| **Mistune** | Fast Markdown |

---

### Data Analysis

| Library | Use Case |
|---|---|
| **pandas** | Tabular data |
| **polars** ⭐ | Pandas alternative (Rust) |
| **numpy** | Numeric arrays |
| **scipy** | Scientific computing |
| **pyarrow** | Apache Arrow / Parquet |

**Recommendation:** **pandas** standard, **polars** for performance.

```python
# Polars (faster than pandas)
import polars as pl

df = pl.read_csv("data.csv")
result = df.filter(pl.col("age") > 18).group_by("country").agg(pl.col("salary").mean())
```

---

### Environment Management

| Tool | Use Case |
|---|---|
| **venv** (stdlib) | Basic |
| **virtualenv** | More features |
| **conda** | Scientific |
| **pyenv** | Python version mgmt |
| **uv** ⭐ | Fast, modern |
| **rye** | Workflow tool |

**Recommendation:** **uv** for speed.

```bash
# uv (Rust-based, very fast)
uv venv
uv pip install fastapi
uv pip install -e .
```

---

### Package Managers

| Tool | Use Case |
|---|---|
| **pip** | Default |
| **pip-tools** | Lockfile |
| **Poetry** | Full mgmt |
| **PDM** | PEP-aligned |
| **uv** ⭐ | Modern, fastest |
| **Hatch** | Project mgmt |

**Recommendation:** **uv** for speed; **Poetry** if you need extensive features.

---

### Code Quality

| Tool | Use Case |
|---|---|
| **ruff** ⭐ | Fast linter + formatter (Rust) |
| **black** | Code formatter |
| **flake8** | Linter (legacy) |
| **pylint** | Comprehensive linter |
| **isort** | Import sorter |
| **mypy** ⭐ | Type checker |
| **pyright** | Faster type checker |
| **pyflakes** | Simple checks |

**Recommendation:** **ruff + mypy** baseline.

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
strict = true
```

---

### Documentation

| Tool | Use Case |
|---|---|
| **Sphinx** | Classic, comprehensive |
| **MkDocs + Material** ⭐ | Modern, beautiful |
| **pdoc** | Auto from docstrings |
| **portray** | Sphinx wrapper |
| **GitBook** | Hosted |

**Recommendation:** **MkDocs Material** for modern projects.

---

### Code Quality Beyond Linting

| Tool | Use Case |
|---|---|
| **bandit** | Security linting |
| **safety** | CVE checking |
| **pip-audit** | Vulnerability scan |
| **pre-commit** | Git hooks |
| **vulture** | Dead code |
| **interrogate** | Docstring coverage |

---

### Async Database Drivers

| Driver | Database |
|---|---|
| **asyncpg** ⭐ | PostgreSQL (fastest) |
| **psycopg3** | PostgreSQL (versatile) |
| **aiomysql** | MySQL |
| **motor** | MongoDB |
| **aioredis** / **redis.asyncio** | Redis |
| **aiosqlite** | SQLite |
| **databases** | Multi-DB wrapper |

---

### Monitoring / Observability

| Tool | Use Case |
|---|---|
| **prometheus-client** | Metrics |
| **OpenTelemetry** ⭐ | Tracing + Metrics + Logs |
| **Sentry SDK** | Error tracking |
| **structlog** | Logs |
| **Datadog SDK** | Datadog APM |
| **New Relic SDK** | New Relic APM |

---

## Decision Matrix — Common Scenarios

### "Build a REST API"

```python
# Modern stack
FastAPI + Pydantic v2 + SQLAlchemy 2.0 async +
asyncpg + Redis + structlog + orjson + httpx +
pytest + ruff + mypy
```

### "Background tasks"

```python
# Async (FastAPI ecosystem)
ARQ + Redis

# Heavy production (any stack)
Celery + RabbitMQ/Redis + Flower (monitoring)
```

### "Data processing pipeline"

```python
# Pure Python
polars + pyarrow (fast)
OR pandas (familiar)

# Distributed
Dask or Ray
```

### "ML training"

```python
PyTorch + Lightning + Weights&Biases
+ DVC (data versioning) + MLflow (tracking)
```

### "Microservice"

```python
FastAPI / gRPC + Pydantic + structlog +
OpenTelemetry + asyncpg + Redis + Sentry
```

### "CLI tool"

```python
Typer + Rich + Questionary (interactive) +
pytest + Click for testing
```

---

## Library Selection Cheatsheet

```markdown
### Modern Python Stack (2024+)

Web:        FastAPI
Validation: Pydantic v2
ORM:        SQLAlchemy 2.0 (async)
DB driver:  asyncpg (Postgres) / motor (Mongo)
Cache:      Redis (aioredis or redis.asyncio)
HTTP:       httpx
Async tasks: ARQ
JSON:       orjson
Logging:    structlog
Config:     pydantic-settings
Testing:    pytest + pytest-asyncio
Linting:    ruff
Types:      mypy
Docs:       MkDocs Material
Packaging:  uv or hatch
Auth:       python-jose (JWT)
CLI:        Typer
Terminal:   Rich
Date:       pendulum (optional)
```

---

## Performance Hierarchy (Speed-Critical Cases)

```
1. Pure Python                  → 1x (baseline)
2. + functools.cache            → 10-100x (cached calls)
3. + asyncio (uvloop)           → 5-10x (I/O bound)
4. + NumPy/Pandas vectorization → 10-100x (numeric)
5. + orjson, httpx, asyncpg     → 2-5x each (library swap)
6. + Cython / Numba             → 10-100x (hot loops)
7. + Rust (PyO3) extension      → 10-1000x (specific functions)
8. + Rewrite in Go/Rust         → 10-100x (whole service)
```

---

## Anti-Patterns (Don't Use)

| Avoid | Reason |
|---|---|
| **requests in async** | Blocks event loop, use httpx |
| **psycopg2 in async** | Use asyncpg/psycopg3 |
| **Pydantic v1** | v2 is 10x faster |
| **stdlib json for big data** | Use orjson |
| **Flask 1.x** | Use Flask 2.x or FastAPI |
| **time.sleep in async** | Use asyncio.sleep |
| **threading for CPU** | GIL — use multiprocessing |
| **pylint for new project** | Use ruff (faster) |
| **black + isort + flake8** | Use ruff (one tool) |
| **setup.py** | Use pyproject.toml |
```
