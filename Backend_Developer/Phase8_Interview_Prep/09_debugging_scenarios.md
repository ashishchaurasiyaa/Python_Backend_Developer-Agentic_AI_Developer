# Backend Debugging Scenarios — Production Triage Playbook

> "Tell me about a time you debugged a production issue" — most common senior-engineer interview question.
> This playbook gives 15 scenarios with structured debug steps so you can speak fluently from real patterns.

**Universal framework — USE this for every scenario:**

```
1. WHAT'S BROKEN?          (symptom, scope, when started)
2. WHAT CHANGED?            (deploys, traffic spike, infra event)
3. WHERE IS IT?             (service, endpoint, region, user segment)
4. WHY IS IT HAPPENING?     (theory + evidence)
5. STOP THE BLEEDING        (mitigate before perfect fix)
6. ROOT CAUSE + FIX
7. PREVENT RECURRENCE       (test, alert, doc)
```

---

## SCENARIO 1 — "API is slow, p99 latency spiked from 200ms to 5s"

### Step 1: Confirm the scope
- All endpoints? Or specific ones?
- All users? Or specific tenant/region?
- All HTTP methods? Or only POSTs (writes)?
- Started at what time? Correlate to deploys/cron jobs.

### Step 2: Check the four golden signals
- **Latency**: Grafana → service p50/p95/p99 over 24h.
- **Traffic**: RPS — did load spike?
- **Errors**: 5xx rate, 4xx rate.
- **Saturation**: CPU, memory, DB connections, queue depth.

### Step 3: Walk the stack
```
Client → LB → API → Cache → DB
                 ↘ → External APIs
                 ↘ → Background tasks
```

For each hop, ask "is this hop slow?"

### Step 4: Quick diagnostics

```bash
# Service-side
kubectl top pods
kubectl logs -f api-pod-xxx --tail=200

# DB
SELECT pid, query, state, query_start, now() - query_start AS dur
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY dur DESC LIMIT 20;

# Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 10;
```

### Common root causes (frequency-ordered)
1. **Slow DB query** (missing index, plan flip, lock wait).
2. **External API timeout** (third-party degradation).
3. **Cache miss storm** (key expired, all hit DB).
4. **GC pause** (long heap in JVM or Python with huge allocations).
5. **Connection pool exhausted** (too many slow queries → pool full → requests queued).

### Mitigation patterns
- Enable circuit breaker for slow downstream.
- Restart service if memory pressure suspected.
- Scale up DB replica reads.
- Roll back deploy if correlated.

---

## SCENARIO 2 — "Memory leak — pods OOM-killed every 4 hours"

### Symptoms
- Pod restart count climbing.
- Memory graph: linear growth over time, sudden drop on restart.
- Some endpoints slower as memory pressure rises.

### Debug steps

**1. Confirm it's a leak (not just high usage):**
```bash
kubectl top pod api-xxx --containers
# Memory grows even with constant traffic = leak.
```

**2. Heap dump:**
```python
# tracemalloc — Python's built-in
import tracemalloc
tracemalloc.start(25)
# ... wait, then snapshot
snap = tracemalloc.take_snapshot()
for stat in snap.statistics("lineno")[:20]:
    print(stat)
```

**3. Common Python leak patterns:**
- Global dict/list that keeps growing.
- Cached objects with strong refs (use `weakref`).
- Logging accumulator (`logger.handlers` list grows on each app re-init).
- Connection objects not closed.
- Closures capturing big objects.

**4. Use a profiler in production:**
- `py-spy dump --pid <PID>` — non-invasive stack snapshot.
- `memray` (newer, very good).
- `objgraph.show_growth()` — periodic snapshots.

### Mitigation
- Set pod memory limit + restart policy.
- Reduce request size limits.
- Schedule preemptive restart (daily cron) until fixed.

### Real-world example
"In one project, we had a `lru_cache` on a method whose `self` parameter kept references to request objects. Each request was being kept alive by the cache. Fix: removed cache, added Redis caching for the actual data."

---

## SCENARIO 3 — "Database connections exhausted"

### Symptom
- `ERROR: remaining connection slots reserved for non-replication superuser connections`
- App returns 503; pods don't crash but stop serving.

### Diagnostic
```sql
-- See current connection count by state
SELECT state, COUNT(*)
FROM pg_stat_activity
GROUP BY state;

-- See idle-in-transaction (worst kind!)
SELECT pid, usename, application_name, query, query_start, now() - state_change AS idle_dur
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY idle_dur DESC;
```

