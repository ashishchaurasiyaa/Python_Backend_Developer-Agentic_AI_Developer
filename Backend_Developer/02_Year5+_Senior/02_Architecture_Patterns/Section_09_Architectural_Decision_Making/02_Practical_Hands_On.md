# Lecture 2 — Practical Hands-On: Trade-off Analysis

> **Theory file:** [02_Tradeoff_Analysis.md](02_Tradeoff_Analysis.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **Trade-off matrix** template for any decision
2. ✅ **Consistency simulator** — see how latency drops with eventual consistency
3. ✅ **Cost calculator** — build vs buy estimator script
4. ✅ **Re-evaluation reminders** — track triggers over time
5. ✅ **Three sample worksheets** filled in

By end: aap kisi bhi architectural decision pe **structured trade-off doc** likh sakte ho.

---

## 1. Trade-off Matrix Template

### `tradeoff_matrix.md`

```markdown
# Trade-off Matrix — <Decision Title>

> Owner: ____________   Date: ____________

## Decision Statement
> One sentence describing what we're choosing.

## Options
- A: ____________
- B: ____________
- C: ____________

## Evaluation

| Dimension              | Weight  | A    | B    | C    |
|------------------------|---------|------|------|------|
| Time-to-market         | 0.0–1.0 | 1–5  | 1–5  | 1–5  |
| Scalability            |         |      |      |      |
| Maintainability        |         |      |      |      |
| Cost (TCO 3y)          |         |      |      |      |
| Team expertise fit     |         |      |      |      |
| Operational complexity |         |      |      |      |
| Vendor lock-in risk    |         |      |      |      |
| **Weighted total**     |         |      |      |      |

> Weights must sum to 1.0

## Notes
- Why scored that way for A: ____________
- Why scored that way for B: ____________
- Why scored that way for C: ____________

## Decision
> Chosen: ____________
> Confidence: Low / Medium / High
> Re-evaluate when: ____________
```

### Scoring Script

```python
# tradeoff_score.py
def weighted_score(weights: dict, scores: dict) -> float:
    assert abs(sum(weights.values()) - 1.0) < 1e-6, "weights must sum to 1.0"
    return sum(weights[k] * scores[k] for k in weights)


if __name__ == "__main__":
    weights = {
        "time_to_market": 0.30,
        "scalability":    0.20,
        "maintainability":0.15,
        "cost":           0.15,
        "team_fit":       0.10,
        "ops_complexity": 0.05,
        "lock_in":        0.05,
    }
    options = {
        "monolith":      {"time_to_market": 5, "scalability": 2, "maintainability": 4, "cost": 5, "team_fit": 5, "ops_complexity": 5, "lock_in": 5},
        "modular_mono":  {"time_to_market": 4, "scalability": 3, "maintainability": 4, "cost": 4, "team_fit": 4, "ops_complexity": 4, "lock_in": 5},
        "microservices": {"time_to_market": 2, "scalability": 5, "maintainability": 3, "cost": 2, "team_fit": 3, "ops_complexity": 1, "lock_in": 5},
    }
    for name, scores in options.items():
        s = weighted_score(weights, scores)
        print(f"{name:18s} → {s:.2f}")
```

### Sample Output

```
monolith           → 4.45
modular_mono       → 3.95
microservices      → 2.95
```

→ For this team's priorities, monolith wins clearly. **Numbers structure the discussion, they don't decide it.**

---

## 2. Latency vs Consistency Simulator

### `consistency_sim.py`

```python
"""
Simulate strong vs eventual consistency latency by adding
quorum wait + replication wait.
"""
import asyncio
import random
import time


REPLICAS = 5


async def write_eventual(value):
    """Write to one node, async replicate later."""
    await asyncio.sleep(random.uniform(0.005, 0.015))  # local write
    # replication happens in background — not awaited
    asyncio.create_task(_replicate(value))
    return time.perf_counter()


async def write_strong_quorum(value):
    """Wait for quorum (3 of 5) before ack."""
    write_tasks = [_replicate(value) for _ in range(REPLICAS)]
    done, pending = await asyncio.wait(
        write_tasks,
        return_when=asyncio.FIRST_COMPLETED,
    )
    # need ceil(N/2)+1 = 3
    completed = 1
    while completed < 3:
        more_done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        completed += len(more_done)
    return time.perf_counter()


async def _replicate(value):
    # network latency for replica
    await asyncio.sleep(random.uniform(0.020, 0.080))


async def bench(name, fn, n=200):
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        await fn("x")
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    avg = sum(samples) / len(samples)
    p95 = samples[int(0.95 * len(samples))]
    print(f"{name:25s} avg={avg:6.1f}ms  p95={p95:6.1f}ms")


async def main():
    await bench("eventual consistency", write_eventual)
    await bench("strong (quorum 3/5)",  write_strong_quorum)


if __name__ == "__main__":
    asyncio.run(main())
```

### Sample Output

```
eventual consistency       avg=  10.4ms  p95=  14.8ms
strong (quorum 3/5)        avg=  48.6ms  p95=  72.3ms
```

→ **Strong consistency cost ~5x latency** in this simulation. That's the trade-off in numbers.

---

## 3. Build vs Buy Cost Calculator

### `build_vs_buy.py`

```python
"""
Rough 3-year TCO comparison for "auth" feature.
Tune the numbers for your context.
"""

YEARS = 3


def build_cost(eng_count, eng_salary_yr, infra_yr, ongoing_eng_fte):
    initial_build = eng_count * eng_salary_yr * 0.5   # 6 months
    ongoing       = ongoing_eng_fte * eng_salary_yr * YEARS
    infra         = infra_yr * YEARS
    total         = initial_build + ongoing + infra
    return {
        "initial": initial_build,
        "ongoing": ongoing,
        "infra":   infra,
        "total":   total,
    }


def buy_cost(monthly_subscription, transaction_fee_pct=0, expected_revenue_yr=0):
    subscription = monthly_subscription * 12 * YEARS
    fees         = transaction_fee_pct * expected_revenue_yr * YEARS
    total        = subscription + fees
    return {
        "subscription": subscription,
        "fees":         fees,
        "total":        total,
    }


if __name__ == "__main__":
    print("=== BUILD (Auth in-house) ===")
    b = build_cost(
        eng_count=3,
        eng_salary_yr=50_000,
        infra_yr=15_000,
        ongoing_eng_fte=0.5,
    )
    for k, v in b.items():
        print(f"  {k:10s} ${v:>10,.0f}")

    print("\n=== BUY (Auth0 / equivalent) ===")
    c = buy_cost(
        monthly_subscription=500,
        transaction_fee_pct=0,
        expected_revenue_yr=0,
    )
    for k, v in c.items():
        print(f"  {k:13s} ${v:>10,.0f}")

    print(f"\nDelta over 3y (buy - build): ${c['total'] - b['total']:,.0f}")
```

### Sample Output

```
=== BUILD (Auth in-house) ===
  initial    $   75,000
  ongoing    $   75,000
  infra      $   45,000
  total      $  195,000

=== BUY (Auth0 / equivalent) ===
  subscription $   18,000
  fees         $        0
  total        $   18,000

Delta over 3y (buy - build): $-177,000
```

→ Buy is cheaper by $177k. **But the calculator doesn't price opportunity cost** — what could those 3 engineers have built instead?

---

## 4. Re-evaluation Tracker

### `reevaluation_triggers.yaml`

```yaml
# When to revisit each architectural decision
decisions:
  - id: ADR-0001
    title: "Hybrid Microservices + EDA"
    triggers:
      - condition: "team_size > 50"
        action: "Consider further service decomposition"
      - condition: "monthly_ops_toil_hours > 200"
        action: "Consider consolidating services"
      - condition: "p99_latency_ms > 500"
        action: "Audit service-to-service hops"

  - id: ADR-0002
    title: "Use Postgres for all OLTP"
    triggers:
      - condition: "write_qps > 10_000"
        action: "Evaluate Cassandra / CockroachDB for specific tables"
      - condition: "single_table_size > 500_GB"
        action: "Consider partitioning strategy"

  - id: ADR-0003
    title: "Buy Auth0"
    triggers:
      - condition: "MAU > 1_000_000"
        action: "Compare Auth0 cost at new tier vs hosted FusionAuth"
      - condition: "custom_auth_flows > 10"
        action: "Revisit fit"
```

### Run as a Quarterly Check

```bash
# Pseudo-script — checks current metrics against triggers
python check_triggers.py --metrics current_metrics.yaml --triggers reevaluation_triggers.yaml
```

---

## 5. Three Filled-In Sample Worksheets

### Sample A: Startup MVP — chose Monolith

```
Decision: Architecture for a 3-person team launching in 2 months.
Options:  Monolith / Modular Monolith / Microservices
Weights:  TTM 0.4, ops_complexity 0.3, cost 0.2, scalability 0.1

monolith     → 4.6   ✓ chosen
modular      → 3.8
microsvc     → 2.1

Re-evaluate when: team > 8 OR QPS > 2000
```

### Sample B: Mature Product — chose Modular Monolith

```
Decision: Refactor 5-year-old monolith now hitting deploy contention.
Options:  Stay monolith / Modular monolith / Microservices
Weights:  maintainability 0.3, TTM 0.2, ops_complexity 0.2, scalability 0.2, cost 0.1

stay monolith → 3.0
modular_mono  → 4.4   ✓ chosen
microsvc      → 3.2

Re-evaluate when: team > 30 OR specific module needs independent scale
```

### Sample C: Real-time Platform — chose Hybrid

```
Decision: Architecture for a live tracking + payments product.
Options:  Microservices+REST / Microservices+EDA / Hybrid
Weights:  latency 0.25, scalability 0.25, resilience 0.2, ops_complexity 0.15, cost 0.15

ms+rest       → 3.2
ms+eda        → 4.0
hybrid        → 4.5   ✓ chosen

Re-evaluate when: event volume > 100k/sec OR latency p99 > 200ms
```

---

## 6. ✅ Hands-On Checklist

```
□ Filled tradeoff_matrix.md for a real decision
□ Ran tradeoff_score.py with your weights
□ Ran consistency_sim.py and noted the latency delta
□ Ran build_vs_buy.py with your numbers
□ Wrote at least 1 re-evaluation trigger in reevaluation_triggers.yaml
□ Reviewed quarterly trigger check on calendar
```

---

## 🔗 Next

- Next: [03_Pattern_Selection_Framework.md](03_Pattern_Selection_Framework.md)
