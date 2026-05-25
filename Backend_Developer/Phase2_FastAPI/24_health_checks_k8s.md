# Health Checks — Kubernetes-Aware Probes

## Why It Matters

Kubernetes probes = your service's contract with the orchestrator:
- **Liveness** → "should restart me?"
- **Readiness** → "should send me traffic?"
- **Startup** → "am I done initializing?"

Get them wrong → restart loops, traffic dropped on healthy pod, or worse, broken pod still receiving requests.

Senior interview: "App returns 200 on /health but DB connection is broken. Why does k8s think it's healthy?" → because /health doesn't check DB.

---

## Core Concepts

### Three Probe Types

| Probe | Purpose | Action on Fail |
|---|---|---|
| **Liveness** | Process alive + responsive | Restart container |
| **Readiness** | Ready to serve traffic | Remove from load balancer |
| **Startup** | Initial bootstrap complete | (Disable other probes until OK) |

### FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException, status
import asyncio
import time


app = FastAPI()
_ready = False
_startup_time = None


@app.on_event("startup")
async def startup():
    global _startup_time, _ready
    _startup_time = time.time()
    # Lazy-init dependencies; mark ready when done
    # await init_db()
    # await init_redis()
    _ready = True


@app.get("/health/live", status_code=200, tags=["health"])
async def liveness():
    """K8s liveness probe — am I alive and responsive?"""
    return {"status": "alive", "uptime_sec": int(time.time() - _startup_time) if _startup_time else 0}


@app.get("/health/ready", status_code=200, tags=["health"])
async def readiness():
    """K8s readiness probe — can I serve traffic?"""
    if not _ready:
        raise HTTPException(503, "Not ready")

    # Check critical dependencies
    checks = await asyncio.gather(
        check_db(),
        check_redis(),
        check_celery(),
        return_exceptions=True,
    )

    failed = [c for c in checks if isinstance(c, Exception) or c is False]
    if failed:
        raise HTTPException(503, "Dependency check failed")

    return {"status": "ready", "checks": ["db", "redis", "celery"]}


@app.get("/health/startup", status_code=200, tags=["health"])
async def startup_probe():
    """K8s startup probe — initialization complete?"""
    if not _ready:
        raise HTTPException(503, "Still starting")
    return {"status": "started"}


async def check_db() -> bool:
    # from db import engine
    # async with engine.connect() as conn:
    #     await conn.execute(text("SELECT 1"))
    return True


async def check_redis() -> bool:
    # from redis_client import r
    # await r.ping()
    return True


async def check_celery() -> bool:
    # from celery import current_app
    # i = current_app.control.inspect(timeout=2)
    # return bool(i.ping())
    return True
```

### Kubernetes Probe Config

```yaml
# deployment.yaml
spec:
  template:
    spec:
      containers:
      - name: app
        image: myapp:latest

        startupProbe:
          httpGet:
            path: /health/startup
            port: 8000
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 30        # 30 * 5s = 150s max startup

        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 0
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3         # 30s grace

        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
          successThreshold: 1
```

### Distinguishing Liveness vs Readiness

**Liveness should NOT check external deps.** If DB is down, restarting your pod won't help — it'll just keep restarting forever.

**Readiness SHOULD check external deps.** If DB is down, stop sending traffic to this pod (so retries hit a healthy pod, if available).

```python
# WRONG — liveness checks DB
@app.get("/health/live")
async def liveness():
    await db.execute("SELECT 1")  # DB down → pod killed → cascading
    return {"status": "ok"}


# RIGHT
@app.get("/health/live")
async def liveness():
    # Only check this process is responsive
    return {"status": "alive"}
```

### Graceful Shutdown

```python
import signal


_shutting_down = False


@app.on_event("shutdown")
async def shutdown():
    global _shutting_down
    _shutting_down = True
    # Wait for in-flight requests
    await asyncio.sleep(5)
    # Close connections gracefully
    # await db.close()


@app.get("/health/ready")
async def ready():
    if _shutting_down:
        raise HTTPException(503, "Shutting down")
    # ... other checks
```

K8s flow:
1. SIGTERM sent
2. Pod removed from service endpoints (no new traffic after delay)
3. App receives signal, sets `_shutting_down = True`
4. Readiness probe fails → confirmed removal
5. App finishes in-flight requests
6. After `terminationGracePeriodSeconds`, SIGKILL

### Detailed Health with Status

```python
@app.get("/health/details")
async def health_details():
    """Detailed status — NOT for k8s probes (expensive)."""
    results = {}
    for name, check_fn in [
        ('database', check_db_with_timing),
        ('redis', check_redis_with_timing),
        ('celery', check_celery_with_timing),
        ('s3', check_s3_with_timing),
    ]:
        try:
            start = time.monotonic()
            ok = await asyncio.wait_for(check_fn(), timeout=3)
            results[name] = {
                'status': 'up' if ok else 'down',
                'latency_ms': int((time.monotonic() - start) * 1000),
            }
        except asyncio.TimeoutError:
            results[name] = {'status': 'timeout'}
        except Exception as e:
            results[name] = {'status': 'error', 'error': str(e)[:200]}

    all_up = all(r['status'] == 'up' for r in results.values())
    return {
        'status': 'up' if all_up else 'degraded',
        'checks': results,
        'version': APP_VERSION,
        'uptime_sec': int(time.time() - _startup_time) if _startup_time else 0,
    }
```

---

## How It Works Internally

### K8s Probe Lifecycle

```
Container start
    ↓
