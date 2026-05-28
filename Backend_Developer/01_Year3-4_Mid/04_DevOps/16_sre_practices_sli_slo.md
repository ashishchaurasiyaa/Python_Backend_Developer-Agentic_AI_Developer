# DevOps — SRE Practices: SLI, SLO, SLA & Error Budgets
**DevOps · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **SRE** = Site Reliability Engineering — Google's discipline for production
- **SLI** = Service Level Indicator — a measurable metric (e.g., latency, error rate)
- **SLO** = Service Level Objective — internal target (e.g., 99.9% of requests < 300ms)
- **SLA** = Service Level Agreement — contractual commitment with consequences
- **Error budget** = (100% - SLO) — allowable failures in a time window
- **Toil** = repetitive manual work that doesn't add value (automate it)
- **Runbook** = documented procedure for handling alerts/incidents
- **Postmortem** = blameless analysis of incidents
- **MTTR / MTTD / MTBF** = Mean Time To Repair / Detect / Between Failures

---

## The SLI/SLO/SLA Pyramid

```
       ┌─────────────┐
       │     SLA     │  Customer-facing (refunds, penalties)
       │  99.9%      │  ← weakest commitment
       └─────────────┘
       ┌─────────────┐
       │     SLO     │  Internal target (drives eng decisions)
       │  99.95%     │  ← stricter than SLA (buffer)
       └─────────────┘
       ┌─────────────┐
       │     SLI     │  Actual measurement
       │   99.97%    │  ← what's really happening
       └─────────────┘
```

**Rule:** SLI > SLO > SLA. Internal target stricter than customer promise.

---

## "Nines" Cheat Sheet

| Availability | Downtime/year | Downtime/month | Downtime/week | Use case |
|---|---|---|---|---|
| 99% | 3.65 days | 7.3 hr | 1.7 hr | Hobby project |
| 99.9% (3 nines) | 8.76 hr | 43.8 min | 10.1 min | Typical SaaS |
| 99.95% | 4.38 hr | 21.9 min | 5.04 min | Mid-tier B2B |
| 99.99% (4 nines) | 52.6 min | 4.38 min | 1.01 min | Tier-1 SaaS |
| 99.999% (5 nines) | 5.26 min | 26.3 sec | 6 sec | Phone, payments |

**Reality:** Each "9" = 10x harder + cost. Don't promise more than business needs.

---

## Interview Questions & Answers

### Q1: Aap SLI/SLO kaise define karte hain ek API ke liye?

**Answer:** Start with user journey, pick measurable indicators.

```yaml
# Example: Order API SLOs
service: order-service

slos:
  # Latency
  - name: api_latency
    sli: |
      Percentage of GET /orders/* requests served in < 300ms
    objective: 99.5%   # 99.5% must be fast
    window: 30d
    alerting:
      page_at: 99.0%       # burn rate triggers page
      ticket_at: 99.4%

  # Error rate
  - name: api_availability
    sli: |
      Percentage of requests that returned non-5xx
    objective: 99.9%
    window: 30d

  # Throughput
  - name: order_creation_success
    sli: |
      Percentage of POST /orders that successfully created order
    objective: 99.95%   # higher — critical business flow
    window: 30d

  # Freshness (background job)
  - name: order_email_freshness
    sli: |
      Percentage of order emails sent within 60s of order creation
    objective: 95%
    window: 7d
```

**4 Golden Signals** (Google SRE book):
1. **Latency** — how long requests take
2. **Traffic** — RPS / QPS
3. **Errors** — % failed requests
4. **Saturation** — how full your service is (CPU, memory, queue depth)

---

### Q2: SLI metrics ko Prometheus se kaise track karte hain?

**Answer:** Use histograms + recording rules.

```python
# app/middleware/metrics.py
from prometheus_client import Counter, Histogram
import time
from fastapi import Request

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
)

async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    endpoint = request.url.path  # normalize for cardinality (e.g., /orders/{id} → /orders/:id)
    http_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
    ).inc()
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(duration)

    return response
```

**Prometheus recording rules (`rules.yml`):**
```yaml
groups:
- name: sli_recording
  interval: 30s
  rules:
    # SLI 1: Availability (success rate)
    - record: sli:availability:30d
      expr: |
        sum(rate(http_requests_total{status!~"5.."}[30d]))
        /
        sum(rate(http_requests_total[30d]))

    # SLI 2: Latency (% of requests < 300ms)
    - record: sli:latency_p99_fast:30d
      expr: |
        sum(rate(http_request_duration_seconds_bucket{le="0.3"}[30d]))
        /
        sum(rate(http_request_duration_seconds_count[30d]))

    # SLO compliance
    - record: slo:availability:compliance
      expr: sli:availability:30d > 0.999

    # Error budget remaining
    - record: slo:availability:error_budget_remaining
      expr: |
        1 - (
          (1 - sli:availability:30d)
          /
          (1 - 0.999)
        )
```

