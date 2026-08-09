# Testcontainers (Python)

> **Interview angle:** "Tests SQLite pe pass hote hain, production Postgres pe fail. Mocks bhi jhooth bol rahe hain. Kya karein?"

---

## Quick Reference

| Cheez | Kya hai | Kab use karein |
|-------|---------|----------------|
| `PostgresContainer` | Ephemeral Postgres in Docker | DB integration tests |
| `RedisContainer` | Ephemeral Redis | Cache / lock / rate-limit tests |
| `DockerContainer` | Generic — koi bhi image | MinIO, Mailhog, Elasticsearch, custom |
| `LogMessageWaitStrategy` | Log line dikhne tak block (`wait_for_logs` ka successor) | Container ready-check |
| `@pytest.fixture(scope="session")` | Ek baar start, sab tests reuse | Container startup cost amortize |
| `TESTCONTAINERS_RYUK_DISABLED` | Cleanup sidecar off | Sirf CI jahan runner khud clean karta ho |
| `.with_reuse(True)` | Container test run ke baad zinda | Local dev inner-loop speed |
| `.with_tmpfs_mount()` | DB datadir RAM me | 2-5x faster DB tests |

```bash
pip install "testcontainers[postgres,redis]"  # extras matter — base package is thin
```

```python
from testcontainers.community.postgres import PostgresContainer   # >= 4.15

with PostgresContainer("postgres:16-alpine") as pg:
    url = pg.get_connection_url()   # postgresql+psycopg2://test:test@localhost:49213/test
    # ...run your test against a REAL Postgres...
# exit → container killed, volume gone
```

> ⚠️ **Version note (4.15+):** saare service modules `testcontainers.community.*` me shift ho gaye hain. Purane paths (`testcontainers.postgres`, `testcontainers.redis`, `testcontainers.kafka`) **abhi bhi kaam karte hain** par `DeprecationWarning` dete hain — aur `filterwarnings = error` wale repos me woh warning aapki poori suite RED kar degi. Portable pattern:
>
> ```python
> try:
>     from testcontainers.community.postgres import PostgresContainer   # >= 4.15
> except ImportError:
>     from testcontainers.postgres import PostgresContainer             # < 4.15
> ```
>
> `testcontainers.core.*` (container, waiting_utils) dono versions me same jagah hai.

---

## 1. WHY — Mocks jhooth bolte hain

Aapne DB layer mock kiya. Test green. Production red. Kyun?

```python
# Test me
mock_db.fetch_user.return_value = {"id": 1, "name": "Alice"}
assert get_user(1)["name"] == "Alice"     # ✅ passes forever
```

Ye test sirf **aapke mock ka** test hai. Ye kabhi nahi batayega:

| Real bug | Mock isko pakadta hai? |
|----------|------------------------|
| SQL syntax error (`SELCT`) | ❌ |
| Missing index → 8s query | ❌ |
| Unique constraint violation | ❌ |
| Transaction deadlock | ❌ |
| `NULL` vs `''` semantics | ❌ |
| Migration file toota hua | ❌ |
| JSONB operator (`@>`) SQLite me nahi hai | ❌ |
| Timezone-aware `timestamptz` rounding | ❌ |
| Connection pool exhaustion | ❌ |

**SQLite-as-test-DB ka jhooth bhi wahi hai** — alag SQL dialect, no JSONB, no `ILIKE`, no window function edge cases, different `ORDER BY` collation, transactional DDL alag. Aap ek *dusre* database ko test kar rahe ho.

**Testcontainers ka core idea:** test **wahi** Postgres 16 ke against chalao jo production me hai — Docker se, per-test-run, disposable.

```
┌──────────────────────────────────────────────┐
│ pytest session start                          │
│   └─ session fixture: docker run postgres:16  │
│        → random host port (49213)             │
│        → wait until "ready to accept conns"   │
│                                               │
│   tests ─────────────────────────────────►    │
│     har test real SQL maarta hai              │
│                                               │
│ pytest session end                            │
│   └─ container kill + volume remove           │
│   └─ ryuk sidecar safety-net cleanup          │
└──────────────────────────────────────────────┘
```

> **Senior Tip:** "Real dependency" ka matlab *production-identical version* hai. `postgres:latest` mat likho — `postgres:16.4-alpine` pin karo, warna ek din CI apne aap Postgres 17 khinch laayega aur aapke tests bina kisi commit ke red ho jayenge.

---

## 2. Terminology — Test double spectrum

Interview me ye distinction poocha jata hai. Rat lo:

| Type | Kya hai | Fidelity | Speed |
|------|---------|----------|-------|
| **Stub** | Hardcoded return value | Zero | µs |
| **Mock** | Stub + call assertions | Zero | µs |
| **Fake** | Working in-memory impl (fakeredis, SQLite) | Partial | µs–ms |
| **Testcontainer** | Asli software, ephemeral | **Full** | ms–s |
| **Shared staging** | Asli software, shared, stateful | Full | s, flaky |

