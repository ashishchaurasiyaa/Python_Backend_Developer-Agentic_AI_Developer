# Lecture 5: Load Balancing and Auto Scaling

> *"The unsung heroes behind systems that feel smooth during a traffic spike."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why load balancing + auto scaling matter**
- **Load balancing fundamentals** — traffic distribution
- **Load balancing algorithms** — round robin, least connections, etc.
- **Auto scaling** — dynamic capacity
- **Horizontal vs vertical scaling**
- **Cloud auto-scaling patterns** — reactive, predictive, scheduled
- **Cloud-native load balancers**
- **Traffic routing strategies** — canary, blue/green, weighted
- **Reducing latency**
- **Observability** — metrics that matter

---

## 1. Why It Matters

### The Challenge

```
Modern apps face:
   ✗ Unpredictable traffic
   ✗ Viral surges
   ✗ Geographic variations
   ✗ Peak hours
   ✗ Failures of individual servers

Manual scaling fails:
   ✗ Over-provision: waste money
   ✗ Under-provision: downtime
   ✗ Slow to react
```

### The Solution

```
LOAD BALANCING:
   ✓ Distribute traffic intelligently
   ✓ Prevent single-server overload
   ✓ Improve reliability + throughput

AUTO SCALING:
   ✓ Adjust capacity automatically
   ✓ Save money during low traffic
   ✓ Handle spikes gracefully
```

### Together

```
Auto-scaling adds/removes instances
   +
Load balancer distributes to them
   = 
Elastic, self-managing infrastructure
```

---

## 2. What Is Load Balancing?

### Definition

**Load balancing = distributing incoming traffic across multiple servers.**

### Visual

```
                ┌──────────────────┐
                │  Load Balancer   │
                │  "Traffic Cop"   │
                └─────────┬────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌────────┐  ┌────────┐
         │Server 1│  │Server 2│  │Server 3│
         └────────┘  └────────┘  └────────┘
```

### Benefits

```
✓ Better RELIABILITY
   - One server down → traffic redirected
   
✓ Higher AVAILABILITY
   - No single point of failure
   
✓ Increased THROUGHPUT
   - Multiple servers handle more traffic
   
✓ Consistent RESPONSE TIMES
   - Load evenly distributed
```

### Load Balancer Layers

```
LAYER 4 (Transport):
   ✓ Routes by IP + port
   ✓ Fast (simple)
   ✓ Use case: TCP/UDP services
   
LAYER 7 (Application):
   ✓ Routes by HTTP path, cookies, headers
   ✓ Smarter (HTTP-aware)
   ✓ Use case: web APIs
```

### Types

```
Hardware:    F5, Citrix (legacy)
Software:    HAProxy, Nginx, Envoy
Cloud:       AWS ALB/NLB, Azure LB, GCP LB
Service Mesh:Istio, Linkerd
```

---

## 3. Load Balancing Algorithms

### Round Robin

```
Send each request to next server in rotation.

   Request 1 → Server A
   Request 2 → Server B
   Request 3 → Server C
   Request 4 → Server A (back to start)
   
✓ Simple
✓ Even distribution (if all servers equal)
✗ Doesn't account for load
```

### Least Connections

```
Send to server with fewest active connections.

✓ Better for long-running connections
✓ Adapts to actual load
✗ Slightly more overhead
```

### IP Hashing (Session Affinity)

```
Hash client IP → always same server.

✓ Session stickiness
✓ Good for stateful apps
✗ Uneven distribution if IPs cluster
```

### Weighted

```
Servers have weights based on capacity.

   Server A (weight 3): gets 3x traffic
   Server B (weight 1): gets 1x traffic
   
✓ Account for different server sizes
✓ Useful for canary deployments
```

### Random

```
Pick random server.

✓ Simple
✗ Can lead to uneven loads
✗ Generally not recommended
```

### Least Response Time

```
Send to fastest-responding server.

✓ Best user experience
✓ Auto-avoids slow/failing servers
✗ More complex monitoring needed
```

### Choosing the Right Algorithm

```
General API:           Round Robin
Long sessions:         Least Connections
Stateful (cart):       IP Hash / Sticky Sessions
Different capacities:  Weighted
Performance critical:  Least Response Time
```

---

## 4. What Is Auto Scaling?

### Definition

**Auto scaling = automatically adjusting number of instances based on demand.**

### How It Works

```
                Metric monitor
   (CPU, memory, request rate, queue depth)
                      │
                      ▼
                Threshold reached?
                      │
              ┌───────┴───────┐
              ▼               ▼
           Scale up        Scale down
           (add instances) (remove instances)
              │               │
              ▼               ▼
          Load balancer adapts
```

