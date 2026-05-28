# 39 — Zero Downtime Deployment

---

## What & Why

**Zero Downtime Deployment** = deploying new code without users experiencing errors, service interruptions, or performance degradation.

Traditional deployment: stop service → deploy → restart → downtime gap.
Modern: run old and new versions simultaneously, gradually shift traffic.

**Why it matters:**
- SLA: 99.99% uptime = 52 minutes/year max downtime
- Global users: no maintenance window without affecting someone
- Frequent deployments (CI/CD): can't afford downtime per deploy

---

## 1. Blue-Green Deployment

```
           ┌─────────┐
           │  Load   │──── production traffic
           │ Balancer│
           └────┬────┘
                │
         ┌──────▼──────┐
         │             │
    ┌────▼────┐   ┌────▼────┐
    │  BLUE   │   │  GREEN  │
    │  v1.0   │   │  v1.1   │ ← deploy new version here
    │(current)│   │(standby)│
    └─────────┘   └─────────┘

Steps:
1. Blue = production (100% traffic)
2. Deploy v1.1 to Green (idle, separate environment)
3. Run smoke tests on Green
4. Switch LB: route 100% traffic to Green
5. Blue becomes standby (instant rollback if needed)
```

```python
class BlueGreenDeployer:
    """
    Automates blue-green deployment via load balancer API.
    Works with AWS ALB, NGINX, HAProxy.
    """

    def __init__(self, lb_client, blue_target_group: str,
                 green_target_group: str):
        self.lb = lb_client
        self.blue_tg  = blue_target_group
        self.green_tg = green_target_group
        self.current_active = "blue"

    async def deploy(self, new_version: str, health_check_url: str) -> bool:
        standby = "green" if self.current_active == "blue" else "blue"
        standby_tg = self.green_tg if standby == "green" else self.blue_tg

        print(f"Deploying {new_version} to {standby} environment...")

        # Step 1: Deploy to standby environment
        await self._deploy_to_environment(standby, new_version)

        # Step 2: Health check standby
        if not await self._health_check(health_check_url, environment=standby):
            print(f"Health check failed on {standby}. Rollback.")
            return False

        # Step 3: Switch traffic to standby
        await self.lb.modify_rule(
            target_group=standby_tg,
            weight=100
        )
        await self.lb.modify_rule(
            target_group=self.blue_tg if standby == "green" else self.green_tg,
            weight=0
        )

        self.current_active = standby
        print(f"Traffic switched to {standby} ({new_version}). Deployment complete.")
        return True

    async def rollback(self):
        """Instant rollback: flip traffic back to old environment."""
        previous = "blue" if self.current_active == "green" else "green"
        prev_tg  = self.blue_tg if previous == "blue" else self.green_tg

        await self.lb.modify_rule(target_group=prev_tg, weight=100)
        await self.lb.modify_rule(
            target_group=self.green_tg if self.current_active == "green" else self.blue_tg,
            weight=0
        )
        self.current_active = previous
        print(f"Rolled back to {previous} environment.")

    async def _deploy_to_environment(self, environment: str, version: str):
        """Deploy new Docker image to target environment."""
        # In production: call Kubernetes, ECS, or Ansible to update instances
        print(f"Deploying version {version} to {environment}...")
        await __import__("asyncio").sleep(1)   # simulate deploy time

    async def _health_check(self, url: str, environment: str,
                             retries: int = 10) -> bool:
        import aiohttp
        for i in range(retries):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass
            await __import__("asyncio").sleep(3)
        return False
```

**Pros:** Instant rollback, isolated environments, test full stack before switch.
**Cons:** Requires 2x infrastructure cost, database schema changes need care.

---

## 2. Canary Deployment

```
           ┌─────────┐
           │  Load   │
           │ Balancer│
           └─────┬───┘
                 │
       ┌─────────┴──────────┐
       │ 95%                │ 5%
  ┌────▼────┐          ┌────▼────┐
  │  v1.0   │          │  v1.1   │← Canary (small slice of traffic)
  │ (stable)│          │  (new)  │← Monitor errors/latency
  └─────────┘          └─────────┘

Steps:
1. Deploy v1.1 as "canary" (5% traffic)
2. Monitor: error rate, latency, business metrics
3. If healthy → gradually increase: 5% → 25% → 50% → 100%
4. If issues → immediately reduce canary to 0%
```

