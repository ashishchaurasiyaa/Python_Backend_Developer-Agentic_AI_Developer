"""
============================================================
TESTCONTAINERS (PYTHON) — Practical
============================================================
Runnable pytest file. Real Postgres + real Redis, ephemeral, per test-run.

Install:
    pip install pytest "testcontainers[postgres,redis]" sqlalchemy psycopg2-binary redis

Run:
    pytest 09_testcontainers_python.py -v                 # sab
    pytest 09_testcontainers_python.py -v -m integration  # sirf container tests
    pytest 09_testcontainers_python.py -v -m "not integration"
    python  09_testcontainers_python.py                   # environment diagnostics

GRACEFUL DEGRADATION (is file ka sabse important hissa):
    - testcontainers install nahi hai  → tests SKIP (error nahi)
    - Docker daemon nahi chal raha     → tests SKIP
    - sqlalchemy / redis missing       → us fixture ke tests SKIP
    Suite kabhi bhi missing infra ki wajah se RED nahi honi chahiye.

Contents:
    1.  Environment guards (import + docker ping)
    2.  Postgres fixtures (session container, per-test transaction)
    3.  Postgres tests — jo mocks/SQLite kabhi nahi pakadte
    4.  Redis fixtures (session container, per-test flush)
    5.  Redis tests — TTL, NX lock, rate-limit window
    6.  Generic DockerContainer + wait strategies
    7.  pytest-xdist per-worker patterns (reference)
    8.  CI configs (reference)
    9.  Anti-patterns (reference)
    10. Diagnostics main()

Related theory: ../theory/09_testcontainers_python.md
Kafka ke saath yahi pattern: ../../../01_Year3-4_Mid/05_Microservices/12_microservices_testing.md
"""

from __future__ import annotations

import functools
import os
import socket
import uuid


# ============================================================
# 1. ENVIRONMENT GUARDS
# ============================================================
# pytest hi na ho to file ko chup-chaap exit karo — traceback dikhane ka
# koi fayda nahi, kyunki bina pytest ke ye file kuch kar hi nahi sakti.
try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover
    print("pytest missing. Install: pip install pytest 'testcontainers[postgres,redis]'")
    raise SystemExit(0)


# --- Guard A: kya testcontainers installed hai? -------------------
# import-time pe ImportError raise NAHI karna — warna collection hi phat jayegi.
#
# VERSION NOTE (asli gotcha, tutorials me nahi milta):
#   testcontainers >= 4.13 me saare service modules `testcontainers.community.*`
#   me shift ho gaye. Purane paths (`testcontainers.postgres`) abhi bhi kaam
#   karte hain par DeprecationWarning dete hain — aur `filterwarnings = error`
#   wale repos me woh warning aapki poori suite ko RED kar degi.
#   Isliye: naya path pehle, purana fallback.
try:
    try:
        from testcontainers.community.postgres import PostgresContainer
        from testcontainers.community.redis import RedisContainer
    except ImportError:                      # testcontainers < 4.13
        from testcontainers.postgres import PostgresContainer
        from testcontainers.redis import RedisContainer

    # core.* dono versions me same jagah hai
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    # Structured wait strategies (testcontainers >= 4.13). Purane versions me
    # sirf `wait_for_logs()` tha — aur ab woh string-predicate ke saath
    # DeprecationWarning deta hai. Naya API available ho to wahi use karo.
    try:
        from testcontainers.core.wait_strategies import LogMessageWaitStrategy

        HAS_WAIT_STRATEGIES = True
    except ImportError:
        LogMessageWaitStrategy = None  # type: ignore[assignment,misc]
        HAS_WAIT_STRATEGIES = False

    HAS_TESTCONTAINERS = True
    TC_IMPORT_ERROR = ""
except Exception as exc:  # ImportError, ya extras missing ki wajah se kuch aur
    PostgresContainer = RedisContainer = DockerContainer = None  # type: ignore[assignment]
    wait_for_logs = LogMessageWaitStrategy = None  # type: ignore[assignment]
    HAS_TESTCONTAINERS = False
    HAS_WAIT_STRATEGIES = False
    TC_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


