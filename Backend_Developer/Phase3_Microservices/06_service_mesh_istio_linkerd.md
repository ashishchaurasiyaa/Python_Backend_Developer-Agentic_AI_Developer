# Service Mesh — Istio, Linkerd, Envoy Sidecar

## Quick Concepts

**WHAT:**
- **Service Mesh** = Infrastructure layer for service-to-service communication
- **Sidecar** = Proxy container alongside your app (handles networking)
- **Data Plane** = Sidecar proxies (Envoy) — handle actual traffic
- **Control Plane** = Brain (Istiod, Linkerd control) — distributes config
- **Istio** = Most popular, feature-rich, complex
- **Linkerd** = Lightweight, Rust-based, simpler
- **Envoy** = High-performance L7 proxy (used by both)

**WHY service mesh:**
- ❌ Without: each service implements retry/mTLS/observability in code
- ❌ Inconsistent across languages (Python, Go, Java)
- ✅ Mesh: all done at network layer, NO code changes
- ✅ Polyglot-friendly
- ✅ Centralized policy (YAML)

**HOW it works:**

```
┌──────────────────────────────────────────┐
│  Pod (Service A)                          │
│  ┌────────┐    ┌─────────────────┐       │
│  │  App   │───►│  Envoy Sidecar  │       │
│  │ :8080  │    │   :15001        │       │
│  └────────┘    └────────┬────────┘       │
└────────────────────────┼──────────────────┘
                         │ mTLS auto
                         │ retries
                         │ load balancing
                         ▼
┌──────────────────────────────────────────┐
│  Pod (Service B)                          │
│  ┌─────────────────┐    ┌────────┐       │
│  │  Envoy Sidecar  │───►│  App   │       │
│  │   :15001        │    │ :8080  │       │
│  └─────────────────┘    └────────┘       │
└──────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Service Mesh kya hai? Kab use karein vs application-level?

**Answer:**

**WHAT:** Infrastructure layer that provides:
- mTLS encryption (automatic)
- Traffic management (retries, timeouts, circuit breaking)
- Observability (metrics, traces, logs)
- Security policies (authz)

**WHY:**
```
Without service mesh:
- Service A code:  retry + mTLS + tracing + metrics
- Service B code:  retry + mTLS + tracing + metrics
- Service C code:  retry + mTLS + tracing + metrics
- 50 services × 4 features = 200 implementations
- Each language has own library
- Inconsistent behavior

With service mesh:
- Mesh sidecar: retry + mTLS + tracing + metrics (once)
- All services: just business logic
- Same behavior across all languages
```

**HOW — Decision matrix:**

| Aspect | Use Mesh | Skip Mesh (App-level) |
|---|---|---|
| **Services count** | 10+ | < 5 |
| **Languages** | Polyglot (Python+Go+Java) | Single language |
| **Team size** | Large (dedicated platform team) | Small (< 5 engineers) |
| **Need mTLS everywhere** | Yes | No |
| **Want unified observability** | Yes | OK with per-service |
| **Need advanced traffic mgmt** | Canary, A/B testing | Simple |
| **AWS only** | Use App Mesh | OK without |

---

### Q2: Istio architecture — components + flow?

**Answer:**

**HOW — Istio components:**

```
┌──────────────────────────────────────────────────┐
│                Control Plane                      │
│  ┌────────────────────────────────────────────┐  │
│  │  Istiod (single binary)                    │  │
│  │  ┌──────┐ ┌─────────┐ ┌────────────┐      │  │
│  │  │ Pilot│ │ Citadel │ │  Galley    │      │  │
│  │  │ (LB) │ │  (CA)   │ │ (Config)   │      │  │
│  │  └──────┘ └─────────┘ └────────────┘      │  │
│  └────────────────────────────────────────────┘  │
└─────────────────────────┬────────────────────────┘
                          │ config + certs
                          ↓
