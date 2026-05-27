# Lecture 2: 12-Factor App Design

> *"A blueprint for building scalable, portable, and maintainable SaaS applications."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Introduction to 12-Factor methodology**
- **Factor 1** — Codebase (single repo, many deploys)
- **Factor 2** — Dependencies (explicit declaration)
- **Factor 3** — Config (environment-based)
- **Factor 4** — Backing services (attached resources)
- **Factor 5** — Build, release, run (separation)
- **Factor 6** — Processes (stateless)
- **Factor 7** — Port binding (self-contained)
- **Factor 8** — Concurrency (scale via processes)
- **Factor 9** — Disposability (fast startup, graceful shutdown)
- **Factor 10** — Dev/prod parity
- **Factor 11** — Logs (treat as event streams)
- **Factor 12** — Admin processes (one-off)

---

## 1. Introduction to 12-Factor Methodology

### Origin

```
Created by Heroku team (2011).
Based on lessons running 1000s of apps in production.
Codifies best practices for cloud-native applications.

→ Now industry standard for SaaS development.
```

### Why It Matters

```
12-factor apps:
   ✓ Scale horizontally without redesign
   ✓ Deploy to any cloud
   ✓ Easy to maintain
   ✓ Resilient to failures
   ✓ Friendly to automated deployment
```

### The Big Picture

```
┌──────────────────────────────────────────────────────────────┐
│              12 FACTORS                                       │
├──────────────────────────────────────────────────────────────┤
│  1. Codebase           │ One per app, many deploys           │
│  2. Dependencies       │ Explicitly declared                  │
│  3. Config             │ Environment-based                    │
│  4. Backing services   │ Attached resources                   │
│  5. Build/release/run  │ Strictly separated                   │
│  6. Processes          │ Stateless                            │
│  7. Port binding       │ Self-contained                       │
│  8. Concurrency        │ Scale via process model              │
│  9. Disposability      │ Fast startup, graceful shutdown      │
│  10. Dev/prod parity   │ Keep environments similar            │
│  11. Logs              │ Event streams                        │
│  12. Admin processes   │ One-off processes                    │
└──────────────────────────────────────────────────────────────┘
```

### Not a Checklist

```
"You don't have to adopt all 12 at once."

Even partial adoption brings:
   ✓ Better scalability
   ✓ Easier deployment
   ✓ Better operability
   
→ Start with the most impactful ones.
```

---

## 2. Factor 1 — Codebase

### Rule

**One codebase tracked in version control, many deploys.**

### Visual

```
   ONE Codebase (Git repo)
            │
            │ Deployed to:
            │
   ┌────────┼────────┐
   │        │        │
   ▼        ▼        ▼
   Dev    Staging   Production
```

### Anti-Patterns

```
✗ Multiple repos for same app (e.g., dev branch repo, prod repo)
✗ Code copied between repos
✗ Same code deployed differently per environment
```

### Best Practice

```
✓ Single Git repo per app
✓ Branch / tag for environments
✓ Same code, different config
✓ Deploys differ only via configuration
```

---

## 3. Factor 2 — Dependencies

### Rule

**Explicitly declare and isolate dependencies.**

### Anti-Patterns

```
✗ Relying on system-wide installed packages
✗ "It works on my machine because I have X installed"
✗ Implicit dependencies on tools (curl, etc.)
```

### Best Practice

```
✓ Declare ALL dependencies in manifest:
   - Python: requirements.txt / pyproject.toml
   - Node.js: package.json
   - Java: pom.xml / build.gradle
   - Ruby: Gemfile

✓ Isolate from system:
   - virtualenv (Python)
   - node_modules (Node)
   - Containers (universal!)
```

### Example

```bash
# Python
requirements.txt:
   fastapi==0.104.0
   uvicorn==0.24.0
   sqlalchemy==2.0.0

# Install in isolated env:
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
```

---

## 4. Factor 3 — Config

### Rule

**Store config in the environment, NOT in code.**

### What Is Config?

