# gRPC Production Deployment — Load Balancing, Kubernetes, AWS ALB/NLB

## Quick Concepts

**WHAT:**
- **gRPC = HTTP/2 based RPC framework** — long-lived connections, multiplexed streams
- **Production deployment** means: scaling, load balancing, health checks, service discovery
- **L4 vs L7 LB** = Transport layer (TCP) vs Application layer (HTTP/2 aware)
- **gRPC Health Check Protocol** = standard gRPC service for liveness/readiness
- **Envoy/Linkerd** = service mesh proxies that understand HTTP/2 + gRPC

**WHY production gRPC deployment is HARD:**
- gRPC clients open **1 persistent connection** + multiplex requests over it
- Regular TCP load balancers (NLB) → connection sticky → **uneven load distribution**
- Need **L7 LB (HTTP/2 aware)** to balance per-request, not per-connection
- ALB supports gRPC since 2020 but with specific config requirements
- Service discovery harder than REST (DNS round-robin doesn't work well)

**HOW production gRPC differs from REST:**
| Aspect | REST | gRPC |
|---|---|---|
| Connection | Short-lived | Long-lived (HTTP/2) |
| Load balancing | Easy (per-request) | Hard (per-stream balancing needed) |
| Health checks | HTTP `/health` | gRPC `grpc.health.v1.Health/Check` |
| AWS LB | ALB or NLB | ALB (with HTTP/2 + target_type=ip) |

---

## Interview Questions & Answers

### Q1: gRPC ko production mein kaise deploy karte ho? Architecture explain karo.

**Answer:**

**WHAT:** Full production architecture has 4 components:
```
Client → Load Balancer → Service Mesh Proxy → gRPC Server Pods
                                              ↑
                                              ↓
                                        Service Registry
```

**WHY each component:**
- **Load Balancer**: Distribute traffic across replicas, SSL termination
- **Service Mesh** (optional): Per-request LB, mTLS, observability
- **Service Registry**: Pod discovery for dynamic scaling
- **Multiple gRPC pods**: HA + scalability

**HOW — Full production deployment on Kubernetes:**

```yaml
# 1. gRPC Server Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
spec:
  replicas: 3                          # ⭐ 3 replicas for HA
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
        - name: user-service
          image: myorg/user-service:1.2.0
          ports:
            - name: grpc
              containerPort: 50051
              protocol: TCP
          # ⭐ gRPC Health Check (NOT HTTP)
          readinessProbe:
            exec:
              command: ["/bin/grpc_health_probe", "-addr=:50051"]
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            exec:
              command: ["/bin/grpc_health_probe", "-addr=:50051"]
            initialDelaySeconds: 30
            periodSeconds: 10
          resources:
            requests: { cpu: "200m", memory: "256Mi" }
            limits:   { cpu: "1000m", memory: "1Gi" }

---
# 2. Headless Service (for client-side LB)
# WHY headless? gRPC client gets ALL pod IPs, balances itself
apiVersion: v1
kind: Service
metadata:
  name: user-service
spec:
  clusterIP: None                      # ⭐ Headless = client gets all IPs
  ports:
    - port: 50051
      targetPort: 50051
      protocol: TCP
  selector:
    app: user-service

---
# 3. HPA (auto-scaling based on CPU)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: user-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: user-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
```

---

### Q2: L4 vs L7 load balancing for gRPC — kya difference hai aur kyu matter karta hai?

**Answer:**

**WHAT:**
- **L4 (Transport):** Looks at TCP packets only — balances per **connection**
- **L7 (Application):** Understands HTTP/2 frames — balances per **request/stream**

**WHY this matters for gRPC:**
```
Problem with L4 LB + gRPC:
┌──────────┐                ┌──────────────┐
│ Client 1 │─── 1 conn ───→ │ Pod A (busy) │  ← gets ALL requests from Client 1
└──────────┘                ├──────────────┤
                            │ Pod B (idle) │  ← gets nothing
                            ├──────────────┤
                            │ Pod C (idle) │  ← gets nothing
                            └──────────────┘

Result: Pod A overloaded, B/C idle → uneven load → scaling broken
```

**HOW to solve:**

| Option | Layer | Works for gRPC? | Notes |
|---|---|---|---|
| **AWS NLB** | L4 | ⚠️ Per-connection only | Use with client-side LB |
| **AWS ALB** | L7 | ✅ Per-request (since 2020) | Requires HTTP/2 target type |
| **Envoy Proxy** | L7 | ✅ Best for gRPC | Per-request LB, retries, mTLS |
| **Linkerd/Istio** | L7 | ✅ Service mesh | Full observability + LB |
| **Headless Service + Client-side LB** | Client | ✅ Simplest | Client picks pod |
| **gRPC built-in `round_robin`** | Client | ✅ With DNS | Works with headless Service |

**HOW — Client-side LB code (simplest production approach):**
```python
import grpc

# ⭐ Use 'dns:///' scheme for client-side LB
# Resolves all A records from headless service, balances round-robin
channel = grpc.aio.insecure_channel(
    "dns:///user-service.default.svc.cluster.local:50051",
    options=[
        ("grpc.lb_policy_name", "round_robin"),
        ("grpc.service_config", '{"loadBalancingConfig":[{"round_robin":{}}]}'),
    ]
)
```

---

### Q3: AWS ALB ke saath gRPC kaise configure karte ho?

**Answer:**

**WHAT:** ALB supports gRPC since 2020 but **specific config** required.

**WHY ALB chosen over NLB:**
- ✅ L7 (HTTP/2 aware) → per-request balancing
- ✅ SSL termination at LB (cheaper certs)
- ✅ WAF integration possible
- ❌ Slightly higher latency than NLB (~1ms)

**HOW — Terraform configuration:**

```hcl
# 1. Target Group (must use HTTP2 protocol)
resource "aws_lb_target_group" "grpc_service" {
  name                 = "user-grpc-tg"
  port                 = 50051
  protocol             = "HTTP"               # NOT TCP
  protocol_version     = "GRPC"               # ⭐ CRITICAL: GRPC version
  target_type          = "ip"                 # ⭐ ip (not instance) for Fargate
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    enabled             = true
    protocol            = "HTTP"
    path                = "/grpc.health.v1.Health/Check"  # ⭐ gRPC health endpoint
    matcher             = "0"                              # ⭐ gRPC status code 0 = OK
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
  }
}

# 2. ALB Listener (HTTPS REQUIRED for HTTP/2)
resource "aws_lb_listener" "grpc" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate.api.arn
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grpc_service.arn
  }
}

# 3. Security Group — allow gRPC port from ALB only
resource "aws_security_group" "grpc_service" {
  name = "user-service-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 50051
    to_port         = 50051
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
}
```

**Critical gotchas:**
- ❌ HTTP listener → won't work (need HTTPS for HTTP/2)
- ❌ `target_type = "instance"` → can't do gRPC (use `ip`)
- ❌ `protocol_version = "HTTP2"` → wrong (must be `"GRPC"`)
- ❌ Health check `matcher = "200"` → wrong (gRPC uses status `0`)

---

### Q4: gRPC Health Check Protocol kya hai? Kaise implement karte ho?

**Answer:**

**WHAT:** Standard gRPC service `grpc.health.v1.Health` with `Check` and `Watch` methods.

**WHY standard protocol needed:**
- ALB/Envoy/K8s probes need consistent way to check gRPC server health
- HTTP `/health` endpoint doesn't work for pure gRPC services
- `grpc_health_probe` binary uses this protocol

**HOW — Python implementation:**

```python
# server.py
import grpc
from grpc_health.v1 import health, health_pb2_grpc, health_pb2
from concurrent import futures
import asyncio

class HealthServicer(health.HealthServicer):
    """
    INTERVIEW: Standard gRPC Health Check service.
    Returns SERVING / NOT_SERVING / SERVICE_UNKNOWN
    """
    def __init__(self):
        super().__init__()
        self._status = {}      # service_name → status

    def set(self, service: str, status):
        self._status[service] = status

    async def Check(self, request, context):
        # ⭐ Empty service name = check OVERALL server health
        status = self._status.get(request.service, health_pb2.HealthCheckResponse.SERVING)
        return health_pb2.HealthCheckResponse(status=status)

    async def Watch(self, request, context):
        # Streaming health updates (for clients that want live status)
        while not context.cancelled():
            status = self._status.get(request.service, health_pb2.HealthCheckResponse.SERVING)
            yield health_pb2.HealthCheckResponse(status=status)
            await asyncio.sleep(5)


async def serve():
    server = grpc.aio.server()

    # Add your services
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)

    # ⭐ Add Health service (REQUIRED for production)
    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    # Mark overall server as SERVING
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    # Mark specific service
    health_servicer.set("userservice.UserService", health_pb2.HealthCheckResponse.SERVING)

    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

**HOW — Dockerfile with grpc_health_probe:**
```dockerfile
FROM python:3.12-slim

# ⭐ Install grpc_health_probe binary (used by K8s probes)
RUN GRPC_HEALTH_PROBE_VERSION=v0.4.24 && \
    wget -qO/bin/grpc_health_probe \
    https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/${GRPC_HEALTH_PROBE_VERSION}/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe

# ... rest of Dockerfile

# K8s readiness check uses this binary
HEALTHCHECK --interval=30s CMD ["grpc_health_probe", "-addr=:50051"]
```

---

### Q5: Envoy Proxy kya hai? gRPC ke liye kyu use karte hain?

**Answer:**

**WHAT:** Envoy = high-performance L7 proxy (originated at Lyft, now CNCF).

**WHY for gRPC specifically:**
- ✅ Native HTTP/2 support → true per-request LB
- ✅ Service discovery integration (DNS, Consul, EDS)
- ✅ Built-in retries, circuit breaking, timeouts
- ✅ mTLS termination
- ✅ Detailed metrics for Prometheus
- ✅ Used by Istio service mesh

**HOW — Envoy config for gRPC:**

```yaml
# envoy.yaml
static_resources:
  listeners:
    - address:
        socket_address: { address: 0.0.0.0, port_value: 8080 }
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                codec_type: HTTP2          # ⭐ HTTP/2 for gRPC
                stat_prefix: ingress_grpc
                route_config:
                  name: grpc_routes
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      routes:
                        - match:
                            prefix: "/userservice.UserService"
                          route:
                            cluster: user_service_cluster
                            timeout: 30s
                            # ⭐ Retry policy (HTTP-level)
                            retry_policy:
                              retry_on: "5xx,reset,connect-failure,refused-stream"
                              num_retries: 3
                              per_try_timeout: 10s
                http_filters:
                  - name: envoy.filters.http.router

  clusters:
    - name: user_service_cluster
      connect_timeout: 5s
      type: STRICT_DNS                   # ⭐ DNS-based discovery
      lb_policy: ROUND_ROBIN             # ⭐ Per-request LB
      http2_protocol_options: {}         # ⭐ Enable HTTP/2

      # Health checking
      health_checks:
        - timeout: 10s
          interval: 30s
          unhealthy_threshold: 3
          healthy_threshold: 2
          grpc_health_check:             # ⭐ Use gRPC health protocol
            service_name: ""

      # Circuit breaker
      circuit_breakers:
        thresholds:
          - max_connections: 1000
            max_pending_requests: 100
            max_requests: 1000
            max_retries: 3

      load_assignment:
        cluster_name: user_service_cluster
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: user-service-headless.default.svc.cluster.local
                      port_value: 50051
```

---

### Q6: Kubernetes me gRPC service ki special considerations kya hain?

**Answer:**

**WHAT/WHY: 3 main considerations:**

**1. Headless Service (for client-side LB)**
```yaml
# WHY: Regular Service does TCP-level LB (connection-sticky)
# Headless Service returns ALL pod IPs → client balances
apiVersion: v1
kind: Service
metadata:
  name: user-service-headless
spec:
  clusterIP: None              # ⭐ Headless
  ports: [{ port: 50051 }]
  selector: { app: user-service }
```

**2. gRPC Health Probes (NOT HTTP)**
```yaml
# WHY: HTTP probes can't check gRPC server health
# Use grpc_health_probe binary inside container
readinessProbe:
  exec:
    command: ["/bin/grpc_health_probe", "-addr=:50051"]

# K8s 1.24+ supports native gRPC probes:
readinessProbe:
  grpc:
    port: 50051
    service: ""                # empty = overall health
```

**3. Pod Disruption Budget (graceful upgrades)**
```yaml
# WHY: During node drain, don't kill ALL pods at once
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: user-service-pdb
spec:
  minAvailable: 2              # ⭐ Always keep 2 pods up
  selector:
    matchLabels:
      app: user-service
```

**4. Graceful Shutdown**
```python
# server.py — handle SIGTERM gracefully
import asyncio
import signal
import grpc

async def serve():
    server = grpc.aio.server()
    # ... add servicers
    server.add_insecure_port("[::]:50051")

    async def shutdown(sig):
        print(f"Received {sig.name}, shutting down...")
        # ⭐ Grace period: complete active RPCs (don't accept new)
        await server.stop(grace=30)

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))

    await server.start()
    await server.wait_for_termination()