# --- Guard B: kya Docker daemon zinda hai? ------------------------
@functools.lru_cache(maxsize=1)
def docker_available() -> bool:
    """
    Docker reachable hai ya nahi — ek baar check, phir cached.

    Ye check zaroori hai kyunki `pip install testcontainers` succeed karta hai
    chahe Docker install hi na ho. Bina is guard ke aapko har test pe
    `DockerException: Error while fetching server API version` milega —
    yaani 40 RED tests, jabki asli message "Docker chalao" hai.
    """
    if not HAS_TESTCONTAINERS:
        return False
    try:
        import docker  # testcontainers ke saath aata hai

        client = docker.from_env()
        client.ping()
        client.close()
        return True
    except Exception:
        # Common causes: daemon band, DOCKER_HOST galat (colima/podman/Rancher),
        # socket permission, rootless podman.
        return False


def _skip_reason() -> str:
    if not HAS_TESTCONTAINERS:
        return f"testcontainers not installed ({TC_IMPORT_ERROR})"
    if not docker_available():
        return "Docker daemon not reachable (check `docker info` / DOCKER_HOST)"
    return ""


# Module-level marks: har test yahan integration hai aur Docker maangta hai.
# `-m "not integration"` se poori file ek second me skip ho jayegi.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not HAS_TESTCONTAINERS or not docker_available(),
        reason=_skip_reason() or "docker available",
    ),
]

# Images PIN karo. `latest` matlab ek din bina kisi commit ke CI red.
PG_IMAGE = os.getenv("TEST_PG_IMAGE", "postgres:16-alpine")
REDIS_IMAGE = os.getenv("TEST_REDIS_IMAGE", "redis:7-alpine")


# ============================================================
# 2. POSTGRES FIXTURES
# ============================================================
# Golden rule: CONTAINER session-scoped (mehnga, ~2s),
#              DATA per-test-scoped (sasta, transaction rollback).

@pytest.fixture(scope="session")
def postgres_container():
    """
    Ek Postgres poori test session ke liye.

    tmpfs + fsync=off  → datadir RAM me, disk sync off. Write-heavy DB tests
    2-5x tez ho jate hain. Ye PRODUCTION me data-loss config hai — yahan
    isliye safe hai kyunki container test ke baad delete ho jata hai.
    """
    container = PostgresContainer(
        PG_IMAGE, username="test", password="test", dbname="test"
    ).with_command(
        "postgres -c fsync=off -c full_page_writes=off "
        "-c synchronous_commit=off -c max_connections=100"
    )

    # API NOTE: tmpfs ke do rup hain, version ke hisaab se.
    #   >= 4.13 : .with_tmpfs_mount(path, size)      <- typed helper
    #   <  4.13 : .with_kwargs(tmpfs={path: opts})   <- raw docker kwargs
    # Naye version pe `with_kwargs(tmpfs=...)` dena CRASH karta hai:
    #   TypeError: create() got multiple values for keyword argument 'tmpfs'
    # ...kyunki library khud bhi `tmpfs=` pass karti hai. Classic double-pass bug.
    #
    # ⚠️ TRAP: `with_tmpfs_mount(path, size)` ka doosra arg naam se "size" hai,
    # par asal me ye Docker ka raw tmpfs OPTIONS string hai. Bare "256m" dene pe
    # daemon reject karta hai:  APIError: invalid tmpfs option ["256m"]
    # Sahi: "size=256m" (ya "rw,size=256m").
    if hasattr(container, "with_tmpfs_mount"):
        container = container.with_tmpfs_mount(
            "/var/lib/postgresql/data", "rw,noexec,nosuid,size=256m"
        )
    else:
        container = container.with_kwargs(
            tmpfs={"/var/lib/postgresql/data": "rw,noexec,nosuid,size=256m"}
        )

    with container as pg:
        # `with` block exit hote hi container kill + volume remove.
        # Agar process crash ho jaye to ryuk sidecar cleanup karega.
        yield pg


@pytest.fixture(scope="session")
def pg_engine(postgres_container):
    """SQLAlchemy engine + schema. Schema sirf EK BAAR banta hai."""
    sa = pytest.importorskip("sqlalchemy", reason="pip install sqlalchemy psycopg2-binary")
    pytest.importorskip("psycopg2", reason="pip install psycopg2-binary")

    # get_connection_url() psycopg2 dialect deta hai:
    #   postgresql+psycopg2://test:test@localhost:49213/test
    # asyncpg chahiye ho to:
    #   url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    url = postgres_container.get_connection_url()
    engine = sa.create_engine(url, pool_pre_ping=True, future=True)

    # Real project me yahan `alembic upgrade head` hota — tab migrations bhi
    # test ho jati hain. Yahan standalone rakhne ke liye raw DDL.
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                email       TEXT NOT NULL UNIQUE,
                prefs       JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_prefs ON users USING GIN (prefs)"
        ))

    yield engine
    engine.dispose()


