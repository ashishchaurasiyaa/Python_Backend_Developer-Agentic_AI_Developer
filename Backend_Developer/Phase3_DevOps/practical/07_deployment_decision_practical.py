"""
Phase3_DevOps — Deployment Decision Framework Practical
=========================================================
Topics covered:
  1. Django vs FastAPI decision matrix (programmatic scoring)
  2. AWS compute choice (EC2 vs ECS Fargate vs EKS vs Lambda)
  3. Database choice (RDS vs Aurora vs Aurora Serverless)
  4. Cost calculator for AWS deployment
  5. Multi-environment setup (dev/staging/prod) with Terraform
  6. Frontend deployment options (S3+CloudFront vs Amplify vs Nginx)
  7. CI/CD branching strategy implementation
  8. Disaster recovery RTO/RPO planning

Run:
  python 07_deployment_decision_practical.py
"""

import json
import os
from dataclasses import dataclass, field
from typing import Literal

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Django vs FastAPI Decision Calculator
# INTERVIEW: Choose based on workload nature, not "newer is better"
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProjectRequirements:
    """Input data for framework decision."""
    needs_admin_panel: bool
    workload_type: Literal["crud_erp", "ai_streaming", "websocket", "microservice", "mixed"]
    team_size: int
    expected_rps: int
    database_complexity: Literal["simple", "moderate", "complex_orm"]
    has_ai_features: bool


