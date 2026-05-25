# Deployment Interview Q&A — Real Senior-Level Questions

## Quick Concepts
- **Interviewer ki expectation** = sirf "Docker use karta hu" nahi, full architecture + trade-offs + production gotchas batao
- **Story-based answer** = "Maine X karne ki koshish ki, Y problem aayi, Z se solve kiya" — STAR method
- **Numbers use karo** = "₹16K/mo cost", "p99 latency 200ms", "500 RPS handle karta hai" — specifics impress karte hain
- **Trade-offs batao** = har choice ka pro/con — perfectionist nahi pragmatic engineer dikho
- **Failure stories** = "Production mein X break hua, maine debug karke Y fix kiya" — interviewer ko real experience dikhana

---

## Section 1: Architecture & Design Questions

### Q1: "Walk me through how you deployed your last project end-to-end"

**Answer Framework (5 min answer):**

> "Sure, maine recently ek **Django-based ERP system** deploy kiya for inventory + jobsite management. Stack tha — Django 5 + DRF + PostgreSQL with PostGIS, Redis cache + Celery, React frontend.
>
> **Architecture-wise:**
> - **Frontend** static React build S3 par hosted hai, CloudFront ke through globally distributed.
> - **Backend** AWS ECS Fargate par chalta hai — 2-10 tasks auto-scale, ALB ke peeche.
> - **Database** RDS PostgreSQL Multi-AZ for HA, PostGIS extension enabled for spatial queries.
> - **Background jobs** Celery workers separate ECS service mein, Celery Beat ek single instance.
> - **Static/media files** django-storages se directly S3 mein.
>
> **CI/CD:** GitHub Actions — push to main triggers tests → Docker build → push to ECR → Alembic migrations as one-off ECS task → rolling deploy of web service. OIDC use kiya AWS auth ke liye, koi long-lived keys nahi.
>
> **Observability:** CloudWatch Logs + structlog JSON logs, Sentry error tracking, Prometheus metrics endpoint scraped by AWS Managed Prometheus.
>
> **Cost:** Production ~₹18K/mo, staging ~₹3K/mo on single EC2.
>
> **One tricky part:** WeasyPrint PDF generation Django web container me karne se memory spike ho rahe the — maine isko Celery worker me move kiya with separate `high_priority` queue."

**Why this works:**
- Specific tech versions
- Architecture flow clear
- Numbers + costs mentioned
- One real problem + solution
- Total < 5 min

---

### Q2: "How would you scale this to 100K daily active users from current 5K?"

**Answer:**

> "Multi-step approach lunga, bottleneck identify karke incrementally:
>
> **Phase 1 — Quick wins (week 1):**
> 1. Profile current bottlenecks via CloudWatch + django-silk → likely DB queries
> 2. Add database indexes on frequent WHERE/ORDER BY columns
> 3. Enable Redis caching for read-heavy endpoints (`@cache_page` decorator)
> 4. Increase ECS Fargate task count, tune Gunicorn workers
>
> **Phase 2 — Architecture improvements (week 2-4):**
> 5. **Read replicas** — RDS read replica for analytics queries, Django DB router se separate
> 6. **Connection pooling** — RDS Proxy use karenge to handle connection spikes
> 7. **CDN aggressive caching** — CloudFront pe API GET responses cache (with proper cache headers)
> 8. **Database queries optimize** — N+1 fix with select_related/prefetch_related
> 9. **Celery scale** — separate queues for different priority tasks, auto-scale based on queue depth
>
> **Phase 3 — Scaling-out (month 2):**
> 10. **Database** — upgrade RDS db.t3.small → db.m6g.xlarge (or Aurora if RPS very high)
> 11. **Sharding strategy** — if certain tables huge (e.g., audit logs), partition by date
> 12. **Microservices extraction** — extract heavy modules (PDF generation, reporting) as separate FastAPI services
> 13. **Multi-region** — read replicas in another region if global users
>
> **Phase 4 — Optimization (ongoing):**
> 14. Move static assets to S3 + CloudFront fully
> 15. Image optimization at upload time (Pillow → WebP)
> 16. Implement HTTP/2 server push
> 17. Database query plans review monthly
>
> **Monitoring throughout:** p99 latency target < 300ms, error rate < 0.1%, DB CPU < 70%.
>
> **Cost impact:** 5K → 100K users = ~₹18K/mo → ~₹80K/mo (database biggest jump)."

---

### Q3: "How do you achieve zero-downtime deployment?"

**Answer:**