@pytest.fixture
def db(pg_engine):
    """
    Per-test connection ek transaction me lipti hui, end me ROLLBACK.

    Isolation yahan se aata hai — container se nahi. Container shared hai;
    agar aap rollback nahi karoge to test #1 ka data test #2 ko dikhega
    aur aapko order-dependent flaky suite milegi.
    """
    conn = pg_engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()   # sab kuch gayab — agla test saaf slate pe
        conn.close()


# ============================================================
# 3. POSTGRES TESTS — jo mock/SQLite kabhi nahi pakadte
# ============================================================

def test_it_is_actually_postgres(db):
    """Sanity: hum sach me Postgres se baat kar rahe hain, kisi fake se nahi."""
    sa = pytest.importorskip("sqlalchemy")
    version = db.execute(sa.text("SELECT version()")).scalar_one()
    assert "PostgreSQL" in version
    print(f"\n[testcontainers] connected to: {version.split(',')[0]}")


def test_unique_constraint_is_enforced(db):
    """
    Mock ke saath ye test likhna hi impossible hai — mock jo bolo wahi karega.
    SQLite ise pakad leta hai, par error type/message alag hota hai,
    isliye aapka `except IntegrityError` handling prod me alag behave karta hai.
    """
    sa = pytest.importorskip("sqlalchemy")
    from sqlalchemy.exc import IntegrityError

    db.execute(sa.text("INSERT INTO users (email) VALUES (:e)"), {"e": "a@x.com"})

    with pytest.raises(IntegrityError) as err:
        db.execute(sa.text("INSERT INTO users (email) VALUES (:e)"), {"e": "a@x.com"})

    # Postgres ka asli SQLSTATE 23505 = unique_violation.
    assert "23505" in str(err.value) or "duplicate key" in str(err.value).lower()


def test_jsonb_containment_query(db):
    """
    `@>` containment operator SQLite me EXIST HI NAHI KARTA.
    Ye woh classic bug hai: test green (SQLite), prod me
    `syntax error at or near "@"`. Real Postgres = real answer.
    """
    sa = pytest.importorskip("sqlalchemy")

    db.execute(
        sa.text("INSERT INTO users (email, prefs) VALUES (:e, CAST(:p AS jsonb))"),
        {"e": "dark@x.com", "p": '{"theme": "dark", "beta": true}'},
    )
    db.execute(
        sa.text("INSERT INTO users (email, prefs) VALUES (:e, CAST(:p AS jsonb))"),
        {"e": "light@x.com", "p": '{"theme": "light"}'},
    )

    rows = db.execute(sa.text(
        """SELECT email FROM users WHERE prefs @> '{"theme": "dark"}'::jsonb"""
    )).scalars().all()

    assert rows == ["dark@x.com"]


def test_rollback_isolation_previous_test_data_is_gone(db):
    """
    Pichhle test ne 'dark@x.com' insert kiya tha. Container wahi hai,
    par transaction rollback ki wajah se table khali hai.
    Ye test proof hai ki fixture isolation kaam kar raha hai.
    """
    sa = pytest.importorskip("sqlalchemy")
    count = db.execute(sa.text("SELECT count(*) FROM users")).scalar_one()
    assert count == 0


def test_timestamptz_is_timezone_aware(db):
    """
    SQLite timestamps ko strings ki tarah rakhta hai — tz info gayab.
    Postgres `timestamptz` UTC-aware datetime deta hai. Ye farq
    scheduling/expiry bugs ki jad hota hai.
    """
    sa = pytest.importorskip("sqlalchemy")
    db.execute(sa.text("INSERT INTO users (email) VALUES ('tz@x.com')"))
    created = db.execute(sa.text("SELECT created_at FROM users")).scalar_one()
    assert created.tzinfo is not None