---

### Q3: Error budget kya hota hai aur kaise use karte hain?

**Answer:** Error budget = how much "bad" you're allowed. Drives release decisions.

**Calculation:**
```
SLO = 99.9% over 30 days
Total minutes = 30 × 24 × 60 = 43,200 min
Error budget = 0.1% × 43,200 = 43.2 min downtime/month

OR for request-based:
SLO = 99.9% success rate
Total requests/month = 100M
Error budget = 100K failed requests
```

**Burn rate alerting** (Google SRE multi-window/multi-burn pattern):
```yaml
groups:
- name: error_budget_burn
  rules:
    # Fast burn: alerts if 14.4× budget consumed in 1 hour
    # (would exhaust 30-day budget in 2 days)
    - alert: HighErrorBudgetBurnFast
      expr: |
        (
          sum(rate(http_requests_total{status=~"5.."}[1h]))
          /
          sum(rate(http_requests_total[1h]))
        ) > 14.4 * 0.001
        AND
        (
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total[5m]))
        ) > 14.4 * 0.001
      for: 2m
      labels:
        severity: page
        slo: availability
      annotations:
        summary: "Fast error budget burn — paging"

    # Slow burn: 6× budget consumed in 6 hours (ticket, not page)
    - alert: ModerateErrorBudgetBurn
      expr: |
        (
          sum(rate(http_requests_total{status=~"5.."}[6h]))
          /
          sum(rate(http_requests_total[6h]))
        ) > 6 * 0.001
      for: 15m
      labels:
        severity: ticket
```

**Burn rate matrix:**
| Burn rate | Time to exhaust | Action |
|---|---|---|
| 14.4× | 2 days | PAGE on-call |
| 6× | 5 days | Ticket / Slack alert |
| 1× | 30 days (normal) | Nothing — within budget |
| < 1× | Saving budget | Ship more features |

---

### Q4: Error budget policy (when to stop shipping)?

**Answer:** Pre-agree consequences before incidents.

```markdown
# Error Budget Policy — Order Service

## SLO
99.9% availability over rolling 30 days
Error budget: 43.2 min downtime / month

## Budget Burn → Action

| Burn % | Status | Action |
|---|---|---|
| 0-50% | Healthy | Normal feature work, deploy freely |
| 50-75% | Caution | Reviews for risky changes; pair-deploy |
| 75-90% | Warning | Feature freeze; only bug fixes + reliability work |
| 90-100% | Critical | Halt all releases except critical fixes; full team focus on reliability |
| > 100% | Breached | Postmortem to leadership; reliability sprint until back in budget |

## Exception Process
- Security patches: always allowed
- P0 customer issues: allowed with PM/Director approval
- Standard deploys above 75%: must include rollback test

## Review Cadence
- Weekly: engineering managers review burn rate
- Quarterly: leadership reviews SLO targets
```

**Why this works:**
- Removes politics from "should we ship?" decisions
- Aligns devs + SREs (shared budget)
- Forces explicit conversation if breached

---

### Q5: Runbook structure (incident response)?

**Answer:** Standard format every team uses.

```markdown
# Runbook: HighErrorBudgetBurnFast Alert

## Severity
🔴 PAGE — on-call must respond within 5 min

## What it means
Error budget is burning 14.4× faster than sustainable rate.
At this rate, 30-day budget will exhaust in 2 days.

## Symptoms to verify
1. Check Grafana: https://grafana.acme.com/d/orders/order-service
2. Confirm error rate > 1% in last 5 min
3. Check recent deploys: `kubectl rollout history deploy/order-service`

## Immediate actions (within 10 min)

### Step 1: Stop the bleeding
- If correlated with recent deploy → **rollback**:
  ```bash
  kubectl rollout undo deploy/order-service -n production
  # Wait 30s
  kubectl rollout status deploy/order-service -n production
  ```
- If no deploy → check upstream services (DB, Redis, payment provider)
  ```bash
  ./scripts/check-deps.sh
  ```

### Step 2: Communicate
- Post in #incident-orders Slack channel
- Update status page: https://status.acme.com/admin → "Investigating"
- Tag @sre-oncall

### Step 3: Triage
- Look at recent logs: `kubectl logs -n production -l app=order-service --tail=200`
- Check Datadog APM for affected endpoints
- Common culprits:
  - DB connection pool exhausted → restart, scale
  - Memory leak → restart pods
  - Downstream API down → enable circuit breaker

## Escalation
- 15 min unresolved → notify EM
- 30 min unresolved → notify Director, declare incident
- Customer impact > $10K/min → declare SEV-1

## After incident
- File postmortem template within 24h
- Add new alerting if gaps found
```