### Root causes
1. **Forgot to commit/rollback** — txn held open. Especially after exception in app code.
2. **Lambda spike** — 1000 lambdas × 5 conns = 5000 conns, DB max=100.
3. **Connection pool misconfigured** — `min_size=N` × replicas → exceeds max.
4. **Long-running query** holding conn.

### Mitigation
```bash
# Kill idle-in-txn connections older than 5 min
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction' AND state_change < now() - interval '5 min';
```

Add to postgres config:
```
idle_in_transaction_session_timeout = '5min'
statement_timeout = '30s'
```

### Permanent fix
- Use PgBouncer in transaction mode → 5000 clients on 100 conns.
- Audit code: `try/finally` around DB sessions, context managers, no async tasks holding sessions.
- Set sensible pool size: `2 × cpu_count` typically.

---

## SCENARIO 4 — "API returning 500s intermittently — flaky errors"

### Step 1: Reproduce + classify
- 500 with what message? Grep logs.
- Pattern: same user always? Same endpoint? Same time of day?
- Distribution: 1% of all requests? 50% of one endpoint?

### Step 2: Trace one failing request
```bash
# Get sample failing request from logs
grep "500" /var/log/app/access.log | tail -5

# Get its trace_id, look up in Jaeger
# See which span failed — DB? External? GC?
```

### Step 3: Common flaky-500 causes

| Cause | Signature |
|---|---|
| External API timeout | "ReadTimeout" / "ConnectionError" in logs |
| DB connection failed mid-query | "server closed connection unexpectedly" |
| Race condition | Only happens under concurrency, hard to reproduce locally |
| Out-of-memory in worker | Last successful log = full memory dump |
| Misconfigured deploy | Some pods new code, some old, breaking compat |
| Network blip | All from same AZ for a 30-sec window |

### Mitigation
- Retry idempotent requests.
- Circuit breaker on external calls.
- Add structured error logging (`sentry`, `bugsnag`).

---

## SCENARIO 5 — "Background jobs not processing"

### Symptom
- Queue depth growing in Celery / RabbitMQ / SQS dashboard.
- User-visible: "I clicked send and nothing happened" (email queue).

### Debug

**1. Are workers alive?**
```bash
# Celery
celery -A app inspect active
celery -A app inspect ping

# RabbitMQ
rabbitmqctl list_consumers
```

**2. If workers alive but not consuming:**
- All workers stuck on a poison message (one job takes forever, blocks others).
- All workers stuck on external dependency (DB, API).
- Prefetch too high — workers hoard messages.

**3. If workers dead:**
- Crashed silently. Check `journalctl -u celery -n 100`.
- OOM killed.
- Auto-scaler scaled to 0 (read your scaling config).

### Common gotchas
- Celery `acks_late=True` + worker crashes = message redelivered → poison message loop.
- Long-running task without checkpointing → restart loses progress.
- `task_soft_time_limit` not set → infinite hangs eat workers.

### Production checklist for queue workers
```python
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 360
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # for long tasks
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
```

---

## SCENARIO 6 — "Cache hit rate dropped 90% → 30%, DB on fire"

### Step 1: What changed?
- Was a new deploy made? Maybe key format changed.
- Did someone `FLUSHDB` or restart Redis without persistence?
- Did the key prefix change (`v1:user:` → `v2:user:`)?

### Step 2: Diagnose

```bash
# Redis: see hit/miss ratio
redis-cli INFO stats | grep -E "keyspace_(hits|misses)"

# Top keys
redis-cli --hotkeys

# Recent key patterns
redis-cli --scan --pattern "user:*" | head -20
```

### Step 3: Common causes
- Cache stampede — popular key expired, thousands hit DB.
- Eviction storm — `maxmemory-policy=allkeys-lru`, Redis evicting hot data.
- Bad new code computing keys differently.
- Big spike in cold traffic (new user signups).

### Mitigation
- Warm cache by replaying common queries.
- Implement single-flight (mutex on cache miss).
- Increase Redis memory or split into multiple instances.

---

## SCENARIO 7 — "DB query suddenly slow, no code change"

### Diagnostic
```sql
-- Check the EXPLAIN — has plan flipped?
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 123;

-- Stats updated?
SELECT schemaname, relname, last_analyze, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
WHERE relname = 'orders';
```

### Common causes
1. **Stats outdated** — `ANALYZE orders;` fixes it.
2. **Index bloat** — `REINDEX CONCURRENTLY` or rebuild.
3. **Table bloat** — `VACUUM FULL` or `pg_repack`.
4. **New data skew** — index estimates wrong, plan flipped to seq scan.
5. **Lock contention** — `pg_locks` view shows waiting txns.
6. **WAL backup** — replication lag → IO saturated.

