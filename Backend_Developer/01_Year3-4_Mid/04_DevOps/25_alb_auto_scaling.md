# ALB + Auto Scaling — Traffic Distribution & Elasticity

## Application Load Balancer (ALB)

### What It Does
ALB = Layer 7 (HTTP/HTTPS) load balancer. Requests receive karta hai → target group ke healthy instances mein distribute karta hai.

```
Internet
    ↓ HTTPS 443
ALB (spans multiple AZs)
    ├── Listener: 443 → Certificate → Forward to Target Group
    └── Listener: 80  → Redirect to 443
         ↓
    Target Group: "django-app-tg"
    (EC2-1, EC2-2, EC2-3 — all in different AZs)
```

### Layer 7 vs Layer 4

| | ALB (Layer 7) | NLB (Layer 4) |
|---|---|---|
| Protocol | HTTP/HTTPS/WebSocket | TCP/UDP/TLS |
| Routing | Path, host, header, query | IP + port only |
| Use case | Web apps, microservices | High perf, gaming, IoT |
| SSL termination | Yes | Yes (passthrough also possible) |

---

## ALB Features

### Path-Based Routing
```
ALB Listener Rules (evaluated top to bottom):

Rule 1: IF path = /api/*      → Forward to "api-target-group"
Rule 2: IF path = /admin/*    → Forward to "admin-target-group"
Rule 3: IF path = /static/*   → Forward to "s3-bucket" (or Nginx)
Rule 4: (default)             → Forward to "django-target-group"
```

### Host-Based Routing
```
api.myapp.com    → "api-target-group"    (FastAPI instances)
admin.myapp.com  → "admin-target-group"  (Django admin, internal only)
myapp.com        → "web-target-group"    (main Django app)
```

### SSL Termination
```
Client → HTTPS 443 → ALB (decrypts TLS) → HTTP 8000 → EC2
```
- Certificate ACM (AWS Certificate Manager) mein store karo — free, auto-renew
- EC2 instances plain HTTP handle karte hain → simpler app config
- EC2 aur ALB same VPC mein hain → private channel pe HTTP safe hai

### Health Checks
```
ALB → GET /health HTTP/1.1 → EC2
      ← 200 OK → healthy
      ← timeout / 5xx → unhealthy → remove from rotation
```

Health check config:
- Path: `/health` (ya `/`)
- Protocol: HTTP
- Port: traffic port (8000)
- Healthy threshold: 2 consecutive successes
- Unhealthy threshold: 3 consecutive failures
- Interval: 30s
- Timeout: 5s

**Django health endpoint:**
```python
# urls.py
from django.http import JsonResponse

def health(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("health", health),
    # Don't check DB here unless you want ALB to pull traffic on DB issues
]
```

### Sticky Sessions (Session Affinity)
- ALB cookie se same user ko same EC2 pe route karta hai
- **Avoid this** — application ko stateless banao (Redis mein session store karo)

---

## Target Groups

```
Target Group: "django-app-tg"
  Type: Instance (EC2 ID) / IP / Lambda
  Protocol: HTTP
  Port: 8000
  Health check: /health

  Registered targets:
    i-0abc123  10.0.3.10:8000  healthy
    i-0def456  10.0.4.11:8000  healthy
    i-0ghi789  10.0.3.12:8000  healthy
```

---

## Auto Scaling Group (ASG)

### Core Concept
```
ASG = Pool of EC2 instances automatically managed

Config:
  Desired capacity: 3   ← chaho kitne instances
  Minimum:          2   ← kabhi 2 se kam nahi hoga
  Maximum:          10  ← kabhi 10 se zyada nahi hoga

Normal traffic:   desired=3  → 3 instances running
Traffic spike:    desired=7  → ASG launches 4 more
Traffic drops:    desired=3  → ASG terminates 4
```