```

---

### Q7: gRPC service discovery kaise karte hain production mein?

**Answer:**

**WHAT:** Mechanism to find available gRPC server instances dynamically.

**WHY needed:**
- Static IPs don't work — pods scale up/down
- DNS-only has TTL issues
- Need real-time membership awareness

**HOW — 4 options ranked by complexity:**

**Option 1: DNS with Headless Service (Simplest)**
```python
# K8s headless service → DNS returns all pod IPs
channel = grpc.aio.insecure_channel(
    "dns:///user-service-headless.default.svc.cluster.local:50051",
    options=[("grpc.lb_policy_name", "round_robin")]
)
# ⚠️ Caveat: DNS TTL caching → slow pod removal awareness
```

**Option 2: Kubernetes Endpoints API (Real-time)**
```python
# Watch K8s Endpoints API → get live pod IPs
from kubernetes import client, watch

v1 = client.CoreV1Api()
w = watch.Watch()
for event in w.stream(v1.list_namespaced_endpoints, namespace="default"):
    endpoints = event["object"]
    if endpoints.metadata.name == "user-service":
        ips = [addr.ip for subset in endpoints.subsets for addr in subset.addresses]
        # Update gRPC channel pool
```

**Option 3: Consul / etcd Service Registry**
```python
import consul