Startup probe runs (every periodSeconds)
    ↓ (succeeds)
Liveness + Readiness probes start
    ↓
Liveness fails → restart container
Readiness fails → remove from service endpoints
```

### Probe Failure Math

```
failureThreshold: 3
periodSeconds: 10
→ Pod considered failed after 3 × 10 = 30 seconds of failures
```

Tune for your SLA. Fast detection (small period/threshold) → false positives. Slow → bad UX during issues.

### Why `initialDelaySeconds` Replaced by `startupProbe`

Old way: `initialDelaySeconds: 60` for liveness → 60s before first check. Bad if app starts in 5s (waste) or 90s (false fail).

New way: `startupProbe` with `failureThreshold` allows variable startup. Once it passes once, liveness/readiness take over.

---

## Common Pitfalls

### 1. Liveness Checks External Dependencies

DB down → all pods killed → cascading failure. Liveness = process-level only.

### 2. Same Endpoint for Liveness + Readiness

```python
@app.get("/health")  # used for both
```

If health checks DB, k8s kills pods on DB outage. Separate them.

### 3. Probes Too Aggressive

```yaml
periodSeconds: 1
failureThreshold: 1
```

Network blip → pod killed. Use 5-10s period + 3+ threshold.

### 4. No Shutdown Grace

App killed mid-request → 500 to user. Always handle SIGTERM, fail readiness, drain.

### 5. Probe Endpoint Heavy

```python
@app.get("/health/ready")
async def ready():
    users = await User.objects.acount()  # slow!
    return {"users": users}
```

Probes hit every few seconds — keep them fast (< 100ms).

### 6. Missing Auth on Probes

```yaml
httpHeaders:
- name: Authorization
  value: Bearer probe-secret
```

For internal services, optional. For public-facing pods, ensure probes aren't accessible externally.

### 7. Probes Don't Include All Critical Deps

App lazy-loads Redis on first request → readiness OK but first user-request fails. Probe checks should match what user-traffic needs.

---

## Interview Q&A

**Q1:** Liveness vs Readiness — line draw karo.
**A:** Liveness = process-level (alive, responsive to HTTP). Readiness = traffic-level (ready to handle real requests, deps OK). Liveness failure → restart. Readiness failure → no traffic. Liveness should NEVER check external deps (restart won't fix DB outage). Readiness SHOULD.

**Q2:** Startup probe ka purpose?
**A:** Apps with variable/slow startup (running migrations, loading ML model). Without startup probe: tune liveness `initialDelaySeconds` to worst-case → wastes time or causes false negatives. With startup probe: probe runs frequently, once OK liveness takes over.

**Q3:** Graceful shutdown FastAPI mein kaise implement karoge?
**A:** (1) `@app.on_event("shutdown")` sets flag. (2) Readiness endpoint returns 503 when flag set. (3) K8s removes pod from endpoints. (4) App finishes in-flight requests during `terminationGracePeriodSeconds`. (5) Close DB pool, Redis, message broker connections.

**Q4:** Probe failure cascading kaise prevent karoge?
**A:** Liveness DOES NOT check shared deps. Readiness can check, but acceptable to have all pods become unready briefly. PodDisruptionBudget ensures min available pods. Plus graceful degradation in app (read from cache when DB unavailable).

**Q5:** Probe interval tuning?
**A:** Trade-off: fast detection vs noise. Production: `periodSeconds: 5-10`, `failureThreshold: 3`. Startup: `periodSeconds: 5`, `failureThreshold: high` (allow slow start). Probe `timeoutSeconds: 2-3` (fast fail). Tune per service SLO.

**Q6:** Custom probe vs Spring-style /actuator?
**A:** Spring: rich /actuator/health with checks per dep, configurable. FastAPI: build similar. Endpoints: `/health/live` (cheap), `/health/ready` (deps), `/health/details` (admin only). Don't expose details on prod public unless behind auth.

**Q7:** Probe path under auth — solution?
**A:** Two options: (1) Whitelist `/health/*` in middleware (no auth required). (2) K8s probes include auth header `httpHeaders`. Most teams choose (1) — probes simpler, less auth risk if creds rotate.

**Q8:** Pod restart loop debug kaise karoge?
**A:** `kubectl logs <pod> --previous` → see why crashed. `kubectl describe pod` → Events show probe failures with timestamps. Check liveness — too aggressive? Check app startup time vs `startupProbe.failureThreshold`. Add structured logs for probe responses.

---

## Real-World Use Cases

### 1. Database Migration on Startup

```python
@app.on_event("startup")
async def startup():
    global _ready
    # Run migrations
    await run_migrations()
    # Warm caches
    await preload_data()
    # Mark ready (readiness returns 200)
    _ready = True
```

Combined with startupProbe `failureThreshold: 60` → tolerates up to 60×5=300s startup.

### 2. Circuit Breaker Integration

```python
@app.get("/health/ready")
async def ready():
    if cb_state['db'].state == 'open':
        # Don't send traffic if DB circuit open
        raise HTTPException(503, "DB circuit open")
```

### 3. Service Mesh Awareness

Istio/Linkerd inject sidecar. Probes hit app port, not sidecar. Configure probes on app port (not 15001 sidecar).

---

## References

- [Kubernetes probes docs](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes)
- [Cloud Native Patterns by Cornelia Davis](https://www.manning.com/books/cloud-native-patterns)
- [Datadog: Probe best practices](https://www.datadoghq.com/blog/kubernetes-probes/)
- Spring actuator parallels
