# High Availability, Disaster Recovery & Production Security

## HA Architecture (Full Diagram)

```
                        Internet
                           ↓
                       Route 53
                (DNS + health-based routing)
                           ↓
               Application Load Balancer
              (spans AZ-1a + AZ-1b, HTTPS 443)
               /                          \
              ↓                            ↓
          AZ-1a                         AZ-1b
    EC2 (Private Subnet)          EC2 (Private Subnet)
    Django + Gunicorn             Django + Gunicorn
      IAM Role attached             IAM Role attached
          |     |                       |     |
          ↓     ↓                       ↓     ↓
     Redis (ElastiCache)          RDS Primary (PostgreSQL)
     (cache, sessions)                 ↓ sync replication
                                  RDS Standby (Multi-AZ)
                                       ↓ async replication
                                  Read Replica (reports)
                ↓
             SQS Queue
                ↓
        Celery Workers (EC2 ASG)
                ↓
           S3 (files, media)
```

**Every layer has redundancy — no single point of failure (SPOF).**

---

## Route 53 — DNS + Health Routing

```
Route 53 roles:
1. Domain → ALB mapping (A record or ALIAS)
2. Health checks on ALB endpoints
3. Routing policies:
   - Simple: one record
   - Weighted: A=90%, B=10% (canary deploy)
   - Latency: closest region
   - Failover: primary/secondary (multi-region DR)
   - Geolocation: by user country
```

**Multi-region failover:**
```
Primary:   ap-south-1 ALB  (active)
Secondary: ap-southeast-1 ALB  (passive)

Route 53: health check primary → if unhealthy → route to secondary
RTO with Route 53 failover: ~60s (TTL + propagation)
```

---

## RPO vs RTO (DR Vocabulary)

```
Incident happens at T=0 (database corrupt, region down)

    T=0             T=RTO
     ↓                ↓
 INCIDENT ──────────────── SERVICE RESTORED
          ←── RTO ────→

    Last backup     T=0
         ↓           ↓
 BACKUP ─────────────── INCIDENT
         ←── RPO ────→

RTO = Recovery Time Objective   "Kitne time mein service wapas?"
RPO = Recovery Point Objective  "Kitna data loss acceptable hai?"
```

| Strategy | RPO | RTO | Cost |
|---|---|---|---|
| Restore from snapshot | Hours | Hours | Low |
| Multi-AZ RDS | ~0 (sync replication) | ~1-2 min (failover) | Medium |
| Read Replica promote | Minutes (async lag) | Minutes | Medium |
| Multi-Region active-active | ~0 | ~0 | High |

**Interview tip:** "Hamara RPO = 5 minutes (automated backups every 5 min), RTO = 10 minutes (Multi-AZ failover + app restart)" — concrete numbers with justification.

---

## The 10× Traffic Scenario (Must Memorize)

**Q: Your Django app suddenly gets 10× normal traffic. What happens? How do you handle it?**

### Step-by-Step Answer

**1. Load Balancer** (already distributes, no change needed)
```
ALB distributes across existing EC2 pool
If all instances saturated → health checks fail → users see 503
```

**2. Auto Scaling** (trigger scale-out)
```
CloudWatch: CPUUtilization > 70% → ASG scale-out
3 EC2 → 10 EC2 (within 3-5 minutes for new instances)
```

**3. App must be stateless** (prerequisite)
```
Sessions in Redis → any instance serves any user
Files in S3 → no local state
```

**4. Redis** (absorbs read pressure)
```
Cache hit rate check karo
If cache missing many → warm up cache
Redis Cluster for horizontal scaling if needed
```

**5. Database bottleneck** (most common real bottleneck)
```
10× app servers → more DB connections → connection exhaustion
Fix:
  - PgBouncer: pool connections (100 app → 20 real DB connections)
  - Read replicas: heavy reads → replica
  - Query optimization: EXPLAIN ANALYZE slow queries
  - Indexes: missing index = table scan = slow
```

**6. Move heavy work to async**
```
PDF generation, emails, reports → SQS → Celery
API responds fast, worker processes slowly
```

**7. CloudWatch monitoring**
```
Watch:
  - ALB: RequestCount, 5XXCount, TargetResponseTime
  - EC2: CPUUtilization, NetworkIn/Out
  - RDS: CPUUtilization, DatabaseConnections, ReadLatency
  - Redis: CacheMisses, CurrConnections
  - SQS: ApproximateNumberOfMessages (queue depth)
```

**8. Protect downstream** (the insight that impresses interviewers)
```
Scaling EC2 5→50 doesn't help if RDS can only handle 5×.
Identify the BOTTLENECK before scaling every layer.
Use metrics to find where latency/errors are coming from.
```

---

## Health Checks

### Liveness vs Readiness

| | Liveness | Readiness |
|---|---|---|
| Question | "Process alive?" | "Can handle traffic?" |
| Fails → | Restart container | Stop sending traffic |
| Endpoint | `/health/live` | `/health/ready` |
| Checks | Process responds | DB + Redis + deps |

