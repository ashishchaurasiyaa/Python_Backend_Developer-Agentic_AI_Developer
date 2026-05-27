# Lecture 4 — Practical Hands-On: Architect's Toolkit

> **Theory file:** [04_Roles_Responsibilities_Software_Architect.md](04_Roles_Responsibilities_Software_Architect.md)

---

## 🎯 Is Practical Mein Kya Karenge?

1. **Design Review Checklist** — ek complete template
2. **7 Real ADR Examples** (production-grade)
3. **Architecture Fitness Functions** — Python code
4. **Stakeholder Communication Scripts**
5. **Architecture Governance Templates**
6. **Architect's Day-1 Onboarding Plan**
7. **Trade-off Analysis Framework**

---

## 1. Design Review Checklist

> **Reviewer ki cheat sheet** — design review meetings mein use karein.

```markdown
# Architecture Design Review Checklist

**Reviewer:** _______________   **Date:** _______
**Reviewing:** Service / Feature: _______________
**PR/Doc Link:** _______

## 1. Requirements
- [ ] Functional requirements clearly stated?
- [ ] Non-functional requirements (ASRs) defined?
- [ ] Success metrics specified?
- [ ] Constraints documented?

## 2. System Design
- [ ] Architecture diagram present (C4 Level 2 minimum)?
- [ ] Components have clear single responsibility?
- [ ] No circular dependencies?
- [ ] Communication patterns sensible (sync vs async)?
- [ ] Failure modes considered?

## 3. Data
- [ ] Schema reviewed?
- [ ] Indexing strategy?
- [ ] Migration path defined?
- [ ] Backup + recovery plan?
- [ ] Data retention policy?

## 4. Scalability
- [ ] Bottleneck analysis done?
- [ ] Horizontal scaling supported?
- [ ] Stateless where possible?
- [ ] Caching strategy?
- [ ] Database sharding plan (if needed)?

## 5. Performance
- [ ] Latency targets defined (p50/p95/p99)?
- [ ] Throughput requirements clear?
- [ ] Connection pooling configured?
- [ ] Async processing where beneficial?

## 6. Availability
- [ ] Redundancy at each tier?
- [ ] Failover strategy?
- [ ] Circuit breakers on external calls?
- [ ] Retry logic with backoff?
- [ ] Health checks defined?

## 7. Security
- [ ] Auth + authz designed?
- [ ] Input validation?
- [ ] Output sanitization?
- [ ] Encryption (at rest + in transit)?
- [ ] Secret management (no hardcoded)?
- [ ] OWASP Top 10 mitigated?
- [ ] Audit logging?

## 8. Observability
- [ ] Structured logging?
- [ ] Metrics (RED method)?
- [ ] Distributed tracing?
- [ ] Alerting rules?
- [ ] Dashboards planned?

## 9. Operability
- [ ] Deployment strategy (canary/blue-green/rolling)?
- [ ] Rollback plan?
- [ ] Feature flags?
- [ ] CI/CD pipeline?
- [ ] Runbooks for common scenarios?

## 10. Documentation
- [ ] ADR(s) for major decisions?
- [ ] API documentation (OpenAPI/AsyncAPI)?
- [ ] README explains how to run locally?
- [ ] Architecture diagrams up to date?

## 11. Testing
- [ ] Unit tests planned?
- [ ] Integration tests?
- [ ] E2E tests for critical paths?
- [ ] Load testing strategy?
- [ ] Security testing (SAST/DAST)?

## 12. Compliance & Governance
- [ ] Data residency requirements (DPDP/GDPR)?
- [ ] Audit logging for sensitive ops?
- [ ] PII handling reviewed?
- [ ] Tech stack approved?

## Reviewer's Verdict
- [ ] ✅ Approved — proceed
- [ ] ⚠️ Approved with changes — minor revisions needed
- [ ] ❌ Rejected — major rework needed

## Comments
________________________________________

## Follow-up Actions
1. ________________________________________
2. ________________________________________
```

---

## 2. 7 Real ADR Examples (Production-Grade)

### ADR-001: Choose PostgreSQL Over MongoDB

