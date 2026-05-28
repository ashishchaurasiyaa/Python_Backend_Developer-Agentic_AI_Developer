"""
Phase3_DevOps — Deployment Interview Q&A Practical
====================================================
Topics covered:
  1. Architecture explanation templates (STAR method)
  2. Scaling answer framework (5K → 100K users)
  3. Zero-downtime deployment patterns (with code)
  4. Incident response runbook (3 AM DB crash example)
  5. Database migration patterns (expand-contract code)
  6. Secrets management 6-layer model
  7. Common debugging scenarios with diagnostic commands
  8. Cost optimization strategies
  9. Junior vs Senior phrase examples
  10. Mock interview Q&A simulator

Run:
  python 08_deployment_interview_practical.py
"""

import os
import json
import textwrap
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Architecture Explanation Template (STAR Method)
# INTERVIEW: "Walk me through your last deployment"
# ─────────────────────────────────────────────────────────────────────────────

ARCHITECTURE_ANSWER_TEMPLATE = """\
# ════════════════════════════════════════════════════════════════════
# Template: "Walk me through your last project deployment" (5-min answer)
# INTERVIEW: Use STAR — Situation, Task, Action, Result
# ════════════════════════════════════════════════════════════════════

INTRO (15 sec):
  "Maine recently ek Django-based ERP system deploy kiya for inventory +
   jobsite management. Stack: Django 5 + DRF + PostgreSQL+PostGIS + Redis +
   Celery, React frontend."

ARCHITECTURE (60 sec):
  "Architecture-wise 3 layers hain:
   - Frontend: Static React build S3 par, CloudFront ke through globally CDN.
   - Backend: AWS ECS Fargate par chalta hai — 2-10 tasks auto-scale, ALB peeche.
   - Database: RDS PostgreSQL Multi-AZ for HA, PostGIS for spatial queries.
   - Background: Celery workers separate ECS service, Beat single instance.
   - Files: django-storages se directly S3 mein."

CI/CD (60 sec):
  "GitHub Actions — push to main triggers tests → Docker build → push to ECR →
   migrations as one-off ECS task → rolling deploy of services.
   OIDC use kiya AWS auth ke liye — no long-lived keys."

OBSERVABILITY (30 sec):
  "CloudWatch Logs + structlog JSON, Sentry for errors,
   Prometheus metrics scraped by AWS Managed Prometheus."

COST (15 sec):
  "Production ~₹18K/mo, staging ~₹3K/mo on single EC2."

ONE TRICKY PROBLEM (60 sec) — ⭐ MOST IMPORTANT PART:
  "Ek interesting problem: WeasyPrint PDF generation Django web container me
   karne se memory spike hote the — sync blocking request bhi slow.
   Maine isko Celery worker me move kiya with separate 'high_priority' queue.
   Workers ko 2x memory diya. Web latency p99 5s → 200ms ho gaya."

WHY THIS WORKS:
  ✅ Specific tech versions (Django 5, Postgres 15)
  ✅ Architecture flow clear (3 layers)
  ✅ Numbers + costs mentioned (₹18K, p99 200ms)
  ✅ One real problem + solution (shows experience)
  ✅ Under 5 minutes
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Scaling Answer Framework
# INTERVIEW: "Scale from 5K to 100K users"
# ─────────────────────────────────────────────────────────────────────────────

SCALING_PHASES = {
    "Phase 1 — Quick wins (Week 1)": {
        "duration": "1 week",
        "cost_increase": "Marginal",
        "actions": [
            "Profile bottlenecks: CloudWatch + django-silk (likely DB queries)",
            "Add database indexes on frequent WHERE/ORDER BY columns",
            "Enable Redis cache for read-heavy endpoints (@cache_page)",
            "Increase ECS Fargate task count (manual scale up)",
            "Tune Gunicorn workers based on metrics",
        ],
        "expected_impact": "30-50% latency reduction",
    },
    "Phase 2 — Architecture (Week 2-4)": {
        "duration": "2-4 weeks",
        "cost_increase": "20-30%",
        "actions": [
            "Add RDS read replica for analytics queries",
            "Use RDS Proxy for connection pooling at infra level",
            "Aggressive CloudFront caching (proper cache headers)",
            "Fix N+1 queries: select_related, prefetch_related",
            "Celery: auto-scale workers based on SQS queue depth",
            "Implement multiple Celery queues (priority-based)",
        ],
        "expected_impact": "Handle 3x current load",
    },
    "Phase 3 — Scaling-out (Month 2)": {
        "duration": "1 month",
        "cost_increase": "100-200%",
        "actions": [
            "Upgrade RDS: db.t3.small → db.m6g.xlarge (or Aurora)",
            "Partition large tables (audit_logs by date)",
            "Extract heavy modules as microservices (PDF gen, reporting)",
            "Multi-region read replicas if global users",
            "Implement event-driven architecture for some flows",
        ],
        "expected_impact": "Handle 100K+ users",
    },
    "Phase 4 — Optimization (Ongoing)": {
        "duration": "Continuous",
        "actions": [
            "Move all static assets to S3 + CloudFront",
            "Image optimization at upload (Pillow → WebP)",
            "Implement HTTP/2 server push",
            "Monthly query plan reviews",
            "Cost optimization: Reserved Instances, Savings Plans",
        ],
        "monitoring": "p99 < 300ms, error rate < 0.1%, DB CPU < 70%",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Zero-Downtime Deployment Implementation
# INTERVIEW: 4 pillars with code examples
# ─────────────────────────────────────────────────────────────────────────────

ZERO_DOWNTIME_PILLARS = """\
# ════════════════════════════════════════════════════════════════════
# 4 PILLARS OF ZERO-DOWNTIME DEPLOYMENT
# ════════════════════════════════════════════════════════════════════

