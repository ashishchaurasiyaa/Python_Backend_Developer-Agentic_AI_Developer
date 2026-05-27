# Lecture 3 — Practical Hands-On: Pattern Selection Frameworks

> **Theory file:** [03_Pattern_Selection_Framework.md](03_Pattern_Selection_Framework.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **Decision tree** as code (Python function)
2. ✅ **Architecture review checklist** in Markdown
3. ✅ **Scoring model** spreadsheet + Python
4. ✅ **Constraint matrix** Python tool
5. ✅ **End-to-end pipeline** — matrix → score → checklist for one decision

By end: aap ke paas **4 reusable tools** honge har architecture decision ke liye.

---

## 1. Decision Tree as Code

### `decision_tree.py`

```python
"""
Encode a recurring decision: "What communication style for this service?"
"""

def choose_comm_style(realtime: bool,
                       sync_required: bool,
                       expected_consumers: int) -> str:
    if realtime:
        return "Event-driven (WebSocket or Kafka)"

    if sync_required:
        if expected_consumers > 5:
            return "GraphQL gateway in front of REST"
        return "REST/gRPC"

    return "Async REST + message queue"


if __name__ == "__main__":
    cases = [
        {"realtime": True, "sync_required": False, "expected_consumers": 1},
        {"realtime": False, "sync_required": True, "expected_consumers": 2},
        {"realtime": False, "sync_required": True, "expected_consumers": 10},
        {"realtime": False, "sync_required": False, "expected_consumers": 1},
    ]
    for c in cases:
        print(f"{c}  →  {choose_comm_style(**c)}")
```

### Sample Output

```
{'realtime': True, ...}  →  Event-driven (WebSocket or Kafka)
{'realtime': False, 'sync_required': True, 'expected_consumers': 2}   →  REST/gRPC
{'realtime': False, 'sync_required': True, 'expected_consumers': 10}  →  GraphQL gateway in front of REST
{'realtime': False, 'sync_required': False, ...}  →  Async REST + message queue
```

---

## 2. Architecture Review Checklist

### `arch_review_checklist.md`

```markdown
# Architecture Review Checklist

> Use this BEFORE merging any architecture change.

## Scale + Performance
- [ ] Expected QPS documented (current, year 1, year 3)
- [ ] Latency SLOs defined (p50, p95, p99)
- [ ] Load test results attached or plan documented
- [ ] Capacity headroom — at least 2x current peak

## Failure Modes
- [ ] Single points of failure identified
- [ ] Behavior under partial outage documented
- [ ] Circuit breakers / timeouts / retries specified
- [ ] Graceful degradation strategy

## Data
- [ ] Schema migration plan (expand/contract)
- [ ] Backup + restore tested
- [ ] Data retention policy
- [ ] PII / secrets handling

## Security
- [ ] AuthN + AuthZ documented
- [ ] Threat model (or STRIDE) referenced
- [ ] Secrets in vault, not in code/env files
- [ ] TLS everywhere; mTLS for service-to-service

## Observability
- [ ] Structured logs with correlation IDs
- [ ] Metrics: RED (rate, errors, duration) + USE (utilization, saturation, errors)
- [ ] Distributed tracing
- [ ] Alerts on SLO violations

## Operability
- [ ] Runbook for top 3 incidents
- [ ] On-call coverage agreed
- [ ] Deploy / rollback strategy
- [ ] Feature flags for risky changes

## Cost
- [ ] Estimated infra cost (month / year)
- [ ] Cost growth model with scale

## Compliance
- [ ] PII inventory
- [ ] Audit log requirements
- [ ] Regulation list (DPDP, GDPR, PCI, ...) checked

## Team
- [ ] Team has skills to operate this
- [ ] Bus factor ≥ 2 on critical components
- [ ] Documentation for new joiners

## Reversibility
- [ ] Decision can be reversed if wrong
- [ ] Re-evaluation triggers defined in ADR
```

---

## 3. Scoring Model

### `scoring_model.py`

```python
"""
Generic weighted scoring model for architecture decisions.
"""
from dataclasses import dataclass, field


@dataclass
class Option:
    name: str
    scores: dict   # factor → 1–5
    notes: str = ""


@dataclass
class ScoringModel:
    name: str
    weights: dict             # factor → weight (sum = 1.0)
    options: list[Option] = field(default_factory=list)

    def validate(self):
        total = sum(self.weights.values())
        assert abs(total - 1.0) < 1e-6, f"weights sum to {total}, not 1.0"
        for opt in self.options:
            missing = set(self.weights) - set(opt.scores)
            assert not missing, f"{opt.name} missing scores for {missing}"

    def score(self, option: Option) -> float:
        return sum(self.weights[k] * option.scores[k] for k in self.weights)

    def rank(self) -> list[tuple[Option, float]]:
        self.validate()
        return sorted(
            ((o, self.score(o)) for o in self.options),
            key=lambda x: x[1],
            reverse=True,
        )

    def report(self):
        print(f"\n=== {self.name} ===\n")
        ranked = self.rank()
        print(f"{'Option':<25s}{'Score':>8s}")
        print("─" * 33)
        for opt, sc in ranked:
            print(f"{opt.name:<25s}{sc:>8.2f}")
        print()


if __name__ == "__main__":
    model = ScoringModel(
        name="API Style Selection",
        weights={
            "latency":         0.25,
            "tooling_support": 0.20,
            "team_familiarity":0.20,
            "ecosystem":       0.15,
            "evolvability":    0.10,
            "cost":            0.10,
        },
        options=[
            Option("REST",     {"latency": 4, "tooling_support": 5, "team_familiarity": 5, "ecosystem": 5, "evolvability": 3, "cost": 5}),
            Option("GraphQL",  {"latency": 3, "tooling_support": 4, "team_familiarity": 3, "ecosystem": 4, "evolvability": 5, "cost": 4}),
            Option("gRPC",     {"latency": 5, "tooling_support": 4, "team_familiarity": 2, "ecosystem": 3, "evolvability": 4, "cost": 4}),
        ],
    )
    model.report()
```

### Sample Output

```
=== API Style Selection ===

Option                      Score
─────────────────────────────────
REST                         4.40
GraphQL                      3.75
gRPC                         3.65
```

---

## 4. Constraint Matrix

### `constraint_matrix.py`

```python
"""
Eliminate non-viable options against hard constraints.
"""


def check(option: dict, constraints: dict) -> tuple[bool, list[str]]:
    """Returns (viable?, list of failed constraints)."""
    failures = []
    for ckey, cfn in constraints.items():
        if not cfn(option.get(ckey)):
            failures.append(ckey)
    return (not failures, failures)


if __name__ == "__main__":
    options = [
        {"name": "Monolith",      "p99_latency": 80,  "compliance": True,  "team_min": 2,  "monthly_cost": 5_000},
        {"name": "Microservices", "p99_latency": 60,  "compliance": True,  "team_min": 12, "monthly_cost": 25_000},
        {"name": "Serverless",    "p99_latency": 600, "compliance": True,  "team_min": 2,  "monthly_cost": 3_000},
        {"name": "SaaS",          "p99_latency": 90,  "compliance": False, "team_min": 1,  "monthly_cost": 8_000},
    ]
    constraints = {
        "p99_latency":  lambda v: v is not None and v <= 100,
        "compliance":   lambda v: v is True,
        "team_min":     lambda v: v is not None and v <= 8,
        "monthly_cost": lambda v: v is not None and v <= 10_000,
    }

    print(f"{'Option':<15s}  Viable?  Failed Constraints")
    print("─" * 55)
    for opt in options:
        viable, fails = check(opt, constraints)
        mark = "✓" if viable else "✗"
        print(f"{opt['name']:<15s}  {mark}        {fails or '—'}")
```

### Sample Output

```
Option           Viable?  Failed Constraints
───────────────────────────────────────────────────────
Monolith         ✓        —
Microservices    ✗        ['team_min', 'monthly_cost']
Serverless       ✗        ['p99_latency']
SaaS             ✗        ['compliance']
```

→ **Monolith is the only viable option** given these constraints.

---

## 5. End-to-End Pipeline

### `decision_pipeline.py`

```python
"""
Full pipeline: Constraint Matrix → Scoring Model → Checklist reminder.
"""
from constraint_matrix import check
from scoring_model import ScoringModel, Option


def pipeline(options_with_metrics, hard_constraints, scoring_weights, scoring_factors):
    # Step 1: constraint filter
    print("\n=== Step 1: Constraint Matrix ===")
    viable = []
    for opt in options_with_metrics:
        is_viable, fails = check(opt, hard_constraints)
        mark = "✓" if is_viable else "✗"
        print(f"  {mark} {opt['name']:<15s} fails: {fails or '—'}")
        if is_viable:
            viable.append(opt)

    if not viable:
        print("⚠ No viable options! Loosen constraints or rethink.")
        return None
    if len(viable) == 1:
        print(f"\n→ Only one viable option: {viable[0]['name']}")
        return viable[0]["name"]

    # Step 2: scoring
    print("\n=== Step 2: Scoring Model ===")
    model = ScoringModel(
        name="Viable options ranked",
        weights=scoring_weights,
        options=[Option(o["name"], scoring_factors[o["name"]]) for o in viable],
    )
    model.report()
    winner = model.rank()[0][0].name

    # Step 3: checklist reminder
    print("=== Step 3: Don't Forget the Checklist ===")
    print(f"  → Before locking in '{winner}', walk through")
    print(f"    arch_review_checklist.md with the team.")
    return winner


if __name__ == "__main__":
    options = [
        {"name": "Monolith",      "p99_latency": 80,  "compliance": True, "team_min": 2,  "monthly_cost": 5_000},
        {"name": "Modular Mono",  "p99_latency": 80,  "compliance": True, "team_min": 4,  "monthly_cost": 6_000},
        {"name": "Microservices", "p99_latency": 60,  "compliance": True, "team_min": 12, "monthly_cost": 25_000},
    ]
    constraints = {
        "p99_latency":  lambda v: v <= 100,
        "compliance":   lambda v: v is True,
        "team_min":     lambda v: v <= 8,
        "monthly_cost": lambda v: v <= 10_000,
    }
    weights = {
        "scalability":     0.25,
        "maintainability": 0.25,
        "ttm":             0.20,
        "cost":            0.15,
        "ops_complexity":  0.15,
    }
    factors = {
        "Monolith":     {"scalability": 2, "maintainability": 3, "ttm": 5, "cost": 5, "ops_complexity": 5},
        "Modular Mono": {"scalability": 4, "maintainability": 5, "ttm": 4, "cost": 4, "ops_complexity": 4},
    }
    pipeline(options, constraints, weights, factors)
```

### Sample Output

```
=== Step 1: Constraint Matrix ===
  ✓ Monolith        fails: —
  ✓ Modular Mono    fails: —
  ✗ Microservices   fails: ['team_min', 'monthly_cost']

=== Step 2: Scoring Model ===

=== Viable options ranked ===

Option                      Score
─────────────────────────────────
Modular Mono                 4.20
Monolith                     3.85

=== Step 3: Don't Forget the Checklist ===
  → Before locking in 'Modular Mono', walk through
    arch_review_checklist.md with the team.
```

---

## 6. ✅ Hands-On Checklist

```
□ Encoded one recurring team decision as a decision tree
□ Adopted (and shortened) arch_review_checklist.md
□ Ran scoring_model.py on a real comparison
□ Ran constraint_matrix.py to eliminate non-viable options
□ Wired all three together in decision_pipeline.py
□ Refined weights with team alignment
```

---

## 🔗 Next

- Next: [04_Architecture_AntiPatterns.md](04_Architecture_AntiPatterns.md)