```markdown
# ADR-001: Use PostgreSQL Instead of MongoDB for Primary Data Store

## Status
Accepted

## Date
2026-05-20

## Participants
- Ashish (Architect)
- Priya (DBA)
- Rajesh (Engineering Manager)
- Suresh (Backend Tech Lead)

## Context

We're building a multi-tenant SaaS platform. Primary entities include:
- Tenants (organizations)
- Users (employees of tenants)
- Subscriptions (billing)
- Audit logs (compliance)

Expected scale:
- 1000 tenants × 100 users = 100K users
- 1B audit log entries/year
- 50M order/transaction rows/year

Requirements:
- ACID transactions critical (financial integrity)
- Complex queries across entities (JOINs)
- Strong consistency for billing
- Team has 5+ years PostgreSQL experience
- India + EU operations (data residency)

## Decision

**We will use PostgreSQL 16 as our primary database.**

Deployment:
- AWS RDS PostgreSQL 16 Multi-AZ
- ap-south-1 (Mumbai) for Indian data
- eu-west-1 (Ireland) for EU data
- Read replicas for analytics queries

## Alternatives Considered

1. **MongoDB**
   - ✓ Schema flexibility, document model
   - ✗ Weaker ACID guarantees
   - ✗ Complex transactions in 4.x (we use 5+ feature support)
   - ✗ Team would need ramp-up time
   - **Rejected**

2. **DynamoDB**
   - ✓ Massively scalable
   - ✓ Managed by AWS
   - ✗ Vendor lock-in
   - ✗ Limited query patterns (no JOINs)
   - ✗ Expensive for our workload
   - **Rejected**

3. **CockroachDB**
   - ✓ PostgreSQL-compatible
   - ✓ Globally distributed
   - ✗ Operationally complex
   - ✗ Higher hosting cost
   - ✗ Smaller ecosystem
   - **Rejected**

## Consequences

### Positive
+ ACID guarantees for critical financial data
+ Mature ecosystem (Alembic, SQLAlchemy, asyncpg)
+ Team expertise → faster development
+ Easy local dev (one Docker image)
+ Rich query language (JOINs, CTEs, window functions)
+ pgvector for AI/ML features (future)

### Negative
- Vertical scaling limits (~50TB single instance)
- Need to plan sharding strategy for 10x growth
- Cross-region writes have latency

### Risks & Mitigations
- **Risk**: Single instance can't handle 10M users
  - **Mitigation**: Use Citus/pg_partman for horizontal scaling

- **Risk**: Long-running migrations affect availability
  - **Mitigation**: Online migrations with pgroll or planned downtime windows

### Follow-up
- Plan sharding strategy in 6 months
- Train team on Patroni for HA
- Set up monitoring (Prometheus exporter)
```

### ADR-002: Use JWT Over Session-Based Auth

```markdown
# ADR-002: Use JWT for User Authentication

## Status
Accepted

## Date
2026-05-22

## Context

Need authentication mechanism for:
- Web app (React)
- Mobile apps (iOS, Android)
- 3rd party API integrations
- Internal service-to-service calls

Constraints:
- Stateless services (Kubernetes auto-scaling)
- Multi-region (low latency for token validation)
- Mobile-first (limited cookie support)
- 100K concurrent users

## Decision

Use **JWT (JSON Web Tokens)** for authentication with:
- Asymmetric signing (RS256)
- 15-min access token expiry
- 7-day refresh token
- Refresh tokens in HTTP-only secure cookies
- Public key cached in services for validation
- Centralized revocation list in Redis

## Alternatives Considered

1. **Session-based (cookies + Redis)**
   - ✓ Easy revocation
   - ✗ Stateful — every service must hit Redis
   - ✗ Cookie issues on mobile
   - ✗ Cross-domain complications
   - **Rejected**

2. **OAuth 2.0 with external provider**
   - ✓ Industry standard
   - ✓ Enterprise SSO
   - ✗ External dependency
   - ✗ Overkill for our needs initially
   - **Deferred to Phase 2**

## Consequences

### Positive
+ Stateless services (scales horizontally)
+ Mobile-friendly
+ Standard format (works with API gateways)
+ Self-contained (claims in token)

### Negative
- Token revocation needs additional infrastructure
- Larger payload than session ID (~1KB vs 32 bytes)
- Need secret rotation strategy

### Mitigations
- Revocation: Redis-based blacklist for compromised tokens
- Size: Use compression on mobile clients
- Rotation: Quarterly key rotation with overlap window
```

### ADR-003: Adopt Kafka for Event Streaming