c = consul.Consul()
# Service registers itself on startup
c.agent.service.register(
    name="user-service",
    service_id="user-service-pod-1",
    address="10.0.1.5",
    port=50051,
    check=consul.Check.tcp("10.0.1.5", 50051, "10s")
)

# Client discovers
_, services = c.health.service("user-service", passing=True)
endpoints = [(s["Service"]["Address"], s["Service"]["Port"]) for s in services]
```

**Option 4: AWS Cloud Map (managed)**
```python
import boto3

sd = boto3.client("servicediscovery")
response = sd.discover_instances(
    NamespaceName="myapp.local",
    ServiceName="user-service",
    HealthStatus="HEALTHY"
)
endpoints = [(i["Attributes"]["AWS_INSTANCE_IPV4"], 50051) for i in response["Instances"]]
```

---

## Production Deployment Checklist

```markdown
### Infrastructure
- [ ] gRPC port 50051 in security groups
- [ ] ALB protocol_version = "GRPC" (NOT HTTP2)
- [ ] Target group health check on /grpc.health.v1.Health/Check
- [ ] HTTPS required (HTTP/2 needs TLS)
- [ ] target_type = "ip" (for Fargate)

### Application
- [ ] gRPC Health Service implemented
- [ ] grpc_health_probe binary in Docker image
- [ ] SIGTERM graceful shutdown handler
- [ ] Connection keepalive configured
- [ ] Max message size set appropriately
- [ ] Server reflection enabled (for debugging)