# ── Pillar 1: Rolling Deployment ────────────────────────────────────
# ECS Fargate service configuration
{
  "deploymentConfiguration": {
    "minimumHealthyPercent": 100,    # ⭐ Always 100% capacity
    "maximumPercent": 200,           # New tasks added FIRST, old removed AFTER
    "deploymentCircuitBreaker": {
      "enable": True,
      "rollback": True               # Auto-rollback on failure
    }
  }
}
# Result: 2 tasks running → deploy time 4 tasks (2 new + 2 old)
# Health check passes → old tasks terminate → 2 tasks again


# ── Pillar 2: Health Checks ────────────────────────────────────────
# Django/FastAPI views
@app.get("/health")
async def liveness():
    \"\"\"Simple alive check (200 = process running)\"\"\"
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness():
    \"\"\"Deep check — return 503 if DB/Redis unreachable\"\"\"
    checks = {"db": "ok", "redis": "ok"}
    try:
        await db.execute("SELECT 1")
    except:
        checks["db"] = "error"
        return Response(json.dumps(checks), status_code=503)

    return checks

# ALB target group health check
{
  "HealthCheckProtocol": "HTTP",
  "HealthCheckPath": "/health/ready",
  "HealthyThresholdCount": 2,
  "UnhealthyThresholdCount": 3,
  "HealthCheckIntervalSeconds": 30
}


# ── Pillar 3: Graceful Shutdown ────────────────────────────────────
# Gunicorn config
gunicorn app.main:app \\
  --graceful-timeout 30 \\          # Active requests get 30s to complete
  --timeout 120                     # Hard timeout per request

# Django signal handler (custom shutdown logic)
import signal
import sys

def graceful_shutdown(signum, frame):
    # 1. Stop accepting new requests (handled by server)
    # 2. Complete active requests (handled by graceful-timeout)
    # 3. Close DB connections
    # 4. Flush Sentry/CloudWatch buffers
    sys.exit(0)

signal.signal(signal.SIGTERM, graceful_shutdown)


# ── Pillar 4: Backward-Compatible Migrations ───────────────────────
# Bad: Direct column rename (old code crashes)
ALTER TABLE orders RENAME COLUMN customer_id TO user_id;  # ❌