Testcontainers `fake` aur `staging` ke beech ka sweet spot hai: **full fidelity + full isolation**.

---

## 3. HOW — PostgresContainer

```python
# tests/conftest.py
import pytest
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres():
    """Ek Postgres, poori test session ke liye. Startup ~2s, isliye session-scoped."""
    with PostgresContainer(
        "postgres:16-alpine",
        username="test",
        password="test",
        dbname="test",
    ) as container:
        yield container
    # context manager exit → container.stop() → docker rm -f


@pytest.fixture(scope="session")
def engine(postgres):
    from sqlalchemy import create_engine
    from myapp.db import Base

    # NOTE: get_connection_url() psycopg2 driver deta hai.
    # psycopg3 chahiye to: .replace("postgresql+psycopg2", "postgresql+psycopg")
    engine = create_engine(postgres.get_connection_url(), pool_pre_ping=True)
    Base.metadata.create_all(engine)     # ya: alembic upgrade head
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    """Per-test transaction, end me rollback → tests ek dusre ko dirty nahi karte."""
    conn = engine.connect()
    trans = conn.begin()
    from sqlalchemy.orm import Session
    session = Session(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()
```

### Useful accessors

```python
pg.get_connection_url()          # SQLAlchemy URL (psycopg2 dialect)
pg.get_container_host_ip()       # usually "localhost"
pg.get_exposed_port(5432)        # random host port, e.g. 49213
pg.exec("psql -U test -c 'SELECT 1'")   # run command inside container
```

> **Senior Tip:** Schema `Base.metadata.create_all()` se mat banao production-jaise repo me. **Alembic migrations chalao** — tab aapka test suite migrations ko bhi test kar raha hai. `create_all()` aur migrations ka drift silently production break karta hai.

```python
from alembic import command
from alembic.config import Config

cfg = Config("alembic.ini")
cfg.set_main_option("sqlalchemy.url", postgres.get_connection_url())
command.upgrade(cfg, "head")     # ← ab migrations bhi tested hain
```

---

## 4. HOW — RedisContainer

```python
import pytest
from testcontainers.community.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as rc:
        yield rc


@pytest.fixture
def redis_client(redis_container):
    client = redis_container.get_client(decode_responses=True)
    client.flushall()        # ← har test ko saaf slate. Cheap (in-memory).
    yield client
    client.flushall()
```

**Kyun asli Redis, fakeredis nahi?** `fakeredis` 90% cases me theek hai, par ye miss karta hai:

- Lua script atomicity (`EVAL`) ka exact semantics
- `EXPIRE` ki real timing + `SET key val NX PX 5000` lock races
- Cluster / pipeline behaviour
- Eviction policy (`maxmemory-policy allkeys-lru`) ka asar
- `WAIT`, `CLIENT NO-EVICT`, RESP3 push messages

Agar aap distributed lock ya rate limiter likh rahe ho — **fakeredis mat use karo**. Wahi to woh code hai jahan bug hoga.

---

## 5. HOW — Generic DockerContainer (jo image aapko chahiye)

Har service ke liye ready-made class nahi hai. `DockerContainer` universal escape hatch hai.

```python
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs


@pytest.fixture(scope="session")
def minio():
    container = (
        DockerContainer("minio/minio:RELEASE.2024-09-13T20-26-02Z")
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_exposed_ports(9000)
        .with_command("server /data")
    )
    with container:
        wait_for_logs(container, r"API:.*", timeout=30)
        host = container.get_container_host_ip()
        port = container.get_exposed_port(9000)
        yield f"http://{host}:{port}"
```

### Builder API cheat-sheet

```python
DockerContainer("image:tag")
  .with_env("KEY", "value")
  .with_exposed_ports(8080, 9090)          # random host port map
  .with_bind_ports(8080, 8080)             # FIXED host port — avoid! (xdist collisions)
  .with_command("server /data")
  .with_volume_mapping("/host/path", "/container/path", mode="ro")
  .with_tmpfs_mount("/data", "size=256m")  # >= 4.15 — RAM-backed mount
  .with_network(net) / .with_network_aliases("db")
  .waiting_for(LogMessageWaitStrategy("ready"))   # >= 4.15
  .with_kwargs(privileged=True)            # raw docker-py escape hatch
  .with_name("explicit-name")              # avoid unless you need it
```

⚠️ **Do landmines is API me:**