def test_index_is_actually_used(db):
    """
    Perf regression guard. Mocks ke paas query planner nahi hota.
    EXPLAIN se aap assert kar sakte ho ki index bana bhi hai aur use bhi ho raha hai.
    (Choti table pe planner seq scan choose kar sakta hai — isliye enable_seqscan off.)
    """
    sa = pytest.importorskip("sqlalchemy")
    db.execute(sa.text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(db.execute(sa.text(
        """EXPLAIN SELECT email FROM users WHERE prefs @> '{"theme": "dark"}'::jsonb"""
    )).scalars().all())
    assert "ix_users_prefs" in plan, f"GIN index not used:\n{plan}"


# ============================================================
# 4. REDIS FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def redis_container():
    """Session-scoped Redis. Startup ~300ms — Postgres se bhi sasta."""
    with RedisContainer(REDIS_IMAGE) as rc:
        yield rc


@pytest.fixture
def redis_client(redis_container):
    """
    Per-test FLUSHALL. Redis me transaction-rollback jaisa kuch nahi hai,
    isliye isolation ka tareeka hai: har test se pehle aur baad me sab uda do.
    In-memory hai, isliye ye microseconds ka kaam hai.
    """
    pytest.importorskip("redis", reason="pip install redis")
    client = redis_container.get_client(decode_responses=True)
    client.flushall()
    yield client
    client.flushall()


# ============================================================
# 5. REDIS TESTS — jahan fakeredis jhooth bolta hai
# ============================================================

def test_redis_is_real_redis(redis_client):
    info = redis_client.info("server")
    assert info["redis_version"]
    print(f"\n[testcontainers] connected to: Redis {info['redis_version']}")


def test_set_get_roundtrip(redis_client):
    redis_client.set("user:1:name", "Alice")
    assert redis_client.get("user:1:name") == "Alice"


def test_ttl_is_set_and_counted_down(redis_client):
    """
    Real expiry semantics. fakeredis time ko simulate karta hai —
    theek hai jab tak aap PX/EX ke edge cases pe depend na karo.
    """
    redis_client.set("session:abc", "token", ex=60)
    ttl = redis_client.ttl("session:abc")
    assert 55 <= ttl <= 60
    assert redis_client.ttl("nonexistent:key") == -2      # -2 = key hi nahi hai
    redis_client.set("forever", "x")
    assert redis_client.ttl("forever") == -1              # -1 = no expiry


def test_distributed_lock_nx_semantics(redis_client):
    """
    `SET key val NX PX ttl` = distributed lock ka core.
    Ye WAHI code hai jise mock karna sabse khatarnak hai — lock ka bug
    hi to woh cheez hai jo aap catch karna chahte ho.
    """
    key = f"lock:order:{uuid.uuid4()}"

    acquired_a = redis_client.set(key, "worker-a", nx=True, px=5000)
    assert acquired_a is True                       # pehla jeeta

    acquired_b = redis_client.set(key, "worker-b", nx=True, px=5000)
    assert acquired_b is None                       # doosra haara — NX ne roka

    assert redis_client.get(key) == "worker-a"      # owner badla nahi
    assert 0 < redis_client.pttl(key) <= 5000       # TTL laga hua hai


def test_safe_lock_release_with_lua(redis_client):
    """
    Naive release (`if get()==me: delete()`) racy hai — check aur delete ke
    beech lock expire ho sakta hai aur aap kisi AUR ka lock delete kar doge.
    Sahi tareeka Lua script hai (atomic). Iska atomicity guarantee sirf
    REAL Redis pe hi verify hota hai.
    """
    key = f"lock:{uuid.uuid4()}"
    token = str(uuid.uuid4())
    redis_client.set(key, token, nx=True, px=5000)

    lua = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    release = redis_client.register_script(lua)

    assert release(keys=[key], args=["wrong-token"]) == 0   # dusre ka lock safe
    assert redis_client.exists(key) == 1

    assert release(keys=[key], args=[token]) == 1           # apna lock chhoot gaya
    assert redis_client.exists(key) == 0


def test_fixed_window_rate_limiter(redis_client):
    """INCR + EXPIRE = simplest rate limiter. Real atomicity chahiye."""
    key = f"ratelimit:ip:1.2.3.4:{uuid.uuid4()}"
    limit = 3

    def allow() -> bool:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60, nx=True)   # TTL sirf pehli baar set ho
        count, _ = pipe.execute()
        return count <= limit

    assert [allow() for _ in range(5)] == [True, True, True, False, False]
    assert 0 < redis_client.ttl(key) <= 60