```python
class CanaryController:
    """
    Progressive canary deployment with automated metric monitoring.
    Auto-promotes if healthy, auto-rolls back on degradation.
    """

    CANARY_STEPS = [5, 10, 25, 50, 75, 100]     # traffic percentages
    STEP_DURATION_MIN = 5                          # wait between steps
    ERROR_RATE_THRESHOLD = 0.01                    # 1% max error rate
    P99_LATENCY_THRESHOLD_MS = 500

    def __init__(self, lb_client, metrics_client):
        self.lb      = lb_client
        self.metrics = metrics_client

    async def run_canary(self, new_version: str, stable_tg: str,
                          canary_tg: str) -> dict:
        """
        Run progressive canary deployment.
        Returns {"status": "promoted"/"rolled_back", "at_step": pct}.
        """
        # Deploy canary instances
        await self._deploy_canary(new_version, canary_tg)

        for step_pct in self.CANARY_STEPS:
            print(f"Setting canary traffic to {step_pct}%...")
            await self.lb.set_weights({
                stable_tg: 100 - step_pct,
                canary_tg: step_pct
            })

            if step_pct == 100:
                return {"status": "promoted", "at_step": 100}

            # Wait and monitor
            await __import__("asyncio").sleep(self.STEP_DURATION_MIN * 60)

            health = await self._check_canary_health(canary_tg)
            if not health["healthy"]:
                # Rollback: remove all canary traffic
                await self.lb.set_weights({stable_tg: 100, canary_tg: 0})
                return {
                    "status":   "rolled_back",
                    "at_step":  step_pct,
                    "reason":   health["reason"]
                }

            print(f"Step {step_pct}% healthy. Proceeding to next step.")

        return {"status": "promoted", "at_step": 100}

    async def _check_canary_health(self, canary_tg: str) -> dict:
        """Check error rate and latency for canary instances."""
        # Query Prometheus/DataDog
        error_rate = await self.metrics.query(
            f'rate(http_requests_total{{target_group="{canary_tg}",status=~"5.."}}[5m]) / '
            f'rate(http_requests_total{{target_group="{canary_tg}"}}[5m])'
        )
        p99_latency = await self.metrics.query(
            f'histogram_quantile(0.99, rate(http_request_duration_ms_bucket'
            f'{{target_group="{canary_tg}"}}[5m]))'
        )

        if error_rate > self.ERROR_RATE_THRESHOLD:
            return {"healthy": False, "reason": f"Error rate {error_rate:.2%} > threshold"}
        if p99_latency > self.P99_LATENCY_THRESHOLD_MS:
            return {"healthy": False, "reason": f"P99 latency {p99_latency}ms > threshold"}

        return {"healthy": True, "error_rate": error_rate, "p99_ms": p99_latency}

    async def _deploy_canary(self, version: str, target_group: str):
        print(f"Deploying {version} to canary target group {target_group}...")
        await __import__("asyncio").sleep(1)
```

**Pros:** Real user traffic test, gradual risk, auto-rollback on issues.
**Cons:** Requires good metrics/alerting, complex routing, DB compatibility.

---

## 3. Rolling Deployment

```
Kubernetes Rolling Update:
Before: [v1.0, v1.0, v1.0, v1.0] (4 pods)

Step 1: [v1.0, v1.0, v1.0, v1.1]  (1 new pod)
Step 2: [v1.0, v1.0, v1.1, v1.1]  (2 new pods)
Step 3: [v1.0, v1.1, v1.1, v1.1]  (3 new pods)
Step 4: [v1.1, v1.1, v1.1, v1.1]  (complete)

maxSurge: how many EXTRA pods can exist temporarily (above desired)
maxUnavailable: how many pods can be DOWN at a time
```

```yaml
# Kubernetes Rolling Update configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2           # at most 12 pods total during update
      maxUnavailable: 0     # never go below 10 pods (zero downtime)
  template:
    spec:
      containers:
      - name: app
        image: myservice:v1.1
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          periodSeconds: 10
```

