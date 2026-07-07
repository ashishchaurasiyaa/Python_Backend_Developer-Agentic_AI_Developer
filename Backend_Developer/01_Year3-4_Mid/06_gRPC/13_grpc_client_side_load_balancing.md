# gRPC Client-Side Load Balancing

## Quick Concepts

**WHAT:**
- **HTTP/2 multiplexing** = gRPC reuses ONE long-lived TCP connection for many concurrent RPCs (unlike HTTP/1.1's connection-per-request)
- **`pick_first`** = default gRPC LB policy — connect to the first resolved address, stick with it, only failover on disconnect
- **`round_robin`** = client-side LB policy — spread RPCs across all resolved backend addresses
- **Name resolver** = component that turns a target string (`dns:///backend:50051`) into a list of actual backend IPs
- **xDS** = the protocol (from Envoy) letting a control plane push LB config + backend lists to clients dynamically

**WHY this is a distinct problem from HTTP L4/L7 load balancing:**
A traditional L4 load balancer (e.g., a plain TCP load balancer, or older
AWS Classic ELB) balances **connections**, not requests. Since gRPC keeps one
connection open indefinitely and multiplexes hundreds of RPCs over it, an L4
LB sends ALL of a client's traffic to whichever single backend pod it
connected to first — the other pods sit idle. This is invisible until you
notice one pod pegged at 100% CPU while its siblings are idle, despite a
"working" load balancer in front.

---

## The core problem, visualized

```
WITHOUT proper gRPC load balancing (L4 LB in front of gRPC):

  Client ──── 1 persistent HTTP/2 connection ────► Pod A  (gets 100% of traffic)
                                                     Pod B  (idle)
                                                     Pod C  (idle)

  The LB balanced the CONNECTION (one event), not the thousands
  of RPCs multiplexed inside it afterward.
```

```
WITH client-side load balancing (round_robin policy):

  Client ──┬─ connection 1 ──► Pod A
           ├─ connection 2 ──► Pod B
           └─ connection 3 ──► Pod C

  Client resolves ALL backend addresses, opens a connection to
  EACH, and spreads individual RPCs across them itself.
```

---

## Fixing it — Python client with `round_robin`

```python
import grpc

# Default is pick_first — sticks to one address. Force round_robin instead:
channel = grpc.insecure_channel(
    "dns:///backend-service:50051",   # DNS resolver returns multiple A records
    options=[
        ("grpc.lb_policy_name", "round_robin"),
    ],
)
stub = MyServiceStub(channel)
```

```python
# Service config JSON — the standard way to set LB policy (also supports
# retry policy, timeout defaults, defined server-side or via resolver)
service_config = {
    "loadBalancingConfig": [{"round_robin": {}}],
}

channel = grpc.insecure_channel(
    "dns:///backend-service:50051",
    options=[
        ("grpc.service_config", json.dumps(service_config)),
        ("grpc.lb_policy_name", "round_robin"),
    ],
)
```

**Requirement:** the name resolver must actually return multiple addresses.
A Kubernetes **headless Service** (`clusterIP: None`) is what makes this
work — DNS returns one A record per pod IP directly, instead of a single
virtual IP that hides the pod count from the client.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  clusterIP: None      # headless — DNS returns each pod's IP individually
  selector:
    app: backend
  ports:
    - port: 50051
```

---

## The three architectural approaches (know the tradeoffs)

| Approach | How it works | When to use |
|---|---|---|
| **Client-side LB (`round_robin` + headless Service)** | Client resolves all pod IPs directly, balances itself | Simple internal service-to-service calls, no need for a control plane |
| **Proxy/sidecar LB (service mesh — Envoy/Istio)** | A sidecar proxy next to each pod handles LB, retries, mTLS — app code doesn't do LB at all | Already running a service mesh (see [../05_Microservices/06_service_mesh_istio_linkerd.md](../05_Microservices/06_service_mesh_istio_linkerd.md)) — offloads this complexity out of application code |
| **Lookaside LB (xDS control plane)** | Client queries a central control plane (e.g., Envoy's xDS API) for the current backend list + LB config, applies it itself | Large fleets needing dynamic, centrally-managed LB policy without a sidecar's per-request latency overhead |

**Interview-correct answer for "how do you load-balance gRPC in
Kubernetes":** either a headless Service + client-side `round_robin` (simple,
no extra infra) OR a service mesh sidecar (more infra, but centralizes
retries/mTLS/LB policy outside app code) — an L4/ClusterIP Service alone is
the wrong answer and the thing interviewers are checking you know to avoid.

---

## Interview Q&A

**Q: Why doesn't a normal Kubernetes `ClusterIP` Service load-balance gRPC properly?**
A: `ClusterIP` operates at L4 (connection-level) via kube-proxy — it
distributes new TCP *connections*, but gRPC's HTTP/2 connections are
long-lived and multiplexed. Once established, ALL RPCs on that connection go
to the one backend pod it connected to; other pods get none of that client's
traffic.

**Q: What's required for `round_robin` client-side LB to actually help?**
A: A name resolver that returns multiple backend addresses — a Kubernetes
headless Service (DNS returns each pod's IP) rather than a normal Service
(DNS returns one virtual ClusterIP). Without multiple resolved addresses,
`round_robin` has nothing to round-robin across.

**Q: Client-side LB vs service mesh sidecar — which do you recommend?**
A: Client-side LB (headless Service + `round_robin`) for simpler, single-team
service-to-service calls — zero extra infrastructure. Service mesh once you
need centralized policy (retries, mTLS, LB) applied consistently across many
services/teams without each one reimplementing it — the operational
complexity of running a mesh is worth it at that scale, not before.

---

Related: [04_grpc_resilience_retries.md](04_grpc_resilience_retries.md)
(retries/deadlines that combine with LB policy in the same `service_config`),
[../05_Microservices/06_service_mesh_istio_linkerd.md](../05_Microservices/06_service_mesh_istio_linkerd.md) (the sidecar alternative to client-side LB).