### Launch Template
ASG banane ke liye template chahiye — naya instance kaise launch ho:
```
Launch Template:
  AMI: ami-xxxxxxxx         (your baked image with app code)
  Instance Type: t3.medium
  Key Pair: my-key
  Security Group: ec2-app-sg
  IAM Instance Profile: MyDjangoAppRole
  User Data: |
    #!/bin/bash
    cd /app
    docker compose up -d
```

### Scaling Policies

#### 1. Target Tracking (Recommended — Simplest)
```
Policy: "Keep average CPU at 60%"
→ ASG automatically adds/removes instances to maintain target
→ No manual thresholds to manage
```

#### 2. Step Scaling
```
CPU 70-80% → add 1 instance
CPU 80-90% → add 2 instances
CPU >90%   → add 3 instances
CPU <30%   → remove 1 instance
```

#### 3. Scheduled Scaling
```
Every weekday 9am: set desired=10  (office hours)
Every weekday 8pm: set desired=3   (night)
```

#### 4. Predictive Scaling
- ML se traffic patterns learn karta hai → proactively scale karta hai

---

## ASG + ALB Integration

```
ALB Target Group ←→ Auto Scaling Group

New instance launches:
  1. ASG launches EC2 from Launch Template
  2. User Data runs (Docker start, etc.)
  3. ALB health check starts (waits for /health 200)
  4. Instance marked "InService" → traffic milna shuru

Instance terminates:
  1. ASG marks instance for termination (scale-in)
  2. ALB stops routing new requests to it (connection draining — default 300s)
  3. Existing requests complete
  4. Instance terminates
```

**Connection Draining (Deregistration Delay):**
- ALB in-flight requests finish hone deta hai before instance terminates
- Default: 300 seconds
- Tune karo app response time ke hisaab se (short requests → 30-60s)

---

## Stateless Application Requirement

ASG ke saath apps STATELESS honi chahiye:

```
# WRONG: State on EC2 ❌
User uploads file → saved to /tmp/uploads/  (lost when instance terminates)
User logs in → session in memory            (next request → different EC2 → logged out)

# CORRECT: State external ✅
User uploads file → saved to S3             (any instance can access)
User logs in → session in Redis             (any instance can read)
```

---

## Warm-Up Period

New instance launch hone ke baad:
- Application boot time: 30-60 seconds
- Agar ASG turant scale decision le toh naye instance count ho jaate hain metrics mein
- Warm-up period set karo (e.g., 180s) → naye instances metrics mein count nahi hote jab tak warm nahi

---

## Interview Q&A

**Q: ALB aur EC2 directly ke beech kya fark hai?**
A: ALB traffic distribute karta hai multiple EC2 instances mein, health check karta hai, SSL terminate karta hai, aur path/host routing support karta hai. Single EC2 ka single point of failure hota hai — ek crash → downtime. ALB ke saath koi unhealthy instance traffic receive nahi karta.

**Q: ALB Layer 7 pe kaam karta hai — iska practical matlab kya hai?**
A: Layer 7 = HTTP aware. ALB URLs dekh sakta hai, headers dekh sakta hai. `/api/` → ek target group, `/admin/` → doosra. NLB sirf TCP/IP dekh sakta hai — URL nahi.

**Q: Auto Scaling minimum 2 kyun rakhte hain?**
A: High availability ke liye. Minimum 1 rakha → vo instance unhealthy ho jaaye toh downtime. Minimum 2 rakho, different AZs mein → ek AZ down bhi ho toh doosra serve karta rehta hai.

**Q: Scale-in ke time instance turant terminate kyon nahi hota?**
A: Connection draining (Deregistration Delay) — ALB active requests finish hone deta hai. Nahi karo toh users mid-request pe 502 dekhte. Django response time dekhke tune karo.

**Q: CPU-based scaling sufficient hai ya kuch aur bhi?**
A: CPU akele kaafi nahi. Django mein I/O-bound requests pe CPU low rehti hai par workers busy hote hain. Better metrics: ALB RequestCountPerTarget (per instance requests), or custom CloudWatch metric (queue depth, active connections). ALB RequestCountPerTarget tracking se better scaling hoti hai web apps ke liye.