```python
from django.http import JsonResponse
import redis, django.db

def liveness(request):
    return JsonResponse({"status": "ok"})

def readiness(request):
    errors = {}
    try:
        django.db.connection.ensure_connection()
    except Exception as e:
        errors["db"] = str(e)
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
    except Exception as e:
        errors["redis"] = str(e)

    if errors:
        return JsonResponse({"status": "degraded", "errors": errors}, status=503)
    return JsonResponse({"status": "ok"})
```

**ALB health check:** use `/health/live` (simpler, don't tie ALB routing to DB health — if DB is down, you want ALB to still route so you can serve cached responses / error pages gracefully)

---

## Production Security Checklist

### Network
```
✅ ALB: HTTPS only (HTTP → redirect 301)
✅ EC2: private subnet, no public IP
✅ RDS: private subnet, Security Group from EC2-SG only
✅ Redis: private subnet, Security Group from EC2-SG only
✅ Security Groups: minimal ports, source = specific SG not 0.0.0.0/0
✅ NAT Gateway: for outbound from private subnet
✅ VPC endpoints: S3, SQS (traffic stays on AWS backbone)
```

### IAM & Credentials
```
✅ EC2: IAM Role (no hardcoded keys)
✅ Secrets: Secrets Manager (auto-rotate)
✅ Root account: MFA enabled, no access keys
✅ IAM users: MFA required
✅ Least privilege: no wildcard (*) actions in policies
✅ Access Analyzer: run periodically to find overly permissive policies
```

### Application
```
✅ HTTPS: ACM certificate, TLS 1.2+ only
✅ HSTS: Strict-Transport-Security header
✅ CSP: Content-Security-Policy (XSS mitigation)
✅ SECRET_KEY: Secrets Manager se load, git mein nahi
✅ DEBUG=False: production mein always
✅ ALLOWED_HOSTS: specific domains only
✅ Database: SSL mode = require
✅ Rate limiting: Django Ratelimit ya WAF rules
```

### Monitoring & Audit
```
✅ CloudTrail: every API call logged (who did what on AWS)
✅ CloudWatch Alarms: CPU, error rates, DLQ depth, RDS connections
✅ GuardDuty: threat detection (unusual API calls, compromised credentials)
✅ Config: resource configuration changes tracked
✅ VPC Flow Logs: network traffic audit
```

### WAF (Web Application Firewall)
```
ALB → WAF rules:
  - Rate limiting: 100 req/5min per IP
  - SQL injection protection
  - XSS protection
  - Geographic blocking (if needed)
  - Known malicious IPs block (AWS Managed Rules)
```

---

## WSGI vs ASGI

| | WSGI | ASGI |
|---|---|---|
| Full form | Web Server Gateway Interface | Async Server Gateway Interface |
| Model | Synchronous | Async + sync |
| Django | ✅ Supported | ✅ Django 3.1+ |
| FastAPI | ❌ (not sync) | ✅ Required |
| Server | Gunicorn | Uvicorn / Daphne |
| WebSockets | ❌ | ✅ |
| Long-lived connections | ❌ | ✅ |

```python
# WSGI (Django + Gunicorn)
# wsgi.py — synchronous, one request one thread/process
application = get_wsgi_application()

# ASGI (Django Channels / FastAPI + Uvicorn)
# asgi.py — async, many concurrent connections
application = get_asgi_application()
```

**Gunicorn workers formula:** `(2 × CPU cores) + 1`
- 2 vCPU EC2 → 5 workers
- Each worker handles 1 request at a time (sync WSGI)
- I/O bound? → `--worker-class gevent` (green threads, more concurrency per worker)

---

## Interview Q&A

**Q: Single point of failure kaise avoid karte hain?**
A: Har layer mein redundancy: ALB multiple AZs mein, EC2 ASG multi-AZ mein, RDS Multi-AZ, Redis cluster mode, S3 (inherently 11 nines durable). Route 53 health checks se multi-region failover bhi possible.

**Q: RPO aur RTO kya hote hain?**
A: RPO = data loss tolerance (backup kitna purana ho sakta hai). RTO = recovery time (service kitne time mein wapas). Multi-AZ RDS se RPO ≈ 0 (sync replication), RTO ≈ 1-2 min (automatic failover). Higher availability = higher cost.

**Q: Production mein secrets kaise manage karte hain?**
A: Secrets Manager mein store karo, EC2 IAM Role se access karo (no hardcoded credentials), auto-rotation enable karo (Secrets Manager automatically rotate karta hai RDS credentials). `.env` files git mein kabhi nahi.

**Q: WSGI vs ASGI — Django ke liye kab ASGI use karo?**
A: WebSockets chahiye (chat, live updates), background async tasks (database_sync_to_async), ya Django Channels use kar rahe ho. Simple REST API ke liye WSGI+Gunicorn fine hai. FastAPI ke liye ASGI required hai.

**Q: Health check endpoint mein DB check karna chahiye?**
A: ALB health check ke liye nahi — agar DB down hai aur health check fail kare toh ALB saare instances unhealthy mark karega aur traffic koi nahi milega. Liveness ke liye `/health/live` sirf process check karo. Readiness (Kubernetes ya custom) ke liye DB + Redis check karo, ALB se nahi.
