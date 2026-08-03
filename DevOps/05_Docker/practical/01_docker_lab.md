# Docker — Hands-On Lab
**DevOps Track · Phase 5 Practical**

## Prerequisites

- Docker installed and running locally — Docker Desktop (macOS/Windows) or Docker Engine (Linux). Verify with `docker version` and `docker run hello-world`.
- No cloud account needed for Labs 1-3. Lab 4's registry section shows Docker Hub (free, no cost) — an ECR walkthrough is referenced but not required to complete the lab.
- No paid account needed anywhere. If you don't want Docker Desktop installed locally, [Play with Docker](https://labs.play-with-docker.com/) gives you a free, disposable Docker host in the browser (4-hour sessions, no signup beyond a Docker Hub account).
- Work in a scratch directory: `mkdir -p ~/docker-lab && cd ~/docker-lab`.

---

## Lab 1: Build a Multi-Stage Python Image and Prove the Cache Works

**Objective:** Build the exact multi-stage pattern from the lesson, then PROVE layer caching behaves the way the theory says it does — not just read about it.

**Task:**
1. Create a minimal FastAPI-ish app: a file `main.py` that just prints something on import and has a health check function (it doesn't need to actually be a working web server for this lab — a trivial Python file is enough to prove the build mechanics).
2. Create `requirements.txt` with one real package in it (e.g. `requests`).
3. Write a Dockerfile with the WRONG layer order first: `COPY . .` before `RUN pip install`.
4. Build it, time it (`time docker build -t myapp:bad .`), then touch `main.py` (change one comment) and rebuild — time it again. Note that pip install re-runs even though only app code changed.
5. Now fix the Dockerfile: copy `requirements.txt` first, install, THEN copy the rest. Rebuild from scratch, then touch `main.py` again and rebuild — confirm via the build output that the pip install layer shows `CACHED` this time.
6. Convert it to a real multi-stage build (builder stage installs into `/install`, runtime stage copies only the installed packages) and compare `docker images` sizes between the single-stage and multi-stage versions.
7. Add a non-root user and confirm with `docker run --rm myapp:multistage whoami` that the container does NOT run as root.

<details>
<summary>Solution / walkthrough</summary>

```bash
mkdir -p ~/docker-lab/app && cd ~/docker-lab/app

cat > main.py << 'EOF'
import requests

def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    print("app started")
EOF

echo "requests==2.31.0" > requirements.txt

# 3. BAD Dockerfile — code copied before deps installed
cat > Dockerfile.bad << 'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
EOF

# 4. Build, touch, rebuild — watch pip install re-run every time
time docker build -f Dockerfile.bad -t myapp:bad .
echo "# comment change" >> main.py
time docker build -f Dockerfile.bad -t myapp:bad .
# Look at the build output: "RUN pip install -r requirements.txt" does
# NOT show "CACHED" — because COPY . . (which includes main.py) comes
# BEFORE it, so any file change invalidates that layer and everything
# after it, even though requirements.txt itself never changed.

# 5. GOOD Dockerfile — deps installed before app code copied
cat > Dockerfile.good << 'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
EOF

docker build -f Dockerfile.good -t myapp:good .
echo "# another comment change" >> main.py
docker build -f Dockerfile.good -t myapp:good .
# Build output now shows:
# => CACHED [3/5] RUN pip install -r requirements.txt
# — proven: only the final COPY . . layer (cheap) rebuilds

# 6. Real multi-stage build
cat > Dockerfile.multistage << 'EOF'
# ---------- builder ----------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup . .
USER appuser
CMD ["python", "main.py"]
EOF

docker build -f Dockerfile.multistage -t myapp:multistage .

docker images | grep myapp
# myapp   bad          ...   ~180MB  (single stage, includes build tools if any were needed)
# myapp   good          ...   ~170MB
# myapp   multistage     ...   ~150MB  (smaller — no pip cache/build leftovers carried forward)
# exact sizes vary, but multistage should be visibly smaller or at
# minimum cleaner — the real win grows a lot once you add compiled deps

# 7. Confirm non-root
docker run --rm myapp:multistage python3 -c "import getpass; print(getpass.getuser())" 2>/dev/null || \
docker run --rm --entrypoint whoami myapp:multistage
# appuser   <- not root
```
</details>

---

## Lab 2: Compose Stack — API + Postgres + Redis With Correct Startup Ordering

**Objective:** Build the exact `depends_on` + `healthcheck` pattern from the lesson and PROVE the classic footgun (app crashing because Postgres isn't ready yet) by deliberately reproducing it first.

**Task:**
1. Reuse the app from Lab 1 (or a fresh trivial one). Write a `docker-compose.yml` with 3 services: `api`, `db` (postgres:16-alpine), `redis` (redis:7-alpine).
2. FIRST, wire `depends_on` WITHOUT any healthcheck/condition — just a bare list. Add a startup command to the `api` service that tries to connect to Postgres immediately (a simple Python snippet using `psycopg2` or even just `nc -zv db 5432` in a shell command is enough to prove the point — you don't need a real ORM).
3. Run `docker compose up` and observe: does `api` ever fail to connect because `db` isn't ready yet? (This may or may not reproduce reliably depending on how fast Postgres inits on your machine — note what you observe either way, and explain why it's inherently a race condition, not a guaranteed failure.)
4. Fix it: add a proper `healthcheck` block to `db` (using `pg_isready`) and `redis` (using `redis-cli ping`), then change `api`'s `depends_on` to use `condition: service_healthy` for both.
5. Tear down and bring the stack up again from a clean state (`docker compose down -v` first). Watch `docker compose ps` — confirm `api` genuinely waits for `db`/`redis` to report healthy before starting.
6. Prove volumes persist correctly: write a value into Postgres, `docker compose down` (no `-v`), bring it back up, confirm the value is still there. Then `docker compose down -v` and confirm it's gone.

<details>
<summary>Solution / walkthrough</summary>

```bash
mkdir -p ~/docker-lab/compose-lab && cd ~/docker-lab/compose-lab

cat > docker-compose.yml << 'EOF'
services:
  api:
    image: python:3.12-slim
    command: >
      sh -c "echo 'checking db...' && nc -zv db 5432 && echo 'DB REACHABLE' || echo 'DB NOT READY YET'"
    depends_on:
      - db
      - redis
    networks: [backend]

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: labpass
      POSTGRES_DB: labdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks: [backend]

  redis:
    image: redis:7-alpine
    networks: [backend]

volumes:
  pgdata:

networks:
  backend:
EOF

# 3. Bare depends_on — watch for the race
docker compose up
# On a slow machine / cold start, you may well see "DB NOT READY YET"
# — depends_on (no condition) only waits for the db CONTAINER to have
# STARTED, not for Postgres to have finished its init/recovery process
# and started accepting connections. This is inherently racy: it might
# even "work" most of the time on a fast machine, which is exactly why
# it's a dangerous footgun — it passes in dev and fails intermittently
# in CI or under real load.
docker compose down

# 4. Fix with healthcheck + condition
cat > docker-compose.yml << 'EOF'
services:
  api:
    image: python:3.12-slim
    command: >
      sh -c "echo 'checking db...' && nc -zv db 5432 && echo 'DB REACHABLE'"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks: [backend]

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: labpass
      POSTGRES_DB: labdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 3s
      timeout: 3s
      retries: 10
    networks: [backend]

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 3s
      retries: 5
    networks: [backend]

volumes:
  pgdata:

networks:
  backend:
EOF

# 5. Clean slate, confirm real ordering
docker compose down -v
docker compose up -d
docker compose ps
# db/redis show (healthy) before api's dependent startup begins —
# api's command now ALWAYS reports "DB REACHABLE", no race

# 6. Volume persistence proof
docker compose exec db psql -U postgres -d labdb -c \
  "CREATE TABLE lab_test (id serial, note text); INSERT INTO lab_test (note) VALUES ('survives restart');"

docker compose down                # containers removed, volume KEPT
docker compose up -d db
sleep 3
docker compose exec db psql -U postgres -d labdb -c "SELECT * FROM lab_test;"
# id | note
# 1  | survives restart      <- still there, volume persisted

docker compose down -v             # NOW remove volumes too
docker compose up -d db
sleep 3
docker compose exec db psql -U postgres -d labdb -c "SELECT * FROM lab_test;"
# ERROR: relation "lab_test" does not exist   <- fresh volume, data gone
```
</details>

---

## Lab 3: Storage and Networking — Bind Mounts vs Volumes, Custom Networks

**Objective:** Feel the practical difference between bind mounts and volumes, and prove container-to-container DNS resolution only works on user-defined networks.

**Task:**
1. Start a container with a bind mount to a host directory containing a text file. Edit the file ON THE HOST while the container is running, and `docker exec` into the container to confirm the change appears live, instantly.
2. Start a second container with a named volume instead. Write a file INSIDE the container via `docker exec`, then inspect where Docker actually stores that data on the host (`docker volume inspect`), and note you can't casually browse/edit it like the bind-mount case.
3. Create two containers on the DEFAULT bridge network (no custom network specified) and try to ping one from the other BY NAME — confirm it fails.
4. Create a user-defined bridge network, attach the same two containers to it (or fresh ones), and confirm ping-by-name now works.
5. Publish a container's port to the host (`-p 8080:80`) and confirm you can reach it from the host via `curl localhost:8080`. Then start a second container WITHOUT publishing a port, and confirm you can still reach it from the FIRST container over the shared custom network, by name, even though it's not reachable from the host at all.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Bind mount — live host <-> container editing
mkdir -p ~/docker-lab/bind-demo
echo "version 1" > ~/docker-lab/bind-demo/file.txt

docker run -d --name bind-test -v ~/docker-lab/bind-demo:/data alpine sleep 3600
docker exec bind-test cat /data/file.txt
# version 1

echo "version 2 - edited on host" > ~/docker-lab/bind-demo/file.txt
docker exec bind-test cat /data/file.txt
# version 2 - edited on host    <- instant, no restart needed, same underlying file

# 2. Named volume — Docker-managed, not casually host-browsable
docker volume create labvol
docker run -d --name vol-test -v labvol:/data alpine sleep 3600
docker exec vol-test sh -c 'echo "written from inside container" > /data/file.txt'

docker volume inspect labvol
# "Mountpoint": "/var/lib/docker/volumes/labvol/_data"
# (on Docker Desktop this path is INSIDE the LinuxKit VM, not directly
# browsable from your Mac/Windows host filesystem at all — another
# concrete Docker Desktop vs Engine gap from the basics lesson)

# 3. Default bridge — no DNS by name
docker run -d --name net-a --rm alpine sleep 3600
docker run -d --name net-b --rm alpine sleep 3600
docker exec net-a ping -c 2 net-b
# ping: bad address 'net-b'   <- fails, default bridge has NO automatic
# DNS resolution by container name (that requires --link, legacy, avoid)

docker rm -f net-a net-b

# 4. User-defined bridge — DNS by name works
docker network create labnet
docker run -d --name net-a --network labnet --rm alpine sleep 3600
docker run -d --name net-b --network labnet --rm alpine sleep 3600
docker exec net-a ping -c 2 net-b
# PING net-b (172.x.x.x): 56 data bytes
# 64 bytes from 172.x.x.x: seq=0 ttl=64 time=0.1 ms
# ... SUCCESS — resolved 'net-b' by name automatically

# 5. Published vs unpublished port on the same network
docker run -d --name web-published --network labnet -p 8080:80 --rm nginx:alpine
curl -sI localhost:8080 | head -1
# HTTP/1.1 200 OK    <- reachable from the HOST, because of -p

docker run -d --name web-internal --network labnet --rm nginx:alpine
curl -sI localhost:8081 2>&1 | head -1 || echo "not reachable from host (expected, no -p)"
docker exec net-a curl -sI http://web-internal:80 | head -1
# HTTP/1.1 200 OK    <- reachable from ANOTHER CONTAINER on the same
# network, by name, port 80 — even though it was never published to
# the host at all. This is exactly the pattern a real backend + db
# stack relies on: the DB is never -p published (not reachable from
# outside), but the API container reaches it by service name over the
# private network.

# cleanup
docker rm -f net-a net-b web-published web-internal 2>/dev/null
docker rm -f bind-test vol-test 2>/dev/null
docker volume rm labvol 2>/dev/null
docker network rm labnet 2>/dev/null
```
</details>

---

## Lab 4: Debug an OOM-Killed Container (Production-Style Scenario)

**Objective:** Reproduce a container getting killed for exceeding its memory limit, diagnose it from the tools available, and fix it — the container equivalent of the Linux phase's "runaway process" lab.

**Task:**
1. Write a tiny Python script `eat_memory.py` that allocates memory in a loop forever (e.g. appends growing strings/lists to a list, sleeping briefly between allocations so you can observe it rather than instantly crashing).
2. Build a minimal image around it (`FROM python:3.12-slim`, `COPY eat_memory.py .`, `CMD ["python", "eat_memory.py"]`).
3. Run it WITH a deliberately low memory limit: `docker run -d --name oom-test --memory=50m myapp:oom`.
4. Watch it with `docker stats oom-test` in one terminal while it runs — observe memory climbing toward the limit.
5. After it gets killed, inspect WHY using `docker inspect oom-test` — find the `OOMKilled` field and the `ExitCode` (OOM kills typically show exit code 137 = 128 + SIGKILL 9).
6. Check `docker logs oom-test` — note that application-level logs likely show NOTHING useful (the process was killed abruptly by the kernel's cgroup OOM killer, not given a chance to log a graceful error) — this is an important realization: OOM kills often look like "silent death," not a clean error message.
7. Fix it two ways and explain the tradeoff of each: (a) raise the memory limit to something realistic, (b) fix the actual application bug (in this synthetic case, add a cap so it doesn't grow unbounded) — explain why (b) is the real production fix and (a) alone is a band-aid.

<details>
<summary>Solution / walkthrough</summary>

```bash
mkdir -p ~/docker-lab/oom-lab && cd ~/docker-lab/oom-lab

cat > eat_memory.py << 'EOF'
import time

hog = []
i = 0
while True:
    # grow by ~5MB per iteration, forever — simulates an unbounded
    # in-memory cache / list that never evicts anything, a real class
    # of production bug (e.g. an unbounded request-log buffer)
    hog.append("x" * 5_000_000)
    i += 1
    print(f"allocated ~{i * 5}MB so far", flush=True)
    time.sleep(0.5)
EOF

cat > Dockerfile << 'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY eat_memory.py .
CMD ["python", "eat_memory.py"]
EOF

docker build -t myapp:oom .

# 3. Run with a tight memory ceiling
docker run -d --name oom-test --memory=50m myapp:oom

# 4. Watch it climb (run in a separate terminal, or just poll)
docker stats oom-test --no-stream
# repeat a few times — MEM USAGE / LIMIT climbs toward 50MiB / 50MiB

sleep 5
docker ps -a --filter name=oom-test
# STATUS shows "Exited (137) ..." once the kernel's cgroup OOM killer
# terminates it for exceeding the memory.max cgroup limit

# 5. Confirm it was specifically an OOM kill, not a crash/error exit
docker inspect oom-test --format '{{.State.OOMKilled}} exit={{.State.ExitCode}}'
# true exit=137
# 137 = 128 + 9 (SIGKILL) — the kernel, not the app, terminated this;
# nothing in the app's own code chose to exit

# 6. Check logs — the "silent death" realization
docker logs oom-test
# allocated ~5MB so far
# allocated ~10MB so far
# ...
# allocated ~45MB so far
# (log just STOPS — no exception, no traceback, no graceful shutdown
# message, because SIGKILL gives the process zero chance to run any
# cleanup or logging code at all — this is exactly why "the container
# just disappeared with no error in the logs" is a classic OOM
# fingerprint, and the FIRST place to check is `docker inspect
# --format '{{.State.OOMKilled}}'`, not the application logs)

docker rm -f oom-test

# 7a. Band-aid: raise the limit
docker run -d --name oom-test-more-mem --memory=512m myapp:oom
sleep 30
docker inspect oom-test-more-mem --format '{{.State.OOMKilled}}'
# still eventually becomes 'true' — it just takes longer, because the
# underlying bug (unbounded growth) was never fixed, only delayed

docker rm -f oom-test-more-mem

# 7b. Real fix: bound the actual memory usage in the application
cat > eat_memory_fixed.py << 'EOF'
import time

MAX_ITEMS = 20   # a real cap — the actual fix, not a bigger container

hog = []
i = 0
while True:
    if len(hog) >= MAX_ITEMS:
        hog.pop(0)     # evict oldest — bounded memory, forever-runnable
    hog.append("x" * 5_000_000)
    i += 1
    print(f"iteration {i}, current buffer size: {len(hog)} items", flush=True)
    time.sleep(0.5)
EOF

cat > Dockerfile.fixed << 'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY eat_memory_fixed.py .
CMD ["python", "eat_memory_fixed.py"]
EOF

docker build -f Dockerfile.fixed -t myapp:oom-fixed .
docker run -d --name oom-fixed-test --memory=50m myapp:oom-fixed
sleep 15
docker inspect oom-fixed-test --format '{{.State.OOMKilled}} status={{.State.Status}}'
# false status=running   <- stable, bounded memory, no OOM kill, EVEN
# under the same tight 50m limit that killed the original version

docker rm -f oom-fixed-test
```

**Why (a) alone is a band-aid:** raising the memory limit treats the symptom, not the cause — an app with a genuine memory leak or unbounded growth pattern will eventually hit ANY limit you set, it just buys time. The correct production fix is always to find and cap the unbounded growth in the application itself (a cache with no eviction policy, a list that's appended to but never trimmed, a connection pool that never releases connections). `--memory` limits exist to make that class of bug FAIL FAST and visibly (a clean, observable OOM kill) instead of slowly starving the whole host of memory — they're a safety net, not a fix.
</details>

---

## Self-Check Checklist

- [ ] Can you explain why layer ordering in a Dockerfile affects build cache, and reorder a bad Dockerfile to fix it?
- [ ] Can you write a working multi-stage Dockerfile from memory (builder + runtime stages)?
- [ ] Can you explain the difference between `CMD`, `ENTRYPOINT`, and `ENTRYPOINT` + `CMD` together, and predict what `docker run img extra-arg` does for each?
- [ ] Do you know why `depends_on` alone doesn't guarantee a dependency is actually ready, and how `healthcheck` + `condition: service_healthy` fixes it?
- [ ] Can you explain bind mount vs named volume and pick the right one for a given scenario without hesitating?
- [ ] Do you know why containers on the default bridge network can't resolve each other by name, but containers on a user-defined bridge can?
- [ ] Can you diagnose an OOM-killed container using `docker inspect` instead of guessing from `docker logs` alone?
- [ ] Can you explain why raising a container's memory limit is a band-aid, not a fix, for a real memory leak?
- [ ] Do you know what ARG vs ENV visibility differences mean for where secrets should (and should not) go?
- [ ] Can you explain why `docker compose down -v` is dangerous and when you'd deliberately use it anyway?