```
Anything that varies between deploys:
   ✓ Database URLs
   ✓ API keys / credentials
   ✓ Hostnames
   ✓ Feature flags
   ✓ Per-environment values
```

### Anti-Patterns

```
✗ Hardcoded credentials in code
✗ Multiple config files (config.dev.json, config.prod.json)
✗ "production" / "development" if-statements

DANGER: Easy to commit secrets to git!
```

### Best Practice

```
✓ Read from environment variables:

import os

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ["API_KEY"]
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

✓ Same code, different env vars per deploy
✓ Litmus test: "Can I open-source this codebase without leaking credentials?"
```

### Test for Compliance

```
Could you open-source your repo RIGHT NOW
without leaking any credentials?

If yes ✓ - you're 12-factor compliant
If no  ✗ - secrets are in code (BAD!)
```

---

## 5. Factor 4 — Backing Services

### Rule

**Treat backing services as attached resources.**

### What's a Backing Service?

```
Any service the app consumes:
   ✓ Databases (PostgreSQL, MongoDB)
   ✓ Caches (Redis, Memcached)
   ✓ Message queues (Kafka, RabbitMQ)
   ✓ SMTP services
   ✓ APIs (third-party)
```

### Key Idea

```
App should NOT know:
   ✗ Whether DB is local or remote
   ✗ Whether email service is internal or SaaS

App should know ONLY:
   ✓ URL/endpoint (from config)
   ✓ Credentials (from config)
```

### Benefits

```
✓ Swap services without code changes
   - Local PostgreSQL → managed RDS (just change env var!)
   - Self-hosted Redis → ElastiCache
   - SMTP server → SendGrid

✓ Different services per environment
✓ No hardcoding service details
```

### Example

```python
# ❌ Anti-pattern
import psycopg2
conn = psycopg2.connect(
    host="localhost",
    user="admin",
    password="secret",
    database="myapp"
)

# ✅ 12-factor
import os
import psycopg2
DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(DATABASE_URL)
# Local: postgresql://user:pass@localhost/myapp
# Prod: postgresql://...@rds.amazonaws.com/myapp
```

---

## 6. Factor 5 — Build, Release, Run

### Rule

**Strictly separate build, release, and run stages.**

### The Three Stages

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  BUILD                                                       │
│  ✓ Take code + dependencies → executable artifact            │
│  ✓ Compile, bundle, build Docker image                       │
│  ✓ Result: immutable artifact                                │
│                                                              │
│  ──────────────────────────────────────                      │
│                                                              │
│  RELEASE                                                     │
│  ✓ Combine BUILD + CONFIG = RELEASE                          │
│  ✓ Versioned (e.g., v1.2.3)                                  │
│  ✓ Released to runtime environment                           │
│                                                              │
│  ──────────────────────────────────────                      │
│                                                              │
│  RUN                                                         │
│  ✓ Execute the release                                       │
│  ✓ Should NOT change code                                    │
│  ✓ Can scale by adding processes                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Why Separation Matters

```
✓ Reproducible builds
✓ Easy rollback (revert release)
✓ Audit trail (which release in production?)
✓ Can re-run releases on new infrastructure
```

### Anti-Pattern

```
❌ "Hot fix" applied directly to production server
   → No record of what changed
   → Lost when server restarts
   → Can't reproduce

✅ All changes go through build → release → run
```

---

## 7. Factor 6 — Processes (Stateless)

### Rule

**Apps run as one or more stateless processes.**

### What Stateless Means

```
✓ No data stored in process memory between requests
✓ No "session in memory"
✓ No "this server holds the user's cart"
✓ Filesystem is ephemeral
```

### Why It Matters

```
Stateless processes = horizontal scaling!

✓ Any instance can handle any request
✓ Add/remove instances freely
✓ Failed instance → no data loss
✓ Easy load balancing
```

### Where to Store State

```
Externalize EVERYTHING:
   ✓ User sessions → Redis
   ✓ Cache → Redis / Memcached
   ✓ File uploads → S3
   ✓ Database → PostgreSQL / MongoDB
   ✓ Queues → Kafka / RabbitMQ
```