┌──────────────────────────────────────────────────┐
│                  Data Plane                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  Envoy   │ │  Envoy   │ │  Envoy   │         │
│  │ Sidecar  │ │ Sidecar  │ │ Sidecar  │         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘         │
│       │            │            │                │
│  ┌────▼─────┐ ┌───▼──────┐ ┌───▼──────┐         │
│  │ Service A│ │ Service B│ │ Service C│         │
│  └──────────┘ └──────────┘ └──────────┘         │
└──────────────────────────────────────────────────┘
```

**Components:**

| Component | Role |
|---|---|
| **Pilot** | Service discovery + traffic config distribution |
| **Citadel** | Certificate authority (issues mTLS certs) |
| **Galley** | Config validation + ingestion |
| **Envoy** | The proxy doing actual work |
| **Istiod** | Combined control plane (since 1.5) |

---

### Q3: Istio installation + basic usage?

**Answer:**

**HOW — Install:**

```bash
# Download istioctl
curl -L https://istio.io/downloadIstio | sh -
cd istio-1.20.0
export PATH=$PWD/bin:$PATH

# Install (demo profile for learning)
istioctl install --set profile=demo -y

# OR production profile
istioctl install --set profile=default -y

# Verify
kubectl get pods -n istio-system
# istiod-xxx                 1/1 Running
# istio-ingressgateway-xxx   1/1 Running

# Enable automatic sidecar injection for namespace
kubectl label namespace default istio-injection=enabled
```

**HOW — Deploy app with sidecar:**

```yaml
# myapp.yaml (no Istio-specific config — sidecar auto-injected)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
        version: v1            # ⭐ For traffic routing
    spec:
      containers:
        - name: myapp
          image: myapp:1.0
          ports:
            - containerPort: 8080

---
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
  ports:
    - port: 80
      targetPort: 8080
```

```bash
# Check sidecar injected
kubectl get pod myapp-xxx -o jsonpath='{.spec.containers[*].name}'
# Output: myapp istio-proxy   ← Envoy sidecar added!
```

---

### Q4: Istio mTLS — automatic + manual config?

**Answer:**

**WHAT:** Istio enables mTLS between sidecars automatically.

**WHY:**
- Cert generation/rotation: handled by Citadel
- No app code changes
- Zero-trust by default

**HOW — Enable mTLS for entire mesh:**

```yaml
# Cluster-wide STRICT mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system    # ⭐ istio-system = applies to whole mesh
spec:
  mtls:
    mode: STRICT
```

**Modes:**
- `DISABLE` — plaintext only
- `PERMISSIVE` — accept both (migration mode)
- `STRICT` — mTLS required

**HOW — Per-namespace mTLS:**

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: production-mtls
  namespace: production
spec:
  mtls:
    mode: STRICT
```

**HOW — Per-service mTLS:**

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: payment-mtls
  namespace: production
spec:
  selector:
    matchLabels:
      app: payment-service
  mtls:
    mode: STRICT
  # Per-port override
  portLevelMtls:
    9090:
      mode: PERMISSIVE     # Metrics port allows plaintext
```

**HOW — Authorization policy (RBAC):**

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: payment-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: payment-service
  action: ALLOW
  rules:
    - from:
        - source:
            # Only these service accounts can call payment
            principals:
              - "cluster.local/ns/production/sa/order-service"
              - "cluster.local/ns/production/sa/admin-service"
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/payments/*"]
      when:
        # Optional: based on JWT claim
        - key: request.auth.claims[role]
          values: ["admin", "operator"]
```

---

### Q5: Traffic management — canary deployment kaise karein?

**Answer:**

**WHAT:** Route % of traffic to new version, monitor, gradually shift.

**HOW — Setup:**

```yaml
# 1. Deploy v1 + v2 of service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-v1
spec:
  replicas: 5
  template:
    metadata:
      labels:
        app: myapp
        version: v1
    spec:
      containers: [...]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-v2
spec:
  replicas: 1                     # ⭐ Less replicas for canary
  template:
    metadata:
      labels:
        app: myapp
        version: v2
    spec:
      containers: [...]
```

```yaml
# 2. DestinationRule — define subsets
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: myapp-subsets
spec:
  host: myapp
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
```

```yaml
# 3. VirtualService — traffic split
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp-canary
spec:
  hosts: [myapp]
  http:
    - route:
        - destination:
            host: myapp
            subset: v1
          weight: 90              # ⭐ 90% to stable
        - destination:
            host: myapp
            subset: v2
          weight: 10              # ⭐ 10% to canary
```