### Benefits

```
✓ Handle traffic spikes automatically
✓ Save cost during low traffic
✓ Meet SLAs without manual work
✓ Self-healing (replace bad instances)
✓ No capacity planning needed
```

### Common Metrics

```
✓ CPU utilization (most common)
✓ Memory usage
✓ Request rate (per second)
✓ Queue depth (for async work)
✓ Response time
✓ Custom business metrics (signups/min)
```

---

## 5. Horizontal vs Vertical Scaling

### Vertical Scaling (Scale Up)

```
Same machine, more power:
   ✓ More CPU
   ✓ More RAM
   ✓ Faster disk
   ✓ Better GPU

Pros:
   ✓ Simple
   ✓ No code changes
   ✓ Better for some workloads (DBs)

Cons:
   ✗ Hard limit (max VM size)
   ✗ Single point of failure
   ✗ Downtime to upgrade
   ✗ Expensive at scale
```

### Horizontal Scaling (Scale Out)

```
More machines:
   ✓ Add identical instances
   ✓ Distribute load via LB
   ✓ Linear capacity growth

Pros:
   ✓ Effectively unlimited
   ✓ Built-in redundancy
   ✓ Pairs with load balancing
   ✓ Cloud-native default

Cons:
   ✗ Apps must be stateless
   ✗ Requires load balancer
   ✗ More complex networking
```

### Visual

```
   VERTICAL                  HORIZONTAL
   
   ┌──────────┐              ┌──┐ ┌──┐ ┌──┐
   │ Server   │              │S1│ │S2│ │S3│
   │  ↑↑↑    │       →      └──┘ └──┘ └──┘
   │  bigger  │
   │          │              + load balancer
   └──────────┘
```

### Cloud Default

```
Cloud-native = horizontal scaling
   ✓ Auto-scaling uses horizontal
   ✓ Containers + Kubernetes designed for it
   ✓ Microservices = horizontal naturally
```

---

## 6. Cloud Auto-Scaling Patterns

### Pattern 1: Reactive Scaling

```
Wait for threshold → react

   CPU > 70% for 5 min → add instances
   CPU < 30% for 10 min → remove instances

✓ Most common
✓ Simple to configure
✗ Reacts AFTER spike starts (lag)
```

### Pattern 2: Predictive Scaling

```
Use ML to forecast demand → scale ahead

   "Traffic always spikes at 10 AM"
   → Scale up at 9:55 AM (proactive)

✓ No lag
✓ Better user experience
✗ Requires historical data
✗ AWS, Azure ML-based
```

### Pattern 3: Scheduled Scaling

```
Known patterns → fixed schedule

   "Every weekday 9 AM: scale to 10 instances"
   "Every weekday 6 PM: scale to 3 instances"

✓ Simple
✓ Cost-effective for known patterns
✗ Doesn't adapt to unexpected events
```

### Pattern 4: Container Auto-Scaling

```
Kubernetes Horizontal Pod Autoscaler (HPA):
   ✓ Pods scale based on CPU/memory/custom metrics
   ✓ Works with Cluster Autoscaler
   
AWS Fargate, GKE Autopilot, Azure Container Apps:
   ✓ Auto-scale at container level
   ✓ Even simpler than VMs
```

### Pattern 5: Function Auto-Scaling

```
Serverless = scale per REQUEST!

   1 request → 1 function instance
   1M requests → potentially 1M parallel
   0 requests → 0 instances (no cost!)

✓ Maximum elasticity
✓ Pay per use
✗ Cold starts
```

### Combined Patterns

```
Best practice: combine approaches

   ✓ Predictive: baseline scaling
   ✓ Scheduled: known events
   ✓ Reactive: fallback for surprises
   
→ Maximum responsiveness + cost efficiency
```

---

## 7. Cloud-Native Load Balancers

### AWS

```
✓ Application Load Balancer (ALB) - Layer 7
   - HTTP/HTTPS
   - Path-based routing
   - WAF integration
   - WebSocket support

✓ Network Load Balancer (NLB) - Layer 4
   - TCP/UDP
   - Ultra-high throughput
   - Static IP
   - Preserve client IP

✓ Classic Load Balancer (legacy, avoid)
```

### Google Cloud

```
✓ HTTP(S) Load Balancer - global, Layer 7
✓ SSL Proxy - global SSL termination
✓ TCP/UDP Load Balancer - regional, Layer 4
✓ Network Load Balancer - regional
```

### Azure

```
✓ Front Door - global HTTP routing
✓ Application Gateway - Layer 7, AKS integration
✓ Azure Load Balancer - Layer 4
✓ Traffic Manager - DNS-based routing
```