### Example

```python
# ❌ Stateful (in-memory)
user_carts = {}  # GLOBAL dict

@app.post("/cart")
def add_to_cart(user_id, item):
    if user_id not in user_carts:
        user_carts[user_id] = []
    user_carts[user_id].append(item)
    # Works on one server, FAILS on multiple servers!

# ✅ Stateless (external store)
@app.post("/cart")
def add_to_cart(user_id, item):
    redis_client.rpush(f"cart:{user_id}", json.dumps(item))
    # Works on ANY server!
```

### Sticky Sessions Anti-Pattern

```
❌ Don't rely on "user always hits same server"
✗ Load balancer "stickiness"
✗ Limits horizontal scaling
✗ Failed server = lost session

✓ Store sessions in Redis
✓ Any server can serve any request
```

---

## 8. Factor 7 — Port Binding

### Rule

**Export services via port binding.**

### What This Means

```
App is SELF-CONTAINED:
   ✓ Includes its web server
   ✓ Listens on a port
   ✓ Doesn't need Apache/Nginx in front

✗ Don't rely on external server (Apache, Tomcat)
```

### Visual

```
   ┌──────────────────┐
   │  Your App         │
   │  ┌────────────┐   │
   │  │ Web server │   │  ← embedded (Gunicorn, Express, etc.)
   │  └────────────┘   │
   │                    │
   │  Listens on :8000  │
   └────────┬───────────┘
            │
            │ (Optionally fronted by Nginx, Caddy, etc.)
            ▼
         Internet
```

### Examples

```python
# Python - Gunicorn embedded
$ gunicorn app:app --bind 0.0.0.0:8000

# Node.js - Express embedded
const express = require('express');
const app = express();
app.listen(process.env.PORT || 3000);

# Java - Spring Boot with embedded Tomcat
$ java -jar app.jar
```

### Benefits

```
✓ Apps are portable
✓ Can be deployed anywhere
✓ No external dependencies on web server
✓ Cloud platforms (Heroku, etc.) need this
```

---

## 9. Factor 8 — Concurrency

### Rule

**Scale out via the process model.**

### Unix Process Model

```
Apps consist of MULTIPLE process types:
   ✓ Web workers (handle HTTP)
   ✓ Background workers (handle jobs)
   ✓ Clock processes (cron-like)
   ✓ etc.

Each scales independently.
```

### Procfile Example (Heroku-style)

```
# Procfile
web: gunicorn app:app
worker: celery -A tasks worker
beat: celery -A tasks beat
```

### Scaling

```
Need more web throughput?
   → Add more web processes
   
Need more job processing?
   → Add more worker processes
   
Each scales horizontally + independently.
```

### Process != Thread

```
Use OS processes, NOT in-process threads:
   ✓ Process model is OS-managed
   ✓ Isolation is built in
   ✓ Can run on different machines
   ✓ Crash recovery automatic
```

---

## 10. Factor 9 — Disposability

### Rule

**Maximize robustness with fast startup and graceful shutdown.**

### Fast Startup

```
Why? Apps must scale up quickly.
   ✓ < 30 seconds ideally
   ✓ Cold-start affects user experience
   ✓ Slow startup = slow recovery

Tips:
   ✓ Lazy-load heavy resources
   ✓ Smaller dependencies
   ✓ Avoid heavy init code
```

### Graceful Shutdown

```
When app receives SIGTERM:
   ✓ Stop accepting new requests
   ✓ Finish in-flight requests
   ✓ Close DB connections
   ✓ Flush queues
   ✓ Then exit cleanly

NOT just kill -9 (forces immediate stop)
```

### Example

```python
import signal
import asyncio

shutdown_event = asyncio.Event()

def handle_sigterm(signum, frame):
    print("SIGTERM received - graceful shutdown")
    shutdown_event.set()

signal.signal(signal.SIGTERM, handle_sigterm)

async def main():
    server = await asyncio.start_server(...)
    
    try:
        await shutdown_event.wait()
    finally:
        # Stop accepting new connections
        server.close()
        await server.wait_closed()
        
        # Wait for active requests
        await drain_active_requests()
        
        # Close resources
        await close_db_pool()
        await close_redis_connection()
        
        print("Shutdown complete")

asyncio.run(main())
```