```markdown
# ADR-003: Use Apache Kafka for Event Streaming

## Status
Accepted

## Date
2026-05-25

## Context

Need event-driven communication between microservices for:
- Order events (created, shipped, delivered)
- User events (signup, login, logout)
- Notifications (multi-channel: email, SMS, push)
- Analytics ingestion (1B events/day projected)
- Audit logging

## Decision

Use **Apache Kafka** (managed via Confluent Cloud) for:
- High-volume event streaming
- Async service-to-service communication
- Event sourcing for critical entities

Topics:
- `orders.*` — order lifecycle
- `users.*` — user events
- `notifications.*` — outbound messages
- `audit.*` — compliance logs

## Alternatives Considered

1. **RabbitMQ**
   - ✓ Easier to operate
   - ✓ Good for task queues
   - ✗ Lower throughput at scale
   - ✗ Less suited for event replay
   - **Rejected for high-volume**

2. **AWS SQS + SNS**
   - ✓ Managed service
   - ✓ Cheap at low scale
   - ✗ No replay capability
   - ✗ Vendor lock-in
   - ✗ Limited fanout patterns
   - **Rejected**

3. **Redis Streams**
   - ✓ Already using Redis
   - ✗ Not designed for billions of events
   - ✗ Limited tooling
   - **Rejected**

## Consequences

### Positive
+ Massive throughput (millions/sec)
+ Event replay for debugging
+ Decouples services
+ Strong ordering per partition

### Negative
- Operational complexity (managed via Confluent to mitigate)
- Higher cost vs simple queue
- Learning curve for team

### Decisions Locked In
- Confluent Cloud (managed service)
- ksqlDB for stream processing
- Schema Registry for Avro events
- ACLs per topic
```

### ADR-004: Multi-Region Active-Passive Deployment

```markdown
# ADR-004: Multi-Region Active-Passive Deployment

## Status
Accepted

## Date
2026-05-26

## Context

Customer base spans India, EU, and US. Requirements:
- 99.95% availability (22 min downtime budget/month)
- GDPR compliance (EU data in EU)
- India DPDP compliance (Indian data in India)
- Disaster recovery from regional outage

## Decision

**Active-passive multi-region deployment:**

Primary regions:
- `ap-south-1` (Mumbai) — Indian users, primary
- `eu-west-1` (Ireland) — EU users, primary
- `us-east-1` (Virginia) — US users + global passive failover

Architecture:
- Each region has full stack (services + DB)
- Cross-region replication (async, ~1s lag)
- Route53 latency-based routing → user → nearest region
- Health checks → automatic failover

## Alternatives Considered

1. **Single region (Mumbai only)**
   - ✗ High latency for EU/US users
   - ✗ Regional outage = full downtime
   - **Rejected**

2. **Active-active multi-region**
   - ✓ Better disaster recovery
   - ✓ Lower latency globally
   - ✗ Complex conflict resolution
   - ✗ 2x infrastructure cost
   - **Deferred (revisit when ARR > $10M)**

3. **CDN + single backend**
   - ✓ Cheap
   - ✗ Doesn't address regional data residency
   - ✗ Single backend = SPOF
   - **Rejected**

## Consequences

### Positive
+ Compliance with GDPR + DPDP
+ Sub-100ms latency for users in each region
+ Survive regional outage

### Negative
- 1.5x infrastructure cost vs single region
- Cross-region data sync complexity
- Failover testing requires drills

### Tools
- Terraform modules for each region
- ArgoCD for GitOps deployment
- Datadog for cross-region monitoring
```

### ADR-005: Microservices Boundaries via DDD

```markdown
# ADR-005: Define Microservice Boundaries Using Domain-Driven Design

## Status
Accepted

## Date
2026-05-27

## Context

Need to split monolith into microservices. Risk: wrong boundaries lead to "distributed monolith" — worst of both worlds.

## Decision

Use **Domain-Driven Design (DDD) bounded contexts** to define microservice boundaries:

Identified bounded contexts:
1. **Identity** — auth, users, permissions
2. **Catalog** — products, restaurants, menus
3. **Ordering** — cart, checkout, order lifecycle
4. **Payment** — gateways, transactions, refunds
5. **Delivery** — agents, routing, ETA
6. **Notification** — multi-channel messaging
7. **Analytics** — events, metrics, reports

Each bounded context → one microservice (initially). Single-team ownership.

## Alternatives Considered

1. **Technology-based split** (e.g., "API service", "DB service")
   - ✗ Creates dependencies on every change
   - ✗ Anti-pattern, leads to distributed monolith
   - **Rejected**

2. **CRUD-based split** (e.g., service per resource)
   - ✗ Doesn't reflect business reality
   - ✗ Cross-cutting changes touch many services
   - **Rejected**

## Consequences

### Positive
+ Clear ownership boundaries (one team per service)
+ Independent deployment cycles
+ Business-aligned (easier roadmap planning)
+ Allows polyglot persistence (different DBs per context)

### Negative
- Initial domain modeling investment (2 weeks)
- Cross-context queries require API calls
- Need eventual consistency between contexts

### Process
- Quarterly DDD workshops to refine boundaries
- ADRs for any cross-context dependencies
- API contracts via OpenAPI
```

### ADR-006: Use Stripe for Payments