### Comparison Quick Hits

```
NEED                      USE
────────────────────────────────────
Layer 7 (HTTP):           ALB / App Gateway
Ultra-fast TCP:           NLB / Cloud LB
Global routing:           CloudFront / Front Door
WebSockets:               ALB / Cloud LB
Static IP:                NLB
WAF integration:          ALB / App Gateway
```

### Integration with Auto-Scaling

```
Auto-scaling group ──► instances appear ──► LB registers them
Instance terminated ──► LB removes it (drain mode)

✓ All automatic
✓ Zero downtime scaling
```

---

## 8. Traffic Routing Strategies

### Canary Deployment

```
Send small % of traffic to new version:

   Phase 1: 99% v1 → 1% v2 (24 hours)
   Phase 2: 90% v1 → 10% v2 (24 hours)
   Phase 3: 50% v1 → 50% v2 (24 hours)
   Phase 4: 0% v1 → 100% v2

✓ Safe, incremental
✓ Easy rollback
✗ Slow rollout
```

### Blue-Green Deployment

```
Two identical environments:
   BLUE (current): handles 100% traffic
   GREEN (new):    deployed, waiting
   
Switch:
   ALL traffic → GREEN
   BLUE: standby (or torn down)

✓ Instant cutover
✓ Easy rollback (switch back)
✗ Resource cost (2x environments)
```

### Weighted Routing

```
Configurable traffic split:
   v1: 70%, v2: 20%, v3: 10%

✓ Flexible (any split)
✓ Multiple versions simultaneously
✓ Good for A/B testing
```

### Geo Routing

```
Route by user location:
   US users → US servers
   EU users → EU servers
   Asia users → Asia servers

✓ Lower latency
✓ Data residency compliance
✗ More complex multi-region setup
```

### Latency-Based Routing

```
Route to fastest server (real-time measurement):
   ✓ Best user experience
   ✓ Adapts to network conditions
   ✗ Requires latency measurement infra
```

### Header / Cookie-Based

```
Route by HTTP header or cookie:
   - Header: "X-Beta-User: true" → beta version
   - Cookie: "preferred_region: eu" → EU servers

✓ Fine-grained control
✓ Useful for feature flags
```

---

## 9. Reducing Latency

### Technique 1: Auto-Scale Near Users

```
Multi-region deployment:
   ✓ US region for US users
   ✓ EU region for EU users
   ✓ Asia region for Asia users
   
+ Global load balancer routes to nearest
```

### Technique 2: CDN for Static Content

```
Cache assets at edge:
   ✓ Images, CSS, JS
   ✓ Videos
   ✓ API responses (if cacheable)
   
→ 10-50x faster delivery
```

### Technique 3: Mitigate Cold Starts

```
Serverless cold starts hurt:
   ✓ Use Provisioned Concurrency
   ✓ Keep functions small
   ✓ Pre-warm with scheduled calls
   ✓ Use faster runtimes (Go, Python)
```

### Technique 4: Connection Reuse

```
HTTP keep-alive:
   ✓ Reuse TCP connections
   ✓ Skip TCP handshake overhead
   ✓ Crucial for high-frequency APIs
```

### Technique 5: Request Buffering

```
Spike absorbed by queue:
   ✓ Requests buffered in SQS/Kafka
   ✓ Workers process at sustained rate
   ✓ No backend overload
```

### Technique 6: Smart Caching

```
✓ Cache hot data in Redis
✓ Cache DB query results
✓ Cache rendered pages
✓ Cache API responses (with TTL)
```

---

## 10. Observability

### Key Metrics

```
TRAFFIC METRICS:
   ✓ Requests per second
   ✓ Active connections
   ✓ Bandwidth

PERFORMANCE METRICS:
   ✓ Response time (P50, P95, P99)
   ✓ Error rate
   ✓ Backend health

RESOURCE METRICS:
   ✓ CPU per instance
   ✓ Memory per instance
   ✓ Disk I/O
   ✓ Network I/O

AUTO-SCALING METRICS:
   ✓ Current instance count
   ✓ Pending scale events
   ✓ Time to scale up
   ✓ Cost per request
```

### Alerts

```
ALERT ON:
   ✓ Error rate > 1% for 5 min
   ✓ P99 latency > 2 seconds
   ✓ CPU > 90% for 5 min (won't scale fast enough)
   ✓ Memory > 95%
   ✓ Health check failures
   ✓ Auto-scaling at max limit

DON'T ALERT ON:
   ✗ Every CPU spike
   ✗ Single request failures
   ✗ Expected scaling events
```

### Tools