1. **`with_kwargs(tmpfs=...)` 4.15+ pe crash karta hai** — library khud bhi `tmpfs=` pass karti hai:
   ```
   TypeError: DockerClient.create() got multiple values for keyword argument 'tmpfs'
   ```
   Use `.with_tmpfs_mount()` instead. Version-portable:
   ```python
   if hasattr(c, "with_tmpfs_mount"):
       c = c.with_tmpfs_mount("/var/lib/postgresql/data", "rw,size=256m")
   else:
       c = c.with_kwargs(tmpfs={"/var/lib/postgresql/data": "rw,size=256m"})
   ```

2. **`with_tmpfs_mount(path, size)` ka `size` arg actually Docker ka raw *options string* hai**, size nahi. Bare `"256m"` dene pe daemon reject karta hai:
   ```
   docker.errors.APIError: 500 ... invalid tmpfs option ["256m"]
   ```
   Sahi: `"size=256m"` ya `"rw,noexec,nosuid,size=256m"`.

> **Senior Tip:** `with_bind_ports()` kabhi mat use karo unless bilkul zaroori ho. Fixed host port = do parallel workers / do CI jobs ek hi machine pe → `port already allocated`. Random port + `get_exposed_port()` hi default hona chahiye.

---

## 6. Wait strategies — sabse bada flakiness source

Container **start** hone aur **ready** hone me farq hai. Docker `running` bol dega jab process spawn ho gaya, par Postgres tab bhi 800ms tak connections reject karega.

### Structured wait strategies (4.15+) — ye ab default hai

Purana `wait_for_logs(container, "...")` ab string predicate ke saath **deprecated** hai. Naya API container ko declaratively batata hai ki ready ka matlab kya hai, aur `.start()` khud block karta hai:

```python
from testcontainers.core.wait_strategies import (
    LogMessageWaitStrategy,   # log line
    HttpWaitStrategy,         # HTTP endpoint
    PortWaitStrategy,         # TCP port
    HealthcheckWaitStrategy,  # image ka apna HEALTHCHECK
    ExecWaitStrategy,         # container ke andar command
    FileExistsWaitStrategy,
    CompositeWaitStrategy,    # multiple, sab satisfy hone chahiye
)

container.waiting_for(LogMessageWaitStrategy("Ready to accept connections"))
```

### Strategy 1 — Log line (sabse common)

```python
container.waiting_for(LogMessageWaitStrategy("database system is ready to accept connections"))

# legacy equivalent (< 4.15):
wait_for_logs(container, "database system is ready to accept connections", timeout=30)
```

⚠️ **Postgres gotcha:** ye line **do baar** print hoti hai — pehli initdb ke temporary server se, doosri asli server se. Sirf pehli pe connect karoge to connection refused milega.

Naye API me iske liye dedicated `times` param hai — yahi is gotcha ka saaf-suthra jawab hai:

```python
LogMessageWaitStrategy("ready to accept connections", times=2)
# signature: LogMessageWaitStrategy(message: str | re.Pattern, times=1,
#                                   predicate_streams_and=False)
# predicate_streams_and=True → stdout AUR stderr dono me match chahiye

# legacy hack (< 4.15) — regex se do occurrence match karo:
wait_for_logs(container, r"ready to accept connections[\s\S]*ready to accept connections", timeout=60)
```

Built-in `PostgresContainer` ye already handle karta hai; ye tab chahiye jab aap apni custom Postgres image `DockerContainer` se chala rahe ho.

### Strategy 2 — Port pe TCP connect

```python
from testcontainers.core.waiting_utils import wait_container_is_ready
import socket

@wait_container_is_ready(OSError, ConnectionRefusedError)
def _wait_port(host, port):
    with socket.create_connection((host, int(port)), timeout=1):
        return True

_wait_port(container.get_container_host_ip(), container.get_exposed_port(9000))
```

TCP-accept ≠ app-ready. Postgres port bind karta hai recovery ke dauraan bhi. Ye weakest signal hai.

### Strategy 3 — Application-level probe (sabse strong)

```python
@wait_container_is_ready(Exception)
def _wait_http(url):
    import urllib.request
    with urllib.request.urlopen(url + "/minio/health/live", timeout=2) as r:
        assert r.status == 200
```

### Strategy 4 — Image ka apna healthcheck

```python
DockerContainer("postgres:16-alpine").with_kwargs(
    healthcheck={
        "test": ["CMD-SHELL", "pg_isready -U test"],
        "interval": 500_000_000,   # nanoseconds → 0.5s
        "retries": 20,
    }
)
```

**Decision:** HTTP/app-level probe > healthcheck > log-regex > TCP port.

> **Interview Angle:** "Aapke integration tests CI me randomly fail kyun hote hain?" — 80% jawab **wait strategy weak hai**. `time.sleep(3)` likhne wala candidate reject ho jata hai; sahi jawab readiness probe + bounded retry hai.

---