```markdown
# ADR-006: Use Stripe as Primary Payment Provider

## Status
Accepted

## Date
2026-05-28

## Context

Need payment processing for:
- One-time payments (orders)
- Recurring subscriptions (SaaS)
- Refunds + disputes
- Multi-currency (INR, USD, EUR)
- PCI compliance

## Decision

Use **Stripe** as primary, **Razorpay** as backup for India.

Stripe for:
- USD, EUR transactions
- Subscription management
- Webhook-based events
- Dispute handling

Razorpay for:
- INR transactions (cheaper than Stripe India)
- UPI integration
- Local Indian payment methods

## Alternatives Considered

1. **Build custom payment system**
   - ✗ 12+ months development
   - ✗ PCI compliance burden
   - ✗ Not core competency
   - **Rejected**

2. **PayPal**
   - ✗ Higher fees
   - ✗ Worse developer experience
   - **Rejected**

3. **Adyen**
   - ✓ Enterprise-grade
   - ✗ Overkill for current scale
   - ✗ Higher minimum fees
   - **Deferred (revisit at $50M+ TPV)**

## Consequences

### Positive
+ Time-to-market: 2 weeks vs 12+ months
+ PCI compliance offloaded to providers
+ Excellent developer documentation
+ Strong fraud detection

### Negative
- Per-transaction fees (2.9% + ₹2 for Stripe, 2% for Razorpay)
- Vendor dependency
- Webhook reliability (must handle gracefully)

### Cost Analysis
- $100K TPV/month × 2.9% = $2,900/month in fees
- Build vs buy: $200K+ savings in first year
```

### ADR-007: Adopt OpenTelemetry for Observability

```markdown
# ADR-007: Standardize on OpenTelemetry for Tracing, Metrics, and Logging

## Status
Accepted

## Date
2026-05-29

## Context

Currently using mix of tools:
- New Relic for APM
- Datadog for logs
- Custom Python logging
- Prometheus for some metrics

Pain points:
- Vendor lock-in
- Inconsistent instrumentation
- High cost ($5K/month)
- Difficulty correlating across tools

## Decision

Migrate to **OpenTelemetry** as instrumentation standard, with:
- **Tracing**: OTel SDK → OTLP → Tempo
- **Metrics**: OTel → Prometheus
- **Logs**: OTel → Loki (with trace correlation)
- Visualization: **Grafana**

## Alternatives Considered

1. **Continue with Datadog**
   - ✓ Mature, integrated
   - ✗ $5K/month cost (growing)
   - ✗ Vendor lock-in
   - **Rejected**

2. **Honeycomb**
   - ✓ Great for tracing
   - ✗ Limited Indian operations
   - ✗ Cost
   - **Rejected**

## Consequences

### Positive
+ Vendor neutral (OTel is OSS standard)
+ Cost: $500/month for self-hosted Grafana stack
+ Consistent instrumentation across services
+ Correlation between logs/traces/metrics

### Negative
- 3-month migration project
- Team needs to learn Grafana ecosystem
- Self-hosting requires ops effort

### Rollout Plan
- Phase 1 (1 month): OTel instrumentation in new services
- Phase 2 (1 month): Migrate existing services
- Phase 3 (1 month): Decommission Datadog
```

---

## 3. Architecture Fitness Functions (Python Code)

> **Fitness functions** = automated checks that verify architecture qualities.

### Concept

```
Traditional Test:     "Does the code work correctly?"
Fitness Function:     "Does the architecture remain healthy?"

Examples:
- "No service has more than 10 dependencies"
- "All endpoints have < 200ms p95 latency"
- "Tenant data is properly isolated"
- "No circular dependencies between modules"
```

### A. Dependency Direction Enforcement

```python
# tests/fitness/test_layer_dependencies.py
import ast
import os
from pathlib import Path


class LayerDependencyChecker:
    """
    Enforce: Domain layer should NOT depend on Infrastructure.
    Clean architecture rule.
    """

    LAYERS = {
        "domain": "src/domain",
        "application": "src/application",
        "infrastructure": "src/infrastructure",
        "presentation": "src/presentation",
    }

    # What each layer is allowed to import
    ALLOWED_DEPS = {
        "domain": [],                       # Pure — no dependencies
        "application": ["domain"],           # Can use domain
        "infrastructure": ["domain", "application"],  # Implements interfaces
        "presentation": ["application", "domain"],     # Calls application
    }

    def check(self) -> list[dict]:
        violations = []

        for layer, layer_path in self.LAYERS.items():
            for py_file in Path(layer_path).rglob("*.py"):
                imports = self._get_imports(py_file)
                for imp in imports:
                    for other_layer, other_path in self.LAYERS.items():
                        if other_layer == layer:
                            continue
                        if other_path.replace("/", ".") in imp:
                            if other_layer not in self.ALLOWED_DEPS[layer]:
                                violations.append({
                                    "file": str(py_file),
                                    "layer": layer,
                                    "imports": imp,
                                    "from_layer": other_layer,
                                })

        return violations

    def _get_imports(self, py_file: Path) -> list[str]:
        with open(py_file) as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        return imports


def test_no_layer_violations():
    checker = LayerDependencyChecker()
    violations = checker.check()
    assert not violations, f"Layer violations found: {violations}"


# Run as part of CI — architecture violations break build
```