### Investigation
```sql
-- Lock contention
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query,
       blocking_activity.query AS blocking_query
FROM pg_locks blocked_locks
JOIN pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.granted
JOIN pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

---

## SCENARIO 8 — "Pod CPU at 100%, requests piling up"

### Step 1: Profile
```bash
# Live CPU sampling (no restart)
py-spy top --pid <PID>

# Flame graph
py-spy record -o profile.svg --pid <PID> --duration 60
```

### Step 2: Common Python CPU eaters
- JSON serialization of huge response (use streaming + `orjson`).
- N+1 query + Python-side filtering.
- Regex with catastrophic backtracking.
- Crypto in request path (bcrypt with high cost factor in tight loop).
- ORM lazy-loading + serialization.

### Mitigation
- Scale horizontally (more pods).
- Optimize hot path.
- Move compute to async worker.
- Cache expensive computation.

---

## SCENARIO 9 — "Deploy went out, error rate jumped"

### Step 1: Rollback first, debug second
Production stability > pride. Always have a rollback button.

```bash
# Kubernetes
kubectl rollout undo deployment/api

# GitHub Actions
gh workflow run rollback.yml -f sha=<last-good-sha>
```

### Step 2: After rollback, diagnose
- Diff old vs new code.
- Run failing requests in staging.
- Check release notes for hidden dependencies (e.g., DB migration not run).

### Common deploy disasters
1. **Migration breaking change** — column rename, old pods crash on new column.
2. **Env var missing** — new code expects `NEW_VAR`, deploy didn't set it.
3. **External dep changed** — bumped library version, breaking change.
4. **Cache key format change** — old keys ignored, all miss.
5. **Resource ratio changed** — new code uses more memory, OOM.

### Prevention
- Canary deploys (5% traffic first).
- Pre-deploy DB migration check.
- Schema-compatible migrations (expand-contract).
- Required env var validation at startup.

---

## SCENARIO 10 — "Race condition in production, intermittent data corruption"

### Symptom
- "Sometimes the count is off by 1."
- "Sometimes the user has duplicate records."
- Can't reproduce locally — only under load.

### Debug approach
1. **Find the suspect code path** — what gets corrupted? Trace writers.
2. **Add structured logging** with `request_id` to all writes.
3. **Replay log timeline** for affected records.

### Common races
```python
# ✗ Read-modify-write race
balance = await db.fetch("SELECT balance FROM accounts WHERE id=$1", uid)
await db.execute("UPDATE accounts SET balance=$1 WHERE id=$2", balance + 100, uid)
# Two requests at same time: both read balance=1000, both write 1100. Lost +100.

# ✓ Atomic
await db.execute("UPDATE accounts SET balance = balance + 100 WHERE id=$1", uid)

# ✓ Pessimistic lock
async with db.transaction():
    bal = await db.fetch("SELECT balance FROM accounts WHERE id=$1 FOR UPDATE", uid)
    await db.execute("UPDATE accounts SET balance=$1 WHERE id=$2", bal + 100, uid)

# ✓ Optimistic
WHERE id=$uid AND version=$expected_version
```

### Common race types
- TOCTOU (time-of-check to time-of-use).
- Lost update.
- Phantom write (two inserts pass uniqueness check, then both commit).
- Double-spend (two simultaneous orders for same inventory).

---

## SCENARIO 11 — "Latency spike at exact 5-minute intervals"

### Investigation
- 5 min = stats flush, cron, cache refresh, GC?

### Common culprits
- Prometheus scrape every 60s → 5-min coincidence less common, but check.
- App-level cache refresh cron.
- GC every N minutes.
- Log rotation.
- Connection pool keepalive cycle.

### Detect
```bash
# What runs every 5 min?
crontab -l
systemctl list-timers
```

### Real example
A team had `apscheduler` running a heavy DB stats job every 5 min that took DB locks → latency spike.

---

## SCENARIO 12 — "Service works locally, fails in production"

### Common environment gaps
| Local | Prod | Failure mode |
|---|---|---|
| sqlite | Postgres | SQL syntax differs (`AUTOINCREMENT` vs `BIGSERIAL`) |
| Direct conn | Through PgBouncer | Prepared statements behave differently in transaction mode |
| Fast disk | Networked disk (EFS) | File I/O slow, timeouts |
| Single instance | Multi-instance | In-memory state lost across pods |
| Permissive net | NAT, VPC | Outbound calls blocked |
| No proxy | Behind LB | `request.remote_addr` is LB IP, not user |

### Checklist for "works locally"
- Same Python version? `sys.version`.
- Same dependency versions? `pip freeze`.
- Same env vars? Diff `os.environ`.
- Same DB schema? Run migrations both places.
- Same TZ? Set `TZ=UTC` everywhere.

---

## SCENARIO 13 — "DDOS / sudden traffic spike"

### First 5 minutes
1. **Identify if legitimate or attack:** user behavior vs single IP hammering.
2. **Enable rate limiting** at LB/WAF level.
3. **Scale up** if legit (auto-scale should kick in).
4. **Block obvious bad IPs** via WAF.

### Investigation tools
```bash
# Top IPs hitting your service
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -20