## 7. Fixture scope — cost vs isolation

Container startup mehnga hai. Postgres ~1.5–3s, Kafka ~8–15s, Elasticsearch ~20s+.

| Scope | Startups (100 tests) | Isolation | Verdict |
|-------|----------------------|-----------|---------|
| `function` | 100 × 2s = **200s** | Perfect | ❌ suicide |
| `class` | ~10 × 2s = 20s | Good | Rarely useful |
| `module` | ~5 × 2s = 10s | Good | OK for big suites |
| `session` | **1 × 2s = 2s** | Container shared | ✅ **default** |

**Rule: container session-scoped, data per-test-scoped.**

```python
@pytest.fixture(scope="session")
def postgres(): ...              # ← mehnga, ek baar

@pytest.fixture                  # ← sasta, har test
def db(engine):
    conn = engine.connect(); trans = conn.begin()
    yield Session(bind=conn)
    trans.rollback(); conn.close()      # ← isolation yahan se aata hai, container se nahi
```

Redis ke liye per-test `flushall()`. Kafka ke liye per-test unique topic name.

---

## 8. pytest-xdist ke saath — the real gotcha

`pytest -n 4` ke saath **`scope="session"` ka matlab "per worker session" hai, "per run" nahi.**

```
pytest -n 4
  ├─ gw0 → apna session fixture → Postgres container #1
  ├─ gw1 → apna session fixture → Postgres container #2
  ├─ gw2 → apna session fixture → Postgres container #3
  └─ gw3 → apna session fixture → Postgres container #4
```

4 Postgres containers = 4 × 2s startup + 4 × ~150MB RAM. Chhote suite pe ye **acceptable** hai (isolation free milta hai). Bade setups (Kafka + ES + Postgres) pe machine mar jayegi.

### Option A — Accept karo (recommended, simple)

Per-worker container = perfect isolation, zero coordination code. Agar image halka hai (`alpine`) to bas ye karo.

### Option B — Ek container, per-worker database

```python
import os
import pytest
from filelock import FileLock       # pip install filelock
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory, worker_id):
    """worker_id fixture xdist deta hai: 'master' (no xdist) ya 'gw0','gw1'..."""
    if worker_id == "master":
        with PostgresContainer("postgres:16-alpine") as pg:
            yield pg.get_connection_url()
        return

    # Sirf ek worker container start kare; baaki URL file se padh lein.
    root = tmp_path_factory.getbasetemp().parent
    url_file = root / "pg_url.txt"

    with FileLock(str(url_file) + ".lock"):
        if url_file.is_file():
            url = url_file.read_text()
            container = None
        else:
            container = PostgresContainer("postgres:16-alpine").start()
            url = container.get_connection_url()
            url_file.write_text(url)

    yield url

    if container is not None:
        container.stop()
```

⚠️ Is pattern me **ownership problem** hai: jo worker container banata hai woh pehle khatam ho sakta hai. Isliye ryuk (§9) ko disable **mat** karo — woh aapka safety net hai.

Phir har worker apna DB banaye:

```python
@pytest.fixture(scope="session")
def engine(pg_url, worker_id):
    from sqlalchemy import create_engine, text
    admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    dbname = f"test_{worker_id}"
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin.dispose()
    return create_engine(pg_url.rsplit("/", 1)[0] + f"/{dbname}")
```

### Option C — `--dist=loadgroup`

Saare container-using tests ek worker pe bhej do:

```python
@pytest.mark.xdist_group("db")
def test_something(db): ...
```

```bash
pytest -n 4 --dist=loadgroup
```

Integration tests serialize ho jate hain, unit tests parallel rehte hain. Sabse kam code, decent result.

> **Senior Tip:** Sabse saaf answer aksar ye hai — **unit tests `-n auto` pe, integration tests `-n 0` pe, alag CI job me**. Ek hi command me sab kuch parallelize karne ki koshish hi complexity paida karti hai.

---

## 9. Ryuk — cleanup sidecar

Jab pehla container start hota hai, testcontainers ek extra container bhi chalata hai: **`testcontainers/ryuk`** (Moby Ryuk).

**Kaam:** Ryuk aapke test process se ek TCP connection hold karta hai. Process mara (Ctrl-C, OOM kill, CI timeout, `kill -9`) → connection toot gayi → ryuk usi session-label wale saare containers, networks aur volumes ko `docker rm -f` kar deta hai.

```
pytest process ──TCP──► ryuk container
     │                       │
     └─ dies unexpectedly ───┘
                             └─► docker rm -f $(label=org.testcontainers.session-id=abc)
```

**Iske bina:** har crashed CI run ek orphan Postgres chhod jayega. Ek hafte me build agent 40 zombie containers ke saath disk-full ho jayega.

### Config