### B. Performance Fitness Function

```python
# tests/fitness/test_performance.py
import pytest
import httpx
import time
import asyncio
from statistics import quantiles


@pytest.mark.asyncio
async def test_endpoint_latency_p95():
    """Architecture fitness: p95 latency < 500ms for critical endpoints."""

    async def measure_one(client, url):
        start = time.perf_counter()
        await client.get(url)
        return (time.perf_counter() - start) * 1000

    async with httpx.AsyncClient(base_url="http://staging.acme.com") as client:
        # Warm up
        for _ in range(10):
            await client.get("/api/orders/1")

        # Measure
        latencies = []
        for _ in range(100):
            elapsed = await measure_one(client, "/api/orders/1")
            latencies.append(elapsed)

    p95 = quantiles(latencies, n=20)[18]  # 95th percentile

    assert p95 < 500, f"p95 latency {p95}ms exceeds 500ms SLA"
```

### C. Security Fitness Function

```python
# tests/fitness/test_security.py
import requests


def test_all_endpoints_require_auth():
    """No endpoint should accept requests without authentication."""

    # Get all endpoints from OpenAPI spec
    openapi = requests.get("http://localhost:8000/openapi.json").json()

    public_endpoints = ["/health/live", "/health/ready", "/metrics", "/docs", "/openapi.json"]

    for path, methods in openapi["paths"].items():
        if path in public_endpoints:
            continue

        for method in methods.keys():
            response = requests.request(method, f"http://localhost:8000{path}")
            assert response.status_code in [401, 403], \
                f"{method} {path} returned {response.status_code} without auth (should be 401/403)"


def test_no_secrets_in_logs():
    """Check that recent logs don't contain potential secrets."""
    import subprocess
    import re

    logs = subprocess.check_output(["docker", "logs", "--tail=10000", "order-service"]).decode()

    # Patterns that might be secrets
    patterns = [
        r"(?i)password['\"\s:=]+[a-zA-Z0-9!@#$%^&*]{8,}",
        r"AKIA[A-Z0-9]{16}",  # AWS access key
        r"sk_live_[a-zA-Z0-9]{24}",  # Stripe key
        r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",  # JWT
    ]

    for pattern in patterns:
        matches = re.findall(pattern, logs)
        assert not matches, f"Potential secrets found in logs: {matches[:3]}"
```

### D. Multi-Tenant Isolation Check

```python
# tests/fitness/test_tenant_isolation.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_no_cross_tenant_access():
    """Critical fitness: tenant A cannot access tenant B's data."""

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Auth as tenant A
        token_a = await get_test_token(tenant_id="tenant-a", user_id=1)

        # Try to access tenant B's data
        response = await client.get(
            "/api/orders?tenant_id=tenant-b",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        # Must be forbidden
        assert response.status_code == 403, \
            f"CRITICAL: Tenant A accessed tenant B's data! {response.json()}"


@pytest.mark.asyncio
async def test_data_returned_is_tenant_specific():
    """When fetching data, only tenant's own data returned."""

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        token_a = await get_test_token(tenant_id="tenant-a", user_id=1)

        response = await client.get(
            "/api/orders",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        orders = response.json()["orders"]
        for order in orders:
            assert order["tenant_id"] == "tenant-a", \
                f"Cross-tenant data leak: order {order['id']} belongs to {order['tenant_id']}"
```

### E. Dependency Count Check

```python
# tests/fitness/test_complexity.py
import json
from pathlib import Path


def test_no_service_has_too_many_dependencies():
    """Architecture fitness: each service has <= 10 external dependencies."""

    SERVICES_DIR = Path("services")
    MAX_DEPS = 10

    for service_dir in SERVICES_DIR.iterdir():
        if not service_dir.is_dir():
            continue

        pyproject = service_dir / "pyproject.toml"
        if not pyproject.exists():
            continue

        import tomllib
        with open(pyproject, "rb") as f:
            config = tomllib.load(f)

        deps = config.get("project", {}).get("dependencies", [])
        # Exclude common framework deps
        external = [d for d in deps if not d.startswith(("fastapi", "uvicorn", "pydantic"))]

        assert len(external) <= MAX_DEPS, \
            f"{service_dir.name} has {len(external)} dependencies, exceeds limit of {MAX_DEPS}"
```

### F. CI Integration

