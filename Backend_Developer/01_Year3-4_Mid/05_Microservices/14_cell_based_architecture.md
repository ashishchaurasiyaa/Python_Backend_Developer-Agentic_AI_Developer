# Microservices — Cell-Based Architecture (Slack, AWS Pattern)
**Microservices · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **Cell** = self-contained instance of your application stack serving subset of users
- **Cell-based architecture** = many small, isolated cells (vs one big shared deployment)
- **Why** = blast radius isolation, independent scaling, faster failure recovery
- **Cell router** = directs each user to their cell (sharding key = user_id, tenant_id, region)
- **Origin pattern** = Slack, AWS (S3, DynamoDB), Salesforce, Doordash
- **Trade-off** = more ops complexity for better resilience
- **Multi-region** = cells deployed per region for data residency too

---

## The Problem Cells Solve

```
MONOLITHIC SCALING (typical):           CELL-BASED:
─────────────────                       ───────────
All users → one big cluster              Users sharded → cells
                                          ├── cell-1 (1M users)
1 bad query → ALL users affected         ├── cell-2 (1M users)
1 corrupt deploy → everyone down         └── cell-N (1M users)
Massive blast radius
Hard to test changes safely              1 bad query → 1 cell affected
                                          1 bad deploy → 1 cell (rolled back)
                                          Independent scaling per cell
                                          Test changes on 1 cell first
```

---

## Real Examples

| Company | Cell Strategy |
|---|---|
| **Slack** | Cells by workspace; ~thousands of cells |
| **AWS S3** | Cells by partition (object key prefix) |
| **AWS DynamoDB** | Tables sharded into thousands of partitions = cells |
| **DoorDash** | Cells by geography (markets) |
| **Salesforce** | Cells by org (tenant) |
| **Roblox** | Cells per game instance |
| **WhatsApp** | Cells by phone number range |

---

## Interview Questions & Answers

### Q1: Cell ki anatomy kya hai?

**Answer:** Each cell = full vertical stack for a subset of users.

```
┌──────────────────────────────────────┐
│ CELL N                                │
│ ┌────────────────────────────────┐   │
│ │ Load Balancer (cell-specific)  │   │
│ └─────────────┬──────────────────┘   │
│               │                       │
│ ┌─────────────▼──────────────────┐   │
│ │ API Servers (FastAPI)          │   │
│ │ replicas: 3                    │   │
│ └─────────────┬──────────────────┘   │
│               │                       │
│ ┌─────────────▼──────────────────┐   │
│ │ Background workers (Celery)    │   │
│ └─────────────┬──────────────────┘   │
│               │                       │
│ ┌─────────────▼──────────────────┐   │
│ │ Database (PostgreSQL)          │   │
│ │ - this cell's users only       │   │
│ └────────────────────────────────┘   │
│ ┌────────────────────────────────┐   │
│ │ Cache (Redis)                  │   │
│ └────────────────────────────────┘   │
│ ┌────────────────────────────────┐   │
│ │ Queues (Kafka topics)          │   │
│ └────────────────────────────────┘   │
└──────────────────────────────────────┘

Cell properties:
- Owns its data (no cross-cell DB queries)
- Can be deployed independently
- Can be sized for its load
- Failure isolated from other cells
```

**Anti-pattern:** A "shared service" across cells = single point of failure. If you must have one (auth?), it must be over-provisioned and very stable.

---

### Q2: Cell router — how do users find their cell?

**Answer:** A thin routing layer maps sharding key → cell.