def test_pipeline_is_isolated(redis_client):
    """Pipeline + transaction: saare commands ek saath apply hote hain."""
    with redis_client.pipeline(transaction=True) as pipe:
        pipe.set("a", "1")
        pipe.incr("counter")
        pipe.incr("counter")
        results = pipe.execute()
    assert results == [True, 1, 2]
    assert redis_client.get("a") == "1"


# ============================================================
# 6. GENERIC DockerContainer + WAIT STRATEGIES
# ============================================================
# Har service ke liye ready-made class nahi hai (MinIO, Mailhog, custom app...).
# `DockerContainer` universal escape hatch hai — image + env + ports + wait.

@pytest.fixture(scope="module")
def generic_redis_url():
    """
    Wahi Redis image, par GENERIC API se — taaki pattern saaf dikhe
    aur koi extra image pull na karna pade.
    """
    container = (
        DockerContainer(REDIS_IMAGE)
        .with_exposed_ports(6379)          # random HOST port — never with_bind_ports()
        .with_command("redis-server --appendonly no --save ''")
    )

    # Wait strategy #1: log message. Container "running" hone aur "ready" hone me
    # farq hai — bina wait ke connection refused milega.
    #
    # Modern API: .waiting_for(LogMessageWaitStrategy(...)) — container START pe
    # hi block karta hai. Purana `wait_for_logs(c, "...")` ab string predicate ke
    # saath DeprecationWarning deta hai.
    #
    # `times=2` woh Postgres wala classic trap solve karta hai jahan
    # "ready to accept connections" DO BAAR aata hai (initdb + asli server).
    if HAS_WAIT_STRATEGIES:
        container = container.waiting_for(
            LogMessageWaitStrategy("Ready to accept connections")
        )
        with container as c:
            yield f"redis://{c.get_container_host_ip()}:{c.get_exposed_port(6379)}/0"
    else:
        with container as c:
            wait_for_logs(c, "Ready to accept connections", timeout=30)
            yield f"redis://{c.get_container_host_ip()}:{c.get_exposed_port(6379)}/0"


def test_generic_container_works(generic_redis_url):
    redis_mod = pytest.importorskip("redis")
    client = redis_mod.Redis.from_url(generic_redis_url, decode_responses=True)
    assert client.ping() is True
    client.set("k", "v")
    assert client.get("k") == "v"
    client.close()


def test_wait_strategy_tcp_probe(generic_redis_url):
    """
    Wait strategy #2: TCP connect. Sabse WEAK signal —
    port bind ho jana ready hona nahi hai (Postgres recovery ke dauraan bhi bind karta hai).
    Reference ke liye rakha hai; production me app-level probe use karo.
    """
    from urllib.parse import urlparse

    parsed = urlparse(generic_redis_url)
    with socket.create_connection((parsed.hostname, parsed.port), timeout=2) as sock:
        assert sock is not None


WAIT_STRATEGIES = r'''
# testcontainers >= 4.13 me structured wait strategies hain. Container ko
# DECLARATIVELY batao ki "ready" ka matlab kya hai; .start() khud block karega.
from testcontainers.core.wait_strategies import (
    LogMessageWaitStrategy,   # log line
    HttpWaitStrategy,         # HTTP endpoint (STRONGEST for web services)
    PortWaitStrategy,         # TCP port (WEAKEST — bind != ready)
    HealthcheckWaitStrategy,  # image ka apna HEALTHCHECK
    ExecWaitStrategy,         # container ke andar command
    FileExistsWaitStrategy,
    CompositeWaitStrategy,    # sab satisfy hone chahiye
)

# ---- #3: application-level HTTP probe (STRONGEST) ----
container.waiting_for(
    HttpWaitStrategy(port=9000).for_path("/minio/health/live").for_status_code(200)
)

# ---- #4: image ka apna healthcheck ----
container.waiting_for(HealthcheckWaitStrategy())
# ...agar image me HEALTHCHECK nahi hai to khud daalo:
DockerContainer("postgres:16-alpine").with_kwargs(
    healthcheck={
        "test": ["CMD-SHELL", "pg_isready -U test"],
        "interval": 500_000_000,   # nanoseconds -> 0.5s
        "retries": 20,
    }
)

# ---- #5: multiple conditions ----
container.waiting_for(CompositeWaitStrategy(
    LogMessageWaitStrategy("ready to accept connections"),
    PortWaitStrategy(port=5432),
))

# ---- Postgres ka classic trap ----
# "database system is ready to accept connections" DO BAAR print hota hai:
#   1. initdb ka temporary server   2. asli server
# Pehli line pe connect karoge -> connection refused.
# Naye API me iske liye dedicated `times` param hai:
LogMessageWaitStrategy("ready to accept connections", times=2)

# legacy (< 4.13) — regex se do occurrence match karo:
wait_for_logs(container,
              r"ready to accept connections[\s\S]*ready to accept connections",
              timeout=60)

# ---- legacy custom probe (< 4.13) ----
from testcontainers.core.waiting_utils import wait_container_is_ready

@wait_container_is_ready(Exception)      # retry until no exception
def wait_http_health(url: str):
    import urllib.request
    with urllib.request.urlopen(f"{url}/health", timeout=2) as r:
        assert r.status == 200

# ---- ❌ NEVER ----
container.start()
time.sleep(5)      # slow CI pe fail, fast machine pe 5s barbaad
'''