```yaml
# .github/workflows/architecture-fitness.yml
name: Architecture Fitness Functions

on:
  pull_request:
  push:
    branches: [main]

jobs:
  fitness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Layer dependency check
        run: pytest tests/fitness/test_layer_dependencies.py -v

      - name: Security checks
        run: pytest tests/fitness/test_security.py -v

      - name: Multi-tenant isolation
        run: pytest tests/fitness/test_tenant_isolation.py -v

      - name: Complexity check
        run: pytest tests/fitness/test_complexity.py -v
```

---

## 4. Stakeholder Communication Scripts

### Script 1: Explaining Microservices to CEO

**Setting:** CEO asks "Why are we spending 6 months on microservices migration?"

**Your script:**

```
"Currently our monolith has 200K lines of code, and one bad deploy
takes down everything. Last month's outage cost us ₹15L in lost
transactions and 50+ angry customer calls.

Microservices will let us:

1. **Deploy faster** — each team ships independently
   - Currently: 2 weeks to release a feature
   - After: 2 days

2. **Scale efficiently** — only scale what's busy
   - Currently: ₹10L/month on infrastructure
   - After: ₹6L/month (40% savings)

3. **Survive outages** — one service failing doesn't break others
   - Currently: 99.5% uptime
   - After: 99.95% uptime (10x fewer outages)

The 6-month investment is ₹50L. Expected returns:
- Infrastructure savings: ₹4L/month = ₹48L/year
- Feature velocity: 5x → ₹2Cr more ARR/year
- Reduced outages: avoid ₹15L+/incident

Break-even: 8 months. After that, pure upside."
```

### Script 2: Explaining Tech Debt to Product Manager

**Setting:** PM asks "Why can't we just add this feature in 1 week?"

**Your script:**

```
"This feature touches 3 areas of the codebase that have accumulated
significant tech debt:

1. **Auth module** (5 years old, no tests)
   - Risk: breaking changes hard to detect
   - Fix: 1 week to add tests before any change

2. **Order service** (tightly coupled with billing)
   - Risk: change ripples to billing
   - Fix: 2 weeks to decouple

3. **Database schema** (denormalized, hard to extend)
   - Risk: migration could affect existing customers
   - Fix: 1 week for safe migration

Adding feature directly: 1 week BUT 80% chance of production incident
With tech debt fix first: 4 weeks, but solid foundation for future features

I recommend: fix Order/Auth first, then add feature.
Net time saved over next 6 months: ~3 months of avoided rework.

Want me to break this into smaller PRs we can review weekly?"
```

### Script 3: Disagreeing with a Junior Dev

**Setting:** Junior dev wants to use a "shiny new framework" for production.

**Your script:**

```
"Hey [name], I love that you're exploring new tech. Let's evaluate it
together using our framework:

1. **Maturity check**
   - Is it 1.0+? When was the last release?
   - Who's using it in production at scale?

2. **Team capability**
   - Do we have 2+ engineers comfortable debugging it?
   - What's the learning curve?

3. **Operations**
   - Can we monitor it?
   - What's the upgrade path?
   - Community size for help?

4. **Compared to current solution**
   - What 3 specific pains does it solve?
   - Is it 10x better, or 1.5x?

For [framework X], here's my analysis:
- Maturity: 0.8.x (not 1.0 yet) ❌
- Production users: Only [small companies] so far ⚠️
- Team: 0 engineers know it ❌
- Vs current: Maybe 20% better, not 10x ❌

I'd suggest: prototype on a side project first.
If it proves valuable AND mature, revisit in 6 months.

For production now, let's stick with what works.

What problem are you really trying to solve? Maybe there's another way."
```

---

## 5. Architecture Governance Templates

### Tech Radar (Quarterly Update)

```markdown
# Tech Radar — 2026 Q2

## Adopt (Use freely)
- FastAPI for new services
- PostgreSQL for OLTP
- Redis for caching
- Kubernetes for orchestration
- OpenTelemetry for observability

## Trial (Use in limited scope)
- ClickHouse for analytics (pilot in analytics-service)
- vLLM for local LLM (POC for inference)
- Polars for data processing (replacing pandas in workers)

## Assess (Investigating)
- WebTransport (vs WebSocket)
- Cloudflare Workers (edge compute)
- Rust extensions via PyO3 (perf-critical code)

## Hold (Don't use without strong justification)
- Django (we standardize on FastAPI)
- MongoDB (PostgreSQL with JSONB is enough)
- Docker Swarm (we use K8s)

## Drop (Migrate away from)
- Datadog (migrating to Grafana stack — see ADR-007)
- Self-hosted Jenkins (moving to GitHub Actions)
- Python 3.10 (upgrade to 3.12+)
```

### Architecture Review Calendar