# Good: Expand-Contract pattern (3 deploys)
# Deploy 1: Add new column, code dual-writes
ALTER TABLE orders ADD COLUMN user_id INT;
# Code writes to BOTH customer_id and user_id

# Deploy 2: Backfill data
UPDATE orders SET user_id = customer_id WHERE user_id IS NULL;
# Code reads from user_id

# Deploy 3: Drop old column
ALTER TABLE orders DROP COLUMN customer_id;
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Incident Response Runbook
# INTERVIEW: "Production DB crashes at 3 AM"
# ─────────────────────────────────────────────────────────────────────────────

INCIDENT_RESPONSE_TIMELINE = [
    {
        "time": "0-2 minutes",
        "phase": "ACKNOWLEDGE + TRIAGE",
        "actions": [
            "Acknowledge alert in PagerDuty (stops escalation)",
            "Declare in Slack #incidents: 'Investigating RDS issue. ETA 10 min.'",
            "Open CloudWatch dashboard for RDS",
            "Check: CPU spike? Memory? Connections? Disk?",
        ],
    },
    {
        "time": "2-5 minutes",
        "phase": "DIAGNOSE",
        "actions": [
            "Query CloudWatch Logs Insights for recent errors:",
            "  fields @timestamp, @message | filter @message like /ERROR|FATAL/ | filter @timestamp > ago(15m)",
            "Check RDS events for AWS-side failover",
            "Application logs (Sentry) — sudden error spike?",
            "Recent deployments in last hour?",
        ],
    },
    {
        "time": "5-15 minutes",
        "phase": "MITIGATE",
        "actions": [
            "If Multi-AZ: Likely auto-failover happening. Verify new endpoint.",
            "If single-AZ: Initiate manual failover OR restore from PITR snapshot.",
            "If connection pool exhausted: Restart ECS tasks to reset pool.",
            "If disk full: aws rds modify-db-instance --allocated-storage 50",
            "If rogue query: SELECT pg_terminate_backend(pid);",
        ],
    },
    {
        "time": "15-30 minutes",
        "phase": "VERIFY",
        "actions": [
            "Smoke test critical endpoints",
            "Check error rate dropped to normal baseline",
            "Verify all dependencies healthy (Redis, S3, external APIs)",
            "Update status page (if customer-facing)",
            "Slack update: 'Resolved. Postmortem tomorrow.'",
        ],
    },
    {
        "time": "Next day",
        "phase": "POSTMORTEM (BLAMELESS)",
        "actions": [
            "Schedule postmortem meeting within 24h",
            "Document timeline (what, when, why)",
            "Identify root cause (5-whys analysis)",
            "Action items: prevention + detection improvements",
            "Update runbook with this scenario",
        ],
    },
]

