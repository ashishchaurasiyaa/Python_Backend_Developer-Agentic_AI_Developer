# DevOps — Multi-Region Deployment (Cross-Region Replication & Failover)
**DevOps · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **Region** = geographic area with multiple data centers (e.g., AWS us-east-1, ap-south-1)
- **AZ** = Availability Zone — isolated DC within a region
- **Multi-AZ** = HA within one region (basic — already covered)
- **Multi-region** = active in multiple regions globally
- **Active-active** = all regions serve traffic
- **Active-passive** = one region serves; others standby
- **RPO** = Recovery Point Objective — max acceptable data loss (e.g., 5 min)
- **RTO** = Recovery Time Objective — max acceptable downtime (e.g., 1 hour)
- **GTM/DNS routing** = Route53, Cloudflare — direct users to nearest region
- **Latency** = single-digit ms within region, 50-200ms cross-region

---

## Why Multi-Region?

```
Single region risks:                Multi-region benefits:
─────────────────                   ─────────────────────
• Region outage = total downtime    • Survive region failure
• High latency for global users     • Sub-100ms globally (CDN + edge)
• Compliance (data residency)       • GDPR/India DPDP compliance
• Capacity ceiling                  • Horizontal scale across regions
                                    • Better disaster recovery
```

**Real outages:**
- AWS us-east-1 (Dec 2021): 7-hour outage affected huge swath of internet
- GCP us-central1 (Jun 2024): control plane down
- Azure (multiple): 2022-2024 DNS issues

---

## Deployment Patterns

| Pattern | When | Cost | Complexity |
|---|---|---|---|
| **Single region multi-AZ** | Startups, regional product | $ | Low |
| **Active-passive (DR)** | Cost-conscious, lower RTO acceptable | $$ | Medium |
| **Active-active (read)** | Read-heavy, latency-sensitive | $$$ | High |
| **Active-active (RW)** | Global product, max availability | $$$$ | Very high |
| **Cell-based / sharded** | Massive scale (Slack, AWS) | $$$$$ | Extreme |

---

## Interview Questions & Answers

### Q1: Active-passive setup with AWS (Route53 failover)?

**Answer:** Primary region serves; standby ready, DNS flips on failure.

```
       ┌────────────────┐
       │  Route 53      │
       │  (health checks)│
       └────────┬───────┘
                │
       ┌────────┴───────┐
       │                │
    ACTIVE          PASSIVE
   (primary)       (standby)
  us-east-1        eu-west-1
       │                │
   ┌───┴───┐        ┌───┴───┐
   │ ALB   │        │ ALB   │ (running but no traffic)
   │ ECS   │        │ ECS   │
   │ RDS   │ ─────→ │ RDS   │ (read replica)
   │       │ sync   │       │
   └───────┘        └───────┘
```

**Route53 config (Terraform):**
```hcl
resource "aws_route53_health_check" "primary" {
  fqdn              = "api-primary.acme.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30
}

resource "aws_route53_record" "primary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.acme.com"
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.primary.id
  alias {
    name                   = aws_lb.primary.dns_name
    zone_id                = aws_lb.primary.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "secondary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.acme.com"
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "secondary"
  alias {
    name                   = aws_lb.secondary.dns_name
    zone_id                = aws_lb.secondary.zone_id
    evaluate_target_health = true
  }
}
```

**Trade-offs:**
- ✅ Cheap (passive region small)
- ✅ Simple operationally
- ❌ DNS TTL = recovery time (60-300s)
- ❌ Passive may be stale on data
- ❌ Single point: DNS provider

---

### Q2: Active-active with latency-based routing?

**Answer:** All regions serve; Route53/Cloudflare picks nearest.

```hcl
# Latency-based routing — automatic
resource "aws_route53_record" "active_active" {
  for_each = {
    us-east-1 = aws_lb.us_east.dns_name
    eu-west-1 = aws_lb.eu_west.dns_name
    ap-south-1 = aws_lb.ap_south.dns_name
  }

  zone_id = aws_route53_zone.main.zone_id
  name    = "api.acme.com"
  type    = "A"

  set_identifier = each.key
  latency_routing_policy { region = each.key }

  alias {
    name                   = each.value
    zone_id                = "..."
    evaluate_target_health = true
  }
}
```