```markdown
# Architecture Governance Calendar

## Weekly (Tuesdays 3pm)
- Architecture sync (30 min)
- Active ADRs discussion
- Cross-team alignment

## Bi-Weekly (Thursdays)
- Design review session
- New ADRs presented
- Tech debt review

## Monthly (1st of month)
- Architecture metrics review:
  - Fitness function results
  - SLO status
  - Incident postmortems
- Roadmap alignment with product

## Quarterly
- Tech Radar update
- DDD bounded context review
- Major version planning
- Security audit
- Cost optimization review

## Annual
- Full architecture review
- Strategic direction set
- Hiring plan for architects/leads
- Conference + learning budget
```

### Architecture Decision Inbox Template

```markdown
# Decision Backlog

| ID | Topic | Proposer | Status | Target Date |
|----|-------|----------|--------|-------------|
| ADR-008 | Choose between Pulumi and Terraform | @ashish | In review | 2026-06-15 |
| ADR-009 | Migration strategy for Auth service | @priya | Draft | 2026-06-20 |
| ADR-010 | Adopt feature flags platform | @rajesh | Proposed | 2026-06-30 |
| ADR-011 | Standardize on Python 3.12 | @suresh | Discussion | TBD |
| ADR-012 | gRPC vs REST for internal APIs | @ashish | Idea | TBD |

## Process
1. Anyone can propose an ADR (open a PR)
2. Architect schedules review (Thursday session)
3. Discussion + iteration
4. Decision (Accepted / Rejected / Deferred)
5. Communicate broadly
```

---

## 6. Architect's Day-1 Onboarding Plan

### Week 1 — Discovery

```markdown
# Day 1
- [ ] Meet with EM + VPE — understand expectations
- [ ] Read CTO/Architect-emeritus documents
- [ ] Check existing ADRs + architecture docs
- [ ] Set up dev environment

# Day 2-3
- [ ] Pair with senior engineers (2 hours each, 3 different teams)
- [ ] Run the application end-to-end locally
- [ ] Make a tiny PR (1 line change) to learn process

# Day 4-5
- [ ] Read incident postmortems (last 6 months)
- [ ] Review production dashboards
- [ ] Attend on-call rotation as observer
```

### Week 2 — Listening Tour

```markdown
# Goal: Talk to 15+ engineers, listen for pain points

Categories:
- Frontend engineers (5+)
- Backend engineers (5+)
- DevOps/SRE (2+)
- Product managers (2+)
- Customer support (1+)

For each conversation, ask:
1. "What's working well architecturally?"
2. "What's painful?"
3. "If you could change one thing, what?"
4. "Where do you waste the most time?"
5. "What scares you about the system?"

Take notes. Look for patterns.
```

### Week 3 — Analysis

```markdown
# Compile findings into:
- Top 5 architectural pain points
- Top 5 architectural strengths
- Inconsistencies across teams
- Risks (security, scale, ops)
- Quick wins (1-2 month payoff)
- Long-term bets (6-12 month payoff)
```

### Week 4 — First Proposal

```markdown
# Deliverable: Architecture roadmap

Format:
1. State of the system (visual)
2. Top pain points (data-backed)
3. Strategic goals (next 6 months)
4. Proposed initiatives (3-5)
5. Resource asks
6. Success metrics

Present to: EM, VPE, CTO, peer leads
Get feedback. Iterate.
```

### Month 3 — First Initiative

```markdown
# Goal: Ship one architectural improvement end-to-end

Examples:
- Migrate one service to new pattern
- Introduce observability tool
- Improve deployment process
- Add architecture fitness functions

Show:
- Before/after metrics
- Team learnings
- ADRs produced
- Documentation created

Build trust through delivery, not just talking.
```

---

## 7. Trade-off Analysis Framework

### Template

```markdown
# Trade-off Analysis: [Decision Topic]

## Context
[1-2 paragraphs of context]

## Options Evaluated

### Option A: [Name]
**Description:** [What it is]

| Attribute | Score (1-5) | Notes |
|-----------|-------------|-------|
| Implementation effort | 4 | 2 weeks, team has expertise |
| Operational complexity | 3 | Moderate ops burden |
| Cost | 5 | Free + cheap to run |
| Performance | 3 | Good enough |
| Scalability | 4 | Scales to 10x easily |
| Security | 5 | OWASP-compliant by default |
| Maintainability | 4 | Easy to debug |
| Team capability | 5 | We know it well |
| **Total** | **33/40** | |

### Option B: [Name]
[Same structure]
| **Total** | **28/40** | |

### Option C: [Name]
[Same structure]
| **Total** | **35/40** | |

## Recommendation
**Option C** scores highest. Rationale:
- [Key advantage 1]
- [Key advantage 2]

## Risks of chosen option
- Risk 1 + mitigation
- Risk 2 + mitigation

## What we accept (trade-offs)
- We accept [drawback] because [reason]

## Validation criteria
We'll know this was the right choice if:
- [ ] Metric 1 hits target
- [ ] Metric 2 hits target
- [ ] No major incidents in 90 days

## Review date
2026-09-15 (revisit in 3 months)
```