REAL_INCIDENT_EXAMPLE = """\
# Real Incident Story (use in interview)
# ════════════════════════════════════════════════════════════════════

SITUATION:
  3 AM Sunday — PagerDuty: '500 error rate spiked to 40%'

DIAGNOSE (5 min):
  CloudWatch → all errors pointed to PostgreSQL connection timeout
  RDS CPU at 95% (normally 30%)
  pg_stat_activity → ek long-running analytics query 800 connections
  Someone manually ran heavy report on production DB

MITIGATE (2 min):
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE query LIKE '%generate_yearly_report%' AND state = 'active';

VERIFY (5 min):
  Error rate back to normal
  CPU dropped to 25%

POSTMORTEM ACTION ITEMS:
  1. Statement timeout: ALTER DATABASE prod SET statement_timeout = '30s';
  2. Read replica added — analytics queries routed there via DB router
  3. CloudWatch alarm: pg_stat_activity_count > 500
  4. Runbook updated with this exact scenario

LEARNING:
  Always set query timeouts on production.
  One bad query can take down entire database.
  Heavy queries on read replica, not primary.

# Total downtime: 12 minutes (instead of hours without this response)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Secrets Management 6-Layer Model
# INTERVIEW: "How do you manage secrets in production?"
# ─────────────────────────────────────────────────────────────────────────────

SECRETS_LAYERS = {
    "Layer 1: Storage": {
        "what": "Where secrets actually live",
        "tools": ["AWS Secrets Manager", "AWS Parameter Store"],
        "rules": [
            "Production secrets → Secrets Manager (with rotation)",
            "Non-sensitive config → Parameter Store (cheaper)",
            "NEVER in: Git, .env committed, Docker images, hardcoded",
        ],
    },
    "Layer 2: Injection": {
        "what": "How secrets reach the application",
        "tools": ["ECS Secrets parameter", "K8s ExternalSecrets"],
        "rules": [
            "ECS task def 'secrets' → AWS injects as env vars at start",
            "NEVER pass secrets as Docker ENV (visible in 'docker history')",
            "K8s: External Secrets Operator + Secrets Manager",
        ],
    },
    "Layer 3: Rotation": {
        "what": "How often to change secrets",
        "tools": ["Secrets Manager auto-rotation", "Lambda rotators"],
        "rules": [
            "DB password: 30-day auto-rotation via Lambda",
            "API keys: quarterly with 24h overlap (old + new accepted)",
            "JWT signing keys: rotate with kid header in token",
        ],
    },
    "Layer 4: Access Control": {
        "what": "Who can read which secret",
        "tools": ["IAM policies", "Resource policies"],
        "rules": [
            "Task role minimal permissions — specific secret ARNs only",
            "Least privilege: prod role can't read dev secrets",
            "Cross-account access via resource policies",
        ],
    },
    "Layer 5: Audit": {
        "what": "Who accessed what, when",
        "tools": ["CloudTrail", "GuardDuty"],
        "rules": [
            "CloudTrail logs every GetSecretValue call",
            "GuardDuty alerts on suspicious access patterns",
            "Monthly audit of Secrets Manager access",
        ],
    },
    "Layer 6: Local Dev": {
        "what": "How team handles secrets locally",
        "tools": ["1Password", "Doppler", "direnv"],
        "rules": [
            ".env.example committed (template only)",
            ".env in .gitignore (actual values)",
            "Team sharing via 1Password / Doppler (NOT Slack/email)",
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Debugging Scenarios
# INTERVIEW: "Site is slow — what do you do?"
# ─────────────────────────────────────────────────────────────────────────────

DEBUGGING_SLOW_SITE = """\
# ════════════════════════════════════════════════════════════════════
# Systematic Debugging — Top-Down Approach
# ════════════════════════════════════════════════════════════════════

# Step 1: Define "slow" precisely
QUESTIONS_TO_ASK = [
    "Which page/endpoint specifically?",
    "Which user / geography (some users or all)?",
    "Started when? After a recent deploy?",
    "100% requests or some intermittently?",
    "p50, p95, or p99 latency?",
]

# Step 2: Layer-by-layer diagnosis
LAYERS = {
    "Network": [
        "CloudFront cache hit rate (CloudWatch)",
        "ALB target response time vs request count",
        "Cross-region latency (if applicable)",
    ],
    "Application": [
        "Gunicorn workers saturated? (queue depth)",
        "CPU/memory of ECS tasks",
        "Recent deployment caused regression?",
    ],
    "Database": [
        "RDS CPU spike?",
        "Slow query log (pg_stat_statements)",
        "Connection count at limit?",
        "Lock contention (pg_locks)?",
        "Missing index?",
    ],
    "External": [
        "Third-party API slow (Stripe, SendGrid)?",
        "Redis latency?",
        "S3 throttling?",
    ],
}

# Step 3: Common root causes (rank-ordered by frequency)
COMMON_CAUSES = [
    ("N+1 query", "Added new feature, didn't use select_related"),
    ("Missing index", "New filter on unindexed column"),
    ("DB connection exhaustion", "Pool too small for load"),
    ("Cache cold", "Bad cache key change → all misses"),
    ("Heavy query during peak", "Analytics on production DB"),
    ("Memory leak", "Container OOM → restart → cold cache"),
    ("External API slow", "No timeout, no circuit breaker"),
]