---

### Q6: Postmortem template (blameless)?

**Answer:** Focus on systems, not people.

```markdown
# Postmortem: Order Service Outage on 2026-05-25

## Status: Resolved | Owner: @ashish | Severity: SEV-2

## Summary
Order service returned 5xx for ~30% of requests between 14:32-14:51 UTC
(19 minutes) due to a database connection pool exhaustion triggered by a slow query.

## Impact
- 18,432 failed order creations (~$45K GMV)
- 412 customer support tickets
- SLO error budget consumed: 18% in 19 minutes
- Affected regions: us-east-1 only

## Timeline (all times UTC)
- 14:30 — Deploy of v2.4.1 includes new "recent orders" widget query
- 14:32 — Error rate begins climbing (Datadog alert fires at 14:35)
- 14:35 — On-call @ashish paged
- 14:38 — @ashish acknowledges; opens Grafana
- 14:42 — Identifies DB connection pool saturated; not deploy-related on surface
- 14:45 — Rolls back v2.4.1 → v2.4.0
- 14:51 — Error rate returns to baseline
- 15:30 — Root cause confirmed: missing index on `orders.user_id` + `orders.created_at`

## Root Cause
New widget query: `SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10`
- Missing composite index → seq scan on 50M-row table
- Each query held DB connection for 4-8 seconds
- Pool exhausted in 30 seconds under normal load

## What went well
- Alert fired within 3 min of error spike
- Rollback was clean (no DB migration)
- Status page updated within 5 min

## What went wrong
- Query was not load-tested with production data volume
- No DB query performance review in PR
- Connection pool limit (20) too low for traffic

## Action items
| # | Action | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Add composite index `(user_id, created_at DESC)` | @ashish | 2026-05-26 | ✅ Done |
| 2 | Require EXPLAIN ANALYZE in PRs touching DB | @team-lead | 2026-06-01 | 🟡 In progress |
| 3 | Increase pgbouncer pool size to 100 | @sre | 2026-05-30 | ⬜ Pending |
| 4 | Add slow-query alert (>1s) | @sre | 2026-06-15 | ⬜ Pending |
| 5 | Document deploy checklist with load testing | @docs | 2026-06-15 | ⬜ Pending |

## Lessons learned
- ORM queries can be deceiving — always check EXPLAIN
- Test against production-scale data, not dev fixtures
- Connection pool sizing should account for slow query worst-case

## Blameless statement
This incident was caused by a process gap (no query review), not individual error.
The engineer followed established patterns; we need to evolve those patterns.
```

---

### Q7: Toil identification + reduction?

**Answer:** Track time spent on toil; automate top items.

**What counts as toil:**
- Manual, repetitive
- Reactive (not proactive)
- No lasting value
- Scales linearly with service growth
- E.g., manual deploys, restarting stuck pods, copy-paste alert responses

**SRE rule:** < 50% of time on toil. If > 50%, hire or automate.

```python
# Quarterly toil audit (every engineer)
TOIL_LOG = """
| Week | Task | Time spent | Could automate? |
|---|---|---|---|
| W1 | Restart stuck Celery workers | 4h | ✅ Yes — auto-restart on liveness fail |
| W1 | Copy-paste runbook for "DB lag high" | 1h | ✅ Yes — Slack bot with runbook |
| W2 | Manually clean up old test data | 3h | ✅ Yes — scheduled cleanup job |
| W2 | Approve dependabot PRs | 2h | ✅ Yes — auto-merge minor patches |
"""
```

**Top automation wins:**
1. Auto-rollback on SLO breach (Argo Rollouts)
2. Auto-scale on queue depth (HPA + custom metric)
3. Bot-driven runbook execution (Slackbot triggers playbooks)
4. Synthetic monitoring (Pingdom, Datadog Synthetics)
5. Auto-failover (Route53 health checks)

---

### Q8: SRE org models + on-call rotation?

**Answer:** Three common models.

**Model 1: Embedded SRE**
- 1-2 SREs per product team
- Pros: deep product knowledge
- Cons: silo'd practices