> "Zero-downtime ke 4 pillars hain:
>
> **1. Rolling deployment (orchestrator level)**
> ECS Fargate me `deploymentConfiguration` set karta hu:
> ```
> minimumHealthyPercent: 100  (kabhi bhi 100% capacity)
> maximumPercent: 200         (new tasks aate hain pehle, fir old hatte hain)
> ```
> Iska matlab: 2 tasks chal rahe hain → deploy time pe 4 tasks (2 old + 2 new), naye healthy hone par purane terminate.
>
> **2. Health checks properly configured**
> - **Readiness probe:** `/health/ready` — DB + Redis check karta hai. Tabhi traffic mile.
> - **Liveness probe:** `/health` — sirf process alive check.
> - ALB target group health check 30s interval, 3 retries before unhealthy.
>
> **3. Graceful shutdown**
> Gunicorn me `--graceful-timeout 30` — active requests ko 30s complete hone diya jata hai before SIGKILL.
> Django me `SIGTERM` handle karke open DB transactions complete.
>
> **4. Database migrations carefully**
> Migrations always **backward-compatible** likhi jaati hain (expand-contract pattern):
> - **Release N:** Add new column as nullable
> - **Release N:** Dual-write code (old + new field)
> - **Release N+1:** Backfill data
> - **Release N+1:** Read from new field
> - **Release N+2:** Drop old column
>
> Migration as one-off ECS task **before** service update — service deploy tabhi hota hai jab migration success.
>
> **Bonus:**
> - **Feature flags** (LaunchDarkly/Unleash) — gradual rollout (1% → 10% → 50% → 100%)
> - **Canary deployment** — Argo Rollouts/Flagger se 5% traffic new version pe, metrics monitor, auto-rollback on error spike
> - **Database connection draining** — old pods Redis se publish karte hain 'shutting down', new pods consume bhejna stop"

---

### Q4: "Your production DB crashes at 3 AM. Walk me through your incident response."

**Answer:**

> "PagerDuty alert aaya — CloudWatch RDS instance unhealthy. Yeh mera **incident response runbook** hai:
>
> **0-2 minutes — Acknowledge + Triage**
> 1. Acknowledge alert in PagerDuty (stops escalation)
> 2. Slack #incidents channel pe declare karta hu: 'Investigating RDS issue. ETA 10 min.'
> 3. Open CloudWatch dashboard — check RDS metrics:
>    - CPU spike? Memory exhausted? Connection count maxed?
>    - Disk space exhausted?
>    - IOPS saturated?
>
> **2-5 minutes — Diagnose**
> 4. CloudWatch Logs Insights query: recent errors before crash
>    ```
>    fields @timestamp, @message
>    | filter @timestamp > ago(15m)
>    | filter @message like /ERROR|FATAL/
>    ```
> 5. RDS event subscription — check for AWS-side failover events
> 6. Application logs (Sentry) — sudden error spike?
>
> **5-15 minutes — Mitigate**
> 7. **If Multi-AZ:** Likely already failed over to standby. Verify new endpoint accessible. Application should auto-reconnect via DNS.
> 8. **If single-AZ:** Initiate manual failover or restore from PITR snapshot.
> 9. **If connection pool exhausted:** Restart ECS tasks to reset connections.
> 10. **If disk full:** Increase storage immediately (`aws rds modify-db-instance --allocated-storage 50`).
>
> **15-30 minutes — Verify recovery**
> 11. Smoke test critical endpoints
> 12. Check error rate dropped below normal
> 13. Customer-facing status page update (if applicable)
>
> **Post-incident (next day):**
> 14. **Blameless postmortem** — what happened, why, action items
> 15. **Root cause analysis** — was it query, deploy, infra issue?
> 16. **Preventive measures** — add CloudWatch alarm earlier, improve monitoring, scale up
>
> **Real example:** Mere project me ek baar disk space exhausted ho gaya tha — pg_stat_statements + WAL logs had grown 80GB. Fix: enabled automated WAL archival to S3, added disk space alarm at 75% threshold. Future incidents prevent ho gaye."

---

## Section 2: Specific Technical Questions

### Q5: "Why ECS Fargate over EC2 or EKS?"

**Answer:**