# ============================================================
# 7. pytest-xdist PATTERNS (reference)
# ============================================================
# GOTCHA: `scope="session"` xdist ke saath PER-WORKER hota hai, per-RUN nahi.
#   pytest -n 4  ->  4 alag Postgres containers.

XDIST_OPTION_A = '''
# ---- Option A: accept karo (simplest, recommended chhote suites ke liye) ----
# Har worker ka apna container = perfect isolation, zero coordination code.
# Alpine images pe 4 x 2s startup acceptable hai.
#   pytest -n 4
'''

XDIST_OPTION_B = '''
# ---- Option B: ek container, per-worker DATABASE ----
# pip install filelock
import pytest
from filelock import FileLock
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory, worker_id):
    """`worker_id` xdist deta hai: "master" (no xdist) ya "gw0","gw1"..."""
    if worker_id == "master":
        with PostgresContainer("postgres:16-alpine") as pg:
            yield pg.get_connection_url()
        return

    root = tmp_path_factory.getbasetemp().parent      # sab workers ke liye common
    url_file = root / "pg_url.txt"

    with FileLock(str(url_file) + ".lock"):
        if url_file.is_file():
            url, container = url_file.read_text(), None      # koi aur start kar chuka
        else:
            container = PostgresContainer("postgres:16-alpine").start()
            url = container.get_connection_url()
            url_file.write_text(url)

    yield url

    if container is not None:
        container.stop()
    # WARNING: jis worker ne banaya woh pehle khatam ho sakta hai.
    # Isliye ryuk ko DISABLE mat karna — wahi aapka safety net hai.


@pytest.fixture(scope="session")
def engine(pg_url, worker_id):
    """Har worker apna DB banaye -> cross-worker data corruption nahi."""
    from sqlalchemy import create_engine, text
    admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    dbname = f"test_{worker_id}"
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin.dispose()
    return create_engine(pg_url.rsplit("/", 1)[0] + f"/{dbname}")
'''

XDIST_OPTION_C = '''
# ---- Option C: container tests ek worker pe serialize karo ----
@pytest.mark.xdist_group("db")
def test_something(db):
    ...

#   pytest -n 4 --dist=loadgroup
# Unit tests parallel rehte hain, integration serial. Kam se kam code.

# ---- Practical reality (aksar sabse achha) ----
#   pytest -m "not integration" -n auto     # fast job
#   pytest -m integration       -n 0        # alag CI job
'''


# ============================================================
# 8. CI CONFIGS (reference)
# ============================================================

CI_GITHUB_ACTIONS = '''
# .github/workflows/test.yml
# GitHub-hosted runners pe Docker PEHLE SE hai -> testcontainers as-is chalta hai.
name: tests
on: [push, pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[test]"
      - run: pytest -m "not integration" -n auto

  integration:
    runs-on: ubuntu-latest
    env:
      TESTCONTAINERS_RYUK_DISABLED: "true"   # ephemeral VM — 5 min me delete
      DOCKER_CLIENT_TIMEOUT: "300"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      # Pre-pull -> pehla test 40s ka pull-wait "flaky timeout" jaisa nahi lagega
      - run: docker pull postgres:16-alpine & docker pull redis:7-alpine & wait
      - run: pip install -e ".[test]"
      - run: pytest -m integration -n 0
'''

