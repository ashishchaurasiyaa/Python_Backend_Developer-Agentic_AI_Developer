# Docker Compose — Services, Volumes, Networks, Env
**DevOps Track · Phase 5: Docker**

## Quick Concepts

- **Compose file** = declarative YAML describing a multi-container application
- **Service** = one logical component (api, db, redis) — Compose runs one or more containers per service
- **Project** = the set of all services in one Compose file, namespaced by directory name (or `-p` flag)
- **Volume** (in Compose) = named, Docker-managed persistent storage declared at the top level
- **Network** (in Compose) = an isolated bridge network auto-created per project; services reach each other by service name (DNS)
- **`depends_on`** = controls startup ORDER, not readiness — pair with `healthcheck` + `condition`
- **`env_file`** = load a `.env`-style file's KEY=VALUE pairs into a service's environment
- **`.env` (project root)** = special file Compose reads automatically for **variable substitution inside the YAML itself** (`${VAR}`), distinct from `env_file`

---

## Why This Matters

```
Almost no real backend app is "just one container." The moment you
need a database + cache + API together, you need Compose (locally)
or a full orchestrator (in production). Compose is also the fastest
way to reproduce a "works on my machine" bug — one command, one file,
identical environment for every teammate.

depends_on WITHOUT healthcheck is the #1 Compose footgun: your app
container starts before Postgres is actually ready to accept
connections, crashes on first query, and looks like a flaky bug.
```

---

## Services

A service is a blueprint — Compose creates containers from it and can scale it to N replicas.

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime          # multi-stage build target
    image: myapp:1.0           # tag given to the built image
    container_name: myapp-api  # fixed name (avoid in scaled setups — clashes)
    ports:
      - "8000:8000"            # host:container
    restart: unless-stopped    # no | always | on-failure | unless-stopped
    command: ["uvicorn", "main:app", "--host", "0.0.0.0"]  # overrides image CMD
```

`restart` policies:

| Policy | Behavior |
|---|---|
| `no` | Never restart (default) |
| `always` | Restart no matter the exit code, even after daemon restart |
| `on-failure[:max-retries]` | Restart only on non-zero exit, optional retry cap |
| `unless-stopped` | Like `always`, but stays stopped if you explicitly `docker stop`ed it |

---

## Volumes

Named volumes declared at the top level are Docker-managed and persist across `docker compose down` (but not `docker compose down -v`).

```yaml
services:
  db:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data   # named volume — persistent
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro  # bind mount, read-only

volumes:
  postgres_data:          # declared here, Docker manages the actual location
    driver: local
```

```bash
docker volume ls
docker volume inspect myapp_postgres_data
docker compose down       # containers removed, VOLUMES KEPT
docker compose down -v    # containers AND volumes removed — data loss
```

---

## Networks

By default, Compose creates one bridge network per project and attaches every service to it. Services resolve each other **by service name** via Docker's embedded DNS — no manual IP management.

```yaml
services:
  api:
    networks:
      - backend
  db:
    networks:
      - backend
  # api can reach db at hostname "db", port 5432 — no config needed

networks:
  backend:
    driver: bridge
```

For multi-tier isolation (e.g., a frontend network the DB should NOT be reachable from):

```yaml
services:
  nginx:
    networks: [frontend]
  api:
    networks: [frontend, backend]   # bridges both
  db:
    networks: [backend]             # unreachable from nginx directly

networks:
  frontend:
  backend:
```

---

## Environment Variables — Three Distinct Mechanisms

```yaml
services:
  api:
    environment:                    # 1. inline, in the YAML itself
      - DEBUG=false
      - LOG_LEVEL=info
    env_file:
      - .env.api                    # 2. load KEY=VALUE pairs from a file into the container
```

```
# .env.api  (loaded INTO the container's environment)
DATABASE_URL=postgresql://user:pass@db:5432/mydb
SECRET_KEY=change-me-in-prod
```

```
# .env  (project root — Compose reads this AUTOMATICALLY for ${VAR}
#         substitution INSIDE the compose YAML file itself, before
#         the file is even parsed as a container's environment)
POSTGRES_PASSWORD=supersecret
API_PORT=8000
```

```yaml
services:
  api:
    ports:
      - "${API_PORT}:8000"          # substituted from project-root .env
  db:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # also from project-root .env