```bash
TESTCONTAINERS_RYUK_DISABLED=true       # off — sirf tab jab runner ephemeral ho
TESTCONTAINERS_RYUK_PRIVILEGED=true     # DinD me chahiye ho sakta hai
RYUK_CONTAINER_IMAGE=my-mirror/ryuk:0.8.1   # air-gapped registry
```

**Ryuk kab disable karein:**

| Situation | Disable? | Kyun |
|-----------|----------|------|
| GitHub Actions ephemeral runner | ✅ safe | VM hi 5 min me delete ho jayegi |
| Self-hosted persistent runner | ❌ **kabhi nahi** | Orphans jamaa honge |
| Local dev laptop | ❌ nahi | Aap Ctrl-C bahut maarte ho |
| Podman rootless (socket issue) | ✅ often needed | Ryuk ko socket access chahiye |
| Corporate registry, ryuk image blocked | ✅ majboori | Aur manual cleanup step add karo |

---

## 10. CI — sabse zyada time yahan jata hai

Testcontainers ko **Docker daemon access** chahiye. CI me ye teen tareeke se milta hai.

### Approach 1 — Docker socket mount (recommended)

Runner ke Docker socket ko test container me daal do.

```yaml
# .gitlab-ci.yml
test:
  image: python:3.12
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  script:
    - pip install -e ".[test]"
    - pytest -m integration
```

**Fayda:** Fast, layer cache reuse, no nested daemon.
**Nuksaan:** Container ko host Docker pe root-equivalent access mil jata hai (security). Aur **networking trap** — sibling container start hota hai *host* pe, aapke test container pe nahi. `localhost` ka matlab alag hai.

Fix — testcontainers ko batao host kaise pahunchna hai:

```bash
export TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal
# ya same docker network use karo aur container name se connect karo
```

### Approach 2 — Docker-in-Docker (DinD)

```yaml
# .gitlab-ci.yml
test:
  image: python:3.12
  services:
    - name: docker:27-dind
      alias: docker
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""
    TESTCONTAINERS_RYUK_PRIVILEGED: "true"
  script:
    - pytest -m integration
```

**Fayda:** Poori isolation, host daemon safe.
**Nuksaan:** Privileged mode chahiye, image cache har run pe khali (slow — har baar `postgres:16` pull), storage driver overhead.

### Approach 3 — GitHub Actions `services:` (testcontainers ke bina)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_PASSWORD: test, POSTGRES_USER: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s
          --health-timeout 5s --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - run: pytest
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test
```

**GHA runners pe Docker already available hai**, isliye testcontainers **as-is chalta hai** — koi extra config nahi. Toh `services:` kab better hai?

| | `services:` | testcontainers |
|-|-------------|----------------|
| CI me setup | YAML | zero |
| **Local pe wahi setup** | ❌ alag (compose likho) | ✅ **same code** |
| Dynamic ports | ❌ fixed | ✅ |
| Test-specific config | ❌ ek hi instance | ✅ per-fixture |
| Startup | CI-parallel, "free" | test time me counted |
| Portability (GHA→GitLab→Jenkins) | ❌ rewrite | ✅ same |

> **Senior Tip:** Asli argument "CI me kya fast hai" nahi hai — **"developer laptop pe `pytest` bina kisi README step ke chalta hai ya nahi"** hai. Wahi testcontainers jeet-ta hai. `services:` faster ho sakta hai, par ye aapke local aur CI setup ko do alag cheezein bana deta hai, aur woh drift hamesha kisi ko ek din maarta hai.

### CI hygiene checklist

```yaml
env:
  TESTCONTAINERS_RYUK_DISABLED: "false"     # persistent runners pe hamesha false
  DOCKER_CLIENT_TIMEOUT: "300"
  COMPOSE_HTTP_TIMEOUT: "300"
  TESTCONTAINERS_HOST_OVERRIDE: ""          # socket-mount setups me set karo
```

- Images pin karo (`postgres:16.4-alpine`), `latest` kabhi nahi
- Images pre-pull karo warm cache ke liye: `docker pull postgres:16.4-alpine &`
- Registry rate-limit se bachne ke liye internal mirror use karo (Docker Hub anonymous pulls throttled hain)
- Integration tests ko `-m integration` se alag job me rakho
- Har job pe `docker system df` log karo — disk creep jaldi pakdi jayegi

---

## 11. Speed tricks

### Trick 1 — `tmpfs` datadir (biggest win)

DB ka fsync disk pe jaana test me bekaar hai. RAM me daal do.

```python
# 4.15+ — note: doosra arg raw Docker OPTIONS string hai, "512m" akela invalid hai
PostgresContainer("postgres:16-alpine").with_tmpfs_mount(
    "/var/lib/postgresql/data", "rw,noexec,nosuid,size=512m"
)