CI_GHA_SERVICES_ALTERNATIVE = '''
# ---- Alternative: GHA `services:` (testcontainers ke BINA) ----
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_USER: test, POSTGRES_PASSWORD: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s
          --health-timeout 5s --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - run: pytest
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test

# services: vs testcontainers
#   services:        CI-parallel start (test time me count nahi), par SIRF CI me,
#                    fixed ports, ek hi instance, har CI provider pe rewrite.
#   testcontainers:  wahi code local + har CI pe, dynamic ports, per-fixture config.
# Asli faisla speed ka nahi — LOCAL/CI PARITY ka hai. `git clone && pytest`
# bina kisi README step ke chalna chahiye.
'''

CI_GITLAB_DIND = '''
# .gitlab-ci.yml — Docker-in-Docker
# Poori isolation, par privileged chahiye aur image cache har run pe COLD.
integration:
  image: python:3.12
  services:
    - name: docker:27-dind
      alias: docker
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""
    TESTCONTAINERS_RYUK_PRIVILEGED: "true"
  script:
    - pip install -e ".[test]"
    - pytest -m integration
'''

CI_GITLAB_SOCKET_MOUNT = '''
# .gitlab-ci.yml — Docker socket mount
# Fast (layer cache reuse), par container ko host Docker pe root-equivalent access.
integration:
  image: python:3.12
  variables:
    # NETWORKING TRAP: sibling container HOST pe start hota hai, aapke test
    # container pe nahi -> "localhost" ka matlab alag hai. Isse fix karo:
    TESTCONTAINERS_HOST_OVERRIDE: "host.docker.internal"
    TESTCONTAINERS_RYUK_DISABLED: "false"   # persistent runner -> ALWAYS false
  script:
    - pytest -m integration
# runner config me: volumes = ["/var/run/docker.sock:/var/run/docker.sock"]
'''

LOCAL_DEV_REUSE = '''
# ---- Local inner-loop speed: container reuse ----
# ~/.testcontainers.properties   (opt-in, per-user)
testcontainers.reuse.enable=true

# code me:
PostgresContainer("postgres:16-alpine").with_reuse(True)

# Startup ~2s -> ~0ms (container run ke baad zinda rehta hai).
# ⚠️ Reuse ke saath ryuk container ko nahi maarta (by design).
# ⚠️ CI me reuse KABHI nahi — stale state test ko jhooth-mooth pass kara degi.

# ---- Non-standard Docker sockets (colima / podman / Rancher Desktop) ----
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock
# podman rootless:
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock

# ⚠️ In VMs pe ryuk aksar start hi nahi hota. Ryuk ko host ka docker.sock
# bind-mount karna padta hai, aur woh path VM ke andar exist nahi karta:
#   docker.errors.APIError: 500 Server Error ... error while creating mount
#   source path '/Users/you/.colima/default/docker.sock':
#   mkdir ...: operation not supported
# Ye aapke test ka bug NAHI hai — HAR container isi pe error karega.
export TESTCONTAINERS_RYUK_DISABLED=true

# Trade-off: ab crashed runs khud clean karne padenge —
#   docker ps -aq --filter label=org.testcontainers=true | xargs -r docker rm -f
'''


# ============================================================
# 9. ANTI-PATTERNS (reference)
# ============================================================

ANTI_PATTERNS = '''
================================================================
❌ 1. Import-time container start
pg = PostgresContainer("postgres:16").start()   # module level
# `pytest --collect-only` bhi Docker maangega. Hamesha FIXTURE ke andar.

❌ 2. Function-scoped container
@pytest.fixture                       # har test 2s
def postgres(): ...
# 100 tests = 200 seconds. Container session, data function.

❌ 3. `latest` tag
PostgresContainer("postgres:latest")
# Ek din registry Postgres 17 de dega -> bina kisi commit ke CI red.

❌ 4. Fixed host ports
DockerContainer("redis:7").with_bind_ports(6379, 6379)
# xdist / concurrent CI job -> "port is already allocated".

❌ 5. sleep() as wait strategy
container.start(); time.sleep(5)
# Slow CI pe fail, fast machine pe 5s barbaad. Readiness probe use karo.

❌ 6. Data cleanup bhool jana
# Container session-scoped hai -> state tests ke beech LEAK hoti hai.
# Postgres: transaction rollback. Redis: flushall. Kafka: unique topic names.

❌ 7. Persistent CI runner pe ryuk disable
TESTCONTAINERS_RYUK_DISABLED=true
# Har crashed run ek orphan container chhodega -> 2 hafte me disk full.

❌ 8. Skip-guard na lagana
# Docker na ho to suite ERROR karti hai, SKIP nahi -> dev machines pe
# log tests chalana chhod dete hain. Is file ka §1 dekho.

❌ 9. Sab kuch testcontainers se test karna
def test_discount(): ...    # pure function pe 2s ka container?
# Test pyramid ulta ho jayega. Unit = mocks/fakes. Integration = containers.

❌ 10. Third-party SaaS ke liye testcontainers dhoondhna
# Stripe/Twilio/SendGrid ka Docker image nahi hai. Wahan contract testing
# (pact) ya mock server (WireMock/respx) use karo.
================================================================
'''