**User in Mumbai → ap-south-1**
**User in New York → us-east-1**
**User in Paris → eu-west-1**

**With Cloudflare:**
```yaml
# Cloudflare uses Anycast → automatically nearest edge
# Load balancer pools per region:
pools:
  - name: us-east
    origins: [{address: us-east.acme.com}]
    monitor: health-check-id
  - name: eu-west
    origins: [{address: eu-west.acme.com}]
  - name: ap-south
    origins: [{address: ap-south.acme.com}]

steering_policy: geo  # or "dynamic_latency"
```

---

### Q3: Cross-region database replication strategies?

**Answer:** Choose based on consistency needs.

**A. Read replica (active-passive, async):**
```hcl
# AWS RDS Cross-Region Read Replica
resource "aws_db_instance" "primary" {
  identifier          = "acme-prod-primary"
  engine              = "postgres"
  instance_class      = "db.r6g.xlarge"
  allocated_storage   = 500
  backup_retention_period = 7
}

resource "aws_db_instance" "replica_eu" {
  identifier          = "acme-prod-eu-replica"
  replicate_source_db = aws_db_instance.primary.arn  # cross-region ARN
  instance_class      = "db.r6g.xlarge"
  # No backup_retention; inherits from source
}
```

**Lag:** typically 1-10 seconds across regions. Monitor:
```sql
-- On replica
SELECT now() - pg_last_xact_replay_timestamp() AS lag;
```

**B. Aurora Global Database (managed, <1s lag):**
```hcl
resource "aws_rds_global_cluster" "main" {
  global_cluster_identifier = "acme-global"
  engine                    = "aurora-postgresql"
  engine_version            = "16.4"
}

resource "aws_rds_cluster" "primary" {
  cluster_identifier = "acme-primary"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  region             = "us-east-1"
  # ... primary writer + readers
}

resource "aws_rds_cluster" "secondary" {
  cluster_identifier = "acme-secondary"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  region             = "eu-west-1"
  # Readers only (until failover)
}
```

**Aurora Global benefits:**
- Sub-second lag (typically 100-500ms)
- 1-minute failover (vs 10+ min for standard)
- Disaster recovery RPO < 1s, RTO < 1 min

**C. DynamoDB Global Tables (active-active, eventual consistency):**
```hcl
resource "aws_dynamodb_table" "users" {
  name             = "users"
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "user_id"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute { name = "user_id" type = "S" }

  replica {
    region_name = "us-east-1"
  }
  replica {
    region_name = "eu-west-1"
  }
  replica {
    region_name = "ap-south-1"
  }
}
```

**Write conflict resolution:** Last-write-wins (LWW) based on timestamp.

**D. Self-managed PostgreSQL streaming replication:**
```bash
# On replica
cat > /etc/postgresql/16/main/recovery.conf <<EOF
primary_conninfo = 'host=primary.acme.com port=5432 user=replicator password=xxx'
primary_slot_name = 'replica_eu_west_1'
EOF
```

---

### Q4: Data partitioning by region (sharding)?

**Answer:** Shard users by region — no cross-region writes.

```
USERS table sharded by user_region:
─────────────────────────────────
us-east-1: users with profile.country in ['US', 'CA', 'MX']
eu-west-1: users with profile.country in EU
ap-south-1: users with profile.country in ['IN', 'SG', 'AU']

Each region is SOURCE OF TRUTH for its users.
```

**Routing logic in app:**
```python
REGION_MAP = {
    "US": "us-east-1", "CA": "us-east-1", "MX": "us-east-1",
    "DE": "eu-west-1", "FR": "eu-west-1", "GB": "eu-west-1",
    "IN": "ap-south-1", "SG": "ap-south-1",
}

def get_user_region(country_code: str) -> str:
    return REGION_MAP.get(country_code, "us-east-1")  # default

def get_db_url(region: str) -> str:
    return {
        "us-east-1": "postgresql://us-db.acme.com/users",
        "eu-west-1": "postgresql://eu-db.acme.com/users",
        "ap-south-1": "postgresql://ap-db.acme.com/users",
    }[region]

# In FastAPI dependency
async def get_db_for_user(user_id: int):
    # JWT claim contains user's home region
    user = await load_user_from_cache(user_id)
    region = user.home_region
    return await get_db_connection(get_db_url(region))
```