```python
# Cell Router (thin service in front of all cells)
from fastapi import FastAPI, Request, HTTPException
import hashlib

app = FastAPI()

# Static routing table (managed in config/DB)
CELL_ASSIGNMENTS = {
    "cell-1": {"endpoint": "https://cell-1.acme.internal", "weight": 1.0},
    "cell-2": {"endpoint": "https://cell-2.acme.internal", "weight": 1.0},
    "cell-3": {"endpoint": "https://cell-3.acme.internal", "weight": 1.0},
}

# User → cell mapping (in Redis for fast lookup)
async def get_user_cell(user_id: int) -> str:
    cached = await redis.get(f"cell_map:{user_id}")
    if cached:
        return cached.decode()

    # Fallback: deterministic hash assignment
    cell_id = consistent_hash(user_id, list(CELL_ASSIGNMENTS.keys()))
    await redis.setex(f"cell_map:{user_id}", 86400, cell_id)
    return cell_id

def consistent_hash(key: int, cells: list[str]) -> str:
    """Stable assignment — adding cell doesn't reshuffle existing."""
    # Real impl: use rendezvous (HRW) or consistent hashing ring
    h = hashlib.md5(str(key).encode()).hexdigest()
    idx = int(h, 16) % len(sorted(cells))
    return sorted(cells)[idx]

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_to_cell(path: str, request: Request):
    # Extract user_id from JWT or session
    user_id = await extract_user_id(request)
    if not user_id:
        raise HTTPException(401, "Auth required")

    # Find cell
    cell_id = await get_user_cell(user_id)
    cell = CELL_ASSIGNMENTS[cell_id]

    # Proxy to cell (using httpx)
    async with httpx.AsyncClient() as client:
        url = f"{cell['endpoint']}/{path}"
        method = request.method
        body = await request.body()
        response = await client.request(
            method,
            url,
            content=body,
            headers={**dict(request.headers), "X-Cell-Id": cell_id},
            timeout=30,
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )
```

**Smart routing strategies:**
- **Geo-routing**: Indian users → ap-south-1 cells
- **Tenant routing**: Each big customer → dedicated cell (premium tier)
- **Load routing**: Spread evenly via consistent hash
- **Affinity routing**: Same user → same cell (for cache locality)

---

### Q3: How to size cells?

**Answer:** Balance blast radius vs ops overhead.

**Typical cell sizes:**

| Pattern | Cell holds | Examples |
|---|---|---|
| **Mega-cells** | 100M+ users | Few cells (3-10); maximize cost efficiency |
| **Medium cells** | 1-10M users | Slack-style |
| **Micro-cells** | 10K-100K users | Per-tenant SaaS |
| **Single-user cells** | 1 user | Per-customer isolation (banks, govt) |

**Decision framework:**
```
Q: What's blast radius cost?
├── Critical (banking, healthcare) → smaller cells
└── Standard SaaS → larger cells

Q: How much ops capacity?
├── Limited team → fewer, larger cells
└── Mature ops → more, smaller cells

Q: Multi-tenancy isolation needs?
├── Enterprise customers want isolation → per-tenant cells (premium)
└── Pooled OK → shared cells
```

**Slack model:**
- Most workspaces share a cell
- Large customers (Fortune 500) get dedicated cell
- Different SLA tiers per cell

---

### Q4: Cross-cell operations (analytics, search)?

**Answer:** Avoid; if necessary, use async aggregation.

**Patterns:**

**1. Don't do cross-cell live queries.** Bad: query 100 cells for admin dashboard.

**2. Pull via CDC + central data lake**
```python
# Each cell streams changes to central Kafka
# CDC (Debezium) → kafka.cell_1.users, kafka.cell_2.users, ...

# Central analytics consumer aggregates
async def aggregate_metrics():
    consumer = AIOKafkaConsumer("kafka.cell_*.metrics")
    async for msg in consumer:
        # Aggregate into central data warehouse
        await snowflake.insert("user_metrics", msg.value)
```

**3. Scatter-gather (last resort)**
```python
async def admin_user_search(query: str) -> list[User]:
    """Search across all cells — slow, do sparingly."""
    cell_ids = await get_all_cell_ids()
    tasks = [
        search_one_cell(cell_id, query)
        for cell_id in cell_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    flattened = [u for r in results if not isinstance(r, Exception) for u in r]
    return flattened[:100]
```