# < 4.15
PostgresContainer("postgres:16-alpine").with_kwargs(
    tmpfs={"/var/lib/postgresql/data": "rw,noexec,nosuid,size=512m"}
)
```

Plus fsync band karo:

```python
.with_command("postgres -c fsync=off -c full_page_writes=off "
              "-c synchronous_commit=off -c max_connections=200")
```

Typical: 2-5x faster write-heavy DB tests. **Sirf tests me** — production me ye data-loss config hai.

### Trick 2 — Reuse (local inner loop)

```python
PostgresContainer("postgres:16-alpine").with_reuse(True)
```

Test run khatam hone pe container zinda rehta hai; agla run usi ko attach kar leta hai. Startup cost ~2s → ~0ms.

Enable karna padta hai (opt-in, per-user):

```properties
# ~/.testcontainers.properties
testcontainers.reuse.enable=true
```

⚠️ **Reuse ke saath ryuk container ko nahi maarta** (by design). ⚠️ **CI me reuse kabhi mat karo** — stale state test ko jhooth-mooth pass kara degi. Sirf local dev.

### Trick 3 — Alpine / slim images

`postgres:16` ≈ 430MB, `postgres:16-alpine` ≈ 250MB. Cold pull me ye seconds hain.

### Trick 4 — Migrations ek baar

Session fixture me `alembic upgrade head` ek baar. Per-test sirf transaction rollback. Migrations 200 baar chalana sabse common self-inflicted slowness hai.

### Trick 5 — Template database (heavy seed data)

```sql
-- ek baar: seeded template banao
CREATE DATABASE test_template;  -- seed karo
-- per test (milliseconds):
CREATE DATABASE test_run_17 TEMPLATE test_template;
```

Postgres file-copy karta hai — bade fixtures ke liye re-seeding se bahut fast.

### Trick 6 — Images pre-pull

```bash
docker pull postgres:16.4-alpine & docker pull redis:7.4-alpine & wait
pytest
```

Warna pehla test 40s pull ka intezaar karega aur "flaky timeout" jaisa dikhega.

---

## 12. Jab testcontainers use **NAHI** karna chahiye

Har test ke liye Docker chalana ek anti-pattern hai. Ye mat karo:

### ❌ Pure logic / unit tests

```python
def test_discount_calculation():
    assert apply_discount(100, "SAVE20") == 80    # ← isko DB ki zaroorat nahi
```

Pure function pe container chalana = 2s ka test jo 0.1ms ho sakta tha. Aapka test pyramid ulta ho jayega.

### ❌ Jahan Docker available hi nahi

- Air-gapped / regulated environments jahan registry pull allowed nahi
- Shared build agents jahan Docker socket policy se blocked hai
- macOS/Windows dev laptops jahan Docker Desktop licensed nahi hai
- Kuch corporate VDI setups

Agar aapki team ka aadha hissa tests nahi chala sakta, to aapne ek **do-tier testing culture** bana diya — worst outcome.

### ❌ Third-party SaaS ka substitute

Stripe, Twilio, SendGrid — inka Docker image nahi hai. Yahan sahi tool **recorded contract / mock server** hai (WireMock, respx, pact). Details: [[04_contract_testing_pact]].

### ❌ Full-system E2E

10 containers ek pytest fixture se orchestrate karna = aapne ek bura Docker Compose likh diya. E2E ke liye compose/k8s ephemeral env use karo.

### ❌ Ultra-fast TDD inner loop

Red-green-refactor 3s ke feedback loop pe kaam nahi karta. TDD ke liye fakes, integration gate pe testcontainers. Dekhein [[07_tdd_bdd_practices]].

---

## 13. Decision table — Mocks vs Fakes vs Testcontainers vs Staging

| Criteria | Mock/Stub | Fake (fakeredis, SQLite) | **Testcontainers** | Shared staging |
|----------|-----------|--------------------------|--------------------|----------------|
| Speed | µs | ms | 100ms–3s + startup | seconds, network |
| Fidelity | zero | partial | **full** | full |
| Isolation | perfect | perfect | **perfect** | ❌ shared, dirty |
| SQL dialect bugs pakadta hai | ❌ | ❌ | ✅ | ✅ |
| Migrations test karta hai | ❌ | partial | ✅ | ✅ |
| Perf/index issue dikhata hai | ❌ | ❌ | partial | ✅ |
| Docker chahiye | ❌ | ❌ | ✅ | ❌ |
| CI setup cost | zero | zero | medium | high |
| Offline chalta hai | ✅ | ✅ | ✅ (cached image) | ❌ |
| Parallel-safe | ✅ | ✅ | ✅ (care se) | ❌ |
| Cost | free | free | CPU/RAM | infra $$ |
| **Best for** | pure logic, error paths | fast repository tests | **integration gate** | pre-prod smoke |

**Practical layering jo actually kaam karta hai:**

```
Unit (60%)          → mocks/fakes, milliseconds, har save pe chalao
Integration (30%)   → testcontainers, seconds, har PR pe chalao
Contract (8%)       → pact/wiremock, external services ke liye
E2E/staging (2%)    → asli deployed env, merge ke baad
```

> **Interview Angle:** "Kya aap mocks hata kar sab testcontainers kar denge?" — **Nahi.** Sahi jawab: pyramid layering. Testcontainers *integration* layer ko fix karta hai, *unit* layer ko replace nahi karta. Jo candidate "sab kuch real" bolta hai woh 45-minute test suite deliver karega jise koi nahi chalayega.

---

## 14. Common pitfalls

### Pitfall 1 — `time.sleep()` wait strategy ki jagah

```python
container.start(); time.sleep(5)     # ❌ slow machine pe fail, fast pe waste
wait_for_logs(container, "ready", 30)  # ✅
```

### Pitfall 2 — Function-scoped container

100 tests × 2s = suite death. Container session-scoped, data per-test.

### Pitfall 3 — Container fresh hai isliye clean hai (galat)

Container session-scoped hai → **state tests ke beech leak hoti hai**. Rollback/flush per test lagao.

### Pitfall 4 — `latest` tag

```python
PostgresContainer("postgres:latest")     # ❌ ek din bina commit ke red
PostgresContainer("postgres:16.4-alpine")  # ✅
```

### Pitfall 5 — Fixed host ports

`.with_bind_ports(5432, 5432)` → xdist / concurrent CI job pe `port is already allocated`.

### Pitfall 6 — Import-time container start

```python
pg = PostgresContainer("postgres:16").start()   # ❌ module import pe chalta hai
```

`--collect-only` bhi Docker maangega. Hamesha fixture ke andar.

### Pitfall 7 — Ryuk persistent runner pe disabled

Orphan containers → disk full → "CI mysteriously broken" 2 hafte baad.

### Pitfall 8 — Driver mismatch

`get_connection_url()` `postgresql+psycopg2://` deta hai. Aapka app asyncpg use karta hai:

```python
url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
```

### Pitfall 9 — `docker.errors.DockerException: Error while fetching server API version`

Docker daemon hi nahi chal raha (ya socket path galat — colima/podman/Rancher Desktop). Fix:

```bash
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock
# ya podman:
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
export TESTCONTAINERS_RYUK_DISABLED=true
```

### Pitfall 9b — colima / Rancher / podman pe ryuk start hi nahi hota

Ryuk ko host ka Docker socket bind-mount karna padta hai. Non-Docker-Desktop VMs me woh socket path VM ke andar exist nahi karta, to daemon use directory bana deta hai aur fail ho jata hai:

```
docker.errors.APIError: 500 Server Error ... error while creating mount source path
'/Users/you/.colima/default/docker.sock': mkdir ...: operation not supported
```

**Ye aapke test ka bug nahi hai** — har container isi pe error karega. Fix:

```bash
export TESTCONTAINERS_RYUK_DISABLED=true    # local dev pe acceptable
```

Trade-off yaad rakho: ab crashed run ke containers khud clean karne padenge (`docker ps -a --filter label=org.testcontainers=true`).

### Pitfall 9c — deprecated import path + `filterwarnings = error`

`from testcontainers.postgres import ...` 4.15+ pe `DeprecationWarning` deta hai. Agar aapke `pytest.ini` me `filterwarnings = error` hai, to **collection hi fail** ho jayegi — aur error message import ke baare me hoga, warning ke baare me nahi, jo debug karna confusing hai. `testcontainers.community.*` pe shift karo.

### Pitfall 10 — Skip guard nahi lagaya

Docker na hone pe suite **error** karti hai, `skip` nahi. Har testcontainers file me guard lagao (dekhein practical file).

---

## 15. Interview Questions

**Q1: Testcontainers kya hai, ek line me?**
Test ke lifecycle se bandhe hue disposable Docker containers — real dependencies (Postgres, Redis, Kafka) ephemeral, randomly-ported instances ke roop me, jo test khatam hote hi delete ho jate hain.

**Q2: Mocks ki jagah kyun? Mocks to fast hain.**
Mocks aapke *assumptions* ko test karte hain, dependency ko nahi. SQL syntax, constraints, migrations, JSONB operators, deadlocks, timezone — kuch bhi nahi pakadte. Testcontainers integration layer ko real banata hai. Unit layer par mocks ab bhi sahi hain.