### Why It Matters

```
Cloud environments:
   ✗ Instances killed unexpectedly
   ✗ Scaling events
   ✗ Deploys
   
With graceful shutdown:
   ✓ No lost requests
   ✓ No corrupted state
   ✓ Easy rollouts
```

---

## 11. Factor 10 — Dev/Prod Parity

### Rule

**Keep development, staging, and production as similar as possible.**

### Three Gaps to Minimize

```
1. TIME GAP
   Code written → deployed to prod
   12-factor: Hours, not weeks

2. PERSONNEL GAP
   Devs write code, ops deploy it
   12-factor: DevOps culture, same team

3. TOOLS GAP
   Dev uses SQLite, prod uses PostgreSQL
   12-factor: Same backing services
```

### Anti-Patterns

```
❌ "Works on my Mac, fails on Linux"
❌ "Different DB in dev (SQLite) than prod (Postgres)"
❌ "Mocked services in dev"
```

### Best Practices

```
✓ Use SAME backing services everywhere
   - Dev: Postgres in Docker
   - Staging: Postgres
   - Prod: Postgres

✓ Use Docker for parity
   - Same OS, same dependencies, same runtime
   - "Works the same everywhere"

✓ Frequent deployments
   - Push code to prod multiple times/day
   - Small changes = less risk
```

### Docker Compose for Local

```yaml
# docker-compose.yml - replicate prod locally
version: '3.8'

services:
  app:
    build: .
    environment:
      DATABASE_URL: postgresql://app:app@db/myapp
      REDIS_URL: redis://redis:6379
    depends_on: [db, redis]
  
  db:
    image: postgres:15  # SAME as production!
  
  redis:
    image: redis:7-alpine
```

---

## 12. Factor 11 — Logs

### Rule

**Treat logs as event streams.**

### Anti-Patterns

```
❌ Apps write to log files directly
❌ Apps manage log rotation
❌ Apps store logs locally
❌ Reading logs requires SSH to server
```

### 12-Factor Approach

```
✓ App writes logs to STDOUT/STDERR
✓ Doesn't manage where they go
✓ Execution environment captures them
✓ Forwarded to log aggregation system
```

### Example

```python
import logging
import sys

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stdout,  # NOT a file!
)

logger = logging.getLogger(__name__)
logger.info("Hello World")
```

### Where Logs Go

```
   App writes to STDOUT
            │
            ▼
   ┌──────────────────────────┐
   │ Container/Pod stdout      │
   └──────────┬───────────────┘
              │ collected by:
              ▼
   ┌──────────────────────────┐
   │ Logging agent (Fluentd,   │
   │   Logstash, Datadog)      │
   └──────────┬───────────────┘
              │ forwarded to:
              ▼
   ┌──────────────────────────┐
   │ Centralized log store     │
   │ (Elasticsearch, S3,        │
   │  Datadog, CloudWatch)     │
   └──────────────────────────┘
              │
              ▼
       Queryable + alerts
```

### Benefits

```
✓ Centralized search
✓ Cross-service correlation
✓ No disk space issues
✓ Easy to add new tools
✓ Real-time log streaming
```

---

## 13. Factor 12 — Admin Processes

### Rule

**Run admin tasks as one-off processes.**

### What Are Admin Tasks?

```
✓ Database migrations
✓ One-off scripts (data import, cleanup)
✓ Console sessions (Rails console, Django shell)
✓ Maintenance tasks
```

### Key Requirements

```
✓ Run in SAME environment as app
✓ Same code, same dependencies
✓ Same configuration
✓ Same backing services

✗ Don't be a separate code path
✗ Don't be on different infrastructure
```

### Examples