def decide_framework(req: ProjectRequirements) -> dict:
    """
    INTERVIEW: Programmatic framework selection.
    Returns recommendation + reasoning.
    """
    django_score = 0
    fastapi_score = 0
    reasons = []

    # Admin panel weight
    if req.needs_admin_panel:
        django_score += 3
        reasons.append("✅ Django Admin saves weeks of work")

    # Workload type
    workload_scores = {
        "crud_erp":      (3, 0),  # (django, fastapi)
        "ai_streaming":  (0, 4),
        "websocket":     (0, 3),
        "microservice":  (0, 3),
        "mixed":         (1, 1),
    }
    d_score, f_score = workload_scores[req.workload_type]
    django_score += d_score
    fastapi_score += f_score
    reasons.append(f"Workload '{req.workload_type}' → Django+{d_score}, FastAPI+{f_score}")

    # Team size
    if req.team_size > 5:
        django_score += 2
        reasons.append("✅ Django conventions help large teams")
    else:
        fastapi_score += 1
        reasons.append("✅ FastAPI less boilerplate for small teams")

    # RPS
    if req.expected_rps > 1000:
        fastapi_score += 3
        reasons.append("✅ FastAPI async wins at >1K RPS")
    elif req.expected_rps < 100:
        django_score += 1
        reasons.append("⚠️ At low RPS, framework choice less critical")

    # Database
    if req.database_complexity == "complex_orm":
        django_score += 2
        reasons.append("✅ Django ORM more mature for complex joins")
    elif req.database_complexity == "simple":
        fastapi_score += 1

    # AI features
    if req.has_ai_features:
        fastapi_score += 3
        reasons.append("✅ FastAPI async-native for LLM streaming, agents")

    # Decision
    winner = "Django + DRF" if django_score > fastapi_score else "FastAPI"

    return {
        "recommendation": winner,
        "django_score": django_score,
        "fastapi_score": fastapi_score,
        "reasons": reasons,
        "confidence": abs(django_score - fastapi_score) / max(django_score + fastapi_score, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: AWS Compute Decision Tree
# INTERVIEW: EC2 vs ECS Fargate vs EKS vs Lambda
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeploymentRequirements:
    """Input for AWS compute service selection."""
    traffic_pattern: Literal["sporadic", "steady", "burst", "massive"]
    monthly_budget_inr: int
    ops_expertise: Literal["minimal", "medium", "full_sre_team"]
    needs_websocket: bool
    needs_gpu: bool
    services_count: int
    latency_p99_target_ms: int


def decide_aws_compute(req: DeploymentRequirements) -> dict:
    """
    INTERVIEW: AWS compute service decision.
    Returns: recommended service + alternatives + cost estimate.
    """
    recommendation = None
    reasons = []
    cost_estimate = 0

    # ── Eliminate options that don't fit ───────────────────────────
    if req.needs_websocket:
        if req.traffic_pattern == "sporadic":
            recommendation = "API Gateway WebSocket + Lambda"
            reasons.append("WebSocket + sporadic → API Gateway WS pattern")
        else:
            reasons.append("❌ Lambda eliminated: WebSocket needs persistent connections")

    if req.needs_gpu:
        if req.services_count > 20:
            recommendation = "EKS with GPU node pool"
        else:
            recommendation = "ECS EC2 with GPU instance (p3/g4)"
        reasons.append("GPU → EC2 backed (Fargate has no GPU)")
        return _build_result(recommendation, reasons, cost_estimate, req)

    # ── Main decision tree ─────────────────────────────────────────
    if req.traffic_pattern == "sporadic" and req.latency_p99_target_ms > 500:
        recommendation = "Lambda + API Gateway"
        reasons.append("Sporadic traffic + p99 > 500ms → Lambda saves cost")
        cost_estimate = 500  # Pay-per-use

    elif req.monthly_budget_inr < 5000 and req.services_count <= 3:
        recommendation = "Single EC2 + Docker Compose"
        reasons.append("Tight budget + few services → EC2 minimal")
        cost_estimate = 3000

    elif req.services_count >= 30 or req.ops_expertise == "full_sre_team":
        recommendation = "EKS (Kubernetes)"
        reasons.append("Many services OR mature SRE → EKS pays off")
        cost_estimate = 40000

    elif req.traffic_pattern in ("steady", "burst") and req.services_count < 30:
        recommendation = "ECS Fargate ⭐"
        reasons.append("Steady traffic + medium scale = sweet spot for Fargate")
        cost_estimate = 16000

    else:
        recommendation = "ECS Fargate (default)"
        reasons.append("Default pragmatic choice")
        cost_estimate = 16000

    return _build_result(recommendation, reasons, cost_estimate, req)


def _build_result(recommendation, reasons, cost_estimate, req):
    return {
        "recommendation": recommendation,
        "reasons": reasons,
        "estimated_monthly_cost_inr": cost_estimate,
        "alternatives_considered": _get_alternatives(recommendation),
    }


def _get_alternatives(recommendation):
    """Return tradeoffs for alternatives not chosen."""
    alts = {
        "Single EC2 + Docker Compose": ["No HA", "Manual ops", "OK for MVP"],
        "ECS Fargate ⭐": ["EKS overkill", "Lambda wrong for steady traffic"],
        "EKS (Kubernetes)": ["Steep learning curve", "$73/mo control plane fee"],
        "Lambda + API Gateway": ["15-min timeout", "Cold starts", "No WebSocket"],
        "ECS EC2 with GPU instance (p3/g4)": ["GPU ops complexity"],
    }
    return alts.get(recommendation, [])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: AWS Cost Calculator
# INTERVIEW: Detailed breakdown — ask "how do you estimate cost?"
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AWSCostEstimate:
    """Monthly cost calculator for ECS Fargate Django/FastAPI deployment."""

    # ECS Fargate
    web_tasks: int = 2                # Always running
    worker_tasks: int = 2
    beat_tasks: int = 1
    task_cpu_units: int = 1024        # 1 vCPU
    task_memory_mb: int = 2048        # 2 GB

    # RDS
    rds_instance_class: str = "db.t3.small"
    rds_storage_gb: int = 20
    rds_multi_az: bool = True

    # ElastiCache
    redis_instance_class: str = "cache.t3.micro"

    # ALB
    alb_lcu_hours_month: int = 730    # 1 LCU continuous

    # S3 + CloudFront
    s3_storage_gb: int = 50
    cdn_data_transfer_gb: int = 100

    # CloudWatch
    log_ingestion_gb_month: int = 10
    metrics_count: int = 50

    def calculate(self) -> dict:
        """
        INTERVIEW: Itemize cost. Ask interviewer "should I optimize X?"
        Prices approximate ap-south-1 region, May 2024.
        """
        # ECS Fargate pricing (per task per month, 24/7)
        # 1 vCPU/2GB ≈ ₹1750/month (24/7)
        fargate_cost_per_task = 1750 * (self.task_cpu_units / 1024)
        total_tasks = self.web_tasks + self.worker_tasks + self.beat_tasks
        fargate_total = fargate_cost_per_task * total_tasks

        # RDS PostgreSQL Multi-AZ pricing
        rds_pricing = {
            "db.t3.micro":  1500,
            "db.t3.small":  3000,
            "db.t3.medium": 6000,
            "db.m6g.large": 12000,
        }
        rds_base = rds_pricing.get(self.rds_instance_class, 3000)
        if self.rds_multi_az:
            rds_base *= 2                # Multi-AZ doubles cost
        rds_storage = self.rds_storage_gb * 12   # GP3 storage
        rds_total = rds_base + rds_storage

        # ElastiCache
        redis_pricing = {
            "cache.t3.micro": 1200,
            "cache.t3.small": 2400,
            "cache.t3.medium": 4800,
        }
        redis_total = redis_pricing.get(self.redis_instance_class, 1200)

        # ALB (per LCU per hour)
        alb_total = 2000   # ~₹2000/mo for 1 LCU

        # S3 + CloudFront
        s3_storage_cost = self.s3_storage_gb * 2     # ₹2/GB/mo
        cdn_cost = self.cdn_data_transfer_gb * 8     # ₹8/GB
        cdn_total = s3_storage_cost + cdn_cost

        # CloudWatch
        log_cost = self.log_ingestion_gb_month * 50  # ₹50/GB ingested
        cw_total = log_cost + 500  # metrics + dashboards

        # Other (Route 53, ACM, etc.)
        other = 200

        breakdown = {
            "ECS Fargate (web+worker+beat)": round(fargate_total),
            "RDS PostgreSQL":               round(rds_total),
            "ElastiCache Redis":            round(redis_total),
            "ALB":                          round(alb_total),
            "S3 + CloudFront":              round(cdn_total),
            "CloudWatch (logs+metrics)":    round(cw_total),
            "Other (Route 53, etc.)":       round(other),
        }
        total = sum(breakdown.values())

        return {
            "monthly_cost_inr": total,
            "monthly_cost_usd": round(total / 83, 2),
            "breakdown": breakdown,
            "yearly_cost_inr": total * 12,
            "optimization_tips": self._optimization_tips(breakdown, total),
        }

    def _optimization_tips(self, breakdown: dict, total: int) -> list:
        tips = []
        if breakdown["ECS Fargate (web+worker+beat)"] > 5000:
            tips.append("Consider 1-year Savings Plan: -40% on Fargate cost")
        if breakdown["RDS PostgreSQL"] > 8000:
            tips.append("Consider 1-year RDS Reserved Instance: -30% cost")
        if breakdown["CloudWatch (logs+metrics)"] > 1500:
            tips.append("Archive logs > 30d to S3 (cheaper than CloudWatch)")
        if total > 30000:
            tips.append("Run Compute Optimizer to identify oversized resources")
        return tips


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Multi-Environment Terraform Pattern
# INTERVIEW: How to manage dev/staging/prod with shared modules
# ─────────────────────────────────────────────────────────────────────────────

TERRAFORM_MULTI_ENV_STRUCTURE = """\
# Terraform multi-environment structure (recommended)
# INTERVIEW: Separate state per env, shared modules
infra/
├── modules/                    # Reusable infrastructure modules
│   ├── ecs_app/
│   │   ├── main.tf            # Service, task def, target group
│   │   ├── variables.tf       # Configurable: cpu, memory, count
│   │   ├── outputs.tf
│   │   └── README.md
│   ├── rds/
│   ├── redis/
│   ├── networking/
│   └── secrets/
├── environments/
│   ├── dev/
│   │   ├── main.tf            # Use modules with dev sizing
│   │   ├── terraform.tfvars   # Dev-specific values
│   │   └── backend.tf         # state: s3://myapp-tf-state/dev
│   ├── staging/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── main.tf
│       ├── terraform.tfvars
│       └── backend.tf
└── shared/                     # Cross-env resources
    ├── route53.tf
    └── ecr.tf
"""

TERRAFORM_ENV_EXAMPLE = """\
# infra/environments/prod/main.tf
module "ecs_django" {
  source = "../../modules/ecs_app"

  environment   = "prod"
  app_name      = "myapp-django"
  desired_count = 2          # ⭐ Prod: HA from start
  cpu           = 1024       # 1 vCPU
  memory        = 2048       # 2 GB

  min_capacity = 2
  max_capacity = 10           # Auto-scale up to 10
  target_cpu   = 70

  image = "ECR_URL/myapp-django:latest"
  vpc_id     = module.networking.vpc_id
  subnet_ids = module.networking.private_subnets
}

# infra/environments/dev/main.tf — same module, smaller sizing
module "ecs_django" {
  source = "../../modules/ecs_app"

  environment   = "dev"
  desired_count = 1          # Single task (no HA needed)
  cpu           = 256        # 0.25 vCPU
  memory        = 512        # 0.5 GB

  min_capacity = 1
  max_capacity = 2           # Minimal scaling

  image = "ECR_URL/myapp-django:dev-latest"
  vpc_id     = module.networking.vpc_id
  subnet_ids = module.networking.private_subnets
}
"""

# Resource sizing per environment
ENV_SIZING = {
    "dev": {
        "ecs_cpu": 256, "ecs_memory": 512,
        "tasks": 1,
        "rds": "db.t3.micro", "rds_multi_az": False,
        "redis": "cache.t3.micro",
        "monthly_cost": 3000,
    },
    "staging": {
        "ecs_cpu": 512, "ecs_memory": 1024,
        "tasks": 1,
        "rds": "db.t3.small", "rds_multi_az": False,
        "redis": "cache.t3.micro",
        "monthly_cost": 8000,
    },
    "prod": {
        "ecs_cpu": 1024, "ecs_memory": 2048,
        "tasks": 2,          # Always 2 for HA
        "rds": "db.t3.small", "rds_multi_az": True,
        "redis": "cache.t3.small",
        "monthly_cost": 16000,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Frontend Deployment Decision
# INTERVIEW: S3+CloudFront vs Amplify vs Nginx container
# ─────────────────────────────────────────────────────────────────────────────

FRONTEND_OPTIONS_COMPARISON = """\
# INTERVIEW: Which to choose for React frontend deployment

| Option              | Cost      | Performance  | Best For           |
|---------------------|-----------|--------------|--------------------|
| S3 + CloudFront ⭐  | ₹500/mo   | 50ms global  | SPA (default)      |
| AWS Amplify         | ₹1500/mo  | Excellent    | Want fully managed |
| Nginx container ECS | ₹3000/mo  | Single region| AVOID — overkill   |
| Vercel/Netlify      | Free-₹2K  | Excellent    | If OK non-AWS      |

# Why S3 + CloudFront wins:
# 1. Cheapest (₹100-500/mo)
# 2. Global edge caching (CloudFront)
# 3. Scales infinitely (no servers)
# 4. HTTPS free via ACM
# 5. SPA routing via CloudFront 404→index.html rewrite
"""

FRONTEND_DEPLOY_SCRIPT = """\
#!/bin/bash
# scripts/deploy-frontend.sh — React SPA to S3 + CloudFront
# INTERVIEW: Cache strategy: assets immutable, index.html no-cache

set -e

BUCKET="myapp-frontend-prod"
DISTRIBUTION_ID="E1234ABCD"
BUILD_DIR="frontend/dist"

# ── 1. Build ──────────────────────────────────────────────────────
cd frontend
VITE_API_URL=https://api.yourapp.com npm run build

# ── 2. Upload assets with LONG cache (immutable) ──────────────────
# Vite generates hashed filenames → safe to cache forever
aws s3 sync "$BUILD_DIR/" "s3://$BUCKET/" \\
    --delete \\
    --cache-control "public, max-age=31536000, immutable" \\
    --exclude "index.html"

# ── 3. Upload index.html with NO cache (always latest) ────────────
# index.html references the hashed assets → must be fresh
aws s3 cp "$BUILD_DIR/index.html" "s3://$BUCKET/index.html" \\
    --cache-control "public, max-age=0, must-revalidate"

# ── 4. Invalidate CloudFront (only index.html) ────────────────────
aws cloudfront create-invalidation \\
    --distribution-id "$DISTRIBUTION_ID" \\
    --paths "/index.html"

echo "✅ Frontend deployed successfully"
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Disaster Recovery RTO/RPO Calculator
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DRRequirements:
    """Disaster recovery requirements."""
    rto_minutes: int          # Recovery Time Objective
    rpo_minutes: int          # Recovery Point Objective
    daily_revenue_inr: int    # For cost-benefit analysis


def recommend_dr_strategy(req: DRRequirements) -> dict:
    """
    INTERVIEW: Match DR strategy to business requirements + budget.
    Don't over-engineer — match what business needs.
    """
    recommendations = []
    monthly_cost_inr = 0

    # RDS strategy
    if req.rpo_minutes < 5:
        recommendations.append({
            "component": "Database",
            "strategy": "Multi-AZ + Cross-region read replica",
            "rto": "5 min", "rpo": "< 1 min",
            "cost_inr": 12000,
        })
        monthly_cost_inr += 12000
    elif req.rpo_minutes < 60:
        recommendations.append({
            "component": "Database",
            "strategy": "Multi-AZ + PITR backups",
            "rto": "15 min", "rpo": "< 5 min",
            "cost_inr": 6000,
        })
        monthly_cost_inr += 6000
    else:
        recommendations.append({
            "component": "Database",
            "strategy": "Single-AZ + nightly snapshots",
            "rto": "1-4 hours", "rpo": "24 hours",
            "cost_inr": 2000,
        })
        monthly_cost_inr += 2000

    # Compute strategy
    if req.rto_minutes < 15:
        recommendations.append({
            "component": "Compute",
            "strategy": "ECS Multi-AZ auto-scaling + warm standby in DR region",
            "rto": "5 min", "rpo": "0",
            "cost_inr": 10000,
        })
        monthly_cost_inr += 10000
    else:
        recommendations.append({
            "component": "Compute",
            "strategy": "ECS Multi-AZ (single region)",
            "rto": "10 min", "rpo": "0",
            "cost_inr": 0,  # included in base
        })

    # Storage
    recommendations.append({
        "component": "S3",
        "strategy": "Versioning + cross-region replication",
        "rto": "Instant", "rpo": "0",
        "cost_inr": 1000,
    })
    monthly_cost_inr += 1000

    # Justify cost
    monthly_downtime_cost = (req.daily_revenue_inr * req.rto_minutes) / (24 * 60) * 30
    cost_justified = monthly_cost_inr < monthly_downtime_cost

    return {
        "recommendations": recommendations,
        "total_dr_cost_monthly_inr": monthly_cost_inr,
        "estimated_downtime_cost_per_incident": round((req.daily_revenue_inr / 1440) * req.rto_minutes),
        "cost_justified": cost_justified,
        "verdict": "DR investment justified ✅" if cost_justified else "DR over-engineered ⚠️",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: CI/CD Branching Strategy
# ─────────────────────────────────────────────────────────────────────────────

CICD_BRANCH_MODEL = """\
# GitHub Flow + Protected Branches (recommended)
# INTERVIEW: When to use trunk-based vs GitFlow vs GitHub Flow?

main          ──●──────●──────●─── (production, auto-deploy on push)
                │      │      │
release/v1.2  ●─┘      │      │     (staging, manual cut from develop)
                       │      │
develop       ●────────●──────●─── (integration, auto-deploy to dev)
                       │      │
feature/abc   ●────────┘      │     (PR to develop)
feature/xyz   ●───────────────┘

# Workflow:
# 1. feature/* → PR → develop → tests pass → merge → auto-deploy DEV
# 2. develop → PR → release/v1.2 → auto-deploy STAGING
# 3. release/v1.2 → PR → main → MANUAL APPROVAL → deploy PROD
# 4. Tag v1.2.0 on main after deploy

# Trunk-based (alternative for high-velocity teams):
# - Only main branch + short-lived feature branches
# - All commits go to main daily
# - Feature flags for incomplete features
# - Each commit deployable

# When to use which?
# - GitHub Flow: 2-10 developers, weekly releases
# - Trunk-based: 10+ developers, multiple deploys/day
# - GitFlow (old): rarely needed, complex for most teams
"""

GITHUB_ACTIONS_ENV_DEPLOY = """\
# .github/workflows/deploy-prod.yml
# INTERVIEW: How to require manual approval for production deploys

name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: production               # ⭐ GitHub Environment
      url: https://api.yourapp.com
    # Settings → Environments → production → Required reviewers (2 people)

    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-prod
          aws-region: ap-south-1

      - name: Deploy
        run: # ... ECS update + smoke tests
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Demo Function — Run Decision Calculators
# ─────────────────────────────────────────────────────────────────────────────

def demo_framework_decision():
    """Test framework decision with 3 different project profiles."""
    print("\n[Framework Decision Demo]")

    scenarios = [
        ("YAM-like ERP", ProjectRequirements(
            needs_admin_panel=True,
            workload_type="crud_erp",
            team_size=5,
            expected_rps=200,
            database_complexity="complex_orm",
            has_ai_features=False,
        )),
        ("AI Agent backend", ProjectRequirements(
            needs_admin_panel=False,
            workload_type="ai_streaming",
            team_size=2,
            expected_rps=500,
            database_complexity="simple",
            has_ai_features=True,
        )),
        ("Realtime chat", ProjectRequirements(
            needs_admin_panel=False,
            workload_type="websocket",
            team_size=3,
            expected_rps=2000,
            database_complexity="moderate",
            has_ai_features=False,
        )),
    ]

    for name, req in scenarios:
        result = decide_framework(req)
        print(f"\n  Project: {name}")
        print(f"  → Recommendation: {result['recommendation']}")
        print(f"  → Confidence: {result['confidence']:.0%}")
        print(f"  → Scores: Django={result['django_score']}, FastAPI={result['fastapi_score']}")


def demo_aws_compute_decision():
    """Test AWS service decision with different scenarios."""
    print("\n[AWS Compute Decision Demo]")

    scenarios = [
        ("MVP startup", DeploymentRequirements(
            traffic_pattern="sporadic",
            monthly_budget_inr=3000,
            ops_expertise="minimal",
            needs_websocket=False,
            needs_gpu=False,
            services_count=2,
            latency_p99_target_ms=2000,
        )),
        ("Production SaaS", DeploymentRequirements(
            traffic_pattern="steady",
            monthly_budget_inr=20000,
            ops_expertise="medium",
            needs_websocket=False,
            needs_gpu=False,
            services_count=5,
            latency_p99_target_ms=300,
        )),
        ("Realtime AI chat", DeploymentRequirements(
            traffic_pattern="burst",
            monthly_budget_inr=50000,
            ops_expertise="medium",
            needs_websocket=True,
            needs_gpu=False,
            services_count=8,
            latency_p99_target_ms=500,
        )),
        ("Large enterprise", DeploymentRequirements(
            traffic_pattern="massive",
            monthly_budget_inr=200000,
            ops_expertise="full_sre_team",
            needs_websocket=True,
            needs_gpu=True,
            services_count=50,
            latency_p99_target_ms=100,
        )),
    ]

    for name, req in scenarios:
        result = decide_aws_compute(req)
        print(f"\n  Scenario: {name}")
        print(f"  → {result['recommendation']}")
        print(f"  → Estimated cost: ₹{result['estimated_monthly_cost_inr']:,}/mo")
        for reason in result['reasons'][:2]:
            print(f"    • {reason}")


def demo_cost_calculator():
    """Show cost breakdown for typical production setup."""
    print("\n[AWS Cost Calculator Demo]")

    cost = AWSCostEstimate(
        web_tasks=2,
        worker_tasks=2,
        beat_tasks=1,
        rds_instance_class="db.t3.small",
        rds_multi_az=True,
        redis_instance_class="cache.t3.micro",
        cdn_data_transfer_gb=100,
    )

    result = cost.calculate()
    print(f"\n  Monthly cost (INR): ₹{result['monthly_cost_inr']:,}")
    print(f"  Monthly cost (USD): ${result['monthly_cost_usd']}")
    print(f"  Yearly: ₹{result['yearly_cost_inr']:,}")
    print("\n  Breakdown:")
    for item, cost_inr in result['breakdown'].items():
        print(f"    {item:<35} ₹{cost_inr:>6,}/mo")
    print("\n  Optimization tips:")
    for tip in result['optimization_tips']:
        print(f"    • {tip}")


def demo_dr_strategy():
    """Test disaster recovery strategy."""
    print("\n[DR Strategy Demo]")

    scenarios = [
        ("Small SaaS", DRRequirements(rto_minutes=60, rpo_minutes=60, daily_revenue_inr=10000)),
        ("E-commerce", DRRequirements(rto_minutes=15, rpo_minutes=5, daily_revenue_inr=500000)),
        ("Banking", DRRequirements(rto_minutes=5, rpo_minutes=1, daily_revenue_inr=10000000)),
    ]

    for name, req in scenarios:
        result = recommend_dr_strategy(req)
        print(f"\n  {name}: RTO={req.rto_minutes}min, RPO={req.rpo_minutes}min")
        print(f"  → DR cost: ₹{result['total_dr_cost_monthly_inr']:,}/mo")
        print(f"  → Single incident cost: ₹{result['estimated_downtime_cost_per_incident']:,}")
        print(f"  → {result['verdict']}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

DECISION_QA = [
    ("Why ECS Fargate over EKS for medium-scale project?",
     "EKS: $73/mo control plane + steep learning curve + YAML complexity\n"
     "     Fargate: AWS-native, simpler, sweet spot for 5-50 services\n"
     "     Rule: EKS justified at 30+ services OR multi-cloud OR multi-team"),

    ("When to choose Lambda for FastAPI/Django?",
     "GOOD: Webhooks, S3 triggers, cron jobs, sporadic APIs\n"
     "     BAD: WebSocket (15-min limit), high-throughput, ERP CRUD\n"
     "     ANTI-PATTERN: Putting entire Django app on Lambda"),

    ("How to manage multi-environment infrastructure?",
     "1. Separate AWS accounts (best) OR separate VPCs (OK)\n"
     "     2. Terraform: shared modules + per-env state files\n"
     "     3. Naming convention: myapp-{env}-resource\n"
     "     4. Sizing: dev < staging < prod"),

    ("Should staging mirror production exactly?",
     "✅ Same infra topology (multi-AZ pattern, same services)\n"
     "     ❌ Same sizing (waste of money)\n"
     "     ✅ Same code paths (test feature flags, migrations)\n"
     "     ⚠️ Different DB data (anonymized prod dump for realistic testing)"),

    ("How to justify AWS over cheaper alternatives like Hetzner?",
     "Engineering time cost > infra savings\n"
     "     20 hrs/mo on Hetzner ops @ ₹2000/hr = ₹40K (vs ₹15K AWS savings)\n"
     "     AWS wins when: HA needed, team scales, compliance required\n"
     "     Hetzner wins: solo dev, <500 users, internal tools"),
]


def main():
    print("=" * 60)
    print("DEPLOYMENT DECISION FRAMEWORK PRACTICAL")
    print("=" * 60)

    demo_framework_decision()
    demo_aws_compute_decision()
    demo_cost_calculator()
    demo_dr_strategy()

    print("\n[Environment Sizing Reference]")
    print(f"  {'Env':<10} {'CPU':<8} {'Mem':<8} {'Tasks':<8} {'RDS':<15} {'Cost'}")
    print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*15} {'-'*10}")
    for env, sizing in ENV_SIZING.items():
        print(f"  {env:<10} {sizing['ecs_cpu']:<8} {sizing['ecs_memory']:<8} "
              f"{sizing['tasks']:<8} {sizing['rds']:<15} ₹{sizing['monthly_cost']:,}/mo")

    print("\n[Decision Framework Interview Q&A]")
    for q, a in DECISION_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("DECISION FRAMEWORK FILES:")
    print("  decision_framework.py     → programmatic decision logic")
    print("  cost_calculator.py        → estimate monthly AWS bill")
    print("  dr_planner.py             → RTO/RPO recommendations")
    print("  infra/environments/*/     → Terraform per-env configs")
    print("=" * 60)


if __name__ == "__main__":
    main()