**Cross-region reads** (e.g., admin dashboard):
```python
async def get_global_stats():
    results = await asyncio.gather(
        query_region("us-east-1", "SELECT COUNT(*) FROM orders"),
        query_region("eu-west-1", "SELECT COUNT(*) FROM orders"),
        query_region("ap-south-1", "SELECT COUNT(*) FROM orders"),
    )
    return {"us": results[0], "eu": results[1], "ap": results[2]}
```

**Use case:** GDPR (EU user data stays in EU), India DPDP (Indian data in India).

---

### Q5: Stateful services (cache, queues) across regions?

**Answer:** Region-local; replicate strategically.

**Redis:**
- Default: each region has independent Redis cluster
- **ElastiCache Global Datastore** for cross-region replication (1s lag)
- Cache misses fetch from region's DB

**Kafka:**
- **MirrorMaker 2** — replicate topics between Kafka clusters
- **Confluent Cloud** multi-region — built-in
```yaml
# MirrorMaker config
sources:
  - alias: us-east-1
    bootstrap.servers: kafka.us-east-1.acme.com:9092
destinations:
  - alias: eu-west-1
    bootstrap.servers: kafka.eu-west-1.acme.com:9092

topics:
  - .*\.orders$    # replicate all orders topics

groups:
  - .*             # replicate consumer group offsets
```

**S3:**
- **Cross-Region Replication (CRR)** automatic
```hcl
resource "aws_s3_bucket_replication_configuration" "main" {
  bucket = aws_s3_bucket.primary.id

  rule {
    id       = "replicate-to-eu"
    status   = "Enabled"
    destination {
      bucket        = aws_s3_bucket.eu.arn
      storage_class = "STANDARD_IA"
      replica_kms_key_id = aws_kms_key.eu.arn
    }
  }
}
```

**Object storage strategy:**
- Original upload to region-A
- Replicate to region-B for resilience
- Serve via CloudFront/Cloudflare CDN globally

---

### Q6: Application deployment — same code, multi-region?

**Answer:** Single Docker image, region-aware config via env.

```python
# config.py
import os

REGION = os.environ["AWS_REGION"]  # auto-injected on ECS/EKS

DATABASE_URL = {
    "us-east-1": os.environ["DB_URL_US_EAST_1"],
    "eu-west-1": os.environ["DB_URL_EU_WEST_1"],
    "ap-south-1": os.environ["DB_URL_AP_SOUTH_1"],
}[REGION]

REDIS_URL = os.environ[f"REDIS_URL_{REGION.upper().replace('-', '_')}"]

# Cross-region service URLs (only when needed)
GLOBAL_AUTH_URL = os.environ.get("GLOBAL_AUTH_URL")  # one auth service worldwide
```

**Terraform per-region (with workspaces):**
```bash
# Bootstrap regions
terraform workspace new us-east-1
terraform workspace new eu-west-1
terraform workspace new ap-south-1

# Apply to specific region
terraform workspace select us-east-1
terraform apply -var-file=us-east-1.tfvars
```

**Better: separate state files, modular code:**
```
infra/
├── modules/
│   ├── api/                  # reusable app stack
│   ├── database/
│   └── cache/
├── envs/
│   ├── us-east-1/
│   │   ├── main.tf
│   │   ├── backend.tf       # state in S3 us-east-1
│   │   └── terraform.tfvars
│   ├── eu-west-1/
│   │   └── ...
│   └── ap-south-1/
│       └── ...
```

---

### Q7: Failover testing (game day)?

**Answer:** Regular drills — simulate region failure.

```python
# Chaos script: simulate primary region failure
import boto3

def simulate_region_failure(region: str):
    """Disable health checks → Route53 marks region unhealthy."""
    cloudwatch = boto3.client("cloudwatch", region_name=region)

    # 1. Force ALB to return 503
    cloudwatch.set_alarm_state(
        AlarmName="api-region-health",
        StateValue="ALARM",
        StateReason="Game day exercise",
    )

    # OR: actually break it
    # asg.update_auto_scaling_group(DesiredCapacity=0)  # ← real chaos

    # Watch:
    # - Route53 fails over (60-300s)
    # - Secondary region absorbs traffic
    # - Customer-facing impact (should be near-zero)

simulate_region_failure("us-east-1")
```