# Step 4: Diagnostic tools
TOOLS = {
    "django-silk": "Profile every request (dev/staging)",
    "EXPLAIN ANALYZE": "Slow PostgreSQL queries",
    "pg_stat_statements": "Top queries by total time",
    "py-spy": "CPU profiling on production (no restart)",
    "CloudWatch Insights": "Query application logs",
    "Datadog APM": "Distributed tracing",
}
"""

DIAGNOSTIC_COMMANDS = """\
# Quick diagnostic commands to copy-paste

# ── PostgreSQL ──────────────────────────────────────────────────────
-- Find slow queries
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 10;

-- Find missing indexes (high seq_scan)
SELECT schemaname, relname, seq_scan, seq_tup_read,
       idx_scan, seq_tup_read / NULLIF(seq_scan, 0) AS avg_seq_tup
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC LIMIT 10;

-- Active connections
SELECT pid, usename, state, query_start, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;

-- Kill rogue query
SELECT pg_terminate_backend(<pid>);

-- Index usage
SELECT indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC LIMIT 10;  -- least used indexes

# ── Django Debugging ────────────────────────────────────────────────
# Profile a view
from django.db import connection
print(connection.queries)  # All SQL for this request

# Check for N+1
# Add to settings: DEBUG_PROPAGATE_EXCEPTIONS = True
# Use: pip install nplusone[django]

# ── Docker/ECS ──────────────────────────────────────────────────────
# Check container resource usage
docker stats

# ECS task logs
aws logs tail /ecs/myapp-django --follow --since 5m

# ECS task health
aws ecs describe-tasks --cluster prod --tasks <task-id>

# ── AWS CloudWatch ──────────────────────────────────────────────────
# Top 10 slowest endpoints (CloudWatch Insights)
fields @timestamp, path, duration_ms
| filter @timestamp > ago(1h)
| sort duration_ms desc
| limit 10

# Error count by endpoint
fields @timestamp, path, status
| filter status >= 500
| stats count() by path
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Junior vs Senior Phrase Mapping
# INTERVIEW: How to sound experienced
# ─────────────────────────────────────────────────────────────────────────────

JUNIOR_VS_SENIOR_PHRASES = [
    ("I used Docker",
     "I containerized the app with multi-stage builds for 70% smaller images"),

    ("I deployed on AWS",
     "I deployed on ECS Fargate with auto-scaling 2-10 tasks based on CPU + queue depth"),

    ("We have logs",
     "Structured JSON logs with request_id correlation, centralized in CloudWatch, queried via Insights"),

    ("I added tests",
     "Unit + integration tests with PostgreSQL service in CI, 85% coverage, blocking merge if drops"),

    ("We use Redis",
     "Redis as L1 cache for hot reads (TTL 5min) + Celery broker + rate limiting backend"),

    ("I set up CI/CD",
     "GitHub Actions with OIDC auth, multi-stage pipeline: lint → test → build → migrate → rolling deploy, manual approval for prod"),

    ("We have monitoring",
     "RED metrics + USE metrics in Grafana, p99 latency SLO 500ms, error rate <0.1%, PagerDuty alerts for Sev-1"),

    ("I optimized the API",
     "Reduced p99 from 2s to 200ms by fixing N+1 queries (select_related), adding compound index on (user_id, created_at)"),

    ("We use HTTPS",
     "TLS 1.3 via ACM cert on ALB, HSTS preload, SECURE_SSL_REDIRECT, certificate auto-renewal"),

    ("I handle errors",
     "Sentry integration with release tagging, alerts piped to Slack, error budget tracked monthly against 99.9% SLO"),
]

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Mock Interview Simulator
# INTERVIEW: Practice mode — read question, write answer, compare
# ─────────────────────────────────────────────────────────────────────────────