### Kubernetes
- [ ] Headless Service for client-side LB
- [ ] Readiness/Liveness probes use grpc_health_probe
- [ ] Pod Disruption Budget configured
- [ ] HPA based on appropriate metrics
- [ ] Resource requests/limits set

### Client
- [ ] Use 'dns:///' scheme + round_robin LB
- [ ] Implement retries with backoff
- [ ] Deadlines on every RPC
- [ ] Channel reuse (not per-request)
- [ ] Graceful channel close on shutdown
```

---

## Common Production Issues + Fixes

| Issue | Cause | Fix |
|---|---|---|
| **Uneven pod load** | L4 LB sticky connections | Headless Service + client-side round_robin |
| **ALB 502 errors** | Wrong protocol_version | Set to "GRPC" not "HTTP2" |
| **Health check failing** | HTTP health check on gRPC port | Use gRPC health check |
| **Slow pod scaling** | DNS TTL caching | Lower TTL or use K8s Endpoints |
| **Connection drops on deploy** | No graceful shutdown | Implement SIGTERM handler with grace=30s |
| **Memory leak** | Channels not closed | Use connection pool, close on shutdown |
| **High latency p99** | Long-lived connections + node failure | Set TCP keepalive |
| **mTLS handshake errors** | Cert mismatch | Verify SAN matches DNS |