**Model 2: Dedicated SRE team**
- Central SRE team supports all products
- Pros: consistent practices
- Cons: bottleneck

**Model 3: SRE as a Service (Anthropic/Google)**
- SRE team partners temporarily, then hands off
- Pros: scales; transfers knowledge
- Cons: requires mature engineering culture

**On-call best practices:**
```yaml
rotation:
  team: order-service
  schedule: weekly  # 7 days, Monday-Monday
  members: 6  # so each person on-call every 6 weeks
  shifts:
    - 09:00-21:00 (primary)
    - 21:00-09:00 (secondary/follow-the-sun if global)

compensation:
  on_call_pay: ₹500/day  # India market
  incident_bonus: ₹2000 per SEV-1/2 handled

burnout_prevention:
  max_pages_per_week: 2  # if exceeded, investigate root cause
  on_call_free_friday: true  # off-rotation handoff
  noisy_alert_review: weekly
```

**Pager hygiene:**
- Every page must be actionable
- Every page must have a runbook
- If page fires > 2x/week → fix the underlying issue or silence the alert
- Track: time to acknowledge, time to resolve

---

## SLO Examples by Service Type

| Service | SLO 1 | SLO 2 | SLO 3 |
|---|---|---|---|
| **Web API** | 99.9% non-5xx | 95% < 300ms | 99% no timeouts |
| **Background job** | 99% jobs complete | 95% within 5 min | < 1% retried |
| **Search** | 99.9% return results | 95% < 200ms | freshness < 30s |
| **Payment** | 99.99% non-error | 99% < 1s | 100% idempotent |
| **LLM endpoint** | 99% non-error | 95% TTFT < 2s | < 1% timeout |
| **WebSocket** | 99.9% connected | < 1% disconnects/min | < 500ms message latency |

---

## Anti-Patterns

| Don't | Why |
|---|---|
| Set SLO at 100% | Impossible; no error budget for change |
| Pick SLI you can't measure | Useless target |
| Hide SLO breaches from product | Erodes trust + delays fixes |
| Page on every error | Alert fatigue → real pages ignored |
| Skip postmortems for "small" incidents | Patterns missed; same bug recurs |
| Blame individuals | Kills psychological safety |
| Set SLA = SLO | No buffer; one bad month = breach |
| Calendar-month SLO windows | Use rolling 30 days |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| SLI cardinality explodes (per-user metric) | Aggregate; use exemplars for drill-down |
| Errors during deploy spike SLI | Deploy windows; canary; gradual rollout |
| Synthetic check failures false-alert | Use blackbox + real user monitoring (RUM) |
| Burn rate alert too noisy | Multi-window pattern (1h + 5m AND condition) |
| SLO too lenient — never fires | Tighten target; users feel pain we don't |
| Postmortems → blame | Strict blameless culture; train EMs |
| On-call burnout | Smaller rotations; better runbooks; reduce toil |
| Error budget never spent | Ship faster; relax SLO; or it's not measuring user pain |

---

## Senior-level Checklist

- [ ] **SLIs defined** per service (latency, error rate, throughput, freshness)
- [ ] **SLOs published** with rolling 30-day windows
- [ ] **SLAs** (if any) buffered above SLOs
- [ ] **Recording rules** in Prometheus for SLI/SLO
- [ ] **Burn rate alerts** (multi-window pattern)
- [ ] **Error budget policy** documented + agreed by team
- [ ] **Runbooks** linked from every alert
- [ ] **Postmortem template** + blameless culture
- [ ] **Action items** tracked to completion
- [ ] **Quarterly SLO review** with stakeholders
- [ ] **Toil < 50%** measured + reported
- [ ] **On-call** rotation healthy (< 2 pages/week typical)
- [ ] **Synthetic monitoring** for critical user journeys
- [ ] **RUM** (Real User Monitoring) for latency from users' perspective
- [ ] **Status page** updated automatically on SLO breach

---

## Related Docs
- `05_prometheus_grafana.md` — metrics foundation
- `08_elk_loki_logging.md` — logs for incident response
- `13_gitops_argocd_flux.md` — safe deploys
- `14_chaos_engineering.md` — practice failure handling
- `15_multi_region_deployment.md` — availability across regions
- `01_Year3-4_Mid/02_API_Design/13_api_monitoring_slo.md` — API-level SLOs

## External References
- Google SRE Book: https://sre.google/sre-book/
- Google SRE Workbook: https://sre.google/workbook/
- Implementing SLOs (free O'Reilly): https://www.oreilly.com/library/view/implementing-service-level/9781492076803/
- Sloth (SLO generator): https://sloth.dev