**HOW — Header-based routing (advanced canary):**

```yaml
# Only internal users get v2
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp-header-canary
spec:
  hosts: [myapp]
  http:
    # Internal users → v2
    - match:
        - headers:
            x-user-type:
              exact: internal
      route:
        - destination:
            host: myapp
            subset: v2
    # Everyone else → v1
    - route:
        - destination:
            host: myapp
            subset: v1
```

**HOW — Gradual rollout pattern:**

```bash
# Week 1: 10% → 25%
kubectl patch virtualservice myapp-canary --type=json \
  -p='[{"op": "replace", "path": "/spec/http/0/route/0/weight", "value": 75},
       {"op": "replace", "path": "/spec/http/0/route/1/weight", "value": 25}]'

# Week 2: 25% → 50%
# Week 3: 50% → 100%
# Week 4: Delete v1
```

---

### Q6: Linkerd vs Istio — comparison + when to choose?

**Answer:**

**HOW — Detailed comparison:**

| Feature | Istio | Linkerd |
|---|---|---|
| **Language** | Go + Envoy (C++) | Rust |
| **Memory per sidecar** | ~50-100 MB | ~10-20 MB |
| **CPU per sidecar** | High | Low |
| **Complexity** | Very high | Moderate |
| **Learning curve** | Steep | Gentler |
| **mTLS** | ✅ | ✅ |
| **Traffic management** | ✅ Advanced | ✅ Basic |
| **Multi-cluster** | ✅ Complex | ✅ Simpler |
| **Service Profile** | ❌ | ✅ |
| **WebAssembly extensions** | ✅ | ❌ |
| **Community** | Larger | Smaller but growing |
| **Best for** | Enterprise, advanced needs | Quick wins, simpler |

**HOW — Linkerd install + use:**

```bash
# Install CLI
curl -sL https://run.linkerd.io/install | sh
export PATH=$PATH:$HOME/.linkerd2/bin

# Pre-flight check
linkerd check --pre

# Install
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -

# Install Viz dashboard
linkerd viz install | kubectl apply -f -

# Enable injection per namespace
kubectl annotate namespace default linkerd.io/inject=enabled

# Restart pods to inject sidecars
kubectl rollout restart deployment/myapp

# Dashboard
linkerd viz dashboard
```

**Linkerd ServiceProfile (unique feature):**

```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: myapp.default.svc.cluster.local
spec:
  routes:
    - name: get_users
      condition:
        method: GET
        pathRegex: "/users(/.*)?"
      responseClasses:
        - condition:
            status:
              min: 500
              max: 599
          isFailure: true
      timeout: 10s
      isRetryable: true
```

---

### Q7: Observability with service mesh — what comes free?

**Answer:**

**WHAT mesh provides automatically:**

**1. Golden Metrics (RED + USE)**
- Request rate, errors, duration
- Per service, per method
- No code changes

**2. Distributed traces**
- Trace ID propagation
- Span per service hop

**3. Access logs**
- Per request
- With timing breakdown

**HOW — Prometheus metrics (Istio):**

```promql
# Request rate per service
sum(rate(istio_requests_total[5m])) by (destination_service)

# Error rate
sum(rate(istio_requests_total{response_code=~"5.."}[5m]))
  / sum(rate(istio_requests_total[5m])) * 100

# p99 latency
histogram_quantile(0.99,
  sum(rate(istio_request_duration_milliseconds_bucket[5m]))
    by (destination_service, le))

# Active connections
sum(envoy_cluster_upstream_cx_active) by (cluster_name)
```

**HOW — Kiali (Istio service graph):**

```bash
# Install
istioctl install --set values.kiali.enabled=true

# Access
istioctl dashboard kiali
```

Visual service-to-service topology with traffic flow, errors, latency overlaid.

**HOW — Jaeger tracing (auto with Istio):**

```bash
# Install
istioctl install --set values.tracing.enabled=true

# Trace context propagation — Istio injects headers
# But: APP MUST FORWARD trace headers to downstream calls
# Headers to forward:
# - x-request-id
# - x-b3-traceid
# - x-b3-spanid
# - x-b3-parentspanid
# - x-b3-sampled
# - x-b3-flags
# - x-ot-span-context
```