### Real Example: Choosing a Cache

```markdown
# Trade-off: Redis vs Memcached vs Hazelcast for Application Cache

## Context
Need to cache user sessions + frequently-accessed data.
Scale: 1M sessions, 100K reads/sec.

## Options

### Redis
| Attribute | Score | Notes |
|-----------|-------|-------|
| Performance | 5 | Sub-ms latency |
| Features (data structures) | 5 | Hashes, lists, sets, sorted sets |
| Persistence | 4 | RDB + AOF |
| Replication | 5 | Built-in |
| Clustering | 4 | Native cluster mode |
| Ecosystem | 5 | Tons of libraries |
| Cost | 4 | Reasonable |
| **Total** | **32/35** | |

### Memcached
| Attribute | Score | Notes |
|-----------|-------|-------|
| Performance | 5 | Very fast |
| Features | 2 | Strings only |
| Persistence | 1 | Memory only |
| Replication | 1 | None built-in |
| Clustering | 2 | Client-side sharding |
| Ecosystem | 4 | Mature |
| Cost | 5 | Very cheap |
| **Total** | **20/35** | |

### Hazelcast
| Attribute | Score | Notes |
|-----------|-------|-------|
| Performance | 4 | Good but JVM overhead |
| Features | 5 | Distributed data structures |
| Persistence | 4 | Optional |
| Replication | 5 | Strong consistency mode |
| Clustering | 5 | Native distributed |
| Ecosystem | 3 | Smaller (Java-focused) |
| Cost | 3 | Enterprise features paid |
| **Total** | **29/35** | |

## Decision: Redis
- Best balance of features, performance, ecosystem
- Team has Redis experience already
- Hazelcast has good clustering but Java-heavy
- Memcached too limited for our needs

## Trade-offs accepted
- Redis is single-threaded — but we use cluster mode for horizontal scale
- More expensive than Memcached — but features justify cost
```

---

## 8. Quick Reference Cards

### Card 1: When to Call an Architect Meeting

```
✓ Major tech choice (DB, framework, cloud provider)
✓ Cross-team integration design
✓ Breaking change to public API
✓ New microservice introduction
✓ Migration plan (legacy → new)
✓ Production incident with architectural cause
✓ Cost optimization (>$5K/month impact)

✗ Bug fixes
✗ UI changes
✗ Internal refactoring within one service
✗ Documentation updates
```

### Card 2: Architect's Quality Bar

```
For every design, ask:

1. Does it pass our fitness functions?
2. Are all 5 NFRs explicitly considered?
3. Does it have an ADR?
4. Has it been peer-reviewed?
5. Is the operational runbook clear?
6. Can a new dev understand in 1 hour?
7. What's the rollback plan?
```

### Card 3: Architect's Communication Style

```
TO CEO/Business:    Outcomes + Cost + Time + Risk
TO Product:         Features + Trade-offs + Timeline
TO Engineering:     Patterns + Tools + Examples
TO Junior devs:     Why + How + Where to learn more
TO Operations:      Runbooks + Failure modes + Recovery
TO Security:        Threat model + Controls + Compliance
```

---

## 9. Summary

```
Architect's Toolkit:
─────────────────
1. Design Review Checklist  → systematic reviews
2. ADRs                     → documented decisions
3. Fitness Functions        → automated architecture tests
4. Communication Scripts    → audience-tailored messaging
5. Governance Templates     → process at scale
6. Onboarding Plan          → start strong
7. Trade-off Framework      → structured decision-making
```

### Action Items for Aspiring Architects

1. ✅ **Write 1 ADR this week** — for any past architectural decision
2. ✅ **Add 1 fitness function** to your current codebase
3. ✅ **Conduct a design review** using the checklist
4. ✅ **Practice the communication scripts** with a peer
5. ✅ **Start a Tech Radar** for your team

---

## 10. Related Resources

- [PythonBackend_SystemDesign/HLD_Theory/Udemy_MasteringSystemDesign/11_Blueprint.md](../../PythonBackend_SystemDesign/HLD_Theory/Udemy_MasteringSystemDesign/11_Blueprint.md)
- [Phase3_DevOps/14_chaos_engineering.md](../../Phase3_DevOps/14_chaos_engineering.md)
- [Phase3_DevOps/16_sre_practices_sli_slo.md](../../Phase3_DevOps/16_sre_practices_sli_slo.md)
- Books: "Building Evolutionary Architectures" by Neal Ford (fitness functions origin)
- Books: "Technology Strategy Patterns" by Eben Hewitt