```

**The distinction that trips people up:**
- `env_file:` under a service → variables land **inside that container's environment**.
- project-root `.env` (no `env_file:` needed) → variables are available for **`${...}` substitution while Compose parses the YAML**, on the host side, before any container exists.

---

## depends_on + healthcheck — Getting Startup Order Right

```yaml
services:
  api:
    build: .
    depends_on:
      db:
        condition: service_healthy      # wait for db's healthcheck to pass
      redis:
        condition: service_started      # just wait for the container to start

  db:
    image: postgres:16
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d mydb"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

`condition` values:

| Condition | Waits for |
|---|---|
| `service_started` | Container process started (default, weakest guarantee) |
| `service_healthy` | Container's `healthcheck` reports `healthy` |
| `service_completed_successfully` | One-shot container exited with code 0 (e.g., a migration job) |

---

## Full Example — Python API + Postgres + Redis

```yaml
# docker-compose.yml
services:
  api:
    build:
      context: .
      target: runtime
    image: myapp:1.0
    ports:
      - "${API_PORT:-8000}:8000"
    env_file:
      - .env.api
    environment:
      - PYTHONUNBUFFERED=1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s
    networks:
      - backend
    restart: unless-stopped

  migrate:
    build:
      context: .
      target: runtime
    image: myapp:1.0
    command: ["python", "manage.py", "migrate", "--noinput"]
    env_file:
      - .env.api
    depends_on:
      db:
        condition: service_healthy
    networks:
      - backend
    restart: "no"          # one-shot job, never restart

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-mydb}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app}"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - backend
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  backend:
    driver: bridge
```

```
.env               # project root — for ${...} substitution in the YAML
POSTGRES_USER=app
POSTGRES_PASSWORD=devpassword
POSTGRES_DB=mydb
API_PORT=8000
```

```
.env.api            # loaded INTO the api/migrate containers
DATABASE_URL=postgresql://app:devpassword@db:5432/mydb
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=info
```

---

## Everyday Commands

```bash
docker compose up -d                    # start all services, detached
docker compose up -d --build            # rebuild images first
docker compose ps                       # status + health of each service
docker compose logs -f api              # follow one service's logs
docker compose logs -f --tail=100       # last 100 lines, all services

docker compose exec api /bin/bash       # shell into a running service
docker compose run --rm api pytest      # one-off command, own container, auto-removed

docker compose stop                     # stop containers, keep them
docker compose down                     # stop + remove containers/networks (volumes kept)
docker compose down -v                  # also remove named volumes (data loss)

docker compose config                   # print fully resolved YAML (validates + shows substitutions)
docker compose -f docker-compose.yml -f docker-compose.override.yml up  # layer overrides
```

### Senior Tip

```
Compose is a LOCAL DEV / SINGLE-HOST tool. It has no concept of
scheduling across multiple machines, no self-healing across node
failure, no rolling updates with real health-gated rollback.

The moment you need multi-host, self-healing, or zero-downtime
rolling deploys — that's the line where Kubernetes takes over.
Compose's `deploy:` key exists for Docker Swarm mode but is largely
legacy; don't confuse it with Kubernetes' Deployment object.
```

---

## Interview Angle

**Q: My API container crashes on startup with a "connection refused" to Postgres, even though `depends_on: [db]` is set. Why?**
`depends_on` without a `condition` only waits for the DB container to **start**, not for Postgres to actually be **accepting connections** — those are different points in time (Postgres does its own init/recovery on first boot). Fix: add a `healthcheck` to the `db` service and `depends_on: db: condition: service_healthy` on the api service.

**Q: What's the difference between the project-root `.env` file and a service's `env_file:` entry?**
Root `.env` is read by the Compose CLI itself, before container creation, purely to substitute `${VAR}` placeholders inside the YAML. `env_file:` under a service loads KEY=VALUE pairs directly into that container's runtime environment. They can even hold different values for the same key with no conflict — they operate at different stages.

**Q: How do you run a one-off migration without leaving a stopped container behind?**
`docker compose run --rm api python manage.py migrate` — `--rm` removes the container as soon as it exits, unlike `docker compose up` which leaves the container in an exited state for inspection.