**4. Global services**
```
Truly global (must exist):
- Auth (one global identity provider)
- Billing (one financial ledger)
- Cell router (entry point)

Better to replicate per-cell:
- Email, SMS, push notification
- Logs, metrics
- Search indices
```

---

### Q5: Cell migration — moving users between cells?

**Answer:** Rebalancing requires careful coordination.

```python
async def migrate_user(user_id: int, source_cell: str, target_cell: str):
    """Move a user from one cell to another. Zero-downtime."""

    # Phase 1: Begin replication
    await db_source.execute("INSERT INTO migration_jobs ...")
    await start_cdc_replication(source_cell, target_cell, user_id)

    # Phase 2: Wait for replication caught up (< 1s lag)
    while True:
        lag = await check_replication_lag(source_cell, target_cell, user_id)
        if lag < 1.0:
            break
        await asyncio.sleep(5)

    # Phase 3: Brief read-only mode on source
    await db_source.execute(
        "UPDATE users SET status = 'migrating' WHERE id = :id",
        {"id": user_id},
    )

    # Phase 4: Final sync (any pending writes)
    await wait_for_drain(source_cell, user_id)

    # Phase 5: Atomic switch — update router
    await redis.set(f"cell_map:{user_id}", target_cell)
    await redis.publish("cell_routing_changes", json.dumps({
        "user_id": user_id,
        "old_cell": source_cell,
        "new_cell": target_cell,
    }))

    # Phase 6: Verify
    await asyncio.sleep(2)  # propagation
    test_result = await test_user_access(user_id, target_cell)
    if not test_result:
        # Rollback
        await redis.set(f"cell_map:{user_id}", source_cell)
        raise MigrationFailed(user_id)

    # Phase 7: Cleanup
    await db_source.execute(
        "DELETE FROM users WHERE id = :id; ...",
        {"id": user_id},
    )
```

**Use cases for migration:**
- Premium tier upgrade (move to better cell)
- Region change (user moved countries)
- Cell decommissioning (rebalancing)
- Compliance (data residency change)

---

### Q6: Deployments in cell architecture?

**Answer:** Canary deploys roll cell-by-cell.

```yaml
# .github/workflows/deploy.yml
name: Cell Deployment
on: [push]

jobs:
  canary:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to canary cell
        run: |
          kubectl set image deployment/api api=registry/api:${SHA} -n cell-canary
          kubectl rollout status deployment/api -n cell-canary

      - name: Run smoke tests on canary
        run: pytest tests/smoke/ --target=https://cell-canary.acme.com

      - name: Watch for 30 min
        run: |
          ./scripts/check-slos.sh cell-canary 1800

  rollout:
    needs: canary
    runs-on: ubuntu-latest
    strategy:
      matrix:
        cell: [cell-1, cell-2, cell-3, cell-4]
      max-parallel: 1   # one at a time
    steps:
      - name: Deploy to ${{ matrix.cell }}
        run: |
          kubectl set image deployment/api api=registry/api:${SHA} -n ${{ matrix.cell }}
          kubectl rollout status deployment/api -n ${{ matrix.cell }}

      - name: Smoke test ${{ matrix.cell }}
        run: pytest tests/smoke/ --target=https://${{ matrix.cell }}.acme.com

      - name: Soak (wait between cells)
        run: sleep 600   # 10 min between cells
```

**Bad deploy detection:**
```python
# Auto-rollback if error rate spikes on a cell
async def watchdog():
    for cell in cells:
        error_rate = await prometheus.query(f'rate(http_requests_total{{cell="{cell}",status=~"5.."}}[5m]) / rate(http_requests_total{{cell="{cell}"}}[5m])')
        if error_rate > 0.01:
            await rollback(cell, "Error rate exceeded 1%")
            await alert("Auto-rollback on " + cell)
```

---

### Q7: Cell observability + tracing?

**Answer:** Tag everything by cell.

