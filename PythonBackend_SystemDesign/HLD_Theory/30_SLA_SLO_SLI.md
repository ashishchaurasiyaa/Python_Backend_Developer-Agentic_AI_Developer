# SLA / SLO / SLI — Service Reliability Metrics

## WHAT

Three terms that define **how reliable a service must be** and how that is measured.

| Term | Full Form | Who it's for | Description |
|---|---|---|---|
| **SLI** | Service Level Indicator | Engineering | What you actually measure (e.g., 99.3% uptime this month) |
| **SLO** | Service Level Objective | Engineering | Internal target (e.g., "we aim for 99.9% uptime") |
| **SLA** | Service Level Agreement | Business / Legal | External promise to customers with financial penalties |

**Hierarchy:**  
`SLI (measured) → SLO (internal goal) → SLA (customer contract)`

---

## SLI — Service Level Indicator

A **quantitative metric** that measures a specific aspect of service quality.

Common SLIs:

| SLI Type | Example Metric |
|---|---|
| Availability | % of successful requests in 30 days |
| Latency | 99th percentile response time ≤ 200ms |
| Error rate | % of 5xx responses out of total requests |
| Throughput | Requests per second processed |
| Saturation | CPU / memory utilization |

```python
# SLI calculation example
def calculate_availability_sli(total_requests: int, successful_requests: int) -> float:
    """Returns availability SLI as a percentage."""
    if total_requests == 0:
        return 100.0
    return (successful_requests / total_requests) * 100

# SLI = 99.91% for the month
sli = calculate_availability_sli(total=1_000_000, successful=999_100)
```

---

## SLO — Service Level Objective

The **internal target** your team commits to hitting. Slightly stricter than SLA.

```
SLO: 99.9% availability per month
  → Allows: 43.8 minutes downtime/month

SLO: p99 latency < 200ms
  → 99% of requests must respond in < 200ms

SLO: Error rate < 0.1%
  → At most 1 in 1000 requests can fail
```

**Error Budget** = `100% - SLO target`
- If SLO = 99.9% → Error budget = 0.1% = 43.8 min/month
- You can use this budget for deployments, experiments
- If budget is exhausted → freeze deployments, focus on reliability

```python
from datetime import timedelta

class SLOTracker:
    def __init__(self, target_percent: float, window_days: int = 30):
        self.target = target_percent                        # e.g., 99.9
        self.window = timedelta(days=window_days)
        self.error_budget_minutes = (100 - target_percent) / 100 * window_days * 24 * 60

    def remaining_budget(self, downtime_minutes: float) -> float:
        return max(0, self.error_budget_minutes - downtime_minutes)

    def budget_consumed_percent(self, downtime_minutes: float) -> float:
        return (downtime_minutes / self.error_budget_minutes) * 100


slo = SLOTracker(target_percent=99.9)
print(f"Monthly error budget: {slo.error_budget_minutes:.1f} minutes")   # 43.8
print(f"After 20min downtime: {slo.remaining_budget(20):.1f} min left")  # 23.8
```

---

## SLA — Service Level Agreement

A **legal/business contract** with customers. Breach → financial penalty (credits, refunds).

| Service | SLA | Penalty if breached |
|---|---|---|
| AWS EC2 | 99.99% monthly | 10–30% credit |
| Google Cloud Run | 99.95% monthly | Up to 50% credit |
| Azure Functions | 99.95% monthly | Service credits |
| GitHub | 99.9% monthly | Pro-rated credits |

**SLA is always looser than SLO:**
```
SLO = 99.95%  ← internal, engineers aim for this
SLA = 99.9%   ← customer promise (buffer for incidents)
```

---

## Nines of Availability

| "Nines" | Availability | Downtime/year | Downtime/month |
|---|---|---|---|
| Two 9s | 99% | 3.65 days | 7.3 hours |
| Three 9s | 99.9% | 8.77 hours | 43.8 min |
| Four 9s | 99.99% | 52.6 min | 4.38 min |
| Five 9s | 99.999% | 5.26 min | 26 sec |

---

## REAL LIFE ANALOGY

**SLI** = Your electricity company's actual uptime meter (99.7% this month)  
**SLO** = Internal target: "We aim for 99.9% uptime"  
**SLA** = Contract to you: "We guarantee 99.5%, else 20% bill discount"

---

## Back-of-Envelope: SLI Calculation

```python
# Monthly availability SLI for LLM API
MONTH_SECONDS = 30 * 24 * 3600      # 2,592,000

# 3 incidents this month:
# - 15 min outage (DB failover)
# - 8 min outage (deploy gone wrong)
# - 22 min partial degradation (counted as 50%)

downtime_seconds = (15 + 8 + 22 * 0.5) * 60  # 1,860 seconds

availability_sli = (1 - downtime_seconds / MONTH_SECONDS) * 100
print(f"SLI: {availability_sli:.4f}%")   # 99.9283%
# SLO (99.9%) met ✓, SLA (99.5%) met ✓
```

---

## Python Backend — SLO Monitoring

```python
import time
from prometheus_client import Counter, Histogram, Gauge

# SLI metrics (exported to Prometheus / Grafana)
REQUEST_COUNT   = Counter("api_requests_total",   "Total API requests", ["status"])
REQUEST_LATENCY = Histogram("api_latency_seconds", "Latency", buckets=[.05,.1,.2,.5,1,2])
ERROR_BUDGET    = Gauge("error_budget_remaining_minutes", "Error budget left this month")

def api_handler(func):
    """Decorator that tracks SLI metrics."""
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            REQUEST_COUNT.labels(status="success").inc()
            return result
        except Exception as exc:
            REQUEST_COUNT.labels(status="error").inc()
            raise
        finally:
            latency = time.perf_counter() - start
            REQUEST_LATENCY.observe(latency)
    return wrapper

@api_handler
def call_llm(prompt: str) -> str:
    # ... real implementation
    return "response"
```

---

## Interview Q&A

**Q: What is an error budget and how do teams use it?**
A: Error budget = 100% - SLO. It's the allowed downtime/errors per period. Teams use it to decide when to do risky deployments. If budget is 80%+ consumed, freeze non-critical changes and focus on reliability.

**Q: What's the difference between SLO and SLA?**
A: SLO is internal (team targets 99.95%). SLA is external (customer contract at 99.9%). SLO is always stricter — the gap is your safety margin for incidents.

**Q: What is a good SLI for an LLM API?**
A: Combination of: (1) availability (% successful requests), (2) latency (p50/p95/p99), (3) token throughput (tokens/sec), (4) error rate. Track separately for streaming vs non-streaming.

**Q: Why is five 9s (99.999%) often overkill?**
A: The cost grows exponentially. Going from 99.9% → 99.99% might require active-active multi-region setup ($$$). Also, your dependencies (DNS, ISP, client network) likely can't guarantee 99.999% themselves.