```python
class HealthEndpoints:
    """
    FastAPI health check endpoints for Kubernetes probes.
    readinessProbe: is app ready to receive traffic?
    livenessProbe: is app still running (should k8s restart if fails)?
    """

    async def liveness(self):
        """K8s kills pod if this fails 3 times. Only check if process is alive."""
        return {"status": "alive"}

    async def readiness(self, db, redis) -> dict:
        """
        K8s removes pod from Service endpoints if this fails.
        Checks real dependencies — pod stays alive but gets no traffic.
        """
        checks = {}
        try:
            await db.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"

        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

        all_ok = all(v == "ok" for v in checks.values())
        status_code = 200 if all_ok else 503
        return {"status": "ready" if all_ok else "not_ready", "checks": checks}, status_code

    async def startup(self, app_state) -> dict:
        """K8s startup probe: only checked once at startup. Allows longer init."""
        if not app_state.initialized:
            return {"status": "starting"}, 503
        return {"status": "started"}
```

---

## 4. Feature Flags

```python
"""
Feature flags: deploy code to production but enable for subset of users.
Decouple deployment from release.
Tools: LaunchDarkly, Unleash, GrowthBook, Flagsmith.
"""

import json
from enum import Enum
from dataclasses import dataclass

class RolloutStrategy(Enum):
    ALL_OFF    = "all_off"
    ALL_ON     = "all_on"
    PERCENTAGE = "percentage"
    USER_LIST  = "user_list"
    BETA_GROUP = "beta_group"

@dataclass
class FeatureFlag:
    flag_id: str
    name: str
    enabled: bool
    strategy: RolloutStrategy
    rollout_percentage: float = 0.0
    allowed_user_ids: list[str] = None
    allowed_groups: list[str] = None


class FeatureFlagService:
    """
    Check if a feature is enabled for a specific user/context.
    Cached in Redis for low latency.
    """

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db    = db_client

    async def is_enabled(self, flag_id: str, user_id: str,
                          user_groups: list[str] = None) -> bool:
        """Check if feature flag is enabled for this user."""
        flag = await self._get_flag(flag_id)
        if not flag or not flag.enabled:
            return False

        match flag.strategy:
            case RolloutStrategy.ALL_ON:
                return True
            case RolloutStrategy.ALL_OFF:
                return False
            case RolloutStrategy.PERCENTAGE:
                return self._is_in_percentage(user_id, flag.rollout_percentage)
            case RolloutStrategy.USER_LIST:
                return user_id in (flag.allowed_user_ids or [])
            case RolloutStrategy.BETA_GROUP:
                return bool(set(user_groups or []) & set(flag.allowed_groups or []))
        return False

    def _is_in_percentage(self, user_id: str, percentage: float) -> bool:
        """Consistent bucketing: same user always gets same result."""
        import hashlib
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        bucket = (hash_val % 10000) / 100.0   # 0.00 to 99.99
        return bucket < percentage

    async def _get_flag(self, flag_id: str) -> FeatureFlag | None:
        """Cache flag config in Redis (TTL=60s for fast updates)."""
        cached = await self.redis.get(f"flag:{flag_id}")
        if cached:
            data = json.loads(cached)
            return FeatureFlag(**data)

        flag_data = await self.db.query_one(
            "SELECT * FROM feature_flags WHERE flag_id=$1", flag_id
        )
        if not flag_data:
            return None

        await self.redis.setex(f"flag:{flag_id}", 60, json.dumps(dict(flag_data)))
        return FeatureFlag(**flag_data)

    async def update_flag(self, flag_id: str, updates: dict):
        """Update flag and invalidate cache."""
        await self.db.execute(
            "UPDATE feature_flags SET enabled=$2, strategy=$3, "
            "rollout_percentage=$4, updated_at=NOW() WHERE flag_id=$1",
            flag_id, updates.get("enabled"), updates.get("strategy"),
            updates.get("rollout_percentage", 0)
        )
        await self.redis.delete(f"flag:{flag_id}")


# Usage in application code:
async def new_checkout_flow(user_id: str, flags: FeatureFlagService):
    if await flags.is_enabled("new_checkout_v2", user_id):
        return await checkout_v2(user_id)     # new code path
    return await checkout_v1(user_id)         # old code path
```

---

## 5. Database Migration Strategies