```
✓ Prometheus + Grafana (cloud-native standard)
✓ AWS CloudWatch
✓ Datadog
✓ New Relic
✓ Azure Monitor
✓ Google Cloud Monitoring
```

### Visualize Auto-Scaling Events

```
Dashboard panel:
   ✓ Current instance count
   ✓ Scale up/down events
   ✓ Alongside traffic graph
   ✓ Cost over time
   
→ Spot inefficient scaling patterns
```

---

## 11. Common Patterns

### Pattern 1: Health Checks

```
Configure LB to check backend health:
   GET /health every 5 seconds
   
   Healthy: include in pool
   Unhealthy: exclude (drain mode)
   
After N failures: remove from rotation
After M successes: add back
```

### Pattern 2: Connection Draining

```
On scale-in or deploy:
   1. Stop sending NEW connections to instance
   2. Wait for existing connections to complete
   3. Terminate instance

→ Zero dropped requests during scale-down
```

### Pattern 3: Cross-Zone Load Balancing

```
Spread traffic across availability zones:
   ✓ Better resilience (zone failure ok)
   ✓ Even distribution
   ✗ Higher cross-AZ data costs
```

### Pattern 4: Sticky Sessions When Needed

```
Some apps need:
   ✗ Stateful sessions in memory
   
Sticky sessions:
   ✓ Same user → same server
   ✗ Limits horizontal scaling
   ✗ User's session lost if server dies
   
→ Prefer external sessions (Redis)
```

### Pattern 5: Warm Pools

```
Pre-warmed instances ready to go:
   ✓ Faster scale-up (skip boot time)
   ✓ Useful for bursty traffic
   ✗ Pay for warm instances even when idle
```

---

## 12. Anti-Patterns

### Anti-Pattern 1: Over-Aggressive Scaling

```
❌ "Scale up at 50% CPU for 1 minute"

Result:
   ✗ Instances flap (up/down/up/down)
   ✗ Cost spikes
   ✗ Performance issues

✅ Stabilization window (5+ min)
✅ Higher threshold (70-80%)
```

### Anti-Pattern 2: Under-Provisioning Minimum

```
❌ "minReplicas: 1" for critical service

Result:
   ✗ Single point of failure
   ✗ Scale-up lag during spikes

✅ Always >= 2 replicas
✅ Across multiple AZs
```

### Anti-Pattern 3: Stateful Apps with Horizontal Scaling

```
❌ Session in memory + horizontal scaling

Result:
   ✗ User loses session randomly
   ✗ Sticky sessions break scaling

✅ Store sessions in Redis
✅ Make apps stateless
```

### Anti-Pattern 4: No Health Checks

```
❌ LB doesn't know which servers are healthy

Result:
   ✗ Traffic sent to broken servers
   ✗ Users see errors

✅ Always configure health checks
✅ Use both liveness + readiness
```

### Anti-Pattern 5: Auto-Scaling Without Monitoring

```
❌ "Set it and forget it"

Result:
   ✗ Don't know if it's working
   ✗ Costs spiral
   ✗ Performance unknown

✅ Monitor scaling events
✅ Alert on stuck at max
✅ Tune based on real data
```

---

## 13. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Load balancers distribute traffic intelligently            │
│  ✅ Auto-scaling adjusts capacity to demand                    │
│  ✅ Horizontal scaling is cloud-native default                 │
│  ✅ Multiple algorithms: round-robin, least connections, etc.  │
│  ✅ Reactive, predictive, scheduled scaling patterns           │
│  ✅ Layer 4 vs Layer 7 LBs serve different needs               │
│  ✅ Canary + blue-green for safe deployments                   │
│  ✅ Reduce latency: CDN + multi-region + caching               │
│  ✅ Monitor everything: metrics + alerts                       │
│  ✅ Avoid: over-aggressive scaling, no monitoring              │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Always have >= 2 instances (HA)
2. Use stateless apps for horizontal scaling
3. Health checks are CRITICAL
4. Stabilization window prevents flapping
5. Match algorithm to workload
6. Use Layer 7 LB for HTTP, Layer 4 for TCP
7. Combine reactive + predictive scaling
8. Test scale-down too (not just scale-up)
9. Connection draining for zero-downtime
10. Monitor + alert on key metrics
```

---

## 🎬 What's Next?

In **Lecture 6**, we'll explore **Edge Architecture** — CDNs and Edge Functions for global performance.

> **Practical file:** [05_Practical_Hands_On.md](05_Practical_Hands_On.md)

---

## 📚 References

- *Site Reliability Engineering* — Google
- AWS Auto Scaling documentation
- Kubernetes HPA documentation
- *Cloud Native Patterns* — Cornelia Davis
- HAProxy + Nginx documentation
