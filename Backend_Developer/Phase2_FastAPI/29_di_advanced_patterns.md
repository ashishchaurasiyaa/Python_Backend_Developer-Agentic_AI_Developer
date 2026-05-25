# FastAPI Dependency Injection — Advanced Patterns

## Why It Matters

DI = FastAPI's superpower. Beyond basic `Depends`:
- **Sub-dependencies** → chain of deps
- **yield + try/finally** → transactional resources (DB sessions, locks)
- **Scope control** → cache per-request vs per-app
- **Class-based dependencies** → stateful, configurable
- **dependency_overrides** → testing without monkey-patching

Senior interview: "DB session lifecycle in FastAPI?" → `yield` dependency with rollback on exception.

---

## Core Concepts

### Basic Dependency

```python
from fastapi import Depends


def common_pagination(skip: int = 0, limit: int = 20):
    return {'skip': skip, 'limit': limit}


@app.get("/items")
def list_items(pagination=Depends(common_pagination)):
    return {'skip': pagination['skip'], 'limit': pagination['limit']}
```

### Sub-Dependencies (chained)

```python
def query_param_extractor(q: str = ""):
    return q


def fancy_query(q: str = Depends(query_param_extractor)):
    return f"FANCY:{q}"


@app.get("/items")
def list_items(q: str = Depends(fancy_query)):
    return {'q': q}
```

FastAPI walks DI graph, caches each by default per-request.

### `yield` Dependencies (Transactional Resources)

```python
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # Auto-close via async with


@app.post("/items")
async def create_item(item: ItemIn, db: AsyncSession = Depends(get_db_session)):
    db_item = Item(**item.model_dump())
    db.add(db_item)
    # Commit happens in dependency on success
    return db_item
```

### Class-Based Dependency (Stateful, Configurable)

```python
class RateLimit:
    def __init__(self, calls: int = 10, period: int = 60):
        self.calls = calls
        self.period = period

    def __call__(self, request: Request):
        # ... check limit
        return True


@app.get("/expensive", dependencies=[Depends(RateLimit(calls=5, period=60))])
def expensive():
    return {}
```

### `use_cache=False` (Disable Per-Request Caching)

```python
def expensive_dep():
    return random.random()


@app.get("/x")
def x(
    a=Depends(expensive_dep),                    # cached: same value
    b=Depends(expensive_dep),                    # same as a (cached)
    c=Depends(expensive_dep, use_cache=False),   # different value
):
    return {'a': a, 'b': b, 'c': c}
```

### Path / Router-Level Dependencies

```python
# All endpoints in router require auth
router = APIRouter(dependencies=[Depends(get_current_user)])

# All endpoints in app
app = FastAPI(dependencies=[Depends(log_request)])

# Single endpoint
@app.get("/x", dependencies=[Depends(verify_admin)])
def x():
    return {}
```

### Global Dependency Overrides (Testing)

```python
from fastapi.testclient import TestClient


def get_test_db():
    # Test DB session
    ...


app.dependency_overrides[get_db_session] = get_test_db


client = TestClient(app)
response = client.post("/items", json={...})


# After test
app.dependency_overrides = {}
```

### Lifespan / App-Scoped Dependency

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    db_engine = create_async_engine(...)
    app.state.db_engine = db_engine
    yield
    # Cleanup
    await db_engine.dispose()


app = FastAPI(lifespan=lifespan)


# Access in dependency
async def get_db_engine(request: Request):
    return request.app.state.db_engine
```

### Background Tasks (vs Celery)

```python
from fastapi import BackgroundTasks


async def send_email_bg(email: str, msg: str):
    # ... actually send
    pass


@app.post("/signup")
async def signup(email: str, background: BackgroundTasks):
    # Save user
    background.add_task(send_email_bg, email, "Welcome!")
    return {"status": "ok"}
```

BackgroundTasks run AFTER response sent. Single worker. Use Celery for heavy/durable work.

### Dependency Ordering Pitfall

```python
# WRONG — depends on get_current_user but auth check inside
def check_premium(user=Depends(get_current_user)):
    if not user.is_premium:
        raise HTTPException(403)
    return user


@app.get("/premium-feature")
def feature(user=Depends(check_premium)):
    return {}
```

This works, but watch ordering: error in earlier dep stops later deps from running.

### Async vs Sync Dependencies

```python
# Both work in async endpoints
def sync_dep():
    return 1

async def async_dep():
    return 2