```bash
# Django migrations
$ heroku run python manage.py migrate

# Database cleanup
$ docker exec myapp python scripts/cleanup_old_data.py

# Bulk import
$ kubectl exec myapp -- python import_users.py users.csv
```

### Anti-Pattern

```
❌ Maintenance scripts in separate repo
❌ Run on developer's laptop
❌ With different versions of dependencies

✅ Same image, same env, just different command
```

---

## 14. Putting It All Together

### A 12-Factor App in Practice

```python
# app.py - 12-factor compliant FastAPI app
from fastapi import FastAPI
import os
import logging
import sys
import asyncpg
import signal

# Factor 11: Logs to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Factor 3: Config from environment
DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
PORT = int(os.environ.get("PORT", 8000))

app = FastAPI()

# Factor 4: Backing service - DB pool created on startup
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    # Factor 9: Fast startup
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    logger.info("Started")

@app.on_event("shutdown")
async def shutdown():
    # Factor 9: Graceful shutdown
    if db_pool:
        await db_pool.close()
    logger.info("Shutdown complete")

# Factor 6: Stateless - no in-memory state
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # External state (DB)
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    return dict(user) if user else None

# Factor 7: Port binding
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

### Procfile (Factor 8: Concurrency)

```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4
worker: celery -A tasks worker --concurrency=4
```

### Dockerfile (Factor 2 + 10)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Factor 2: Explicit dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Factor 7: Port binding (just exposes, env decides)
EXPOSE 8000

# Factor 9: Disposability - handles SIGTERM
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--graceful-timeout", "30"]
```

---

## 15. Benefits Recap

### Why 12-Factor?

```
✓ HORIZONTAL SCALING
   Stateless processes scale freely

✓ EASY DEPLOYMENT
   Push code + set env vars = done

✓ CLOUD PORTABILITY
   Same app on AWS, GCP, Azure

✓ MAINTAINABILITY
   Clear separation of concerns

✓ OPERATOR-FRIENDLY
   Standard patterns, easy to manage

✓ RESILIENT
   Fail-fast, recover-fast philosophy
```

### Modern Extensions

```
12-factor is from 2011. Some modern additions:

✓ API-first design
✓ Telemetry (logs + metrics + traces)
✓ Authentication / authorization
✓ Secrets management (not just env vars)
✓ Service mesh integration

→ Build on 12-factor + extend.
```

---

## 16. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Single codebase, many deploys (Factor 1)                   │
│  ✅ Explicit dependencies (Factor 2)                           │
│  ✅ Config in environment, NOT code (Factor 3)                 │
│  ✅ Backing services as attached resources (Factor 4)          │
│  ✅ Separate build, release, run (Factor 5)                    │
│  ✅ Stateless processes - state externalized (Factor 6)        │
│  ✅ Self-contained with port binding (Factor 7)                │
│  ✅ Scale via process model (Factor 8)                         │
│  ✅ Fast startup, graceful shutdown (Factor 9)                 │
│  ✅ Dev/prod parity - use same services (Factor 10)            │
│  ✅ Logs to stdout - treat as streams (Factor 11)              │
│  ✅ Admin tasks in same env as app (Factor 12)                 │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Single Git repo per app
2. NEVER commit secrets - use env vars
3. Stateless = scale-friendly
4. Logs to stdout, NOT files
5. Same services dev → staging → prod
6. Build + release + run = separate concerns
7. Fast startup + graceful shutdown
8. Scale by adding processes
9. Use containers for parity
10. Adopt all 12 incrementally
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll dive into **Serverless Architecture** — Functions as a Service, cold starts, event triggers, and when to use it.

> **Practical file:** [02_Practical_Hands_On.md](02_Practical_Hands_On.md)

---

## 📚 References

- *The Twelve-Factor App* — 12factor.net (the original!)
- *Beyond the Twelve-Factor App* — Kevin Hoffman (free O'Reilly eBook)
- Heroku Dev Center documentation
- Cloud Native Computing Foundation (CNCF)
- *Cloud Native Patterns* — Cornelia Davis