```python
"""
DB schema changes during zero-downtime deployment.
Problem: both old (v1) and new (v2) code run simultaneously during rollout.
Schema must be compatible with BOTH versions.

Pattern: Expand → Migrate → Contract (3-phase migration)

Example: rename column `user_name` → `full_name`

Phase 1 (Expand) — v1.1 deployed:
  - ADD COLUMN full_name TEXT (new column)
  - v1.1 writes to BOTH user_name AND full_name
  - v1.1 reads from user_name (for compatibility with v1.0 still running)

Phase 2 (Migrate) — background job:
  - Backfill: UPDATE users SET full_name = user_name WHERE full_name IS NULL

Phase 3 (Contract) — v1.2 deployed:
  - v1.2 reads from full_name only
  - DROP COLUMN user_name (safe: no code uses it)
"""

class MigrationStrategy:

    @staticmethod
    def expand_migration():
        """Phase 1: Add new structure alongside old (backward compatible)."""
        return [
            # Add new column (nullable! not NOT NULL yet)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT",
            # Add trigger to keep in sync (optional, for zero-lag sync)
            """
            CREATE OR REPLACE FUNCTION sync_names() RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.user_name IS NOT NULL THEN
                    NEW.full_name = NEW.user_name;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,
            """
            CREATE TRIGGER sync_user_full_name
            BEFORE INSERT OR UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION sync_names();
            """
        ]

    @staticmethod
    def backfill_migration():
        """Phase 2: Migrate existing data in batches (no table lock)."""
        return """
        DO $$
        DECLARE
            batch_size INT := 10000;
            last_id BIGINT := 0;
            rows_updated INT;
        BEGIN
            LOOP
                UPDATE users
                SET full_name = user_name
                WHERE id > last_id
                  AND full_name IS NULL
                  AND id <= last_id + batch_size;

                GET DIAGNOSTICS rows_updated = ROW_COUNT;
                EXIT WHEN rows_updated = 0;

                SELECT MAX(id) INTO last_id FROM users WHERE id <= last_id + batch_size;
                PERFORM pg_sleep(0.1);   -- be kind to production DB
            END LOOP;
        END $$;
        """

    @staticmethod
    def contract_migration():
        """Phase 3: Remove old structure (only after ALL code uses new)."""
        return [
            "DROP TRIGGER IF EXISTS sync_user_full_name ON users",
            "DROP FUNCTION IF EXISTS sync_names()",
            "ALTER TABLE users DROP COLUMN user_name"
        ]
```

---

## 6. Comparison Table

| Strategy | Rollback Speed | Traffic Impact | Infrastructure Cost | DB Compatibility |
|----------|---------------|----------------|--------------------|--------------------|
| Blue-Green | Instant | Zero (switch) | 2x | Requires compat schema |
| Canary | Fast (set %) | Tiny (canary%) | 1.05-1.5x | Requires compat schema |
| Rolling | Slow (redeploy) | Zero (probes) | 1x | Requires compat schema |
| Feature Flag | Instant (toggle) | Zero | 1x | Flexible |

---

## 7. Interview Questions

**Q1: What is the difference between blue-green and canary?**
> Blue-green: instant 100% switch between two complete environments. Risk: all users hit new version at once if something is missed in testing. Canary: gradual traffic shift (5% → 100%) — real users test in production with controlled blast radius. Blue-green is faster to deploy; canary is safer for risky changes.

**Q2: How do you handle database migrations with zero downtime?**
> 3-phase "Expand → Migrate → Contract": (1) Expand: add new column/table, both old and new code paths work. (2) Migrate: backfill data in batches (avoid full table lock). (3) Contract: once all pods run new code, remove old column. Never do breaking DB changes (DROP/RENAME) in the same deploy as app code changes.

**Q3: What is a feature flag and when should you use it?**
> Feature flag: runtime switch to enable/disable code paths without redeployment. Use when: testing new features with subset of users (percentage rollout), A/B testing, kill switches for risky features, enabling feature for beta groups. Decouple deployment (code reaches prod) from release (feature becomes visible). LaunchDarkly/Unleash handle distributed flag evaluation.

**Q4: How does Kubernetes ensure zero downtime during rolling updates?**
> readinessProbe: k8s only sends traffic to pods that pass the probe (new pod not added to service endpoints until healthy). maxUnavailable=0: never removes old pod until new one is ready. Graceful shutdown: SIGTERM sent to old pod → old pod finishes in-flight requests → killed after terminationGracePeriodSeconds. Combined: traffic always goes to healthy pods.

**Q5: How does consistent hashing in feature flags work?**
> User bucketing: hash(user_id) % 10000 → value 0-9999 (0.00-99.99%). For a 25% rollout: users with bucket < 2500 see the feature. Same user always gets same bucket (deterministic). This means: the same user consistently sees old or new UX (no flipping on each request), which is critical for UX consistency.