# Sync dep in async endpoint = runs in threadpool
# Async dep in sync endpoint = error (use async endpoint)
```

---

## How It Works Internally

### DI Resolution Tree

FastAPI parses signature → builds dep graph at startup. On request:
1. Resolve leaf dependencies first
2. Cache values per-request (unless `use_cache=False`)
3. Pass resolved values to endpoint

### `yield` Lifecycle

```
1. Dep called → runs until `yield`
2. `yield` value passed to endpoint
3. Endpoint runs
4. Endpoint returns or raises
5. Code AFTER yield runs (cleanup)
```

Use try/finally for guarantees.

---

## Common Pitfalls

### 1. Forgetting Transaction Commit/Rollback

```python
async def get_db():
    async with Session() as s:
        yield s
        # If endpoint raised, no commit happens (good)
        # But no explicit rollback either (relies on async with)
```

Better: explicit commit/rollback.

### 2. `use_cache=False` Misused

Removing cache → dep runs multiple times → side effects multiply. Only disable when truly needed.

### 3. State in Sync Dep with Async Endpoint

Sync dep runs in threadpool → thread-local state doesn't transfer. Use ContextVar for context propagation.

### 4. Heavy Work in Dependency

```python
def slow_dep():
    return huge_db_query()  # blocks every request
```

Cache via Redis/in-memory; or use BackgroundTasks for post-response work.

### 5. Circular Dependencies

A depends on B, B depends on A → error at startup.

### 6. dependency_overrides Not Cleaned Up

Leaves state between tests. Use fixtures with cleanup.

---

## Interview Q&A

**Q1:** DI ka real benefit kya hai FastAPI mein?
**A:** (1) Reusable cross-cutting code (auth, pagination, DB session). (2) Testable — override deps without monkey-patching. (3) Hierarchical — chain of resolved deps. (4) Auto-validation — query params resolved + validated. (5) Lifecycle management via `yield` (DB sessions, file handles).

**Q2:** `yield` dependency ka use kab?
**A:** Resource management — DB session, file handle, distributed lock. Setup before `yield`, cleanup after. Auto-runs even if endpoint raises (similar to try/finally). Common: open DB session → yield → commit/rollback on completion.

**Q3:** Dependency caching kya hai?
**A:** Default: same dep used multiple times in one request = called once, result reused. Saves DB calls / external API calls. Disable with `use_cache=False` if dep has side effects you want repeated. Cache is per-request, not global.

**Q4:** Testing FastAPI app — DI override pattern?
**A:** `app.dependency_overrides[real_dep] = fake_dep`. Cleaner than monkey-patching. Use pytest fixture for setup/cleanup. Combined with TestClient: full integration tests with mocked deps.

**Q5:** Class-based dep vs function-based?
**A:** Function: simple, stateless, common case. Class: configurable instances (`Depends(RateLimit(calls=5))` — multiple endpoints use different config from same class). Class has `__call__`. Cleaner for parameterized deps.

**Q6:** Sub-dependency chain explain karo.
**A:** Dep A depends on Dep B depends on Dep C. FastAPI resolves DAG: C first, then B uses C result, then A uses B result. All cached per-request. Order matters for deps with side effects.

**Q7:** Background tasks vs Celery?
**A:** BackgroundTasks: in-process, same worker, runs after response. Suitable for fire-and-forget like logging, lightweight email. Celery: separate workers, durable queue, retries. Use for anything that must complete reliably or takes >1 second.

**Q8:** Request-scoped vs App-scoped state?
**A:** App-scoped: `app.state.X` (DB engine, Redis client, ML model). Lifespan context manager initializes once. Request-scoped: dep returns new instance per request (DB session). Don't share request state across requests.

---

## Real-World Use Cases

### 1. Multi-Tenant DB Session

```python
async def get_tenant_db(user=Depends(get_current_user)):
    schema = f"tenant_{user.tenant_id}"
    async with AsyncSessionLocal() as s:
        await s.execute(text(f"SET search_path TO {schema}"))
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
```

### 2. Feature Flag Check

```python
class FeatureFlag:
    def __init__(self, flag_name: str):
        self.flag_name = flag_name

    async def __call__(self, user=Depends(get_current_user)):
        if not await check_flag(self.flag_name, user.id):
            raise HTTPException(403, f"Feature {self.flag_name} not enabled")


@app.get("/beta-feature", dependencies=[Depends(FeatureFlag('new_dashboard'))])
def beta():
    return {}
```

### 3. Audit Logging Dependency

```python
async def log_audit_action(action: str, request: Request, user=Depends(get_current_user)):
    await db.audit_log.create(
        action=action,
        user_id=user.id,
        ip=request.client.host,
        path=request.url.path,
    )


@app.post("/sensitive-op")
async def sensitive(_=Depends(lambda r, u: log_audit_action('sensitive_op', r, u))):
    ...
```

---

## References

- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Advanced Dependencies](https://fastapi.tiangolo.com/advanced/advanced-dependencies/)
- pytest-fastapi-deps for test patterns