> "Maine yeh decision **trade-offs analyze karke** liya:
>
> **EC2 self-managed Docker Compose ke against:**
> - Single point of failure → multi-AZ needed → manual ALB + multi-instance setup complex
> - No auto-scaling without ASG
> - Manual OS patches, kernel updates — ops overhead
> - Container crashes manual restart
>
> **EKS ke against:**
> - Cluster fee $73/month base
> - Steep learning curve — Deployment, Service, Ingress, HPA, NetworkPolicy YAMLs
> - Multi-team / 50+ services scale par make sense karta hai, mere 5 services ke liye overkill
> - Hiring K8s engineers expensive
>
> **Fargate ke pros:**
> - No EC2 management
> - Task-level auto-scaling
> - AWS-native — IAM, Secrets Manager, CloudWatch direct integration
> - Pay-per-second billing
> - Sweet spot for 5-50 services
>
> **Fargate ke cons (I'm aware):**
> - 2x cost of EC2 at same compute
> - No GPU support (need EC2 for AI inference)
> - 30-second cold start vs <1s on warm EC2
> - Limited to AWS
>
> **Migration path:** Agar future me hum 50+ services + multi-team + need ArgoCD/Istio/KEDA — to EKS migrate karenge. Abhi YAGNI principle."

---

### Q6: "How do you manage secrets in production?"

**Answer:**

> "**Layered approach:**
>
> **Layer 1: Storage**
> - **AWS Secrets Manager** for production secrets (DB password, API keys, JWT signing keys)
> - **AWS Parameter Store** for config (non-sensitive but env-specific)
> - **Never** in: Git, env files committed, Docker images, hardcoded
>
> **Layer 2: Injection**
> ECS task definition mein secrets reference karta hu:
> ```json
> 'secrets': [{
>   'name': 'DB_PASSWORD',
>   'valueFrom': 'arn:aws:secretsmanager:..:secret:myapp/prod/db-password'
> }]
> ```
> Container start hote hi Fargate Secrets Manager se fetch karke env var inject karta hai.
>
> **Layer 3: Rotation**
> - DB password — Secrets Manager native rotation (Lambda function rotates every 30 days)
> - API keys — manually rotate quarterly with feature flag (old + new accept for 24h overlap)
> - JWT signing keys — rotate via key versioning (`kid` header in JWT)
>
> **Layer 4: Access control**
> - ECS task role minimal permissions — sirf specific secret ARNs pe `secretsmanager:GetSecretValue`
> - IAM policies follow least privilege
> - Secrets Manager resource policy restricts cross-account access
>
> **Layer 5: Audit**
> - CloudTrail logs every secret access
> - GuardDuty alerts on suspicious access patterns
>
> **For local dev:**
> - `.env.example` committed (template)
> - `.env` in `.gitignore` (actual values)
> - Use `direnv` for auto-loading
> - For team: 1Password / Doppler for sharing
>
> **Anti-patterns I avoid:**
> - ❌ Secrets in Docker `ENV` (visible in `docker history`)
> - ❌ Secrets in K8s ConfigMap (only Secrets, base64 ≠ encrypted)
> - ❌ Long-lived AWS access keys — use OIDC for CI/CD"

---

### Q7: "Walk me through a CI/CD pipeline for production deployment"

**Answer:**

> "**6-stage pipeline** in GitHub Actions:
>
> **Stage 1: Pre-merge (PR checks)**
> - Lint (Ruff)
> - Type check (mypy)
> - Unit tests with coverage > 80%
> - Security scan (bandit, safety)
> - Docker build dry-run
> *Fails block PR merge.*
>
> **Stage 2: Post-merge to main**
> - Run full test suite with PostgreSQL + Redis services
> - Integration tests against test DB
> - Generate OpenAPI schema for frontend types
>
> **Stage 3: Build + Push**
> - Build Docker image with multi-stage Dockerfile
> - Tag with `git.sha` and `latest`
> - Push to ECR (use OIDC, no long-lived keys)
> - Scan image for vulnerabilities (Trivy/Inspector)
>
> **Stage 4: Migrations**
> - Run Alembic/Django migrations as **one-off ECS task**
> - Wait for exit code 0
> - **Fail entire pipeline if migration fails** (don't deploy)
>
> **Stage 5: Deploy**
> - ECS update-service with `--force-new-deployment`
> - Rolling update with new task definition
> - Wait for `services-stable` (all tasks healthy)
> - Health check verification post-deploy
>
> **Stage 6: Post-deploy**
> - Smoke tests against production
> - Slack notification (success/failure)
> - If failure → auto-rollback to previous task def
> - Sentry release marker
>
> **Branch strategy:**
> - `feature/*` → PR → `develop` → auto-deploy to **dev** environment
> - `develop` → PR → `release/v1.2` → auto-deploy to **staging**
> - `release/*` → PR → `main` → **manual approval** → deploy to **prod**
>
> **Rollback:**
> - `workflow_dispatch` workflow accepts old task def revision
> - One-click rollback: `aws ecs update-service --task-definition myapp:42`
> - DB rollback only if backward-compatible (otherwise restore from PITR)
>
> **Specific improvements I'd add:**
> - **Canary deployment** with Argo Rollouts — 5% traffic, monitor, full rollout
> - **Feature flags** to decouple deploy from release
> - **Trunk-based development** for fast-moving teams (no long-lived release branches)"

---

### Q8: "How do you handle observability — logs, metrics, traces?"

**Answer:**

> "**3 pillars of observability:**
>
> **1. Logs — structured + centralized**
> - `structlog` for JSON logs in Python
> - Every log line has `request_id`, `user_id`, `timestamp`, `level`
> - Container writes to stdout → ECS auto-pushes to CloudWatch Logs
> - **Query example:** Find all 500 errors for user X in last hour
>   ```
>   fields @timestamp, @message
>   | filter user_id = '123' and status = 500
>   | sort @timestamp desc
>   ```
> - Retention: 30 days CloudWatch, 1 year archived to S3 (cheaper)
>
> **2. Metrics — Prometheus + CloudWatch**
> - Application exposes `/metrics` (Prometheus format) — Counters, Histograms
> - AWS Managed Prometheus scrapes every 15s
> - Grafana for visualization
> - Key metrics tracked:
>   - **RED** — Rate, Errors, Duration per endpoint
>   - **USE** — Utilization, Saturation, Errors of resources (CPU, mem, DB connections)
>   - Business metrics — orders/min, signup rate, payment failures
>
> **3. Traces — distributed tracing**
> - OpenTelemetry SDK in Python
> - Trace ID propagated across services via headers
> - Backend: AWS X-Ray (cheap) or Jaeger/Tempo (self-hosted)
> - Critical for microservices — see which service slow
>
> **4th pillar I add: Errors**
> - **Sentry** for real-time error tracking
> - Stack traces with source context
> - Release tagging — which version introduced bug
> - User context (PII-safe)
>
> **Alerting strategy:**
> - **Sev-1 (PagerDuty page):** 5xx rate > 1%, RDS CPU > 90%, queue depth > 5000
> - **Sev-2 (Slack):** p99 latency > 2s, disk > 75%, deploy failure
> - **Sev-3 (Email):** Cost anomaly, dependency vulnerability
>
> **SLO/SLA framework:**
> - **SLI:** Availability (% successful requests), latency p99
> - **SLO:** 99.9% availability monthly, p99 < 500ms
> - **Error budget:** 0.1% downtime = 43 min/month — track burn rate
>
> **Cost note:** Observability tax ~5-10% of infra cost. Worth every penny — without it you're flying blind."

---

### Q9: "How do you secure your AWS deployment?"

**Answer:**

> "**Defense-in-depth — 6 layers:**
>
> **Layer 1: Network**
> - **VPC** with public + private subnets
> - **ALB** in public subnet (only port 443 open to internet)
> - **ECS tasks** in private subnets (no public IP)
> - **RDS/Redis** in private subnets (only ECS SG can access)
> - **NACLs** as additional firewall layer
> - **NAT Gateway** for outbound internet from private subnets
>
> **Layer 2: IAM (least privilege)**
> - **No root account use** — IAM users with MFA
> - **ECS task role** — sirf specific S3 bucket, Secrets Manager ARNs
> - **OIDC for CI/CD** — no long-lived keys
> - **IAM Access Analyzer** weekly review
>
> **Layer 3: Data**
> - **Encryption at rest** — RDS, EBS, S3 all encrypted (AWS-managed KMS keys)
> - **Encryption in transit** — TLS 1.2+ everywhere (ALB, RDS, Redis)
> - **S3 bucket policies** — block public access by default
> - **Backup encryption** — same KMS keys
>
> **Layer 4: Application**
> - **HTTPS only** — `SECURE_SSL_REDIRECT=True`, HSTS headers
> - **JWT with short expiry** (15 min access, 7d refresh)
> - **Rate limiting** at ALB (AWS WAF) + application (django-ratelimit)
> - **CORS** restrictive — exact origin match
> - **SQL injection** — ORM only, parameterized queries
> - **XSS** — Django auto-escapes templates, React JSX auto-escapes
> - **CSRF** — Django CSRF middleware
> - **Security headers** — CSP, X-Frame-Options, X-Content-Type-Options
>
> **Layer 5: Container security**
> - **Non-root user** in Docker (`USER app`)
> - **Distroless or slim base images**
> - **Vulnerability scanning** — Trivy on every build, ECR Inspector
> - **No secrets in image layers** — buildkit secrets mount
> - **Read-only filesystem** where possible
>
> **Layer 6: Monitoring + Audit**
> - **CloudTrail** — every AWS API call logged
> - **GuardDuty** — threat detection (ML-based)
> - **AWS Config** — compliance rules (e.g., S3 must be encrypted)
> - **Security Hub** — central security dashboard
> - **Sentry** — application error monitoring
>
> **Compliance considerations:**
> - GDPR — PII encryption, right-to-delete implemented
> - SOC2 — audit logs, access reviews, incident response runbooks
> - PCI-DSS (if payments) — Stripe/Razorpay tokenization, no card data stored
>
> **Common attacks defended:**
> - **DDoS** → CloudFront + WAF + AWS Shield Standard
> - **SQL injection** → ORM + Django auto-escape
> - **Credential stuffing** → rate limit + captcha + breach DB check
> - **JWT theft** → short expiry + IP binding + refresh rotation
> - **SSRF** → outbound traffic restrictions in security groups"

---

### Q10: "What's your cost optimization strategy?"

**Answer:**

> "**Continuous cost optimization** — 5 strategies:
>
> **1. Right-sizing**
> - Monthly review of CloudWatch — CPU/memory utilization < 30% → downsize
> - **AWS Compute Optimizer** recommendations
> - ECS task definitions adjusted based on actual usage
>
> **2. Auto-scaling effectively**
> - Min capacity = baseline traffic
> - Max capacity = peak + 20%
> - **Scale down aggressive** off-peak (night hours for B2B)
> - Schedule-based scaling for predictable patterns
>
> **3. Reserved Instances / Savings Plans**
> - 1-year Compute Savings Plan for predictable Fargate workload (40% savings)
> - RDS Reserved Instances (30-50% savings)
> - **Avoid lock-in:** 1-year (not 3-year) until usage stable
>
> **4. Storage optimization**
> - **S3 lifecycle policies:**
>   - Standard → Standard-IA after 30 days
>   - → Glacier after 90 days
>   - → Delete after 7 years (compliance)
> - **RDS storage** GP3 (cheaper than GP2 for same IOPS)
> - **CloudWatch Logs** retention 30d (then archive to S3)
> - **ECR lifecycle** — keep last 50 images, delete older
>
> **5. Network costs (often ignored)**
> - **Data transfer between AZs:** $0.01/GB — costly at scale
> - **Use VPC endpoints** for S3, DynamoDB (free intra-VPC)
> - **CloudFront** reduces S3 egress costs
> - **Avoid cross-region** unless necessary
>
> **6. Monitoring + alerts**
> - **AWS Budgets** — alert at 80%, 100%, 120% of monthly budget
> - **Cost anomaly detection** — ML-based alerts on unusual spend
> - **Daily cost dashboard** for team visibility
> - **Tag everything** — costs allocated per project/team
>
> **Real wins from past:**
> - Switched ALB to NLB for internal services — saved ₹1500/mo (no L7 features needed)
> - Moved RDS dev environment to Aurora Serverless — saved ₹3000/mo
> - Consolidated 3 small RDS to 1 with multiple DBs — saved ₹4500/mo
> - CloudFront cache hit rate 80% → 95% by tuning cache headers — reduced origin requests, saved ₹2000/mo
>
> **Cost philosophy:** Don't over-engineer for cost optimization early. Get product working first, optimize when monthly bill > ₹50K. Below that, optimization time worth more than savings."

---

## Section 3: Trick / Trade-off Questions

### Q11: "Your manager says 'Why are we paying ₹20K/mo for AWS? We can just use a ₹3K Hetzner VPS'. How do you respond?"

**Answer:**

> "Great question — main bhi yeh sochta tha pehle. Honest answer **'it depends'** hai:
>
> **Hetzner VPS makes sense when:**
> - Single developer / small team (< 3 people)
> - < 1000 daily active users
> - Internal tools / non-critical apps
> - Downtime tolerable (1-2 hrs/month OK)
> - You enjoy ops work
>
> **AWS makes sense when:**
> - **Customer-facing app** — 1 hour downtime = lost revenue + reputation
> - **Multi-AZ HA needed** — Hetzner single datacenter
> - **Auto-scaling** — manual scaling on VPS is painful
> - **Compliance** — SOC2/HIPAA easier with AWS
> - **Team scaling** — 5+ engineers, need RBAC, IAM, audit logs
> - **Integration** — need S3, RDS, SQS, Bedrock — Hetzner doesn't have
>
> **Real cost breakdown:**
> ```
> Hetzner CX31 (4 vCPU, 8GB):      ₹1500/mo
> + DB (manual install):             ₹0
> + Backups (manual to S3):          ₹500
> + Monitoring (manual Grafana):     time cost
> Total visible: ₹2000/mo
> Total real (with ops time): ₹2000 + 20 hrs/mo eng time
>
> AWS production (current):
> RDS + ECS + ALB + S3 + ElastiCache: ₹18000/mo
> Total visible: ₹18000/mo
> Real (with auto-managed): ₹18000 + 5 hrs/mo
>
> Engineering cost @ ₹2000/hr:
> Hetzner: ₹2000 + 40000 = ₹42000/mo
> AWS:     ₹18000 + 10000 = ₹28000/mo
> ```
>
> **AWS cheaper jab engineering time consider karein.**
>
> **Honest middle ground:** Hybrid approach:
> - Dev/staging on Hetzner / Hetzner Cloud (₹3-5K/mo)
> - Production on AWS (₹18K/mo)
> - Saves money on non-prod environments
>
> **What I won't do:** Penny-pinch on production for customer-facing app. Outage cost > infra savings."

---

### Q12: "Why not Kubernetes? It's industry standard."

**Answer:**

> "Industry standard ≠ right tool for every project. **YAGNI principle.**
>
> **Kubernetes wins when:**
> - 20+ microservices
> - Multi-team (need RBAC, namespaces)
> - Multi-cloud / hybrid cloud
> - Need ecosystem (Helm, Operators, ArgoCD, Istio, KEDA)
> - Stateful workloads (StatefulSets) at scale
> - Have dedicated SRE team
>
> **Kubernetes loses when:**
> - 1-10 services
> - Small team (no dedicated K8s expert)
> - AWS-committed (no multi-cloud need)
> - Standard 3-tier apps
>
> **Real costs of K8s:**
> - EKS control plane: $73/mo
> - Cluster autoscaler + monitoring add-ons: ~$200/mo
> - **Engineering cognitive load** — Deployment, Service, Ingress, PVC, ConfigMap, Secret, NetworkPolicy, HPA, ServiceAccount, RBAC...
> - **YAML hell** — Kustomize/Helm to manage
> - **Upgrades** — quarterly K8s version upgrades (1.28 → 1.29) need testing
> - **Hiring** — K8s engineers 30% more expensive
>
> **My rule:**
> ```
> Services count:
>   1-10:   ECS Fargate ✅
>   10-30:  ECS Fargate or start considering EKS
>   30+:    EKS justified
> 
> Team size:
>   1-5:    Fargate ✅
>   5-15:   Either
>   15+:    EKS often better (RBAC, namespaces)
> ```
>
> **Bonus argument:** Fargate runs containers — same Docker images. If we outgrow Fargate, migration to EKS Fargate is straightforward (same execution model). Not a one-way door."

---

### Q13: "How do you handle database migrations in a high-traffic production app?"

**Answer:**

> "**3 principles + 5 patterns.**
>
> **Principle 1: Backward compatibility**
> Application code N must work with **both** schema N and N+1.
>
> **Principle 2: Small migrations**
> Big schema changes → break into multiple deploys.
>
> **Principle 3: Always reversible**
> Every migration has tested rollback path.
>
> ---
>
> **Pattern 1: Adding a column (safe)**
> ```python
> # Migration: Add nullable column
> migrations.AddField(
>     'order', 'tracking_id',
>     models.CharField(max_length=50, null=True, blank=True)
> )
> ```
> ✅ Safe — old code ignores new column, new code uses it.
>
> ---
>
> **Pattern 2: Renaming a column (DANGEROUS — never do directly)**
> ❌ `ALTER COLUMN RENAME` — old code crashes immediately.
>
> **Right way (3 deploys):**
> ```
> Deploy 1:
>   - Add new column (nullable)
>   - Code writes to BOTH old + new column
>   - Code reads from OLD column
>
> Deploy 2 (after backfill):
>   - Backfill new column from old (Celery batch job)
>   - Code reads from NEW column
>   - Code still writes to BOTH
>
> Deploy 3:
>   - Code only writes to NEW column
>   - Drop OLD column
> ```
>
> ---
>
> **Pattern 3: Adding a NOT NULL column (dangerous)**
> ❌ `ADD COLUMN status VARCHAR NOT NULL` — table lock on huge tables, blocks writes.
>
> **Right way:**
> ```sql
> -- Step 1: Add nullable with default
> ALTER TABLE orders ADD COLUMN status VARCHAR DEFAULT 'pending';
>
> -- Step 2: Backfill in batches (Celery task)
> -- Update 1000 rows at a time to avoid lock
>
> -- Step 3: Add NOT NULL constraint (separate deploy)
> ALTER TABLE orders ALTER COLUMN status SET NOT NULL;
> ```
>
> ---
>
> **Pattern 4: Adding an index on huge table (dangerous)**
> ❌ `CREATE INDEX` — locks table for writes.
>
> ✅ `CREATE INDEX CONCURRENTLY` — no lock (PostgreSQL).
> ```python
> # Django migration
> class Migration:
>     atomic = False   # ⚠️ CONCURRENTLY needs no transaction
>     operations = [
>         migrations.RunSQL(
>             "CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);"
>         )
>     ]
> ```
>
> ---
>
> **Pattern 5: Migration deployment in CI/CD**
> ```yaml
> # Migrations run as one-off ECS task BEFORE service update
> 1. Build new image with migration
> 2. Push to ECR
> 3. Run ECS task: `python manage.py migrate`
> 4. Wait for exit 0
> 5. THEN update service to new image
> 
> # If migration fails → service NOT updated → easy rollback (no schema change)
> # If service deploy fails → schema is forward-compatible → easy rollback
> ```
>
> **Real disaster I avoided:** Migration tried to add NOT NULL column on 50M row `orders` table — would have locked for 20+ min, blocking checkout. Caught in staging because we test against prod-sized data dump. Used expand-contract pattern instead."

---

### Q14: "How would you debug a 'site is slow' complaint?"

**Answer:**

> "**Systematic debugging — top-down approach:**
>
> **Step 1: Define 'slow'**
> - Which page/endpoint?
> - Which user / geography?
> - Started when? After a deploy?
> - 100% requests or some?
>
> **Step 2: Check observability dashboards**
> - **CloudWatch:** p50, p95, p99 latency per endpoint
> - **Sentry:** any error spike?
> - **Application logs:** slow query warnings?
> - Recent deployments?
>
> **Step 3: Layer-by-layer diagnosis**
>
> **Layer 1: Network**
> - CloudFront cache hit rate dropped?
> - ALB target response time vs request count time
> - Cross-region latency (if applicable)
>
> **Layer 2: Application**
> - Gunicorn workers saturated? (queue depth)
> - CPU/memory of containers
> - Auto-scaling triggered?
>
> **Layer 3: Database**
> - RDS CPU spike?
> - Slow query log (`pg_stat_statements`)
> - Connection count at limit?
> - Lock contention (`pg_locks`)?
> - Missing index?
>
> **Layer 4: External dependencies**
> - Third-party API (Stripe, SendGrid) slow?
> - Redis latency?
> - S3 throttling?
>
> **Common root causes (rank-ordered):**
> 1. **N+1 query** — added new feature, didn't use select_related
> 2. **Missing index** — new filter on unindexed column
> 3. **DB connection exhaustion** — pool too small
> 4. **Cache invalidation** — bad cache key change → cold cache
> 5. **Heavy query during peak** — analytics on production DB
> 6. **Memory leak** — container OOM, restarts cause cold cache
> 7. **External API slow** — no timeout, no circuit breaker
>
> **Tools I use:**
> - `django-silk` or FastAPI middleware for request profiling
> - `EXPLAIN ANALYZE` on slow queries
> - `pg_stat_statements` for top queries
> - `py-spy` for CPU profiling production process (no restart needed)
> - CloudWatch Insights for log queries
>
> **Real story:** User complained 'product list slow'. Found Django ORM was firing 500 queries (N+1) for category names. Fix: `prefetch_related('category')`. p99 latency dropped from 8s to 200ms."

---

## Section 4: Senior-Level Behavioral

### Q15: "Tell me about a production incident you handled"

**Answer (STAR method):**

> "**Situation:** 3 AM Sunday — PagerDuty alert: '500 error rate spiked to 40%'. Mein on-call tha.
>
> **Task:** Identify and fix root cause + minimize customer impact.
>
> **Action:**
> 1. **Triage (2 min):** Slack #incidents declare karta hu. CloudWatch dashboard open.
> 2. **Diagnose (5 min):** Errors all pointed to PostgreSQL connection timeout. RDS CPU 95%. Looking at `pg_stat_activity`, ek long-running analytics query 800 connections consume kar raha tha.
> 3. **Mitigate (3 min):** Killed the rogue query (`SELECT pg_terminate_backend(pid)`). Error rate dropped to normal in 2 min.
> 4. **Verify (5 min):** Smoke tests on critical endpoints. Customer-facing OK.
>
> **Total downtime:** 15 minutes (limited to 1 endpoint, not full app).
>
> **Result:**
> - Customers minimally impacted (15-min partial outage)
> - Slack postmortem documented next day
>
> **Action items from postmortem:**
> 1. **Statement timeout** on production DB: `SET statement_timeout = '30s'` — prevent rogue queries hogging DB
> 2. **Analytics moved to read replica** — production DB only for transactional load
> 3. **CloudWatch alarm** on `pg_stat_activity` count — alert if > 500 connections
> 4. **Runbook updated** with this scenario
>
> **Learning:** Always set query timeouts. One bad query can take down production. Always have read replicas for heavy queries."

---

### Q16: "How do you stay updated with DevOps trends?"

**Answer:**

> "**Mix of sources:**
>
> **Daily (15 min):**
> - HackerNews — top stories filtered by 'AWS', 'Docker', 'Kubernetes'
> - lobste.rs — high-quality engineering posts
>
> **Weekly:**
> - **Newsletters:** Last Week in AWS (Corey Quinn — funny + insightful), DevOps Weekly, KubeWeekly
> - **YouTube:** AWS re:Invent talks, TechWorld with Nana (K8s), Hussein Nasser (system design)
>
> **Monthly:**
> - **Blogs:** Netflix Tech Blog, Uber Engineering, AWS Architecture Blog
> - **Books:** Currently reading 'Designing Data-Intensive Applications' (DDIA — gold standard)
>
> **Hands-on:**
> - Build side projects with new tech (e.g., recently tried Pulumi as Terraform alternative)
> - Contribute to open source (small PRs to libraries I use)
>
> **Conferences/Talks:**
> - AWS re:Invent talks on YouTube (free, high-quality)
> - PyCon India talks
> - Local DevOps Bangalore meetup
>
> **Communities:**
> - Reddit r/devops, r/aws
> - Discord — Cloud Native Computing Foundation (CNCF)
>
> **Filter for noise:**
> - Don't chase every new tool — wait 1-2 years for ecosystem maturity
> - Solve actual problems, not theoretical ones
> - 'Boring' production tech > cutting-edge tools that break"

---

## Cheat Sheet — Phrases that Sound Senior

| Junior Phrase | Senior Replacement |
|---|---|
| "I used Docker" | "I containerized the app with multi-stage builds for 70% smaller images" |
| "I deployed on AWS" | "I deployed on ECS Fargate with auto-scaling 2-10 tasks based on CPU + queue depth" |
| "We have logs" | "Structured JSON logs with request_id correlation, centralized in CloudWatch, queried via Insights" |
| "I added tests" | "Unit + integration tests with PostgreSQL service in CI, 85% coverage, blocking merge if drops" |
| "We use Redis" | "Redis as L1 cache for hot reads (TTL 5min) + Celery broker + rate limiting backend" |
| "I set up CI/CD" | "GitHub Actions with OIDC auth, multi-stage pipeline: lint → test → build → migrate → rolling deploy, with manual approval gate for prod" |
| "We have monitoring" | "RED metrics + USE metrics in Grafana, p99 latency SLO 500ms, error rate < 0.1%, PagerDuty alerts for Sev-1" |
| "I optimized the API" | "Reduced p99 from 2s to 200ms by fixing N+1 queries (select_related), adding compound index on (user_id, created_at), enabling Redis cache" |
| "We use HTTPS" | "TLS 1.3 via ACM cert on ALB, HSTS preload, SECURE_SSL_REDIRECT, certificate auto-renewal" |
| "I handle errors" | "Sentry integration with release tagging, alerts piped to Slack, error budget tracked monthly against 99.9% SLO" |

---

## Final Tips for Deployment Interviews

1. **Always specify versions** — "Python 3.12, Django 5.1.3" — shows you know your stack
2. **Mention numbers** — "₹18K/mo", "p99 200ms", "85% test coverage" — credibility
3. **Talk trade-offs** — every choice has cons, acknowledge them
4. **Real failures** — "Production X broke, I fixed by Y" — shows experience
5. **Migration paths** — "Currently X, would migrate to Y when Z" — pragmatic
6. **Cost-aware** — mention cost optimization — shows business sense
7. **Avoid hype** — don't say "blockchain", "AI for everything", "microservices for 3 services"
8. **Ask clarifying questions** — "What's the team size?", "What's the user scale?" — senior behavior