**Checklist before game day:**
- [ ] Inform team + customers (if customer-impacting)
- [ ] Have rollback plan
- [ ] Monitoring dashboards open
- [ ] Pager rotation active
- [ ] Database lag confirmed < RPO target
- [ ] Document timeline for postmortem

**Run frequency:** Quarterly minimum, monthly ideal.

---

### Q8: Cost optimization for multi-region?

**Answer:** Active-active is 2-3x cost. Mitigate.

| Cost driver | Mitigation |
|---|---|
| Compute in 2+ regions | Right-size; spot instances for non-critical |
| Data transfer between regions | VPC peering; minimize cross-region calls |
| Cross-region DB sync | Use Aurora Global (cheaper than self-managed) |
| Duplicate S3 storage | Glacier/IA in passive region |
| Duplicate logs | Centralize logging in one region |
| Idle passive resources | Use minimal capacity; scale up on failover |
| ALB per region | Cheaper alt: Cloudflare Load Balancer |

**Cost estimate (rough):**
```
Single region (us-east-1):     $10K/mo (baseline)
Active-passive (2 regions):    $13-15K/mo (+30-50%)
Active-active (3 regions):     $22-25K/mo (+120-150%)
```

**ROI justification:**
- Avoid 1 outage per year × $X downtime cost
- Open new markets (data residency unlocks customers)
- Reduce latency = better conversion

---

## Decision Tree

```
Q: Annual revenue at risk if region fails?
├── < $100K → Single region, multi-AZ
├── $100K-1M → Active-passive (warm standby)
├── $1M-10M → Active-active read; primary write
└── > $10M → Full active-active multi-region

Q: Compliance requires data residency?
├── Yes (GDPR, India DPDP, China) → Sharded by region (Q4)
└── No → Replicated everywhere

Q: User base distribution?
├── Single country → Region with multi-AZ
├── Few countries → 2-3 regions latency-routed
└── Global → 5+ regions + CDN + edge
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| DNS TTL too high → slow failover | Set TTL to 30-60s |
| Stateful WebSocket connections drop on failover | Use sticky sessions per region |
| Background jobs only run in one region | Use distributed scheduler (Temporal, Airflow) |
| Cross-region writes cause inconsistency | Avoid; use sharding |
| Logs scattered across regions | Centralize to Datadog/Loki |
| Secrets per region | Use AWS Secrets Manager replicated secrets |
| Forgot to test failover | Game day quarterly |
| Aurora Global writer can't be promoted fast | Manual procedure documented |
| Cache invalidation across regions | Use Redis pub/sub or app-level events |
| Region-specific bugs (Indian datetime handling) | E2E tests per region |

---

## Senior-level Checklist

- [ ] **RPO/RTO** documented and tested
- [ ] **Architecture diagram** with all cross-region flows
- [ ] **Route53 health checks** + failover records configured
- [ ] **Database replication** strategy chosen (read replica / Aurora Global / DynamoDB GT)
- [ ] **Replication lag** monitored + alerts < RPO
- [ ] **CDN/edge caching** for static + API responses
- [ ] **Terraform modules** reusable across regions
- [ ] **Region-aware config** in app code
- [ ] **Centralized logging** (single Datadog/CloudWatch account)
- [ ] **Cross-region IAM** roles/policies
- [ ] **Backup** to different region (cold)
- [ ] **Game day** quarterly; documented runbook
- [ ] **Cost** budgets per region with alerts
- [ ] **DNS TTL** appropriately low (30-60s)
- [ ] **Stateful service** strategy (cache, queue, WebSocket)
- [ ] **Data residency** compliance verified

---

## Related Docs
- `04_aws_basics.md` — AWS fundamentals
- `06_kubernetes_helm.md` — K8s multi-cluster
- `07_terraform.md` — IaC for multi-region
- `13_gitops_argocd_flux.md` — multi-cluster GitOps
- `14_chaos_engineering.md` — chaos for resilience
- `16_sre_practices_sli_slo.md` — SLOs across regions
- `00_Year0-2_Junior/04_Database_SQL/09_postgresql_ha_read_replicas.md` — DB replication deep

## External References
- AWS Multi-Region Reference Architecture: https://docs.aws.amazon.com/whitepapers/latest/aws-multi-region-fundamentals/
- GCP Multi-region: https://cloud.google.com/architecture/disaster-recovery
- Aurora Global Database: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html