DECISION_TABLE = """
================================================================
MOCKS vs FAKES vs TESTCONTAINERS vs STAGING
================================================================
Criteria            Mock       Fake        Testcontainers   Staging
----------------------------------------------------------------
Speed               µs         ms          100ms-3s         seconds
Fidelity            zero       partial     FULL             full
Isolation           perfect    perfect     perfect          ❌ shared
SQL dialect bugs    ❌         ❌          ✅               ✅
Migrations tested   ❌         partial     ✅               ✅
Perf/index issues   ❌         ❌          partial          ✅
Needs Docker        ❌         ❌          ✅               ❌
CI setup cost       zero       zero        medium           high
Works offline       ✅         ✅          ✅ (cached)      ❌
Parallel-safe       ✅         ✅          ✅ (care se)     ❌
----------------------------------------------------------------
Best for            pure       fast repo   INTEGRATION      pre-prod
                    logic      tests       GATE             smoke
================================================================
Layering jo actually kaam karta hai:
  Unit         60%  -> mocks/fakes      -> har save pe
  Integration  30%  -> TESTCONTAINERS   -> har PR pe
  Contract      8%  -> pact/wiremock    -> external services
  E2E/staging   2%  -> deployed env     -> merge ke baad
================================================================
"""


# ============================================================
# 10. DIAGNOSTICS MAIN
# ============================================================
def _diagnostics() -> None:
    """`python 09_testcontainers_python.py` — environment check + reference dump."""
    print("=" * 60)
    print("TESTCONTAINERS (PYTHON)")
    print("=" * 60)

    print("\n--- ENVIRONMENT ---")
    print(f"  testcontainers installed : {HAS_TESTCONTAINERS}")
    if not HAS_TESTCONTAINERS:
        print(f"      reason               : {TC_IMPORT_ERROR}")
        print("      fix                  : pip install 'testcontainers[postgres,redis]'")
    print(f"  docker reachable         : {docker_available()}")
    if HAS_TESTCONTAINERS and not docker_available():
        print("      fix                  : start Docker, or set DOCKER_HOST")
        print("                             (colima/podman/Rancher use custom sockets)")

    for mod in ("pytest", "sqlalchemy", "psycopg2", "redis"):
        try:
            __import__(mod)
            print(f"  {mod:<24} : ok")
        except ImportError:
            print(f"  {mod:<24} : MISSING")

    reason = _skip_reason()
    print("\n  verdict: " + ("all tests will RUN" if not reason
                             else f"all tests will SKIP ({reason})"))

    print("\n--- WAIT STRATEGIES ---")
    print(WAIT_STRATEGIES)
    print("\n--- XDIST: OPTION A ---")
    print(XDIST_OPTION_A)
    print("\n--- XDIST: OPTION B ---")
    print(XDIST_OPTION_B)
    print("\n--- XDIST: OPTION C ---")
    print(XDIST_OPTION_C)
    print("\n--- CI: GITHUB ACTIONS ---")
    print(CI_GITHUB_ACTIONS)
    print("\n--- CI: GHA services: ALTERNATIVE ---")
    print(CI_GHA_SERVICES_ALTERNATIVE)
    print("\n--- CI: GITLAB DinD ---")
    print(CI_GITLAB_DIND)
    print("\n--- CI: GITLAB SOCKET MOUNT ---")
    print(CI_GITLAB_SOCKET_MOUNT)
    print("\n--- LOCAL DEV: REUSE + SOCKETS ---")
    print(LOCAL_DEV_REUSE)
    print(ANTI_PATTERNS)
    print(DECISION_TABLE)

    print("Run the tests:")
    print("  pytest 09_testcontainers_python.py -v")
    print("  pytest 09_testcontainers_python.py -v -m 'not integration'")


if __name__ == "__main__":
    _diagnostics()
