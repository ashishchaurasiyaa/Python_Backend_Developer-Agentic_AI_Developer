# Kubernetes Services, Networking & Ingress
**DevOps Track · Phase 6: Kubernetes**

## Quick Concepts

- **Service** = stable virtual IP + DNS name in front of a set of Pods, selected by label
- **ClusterIP** = default Service type, reachable only inside the cluster
- **NodePort** = exposes the Service on a static port on every node's IP
- **LoadBalancer** = provisions an external cloud load balancer pointing at the Service
- **Headless Service** = `clusterIP: None` — no virtual IP, DNS returns Pod IPs directly
- **Ingress** = HTTP(S) layer-7 router sitting in front of multiple Services (host/path-based routing, TLS termination)
- **Ingress Controller** = the actual proxy (nginx, Traefik, ALB Ingress Controller) that implements Ingress rules — Ingress objects do nothing without one running in the cluster
- **NetworkPolicy** = firewall rules for Pod-to-Pod traffic, enforced by the CNI plugin

---

## Why This Matters

```
Pods are ephemeral — they die and get replaced with new IPs constantly.
Nothing should ever talk to a Pod IP directly. Services exist to give
a STABLE address in front of a churning set of Pods, and Ingress exists
to give ONE external entry point that fans out to many Services by
hostname/path instead of provisioning a separate cloud load balancer
(and its cost) per service.

NetworkPolicy is the piece people forget: by default, Kubernetes
networking is a flat network — EVERY Pod can reach EVERY other Pod,
across namespaces, with zero firewalling. That's a real security gap
in multi-tenant or compliance-sensitive clusters.
```

---

## Services

A Service selects Pods by **label**, not by name or identity — `kube-proxy` on every node programs routing rules (iptables/IPVS) so traffic to the Service's virtual IP gets distributed across all matching, ready Pods.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
spec:
  selector:
    app: api                # matches Pods labeled app: api
  ports:
    - port: 80               # Service's own port
      targetPort: 8000        # container port to forward to
```

### Service Types Compared

| Type | Reachable from | Gets a cloud LB | Typical use |
|---|---|---|---|
| **ClusterIP** (default) | Inside the cluster only | No | Internal service-to-service traffic (api → db) |
| **NodePort** | Anywhere that can reach any node's IP, on a fixed port (30000-32767) | No | Dev/testing, on-prem clusters without a cloud LB integration |
| **LoadBalancer** | Public internet (or internal LB, depending on annotation) | Yes — cloud provider provisions a real LB | Production external entry point for one service |
| **Headless** (`clusterIP: None`) | DNS returns individual Pod IPs, not a virtual IP | No | StatefulSets — clients need to address specific Pod instances directly |

```yaml
# ClusterIP — internal only (default, no need to set type explicitly)
apiVersion: v1
kind: Service
metadata:
  name: db-internal
spec:
  type: ClusterIP
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

```yaml
# NodePort — exposes on <any-node-ip>:30080
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
spec:
  type: NodePort
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8000
      nodePort: 30080
```

```yaml
# LoadBalancer — cloud provider provisions a real external LB, gets a public IP/DNS
apiVersion: v1
kind: Service
metadata:
  name: api-external
spec:
  type: LoadBalancer
  selector:
    app: api
  ports:
    - port: 443
      targetPort: 8000
```

```yaml
# Headless — used with StatefulSets so each Pod is individually addressable
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
    - port: 5432
# DNS: postgres-0.postgres-headless.default.svc.cluster.local → Pod 0's own IP
#      postgres-1.postgres-headless.default.svc.cluster.local → Pod 1's own IP
```

```
Layering (each type BUILDS on the one below it):

  LoadBalancer  ──► also creates ──► NodePort ──► also creates ──► ClusterIP
  (external LB routes to)          (node-level port routes to)   (base virtual IP)
```

---

## Ingress

Ingress is a layer-7 (HTTP/HTTPS) router — it exists so you don't need one LoadBalancer Service (and its cloud cost) per application. One Ingress + one Ingress Controller can fan out to dozens of backend Services by hostname and path.

**Important:** creating an `Ingress` object does nothing on its own — you need an **Ingress Controller** (nginx-ingress, Traefik, AWS ALB Ingress Controller, etc.) actually deployed and watching for Ingress objects to configure itself.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls-cert
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend-service
                port:
                  number: 80
```

```
app.example.com/api/*  ──►  api-service      (backend API)
app.example.com/*      ──►  frontend-service (React/Vue static app)

Both served through ONE external IP / LoadBalancer, TLS-terminated
at the Ingress Controller — instead of two separate cloud LBs.
```

```bash
kubectl get ingress
kubectl describe ingress app-ingress
```

---

## Network Policies

By default, Kubernetes networking is **flat** — any Pod can reach any other Pod on any port, cluster-wide, regardless of namespace. NetworkPolicy objects restrict this, but only take effect if your CNI plugin supports enforcement (Calico, Cilium, Weave Net — the default `kubenet`/basic bridge does NOT enforce them, silently).

### Deny-All-By-Default (the recommended baseline)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}          # selects ALL pods in the namespace
  policyTypes:
    - Ingress
    - Egress
  # no ingress/egress rules defined → nothing is allowed in or out
```

### Then Allow Specific Traffic

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-to-db
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: postgres           # this policy applies TO postgres Pods
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api          # ONLY Pods labeled app=api may connect
      ports:
        - protocol: TCP
          port: 5432
```

```yaml
# allow egress from api Pods to postgres AND to DNS (kube-dns needs port 53,
# almost always required alongside any egress-restricting policy)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

### Senior Tip

```
NetworkPolicies are ADDITIVE within a selector scope — once ANY policy
selects a Pod for a given direction (ingress/egress), that direction
becomes default-deny except for what policies explicitly allow. There
is no "deny" rule type — you only ever write "allow" rules, and the
absence of a matching allow rule IS the deny.

Classic footgun: writing an egress-restricting NetworkPolicy and
forgetting to allow DNS (port 53) — the app can't resolve ANY hostname
afterward, including its own dependencies, and looks completely broken
for a reason that has nothing to do with the actual rule you wrote.
```

---

## Interview Angle

**Q: Why use Ingress instead of just giving every Service a `LoadBalancer` type?**
Cost and manageability — every `LoadBalancer` Service provisions a real cloud load balancer (billed separately). Ingress lets one external LB/entry point fan out to many backend Services by host/path, with centralized TLS termination, instead of one expensive LB per microservice.

**Q: What's the actual difference between a headless Service and a normal ClusterIP Service?**
A ClusterIP Service load-balances traffic across Pods behind one stable virtual IP — clients don't know or care which Pod answered. A headless Service (`clusterIP: None`) has no virtual IP at all; DNS lookups return the individual Pod IPs directly, letting clients address a *specific* Pod instance — required for StatefulSets where each replica has distinct identity/data (e.g., connecting to `postgres-0` specifically, not "any postgres Pod").

**Q: You wrote a default-deny NetworkPolicy and now the app can't reach the internet at all — what's the most common cause?**
Forgetting to allow egress to DNS (UDP/TCP port 53) alongside your intended egress rule. Once any egress policy selects a Pod, DNS resolution itself is blocked unless explicitly allowed — the app then fails on hostname lookups for everything, not just the traffic you meant to restrict.