MOCK_INTERVIEW_QUESTIONS = [
    {
        "question": "Walk me through your last project's deployment architecture",
        "key_points": [
            "Tech stack with versions",
            "3-layer architecture (frontend/backend/data)",
            "Specific AWS services used and why",
            "Cost (₹ figure)",
            "One real problem + solution",
        ],
        "duration": "4-5 minutes",
        "tip": "Don't dump tools — tell a story with WHY each choice",
    },
    {
        "question": "How would you scale from 5K to 100K daily users?",
        "key_points": [
            "Phase 1: Quick wins (profile, cache, indexes)",
            "Phase 2: Architecture (read replicas, RDS Proxy)",
            "Phase 3: Scale-out (microservices, partition)",
            "Cost impact at each phase",
            "Monitoring throughout",
        ],
        "duration": "5 minutes",
        "tip": "Show phased thinking — don't jump to 'add more servers'",
    },
    {
        "question": "How do you achieve zero-downtime deployment?",
        "key_points": [
            "Rolling deployment (orchestrator level)",
            "Health checks (readiness vs liveness)",
            "Graceful shutdown (SIGTERM handling)",
            "Backward-compatible migrations (expand-contract)",
            "Bonus: feature flags, canary deployments",
        ],
        "duration": "3-4 minutes",
        "tip": "All 4 pillars matter — missing any = downtime",
    },
    {
        "question": "Your production DB crashes at 3 AM. Walk me through your response.",
        "key_points": [
            "0-2 min: Acknowledge + triage",
            "2-5 min: Diagnose (CloudWatch, Insights)",
            "5-15 min: Mitigate (specific actions)",
            "15-30 min: Verify recovery",
            "Next day: Blameless postmortem",
        ],
        "duration": "5 minutes",
        "tip": "Show calm methodical approach, not panic",
    },
    {
        "question": "Why ECS Fargate over EKS or EC2?",
        "key_points": [
            "Pros of Fargate (managed, native AWS, sweet spot)",
            "Cons of EKS for current scale (overhead, cost)",
            "Cons of EC2 (no HA, manual ops)",
            "Migration path if scale grows",
            "Cost comparison",
        ],
        "duration": "3 minutes",
        "tip": "Show trade-offs — acknowledge cons of your choice",
    },
    {
        "question": "How do you manage secrets in production?",
        "key_points": [
            "AWS Secrets Manager (not env vars)",
            "ECS task definition secrets parameter",
            "IAM least privilege (task role)",
            "Rotation (auto via Lambda)",
            "Audit (CloudTrail)",
            "Local dev (1Password/Doppler)",
        ],
        "duration": "3-4 minutes",
        "tip": "6-layer model — storage, injection, rotation, access, audit, local",
    },
    {
        "question": "How do you debug 'site is slow' complaint?",
        "key_points": [
            "Define 'slow' precisely",
            "Top-down: network → app → DB → external",
            "Use observability tools (CloudWatch, Sentry)",
            "Common causes (N+1, missing index, etc.)",
            "Real example from past",
        ],
        "duration": "4 minutes",
        "tip": "Show systematic approach, not 'add more cache'",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Demo functions
# ─────────────────────────────────────────────────────────────────────────────

def demo_run_mock_interview():
    """Print mock interview questions for practice."""
    print("\n[Mock Interview Practice]")
    print("=" * 60)
    for i, q in enumerate(MOCK_INTERVIEW_QUESTIONS, 1):
        print(f"\n  Q{i}: {q['question']}")
        print(f"  Duration: {q['duration']}")
        print(f"  Key points to cover:")
        for point in q['key_points']:
            print(f"    • {point}")
        print(f"  💡 Tip: {q['tip']}")
        print("  " + "-" * 56)


def demo_scaling_phases():
    """Show scaling roadmap."""
    print("\n[Scaling Roadmap: 5K → 100K Users]")
    for phase, details in SCALING_PHASES.items():
        print(f"\n  {phase}")
        print(f"  Duration: {details.get('duration')}")
        if 'cost_increase' in details:
            print(f"  Cost increase: {details['cost_increase']}")
        print(f"  Actions:")
        for action in details['actions']:
            print(f"    • {action}")
        if 'expected_impact' in details:
            print(f"  Expected: {details['expected_impact']}")


def demo_incident_runbook():
    """Show incident response timeline."""
    print("\n[Incident Response Runbook]")
    for phase in INCIDENT_RESPONSE_TIMELINE:
        print(f"\n  [{phase['time']}] {phase['phase']}")
        for action in phase['actions']:
            print(f"    → {action}")


def demo_secrets_model():
    """Show secrets management layers."""
    print("\n[Secrets Management 6-Layer Model]")
    for layer, info in SECRETS_LAYERS.items():
        print(f"\n  {layer}")
        print(f"  What: {info['what']}")
        print(f"  Tools: {', '.join(info['tools'])}")
        for rule in info['rules']:
            print(f"    • {rule}")


def demo_junior_vs_senior():
    """Show phrase comparisons."""
    print("\n[Junior vs Senior Phrases]")
    print(f"  {'Junior':<35} {'Senior (use this)'}")
    print(f"  {'-'*35} {'-'*60}")
    for junior, senior in JUNIOR_VS_SENIOR_PHRASES[:5]:
        # Truncate for display
        print(f"  {junior[:33]:<35} {senior[:60]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Final Cheatsheet
# ─────────────────────────────────────────────────────────────────────────────

FINAL_TIPS = [
    "Always specify versions ('Python 3.12', 'Django 5.1.3') — shows expertise",
    "Mention numbers ('₹18K/mo', 'p99 200ms', '85% coverage') — credibility",
    "Talk trade-offs — every choice has cons, acknowledge them",
    "Real failures: 'Production X broke, I fixed by Y' — shows experience",
    "Migration paths: 'Currently X, would migrate to Y when Z' — pragmatic",
    "Cost-aware: mention cost optimization — shows business sense",
    "Avoid hype: don't say 'blockchain' or 'microservices for 3 services'",
    "Ask clarifying questions: 'What's the team size?', 'User scale?'",
    "Show monitoring obsession — SLO, error budget, alerts",
    "Security mindset: least privilege, encryption, audit logs",
]

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("DEPLOYMENT INTERVIEW Q&A PRACTICAL")
    print("=" * 60)

    print("\n[1] Architecture Answer Template (5-min answer):")
    print(textwrap.dedent(ARCHITECTURE_ANSWER_TEMPLATE)[:1200] + "...")

    demo_scaling_phases()

    print("\n[2] Zero-Downtime — 4 Pillars Summary:")
    pillars = [
        "1. Rolling deployment (minimumHealthyPercent: 100)",
        "2. Health checks (readiness 503 stops traffic, liveness restart)",
        "3. Graceful shutdown (--graceful-timeout 30)",
        "4. Backward-compatible migrations (expand-contract)",
    ]
    for p in pillars:
        print(f"  {p}")

    demo_incident_runbook()
    demo_secrets_model()

    print("\n[3] Debugging 'Slow Site' Layers:")
    layers = ["Network (CDN, ALB)", "Application (Gunicorn, code)",
              "Database (queries, indexes)", "External (3rd party APIs)"]
    for layer in layers:
        print(f"  → {layer}")

    demo_junior_vs_senior()

    demo_run_mock_interview()

    print("\n" + "=" * 60)
    print("FINAL INTERVIEW TIPS")
    print("=" * 60)
    for i, tip in enumerate(FINAL_TIPS, 1):
        print(f"  {i:>2}. {tip}")

    print("\n" + "=" * 60)
    print("PRACTICE PLAN:")
    print("  Week 1: Read 12_deployment_interview_qa.md fully")
    print("  Week 2: Practice each Q&A out loud (record yourself)")
    print("  Week 3: Mock interview with friend (use questions above)")
    print("  Week 4: Tailor answers to your actual project specifics")
    print("=" * 60)


if __name__ == "__main__":
    main()