```python
# Python: forward headers
TRACE_HEADERS = [
    "x-request-id",
    "x-b3-traceid",
    "x-b3-spanid",
    "x-b3-parentspanid",
    "x-b3-sampled",
    "x-b3-flags",
    "x-ot-span-context",
]

@app.middleware("http")
async def forward_trace_headers(request: Request, call_next):
    # Save headers to context
    trace_headers = {h: request.headers.get(h) for h in TRACE_HEADERS if h in request.headers}
    request.state.trace_headers = trace_headers
    return await call_next(request)


# When calling downstream
async def call_downstream(url):
    headers = current_request.state.trace_headers
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
```

---

### Q8: Service mesh anti-patterns — kya nahi karein?

**Answer:**

**❌ Anti-pattern 1: Use mesh for small projects**

```
3 services, monolith-like:
- Mesh overhead: 50 MB × 3 = 150 MB extra RAM
- Operational complexity
- Steep learning curve

✅ Just use Kubernetes Services with TLS in app
```

**❌ Anti-pattern 2: Skip business logic with mesh**

```
"Mesh handles auth, so we don't need to validate in app"

WRONG: Mesh provides:
- Service identity (who is calling)
- Encryption (mTLS)

Mesh does NOT provide:
- User authentication (JWT validation)
- Business rules ("can user X access order Y?")
- Resource-level authorization

✅ Mesh + App-level both needed
```

**❌ Anti-pattern 3: Use mesh as API gateway**

```
Service mesh ≠ API gateway

Mesh: East-west (service-to-service inside cluster)
Gateway: North-south (external users → cluster)

Different concerns:
- Gateway: rate limiting per user, JWT validation, request transformation
- Mesh: service identity, internal routing
```

**❌ Anti-pattern 4: Mesh for monolith**

```
Single deployment doesn't need service mesh
No service-to-service traffic to mesh!
```

**❌ Anti-pattern 5: Skip observability investment**

```
"Istio gives us observability for free!"

Reality:
- Need Prometheus, Grafana, Jaeger, Kiali installed
- Dashboards need building
- Alerts need configuring
- Storage costs add up
- Operational team needed

✅ Budget for observability infrastructure
```

---

## Service Mesh Setup Checklist

```markdown
### Choosing Mesh
- [ ] 10+ services? (mesh worth it)
- [ ] Polyglot? (mesh > app library)
- [ ] Team capable? (operational complexity)
- [ ] AWS-only? (consider App Mesh)

### Installation
- [ ] Istio OR Linkerd (don't run both)
- [ ] Profile choice (demo vs default vs minimal)
- [ ] Namespace injection enabled
- [ ] Sidecar resource limits set

### Security
- [ ] mTLS STRICT mode (after migration)
- [ ] AuthorizationPolicies per service
- [ ] JWT validation at gateway/mesh
- [ ] Network policies as defense in depth

### Traffic Management
- [ ] DestinationRules per service
- [ ] VirtualServices for routing
- [ ] Canary deployment process
- [ ] Circuit breaker config
- [ ] Retry/timeout policies

### Observability
- [ ] Prometheus + Grafana
- [ ] Jaeger / Tempo for tracing
- [ ] Kiali / Linkerd Viz for service graph
- [ ] Trace headers forwarded in app code

### Operations
- [ ] Upgrade plan (mesh upgrades non-trivial)
- [ ] Backup of CRDs
- [ ] Monitoring of mesh itself
- [ ] On-call runbook for mesh issues
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Skip trace header forwarding | Broken traces | Forward in app code |
| Strict mTLS during migration | Service outage | Use PERMISSIVE first |
| No resource limits on sidecar | OOM kills | Set requests + limits |
| Mesh for 3 services | Over-engineering | Skip mesh |
| Single Istiod instance | SPOF | HA Istiod (3+ replicas) |
| No mesh upgrade plan | Stuck on old version | Quarterly upgrades |
| Forget app-level RBAC | Mesh ≠ authorization | App still validates |
