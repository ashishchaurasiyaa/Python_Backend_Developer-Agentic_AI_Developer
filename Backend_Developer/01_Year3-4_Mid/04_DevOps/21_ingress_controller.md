# 21 — Kubernetes Ingress Controller

> The single entry point that routes external HTTP(S) traffic into the right Service inside a cluster, based on hostname/path.

---

## Why It Matters

Every app on Kubernetes eventually needs external traffic routed in by host
(`api.example.com` vs `admin.example.com`) or path (`/api` vs `/app`) to
different Services — without provisioning a separate cloud load balancer per
app. Ingress is the standard way this is done, and it's the piece that sits
directly in front of everything else in this folder (Nginx config, TLS certs,
rate limiting) at the cluster boundary.

Senior interview: "You have 5 microservices in one cluster, need one public
domain routing to each by path — how?" → one Ingress resource + an Ingress
controller (nginx-ingress, Traefik, or a cloud-native ALB controller).

---

## Core Concept — Ingress *resource* vs Ingress *controller*

```
Ingress RESOURCE = a Kubernetes object (YAML) declaring routing RULES.
                   Does nothing by itself.

Ingress CONTROLLER = the actual running software (a pod, usually built on
                   Nginx/Envoy/HAProxy) that reads Ingress resources and
                   configures itself to implement the routing.

You always need BOTH — a cluster with zero Ingress controllers installed
will accept Ingress resources but nothing will actually route traffic.
```

```
Internet
   │
   ▼
Cloud Load Balancer (1 external IP)
   │
   ▼
Ingress Controller (pod, e.g., ingress-nginx)
   │  reads Ingress resources, routes by host/path
   ├──► Service A (api.example.com/orders)
   ├──► Service B (api.example.com/users)
   └──► Service C (admin.example.com)
```

---

## Basic Ingress resource

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /orders
            pathType: Prefix
            backend:
              service:
                name: orders-service
                port: { number: 80 }
          - path: /users
            pathType: Prefix
            backend:
              service:
                name: users-service
                port: { number: 80 }
    - host: admin.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-service
                port: { number: 80 }
```

One Ingress resource, one cloud load balancer, routes to 3 different
backend Services by host+path — versus provisioning 3 separate cloud LBs
(expensive, one per app) without Ingress.

---

## TLS termination at the Ingress

```yaml
spec:
  tls:
    - hosts: ["api.example.com"]
      secretName: api-example-com-tls   # a K8s Secret holding cert+key
  rules:
    - host: api.example.com
      # ...
```

```bash
# cert-manager automates issuing/renewing this secret via Let's Encrypt
# (the standard pairing: ingress-nginx + cert-manager)
kubectl annotate ingress myapp-ingress \
  cert-manager.io/cluster-issuer=letsencrypt-prod
```

TLS terminates **at the Ingress controller** — traffic from the Ingress
controller to backend pods is typically plain HTTP inside the cluster
network (unless you're also running a service mesh enforcing mTLS internally,
see `06_kubernetes_helm.md`'s Istio coverage).

---

## Popular Ingress controllers (know the tradeoffs)

| Controller | Notes |
|---|---|
| **ingress-nginx** | Most common, mature, config via annotations (can feel hacky at scale) |
| **Traefik** | Cloud-native from the ground up, cleaner CRD-based config, built-in Let's Encrypt |
| **AWS ALB Ingress Controller** | Provisions an actual AWS Application Load Balancer per Ingress — no separate nginx pod layer, native AWS integration |
| **Istio Gateway** | If already running a service mesh, Istio's own ingress replaces a separate controller entirely |
| **Gateway API** (newer K8s standard) | Successor to Ingress — more expressive (traffic splitting, header-based routing) but Ingress is still the more widely deployed standard today |

**Interview-correct positioning:** know `ingress-nginx` cold (most common in
interviews/real deployments), be aware `Gateway API` exists as where the
ecosystem is heading.

---

## Rate limiting / auth at the Ingress layer (ties to existing coverage)

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "10"          # requests/sec per IP
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: basic-auth
```

This is a second, infra-level rate-limiting layer distinct from the
application-level rate limiting in `41_fastapi_rate_limiting.md` — Ingress-level
protects against volumetric abuse before a request even reaches your app pods;
app-level enforces per-user/business-logic limits. Production systems layer both.

---

## Interview Q&A

**Q: Do you need an Ingress controller for a cluster to work at all?**
A: No — Ingress is purely for routing external HTTP(S) traffic in by
host/path. A cluster works fine without one; you'd just need a separate
`LoadBalancer`-type Service (and separate cloud LB, $$$) per app instead of
one shared entry point.

**Q: Ingress vs a plain `Service` of type `LoadBalancer` — why prefer Ingress?**
A: `LoadBalancer` Services provision one cloud load balancer PER service —
expensive and doesn't support host/path-based routing. Ingress lets many
Services share ONE external load balancer with routing rules on top.

**Q: Where does TLS get terminated in a typical Ingress setup?**
A: At the Ingress controller itself — it holds the cert (often via
cert-manager + Let's Encrypt), decrypts incoming HTTPS, and typically
forwards plain HTTP to backend pods within the cluster network.

---

Related: `02_nginx.md` (same reverse-proxy concepts, cluster-external vs
cluster-internal), `06_kubernetes_helm.md`, [41_fastapi_rate_limiting.md](../../00_Year0-2_Junior/06_FastAPI/41_fastapi_rate_limiting.md)
(app-level rate limiting this complements).