```python
# Add cell_id to every log + metric + trace
from opentelemetry import trace

@app.middleware("http")
async def cell_context_middleware(request: Request, call_next):
    cell_id = os.environ["CELL_ID"]    # set in K8s env
    span = trace.get_current_span()
    span.set_attribute("cell.id", cell_id)

    # Add to logger context
    logger.bind(cell_id=cell_id)

    response = await call_next(request)
    response.headers["X-Cell-Id"] = cell_id
    return response

# Prometheus — cell label on all metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total requests",
    ["cell_id", "method", "endpoint", "status"],
)
```

**Per-cell dashboards in Grafana:**
- Latency p50/p95/p99 per cell
- Error rate per cell
- Saturation (CPU/memory/DB connections) per cell
- Cost per cell (LLM, infra)

---

### Q8: When to choose cells vs alternatives?

**Answer:**

| Pattern | When |
|---|---|
| **Single monolith** | < 1M users, single team, single region |
| **Microservices (shared)** | 1-10M users, multiple teams |
| **Sharded DB + shared app** | DB is bottleneck, app fits in one cluster |
| **Cells** | > 10M users, blast radius matters, multi-region needed |
| **Cells + microservices** | > 100M users, complex domain |

**Don't use cells if:**
- Small team (< 10 engineers ops capacity)
- Cross-cell queries are common
- Compliance allows shared infrastructure
- Cost-sensitive (cells = more infra)

---

## Comparison: Cells vs Sharding

| Aspect | Cells | DB Sharding |
|---|---|---|
| Scope | Full app stack | Just DB |
| Blast radius | Cell only | Multi-cell possible |
| Operational complexity | Higher | Lower |
| Deploy safety | Rolling per cell | All-or-nothing |
| Latency | Cell-local everything | DB calls still cross-shard |
| Cost | Higher (duplicate infra) | Lower |

**Cells = "sharding everything", not just DB.**

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Cross-cell queries creep in | Code review; gateway pattern |
| Cell router becomes bottleneck | Multiple routers; client-side routing |
| Hot cell (uneven load) | Better sharding key; cell migration |
| Cross-cell auth slow | Cache auth decisions in cell-local Redis |
| Deploy cells out of sync | Schema versioning; backward compat |
| Cell decommissioning manual | Automate; tested migration tooling |
| Logs scattered | Central log aggregation (cell_id tag) |
| Cost ballooning | Right-size each cell; auto-scale |
| User in wrong cell after region change | Migration job; routing reload |
| Single-cell failure cascades | Circuit breakers; bulkheads |

---

## Senior-level Checklist

- [ ] Sharding key chosen (user_id, tenant_id, region)
- [ ] Cell router service deployed + monitored
- [ ] Cell-to-cell communication minimized
- [ ] CDC pipeline to central data lake for analytics
- [ ] Per-cell K8s namespaces + IAM isolation
- [ ] Deployment automation rolls cells one-at-a-time
- [ ] Canary cell with extended soak
- [ ] Auto-rollback on per-cell SLO breach
- [ ] Cell migration tooling tested
- [ ] All telemetry tagged with cell_id
- [ ] Per-cell cost tracking
- [ ] Disaster recovery: cell loss tested
- [ ] Documentation per cell (owner, customers, special config)
- [ ] Multi-region cells for data residency

---

## Related Docs
- `01_microservices_patterns.md` — patterns foundation
- `06_service_mesh_istio_linkerd.md` — service mesh
- `10_distributed_systems_theory.md` — distributed fundamentals
- `01_Year3-4_Mid/04_DevOps/15_multi_region_deployment.md` — multi-region
- `01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md` — SLOs per cell
- `00_Year0-2_Junior/04_Database_SQL/10_postgresql_partitioning_sharding.md` — DB sharding

## External References
- AWS Cell-based architecture: https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/
- Slack cells blog: https://slack.engineering/slacks-migration-to-a-cellular-architecture
- DoorDash cells: https://doordash.engineering/2022/12/06/how-doordash-is-using-cell-based-architecture
- Werner Vogels on shuffle sharding: https://www.allthingsdistributed.com/2024/02/dynamo-evolution.html