# Top endpoints
awk '{print $7}' access.log | sort | uniq -c | sort -rn | head -20

# User agents
awk -F\" '{print $6}' access.log | sort | uniq -c | sort -rn | head -20
```

### Long-term
- CDN + WAF (Cloudflare, AWS WAF).
- Rate limit per IP, per token, per endpoint.
- CAPTCHA on expensive endpoints.

---

## SCENARIO 14 — "Webhook deliveries failing silently"

### Common patterns
- Receiver rejected with 4xx → no retry.
- Receiver timed out → retried, duplicated.
- Receiver took 30s → producer timed out.

### Debug
```sql
-- Webhook delivery log table
SELECT id, url, status_code, response_time_ms, attempts, last_attempt_at, error
FROM webhook_deliveries
WHERE status = 'failed'
ORDER BY last_attempt_at DESC LIMIT 50;
```

### Best practices
- Persist every webhook attempt with status.
- Exponential backoff: 1, 5, 25, 125, 625 sec...
- Stop retrying on 4xx (client said "no").
- Dead-letter after N retries.
- Signed payloads (HMAC).
- Idempotency key in payload.
- Replay UI for ops team.

---

## SCENARIO 15 — "Replication lag, reads returning stale data"

### Symptom
- User updates name, refreshes, still sees old name.
- Or analytics dashboard 2 hours behind.

### Diagnose
```sql
-- On replica: how far behind primary?
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;

-- On primary: see replication slots
SELECT * FROM pg_replication_slots;
```

### Common causes
1. **Heavy write spike** on primary, replica can't keep up.
2. **Replica under-provisioned** (smaller box, slow disk).
3. **Network bottleneck** between primary/replica.
4. **Long-running transaction on replica** delays apply.

### Mitigation
- Critical reads from primary (read-your-writes).
- Stick session to primary for N seconds after a write.
- Use connection-level routing (PgBouncer + multiple targets).
- Add `synchronous_commit = on` for critical writes (consistency over latency).

---

## INTERVIEW SCRIPT — Telling a debugging story

When asked "tell me about a tough bug":

1. **Context** (10s): "We had a payment service serving 5K RPS, and customers started seeing 'duplicate charge' errors..."
2. **Symptom** (15s): "Roughly 0.1% of orders had two payment_intents created within 100ms."
3. **Investigation** (30s): "I started with the trace_id of the affected orders. Found that the API received two requests with same idempotency_key but our code checked Redis cache then DB — race condition between check and write."
4. **Root cause** (15s): "We assumed idempotency check + insert was atomic, but it wasn't."
5. **Fix** (15s): "Moved the dedup to a unique constraint in DB. Wrapped in transaction. Added test using `asyncio.gather` to simulate concurrent calls."
6. **Outcome** (10s): "Errors dropped to 0. Added monitoring alert for any non-zero rate."

**Total: ~1.5 min.** Long enough to demonstrate depth, short enough to invite follow-ups.

---

## TOOLS CHEAT SHEET

| Tool | Use |
|---|---|
| `kubectl logs -f` + `--tail` | Live log tailing |
| `kubectl exec -it pod -- sh` | Shell into pod |
| `kubectl top pod/node` | Resource usage |
| `py-spy top/dump/record` | Python CPU profiling (live, no restart) |
| `memray` | Python memory profiling |
| `tracemalloc` | Built-in memory tracing |
| `objgraph` | Reference graph analysis |
| `tcpdump`, `wireshark` | Network packet inspection |
| `strace` | Syscall tracing (Linux) |
| `lsof -p PID` | Open file/socket count |
| `htop`, `atop`, `iotop` | System resource monitoring |
| `pg_stat_activity` | Postgres running queries |
| `pg_stat_statements` | Postgres slow query history |
| `EXPLAIN ANALYZE` | Query plan analysis |
| Grafana / Datadog | Metrics dashboards |
| Jaeger / Tempo / X-Ray | Distributed tracing |
| Sentry / Bugsnag | Error tracking |
| `gh run logs` | CI logs |

**Pro move in interview:** "I'd want a flame graph from py-spy and the pg_stat_statements output — that usually narrows it to 2-3 candidates."
