"""
Health Checks — Kubernetes Probes — Production Patterns
"""

import asyncio
import time
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Response, status


APP_VERSION = os.environ.get('APP_VERSION', 'unknown')


# ==========================================================================
# 1. STATE TRACKING
# ==========================================================================

class AppState:
    startup_time: float = 0.0
    is_ready: bool = False
    is_shutting_down: bool = False


state = AppState()


# ==========================================================================
# 2. LIFESPAN — Startup + Shutdown
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    state.startup_time = time.time()
    print("Starting up...")

    # Initialize critical dependencies
    # try:
    #     await db.connect()
    #     await redis.connect()
    # except Exception as e:
    #     print(f"Startup failed: {e}")
    #     raise

    state.is_ready = True
    print(f"Ready in {time.time() - state.startup_time:.2f}s")

    yield  # serve traffic

    # Shutdown
    print("Shutting down...")
    state.is_shutting_down = True

    # Wait for in-flight requests
    # K8s will stop sending traffic via readiness probe
    await asyncio.sleep(5)

    # Close connections
    # await db.close()
    # await redis.close()
    print("Shutdown complete")


app = FastAPI(lifespan=lifespan)


# ==========================================================================
# 3. LIVENESS PROBE (cheapest — process alive)
# ==========================================================================

@app.get("/health/live", tags=["health"], status_code=200)
async def liveness():
    """K8s liveness probe.

    DO NOT check external dependencies — restarting won't fix them.
    Only verifies process is responsive.
    """
    uptime = int(time.time() - state.startup_time) if state.startup_time else 0
    return {
        "status": "alive",
        "uptime_sec": uptime,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ==========================================================================
# 4. READINESS PROBE (checks dependencies)
# ==========================================================================

async def check_db() -> tuple[bool, str]:
    """Return (success, error_msg)."""
    try:
        # from db import engine
        # async with engine.connect() as conn:
        #     await conn.execute(text("SELECT 1"))
        await asyncio.sleep(0)  # placeholder
        return True, ""
    except Exception as e:
        return False, str(e)[:100]


async def check_redis() -> tuple[bool, str]:
    try:
        # from redis_client import r
        # await r.ping()
        await asyncio.sleep(0)
        return True, ""
    except Exception as e:
        return False, str(e)[:100]


async def check_celery_broker() -> tuple[bool, str]:
    try:
        # from celery import current_app
        # response = await asyncio.wait_for(
        #     asyncio.to_thread(lambda: current_app.control.inspect(timeout=2).ping()),
        #     timeout=3,
        # )
        return True, ""
    except Exception as e:
        return False, str(e)[:100]


CHECKS = {
    'database': check_db,
    'redis': check_redis,
    'celery_broker': check_celery_broker,
}


@app.get("/health/ready", tags=["health"])
async def readiness():
    """K8s readiness probe — ready to serve traffic?"""
    if not state.is_ready:
        raise HTTPException(503, "Not ready")

    if state.is_shutting_down:
        raise HTTPException(503, "Shutting down")

    # Run all checks in parallel with timeout
    results = {}
    for name, check_fn in CHECKS.items():
        try:
            ok, err = await asyncio.wait_for(check_fn(), timeout=2.5)
            results[name] = {'ok': ok, 'error': err}
        except asyncio.TimeoutError:
            results[name] = {'ok': False, 'error': 'timeout'}
        except Exception as e:
            results[name] = {'ok': False, 'error': str(e)[:100]}

    all_ok = all(r['ok'] for r in results.values())
    if not all_ok:
        raise HTTPException(503, detail={'status': 'not_ready', 'checks': results})

    return {'status': 'ready', 'checks': results}


# ==========================================================================
# 5. STARTUP PROBE (for variable startup time)
# ==========================================================================

@app.get("/health/startup", tags=["health"])
async def startup_probe():
    """K8s startup probe — initialization complete?

    Use this for apps that take variable time to start (ML model load,
    migrations, etc.). Once it passes once, k8s switches to liveness/readiness.
    """
    if not state.is_ready:
        raise HTTPException(503, "Still starting")
    return {"status": "started"}


# ==========================================================================
# 6. DETAILED HEALTH (admin endpoint, not probe)
# ==========================================================================

@app.get("/health/details", tags=["health"])
async def health_details():
    """Verbose health info — NOT for k8s probes. Behind auth in prod."""
    results = {}
    for name, check_fn in CHECKS.items():
        start = time.monotonic()
        try:
            ok, err = await asyncio.wait_for(check_fn(), timeout=3)
            results[name] = {
                'status': 'up' if ok else 'down',
                'latency_ms': int((time.monotonic() - start) * 1000),
                'error': err if not ok else None,
            }
        except asyncio.TimeoutError:
            results[name] = {
                'status': 'timeout',
                'latency_ms': 3000,
            }
        except Exception as e:
            results[name] = {
                'status': 'error',
                'error': str(e)[:200],
            }

    all_up = all(r['status'] == 'up' for r in results.values())

    return {
        'status': 'up' if all_up else 'degraded',
        'version': APP_VERSION,
        'uptime_sec': int(time.time() - state.startup_time) if state.startup_time else 0,
        'startup_time': datetime.fromtimestamp(state.startup_time).isoformat() if state.startup_time else None,
        'is_ready': state.is_ready,
        'is_shutting_down': state.is_shutting_down,
        'checks': results,
    }


# ==========================================================================
# 7. INFO ENDPOINT (build metadata)
# ==========================================================================

@app.get("/info", tags=["health"])
async def info():
    """Build / deployment info."""
    return {
        'service': 'myapp',
        'version': APP_VERSION,
        'commit_sha': os.environ.get('GIT_COMMIT_SHA', 'unknown'),
        'environment': os.environ.get('ENVIRONMENT', 'unknown'),
        'started_at': datetime.fromtimestamp(state.startup_time).isoformat() if state.startup_time else None,
    }


# ==========================================================================
# 8. PROMETHEUS-STYLE METRICS (basic)
# ==========================================================================

# Use prometheus_client for full implementation
from collections import defaultdict


_metrics = {
    'requests_total': defaultdict(int),
    'errors_total': defaultdict(int),
    'health_check_failures': defaultdict(int),
}


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    _metrics['requests_total'][f'{request.method}_{response.status_code}'] += 1
    if response.status_code >= 500:
        _metrics['errors_total'][request.url.path] += 1
    return response


@app.get("/metrics", tags=["health"])
async def metrics():
    """Simplified Prometheus-style output. Use prometheus_client in prod."""
    lines = []
    for status_code, count in _metrics['requests_total'].items():
        lines.append(f'requests_total{{label="{status_code}"}} {count}')
    for path, count in _metrics['errors_total'].items():
        lines.append(f'errors_total{{path="{path}"}} {count}')
    return Response('\n'.join(lines), media_type='text/plain')


# ==========================================================================
# 9. KUBERNETES MANIFEST (reference)
# ==========================================================================

KUBERNETES_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: app
        image: myapp:v1.0.0
        ports:
        - containerPort: 8000

        startupProbe:
          httpGet:
            path: /health/startup
            port: 8000
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 30   # 150s max startup

        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
          successThreshold: 1

        env:
        - name: APP_VERSION
          value: "1.0.0"
        - name: ENVIRONMENT
          value: "production"

        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 1Gi

---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: myapp-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: myapp
"""


# ==========================================================================
# 10. CIRCUIT BREAKER STATE IN READINESS
# ==========================================================================

class CircuitBreaker:
    def __init__(self):
        self.failures = 0
        self.threshold = 5
        self.state = 'closed'  # closed, open, half-open

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.state = 'open'

    def record_success(self):
        self.failures = 0
        self.state = 'closed'

    @property
    def is_open(self):
        return self.state == 'open'


db_cb = CircuitBreaker()
redis_cb = CircuitBreaker()


@app.get("/health/ready-with-cb", tags=["health"])
async def readiness_with_cb():
    """Readiness checks circuit breakers too."""
    if not state.is_ready or state.is_shutting_down:
        raise HTTPException(503, "Not ready")

    open_breakers = []
    if db_cb.is_open:
        open_breakers.append('db')
    if redis_cb.is_open:
        open_breakers.append('redis')

    if open_breakers:
        raise HTTPException(503, detail={
            'status': 'circuit_open',
            'breakers': open_breakers,
        })

    return {'status': 'ready'}