**Q3: SQLite se test kar lein, tez hai?**
SQLite ek alag database hai — no JSONB, no `ILIKE`, alag collation, alag transactional DDL, alag concurrency model. Aap production ka nahi, SQLite ka test likh rahe ho. Classic failure: JSONB query test me pass, prod me syntax error.

**Q4: Fixture scope kya rakhenge?**
Container `session`, data `function`. Container startup mehnga (~2s), data reset sasta (transaction rollback / `FLUSHALL`). Function-scoped container 100-test suite ko 200s bana deta hai.

**Q5: pytest-xdist ke saath kya hota hai?**
`scope="session"` per-**worker** hota hai, per-run nahi — `-n 4` = 4 containers. Options: (a) accept karo, isolation free milta hai, (b) `filelock` + shared URL file se ek container, per-worker DB, (c) `@pytest.mark.xdist_group` + `--dist=loadgroup` se serialize. Practically: unit tests parallel, integration serial in a separate job.

**Q6: Ryuk kya hai?**
Cleanup sidecar container. Aapke test process se TCP connection hold karta hai; process crash/Ctrl-C hone pe usi session-label ke containers/volumes/networks force-remove karta hai. Persistent CI runners pe isko disable karna orphan containers aur disk-full ka seedha rasta hai.

**Q7: CI me DinD vs socket mount?**
Socket mount: fast, image cache reuse, par container ko host Docker pe root-equivalent access; `localhost` semantics badal jate hain (`TESTCONTAINERS_HOST_OVERRIDE` chahiye). DinD: poori isolation, par privileged chahiye aur cache har run pe cold. GitHub-hosted runners pe Docker already hai — kuch bhi nahi chahiye.

**Q8: GHA `services:` vs testcontainers?**
`services:` CI-parallel start hota hai (test time me count nahi hota) par sirf CI me kaam karta hai, fixed ports, ek hi instance. Testcontainers wahi code local aur har CI provider pe chalata hai, dynamic ports, per-fixture config. Asli faisla speed ka nahi — local/CI parity ka hai.

**Q9: Tests slow ho gaye — kya karenge?**
tmpfs datadir + `fsync=off`, alpine images, migrations sirf session fixture me, local pe `.with_reuse(True)`, images pre-pull, heavy seed ke liye Postgres `TEMPLATE` database, aur integration tests ko alag marker/job me daalo.

**Q10: Kab NOT use karenge?**
Pure-logic unit tests, TDD inner loop, air-gapped/Docker-less environments, third-party SaaS (contract tests use karo), aur full multi-service E2E (compose/k8s use karo).

**Q11: Wait strategy kaise choose karenge?**
Application-level readiness probe sabse strong (HTTP health, `SELECT 1`); phir image healthcheck; phir log-regex; TCP port sabse weak (bind ≠ ready). `time.sleep()` kabhi nahi. Postgres ka classic trap: "ready to accept connections" **do baar** print hota hai (initdb + real server).

**Q12: Test suite bina Docker wale machine pe kya karega?**
`pytest.importorskip` + docker-ping guard ke saath **skip** karna chahiye, error nahi. Warna aapki suite ka result environment pe depend karta hai — dev machines pe log tests chalana chhod dete hain.

---

## 16. Best Practices

1. **Container session-scoped, data per-test** — cost amortize, isolation rollback se
2. **Exact image tags pin karo** — `postgres:16.4-alpine`, `latest` kabhi nahi
3. **Readiness probe** use karo, `sleep` nahi
4. **Migrations chalao**, `create_all()` nahi — migrations bhi test ho jayenge
5. **Ryuk enabled** rakho har us jagah jahan machine persistent hai
6. **Random ports** — `get_exposed_port()`, kabhi `with_bind_ports()` nahi
7. **`-m integration` marker** + graceful skip jab Docker na ho
8. **tmpfs + `fsync=off`** DB tests ke liye
9. **Local pe `reuse`, CI me kabhi nahi**
10. **Testcontainers ko sirf integration layer pe rakho** — pyramid ka base mocks/fakes hi rahe

---

## Related
- [[01_pytest_advanced]]
- [[04_contract_testing_pact]] — jab dependency ka Docker image nahi hai (Stripe, Twilio)
- [[05_test_parallelization]] — xdist scoping aur per-worker isolation ki detail
- [[07_tdd_bdd_practices]] — inner-loop me fakes, gate pe containers
- [[08_fastapi_testing_patterns]] — testcontainer engine ko FastAPI dependency override me plug karna
- [[../../01_Year3-4_Mid/05_Microservices/12_microservices_testing]] — `KafkaContainer` se event-flow integration test aur microservices test pyramid. (Wahan ka snippet legacy import `testcontainers.kafka` use karta hai; 4.15+ pe woh `testcontainers.community.kafka` hai — baaki fixture pattern bilkul wahi hai jo yahan §7 me hai.)
