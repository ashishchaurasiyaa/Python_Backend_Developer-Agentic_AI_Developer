# Lecture 4: Containerization with Docker and Kubernetes

> *"Containers package apps consistently. Kubernetes runs them at scale."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why containerization** — solving deployment pain
- **Docker fundamentals** — images and containers
- **Why Kubernetes** — orchestrating at scale
- **What Kubernetes provides** — core capabilities
- **Architectural implications**
- **When to use Docker + K8s**

---

## 1. Why Containerization?

### The Old World

```
Traditional deployments faced:
   ✗ "Works on my machine" syndrome
   ✗ App tightly coupled to OS
   ✗ Different libs in dev vs prod
   ✗ Brittle setup
   ✗ Scaling = repeating fragile setup
   ✗ Configuration drift
```

### The Container Solution

```
Containers package:
   ✓ Application code
   ✓ All dependencies
   ✓ Runtime
   ✓ System tools
   ✓ Configuration

All in ONE lightweight, isolated unit.

→ Runs THE SAME EVERYWHERE.
```

### Real Benefits

```
✓ True environment parity
✓ Predictable deployments
✓ Easy horizontal scaling
✓ Reduced operational overhead
✓ Fast startup (seconds vs minutes)
✓ Better resource utilization
```

---

## 2. Docker Fundamentals

### Two Core Concepts

```
IMAGE: blueprint (read-only template)
CONTAINER: running instance of image
```

### Visual

```
   ┌────────────────────┐
   │   Docker Image     │  ← Blueprint
   │   (read-only)       │     - App code
   │                     │     - Dependencies
   │                     │     - Runtime
   └─────────┬──────────┘     - Config
             │
             │ docker run
             ▼
   ┌────────────────────┐
   │   Container        │  ← Running instance
   │   (running)         │     - Isolated process
   │                     │     - Has own network
   │                     │     - Own filesystem
   └────────────────────┘
```

### Containers vs VMs

```
   VM:                       Container:
   ┌──────────┐             ┌──────────┐
   │   App    │             │   App    │
   ├──────────┤             ├──────────┤
   │  Libs    │             │  Libs    │
   ├──────────┤             ├──────────┤
   │   OS     │             │ (shares  │
   │ (full!)  │             │  host OS)│
   ├──────────┤             ├──────────┤
   │Hypervisor│             │  Docker  │
   ├──────────┤             ├──────────┤
   │ Hardware │             │ Hardware │
   └──────────┘             └──────────┘
   
   Size: GBs                 Size: MBs
   Boot: minutes             Boot: seconds
   Overhead: heavy           Overhead: minimal
```

### Dockerfile

```dockerfile
# Recipe for building image
FROM python:3.11-slim          # Base image

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code
COPY . .

# How to run
EXPOSE 8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
```

### Docker Commands

```bash
# Build image
$ docker build -t myapp:v1 .

# Run container
$ docker run -p 8000:8000 myapp:v1

# Push to registry
$ docker push registry.example.com/myapp:v1

# Run from registry anywhere!
```

### CI/CD Foundation

```
Build → Test → Push to registry → Deploy
   ✓ Image is immutable
   ✓ Same image in dev, staging, prod
   ✓ Repeatable, automated, fast
```

---

## 3. Why Kubernetes?

### One Container ≠ Production System

```
For real systems you need:
   ✓ Multiple services
   ✓ Multiple instances of each
   ✓ Across multiple machines
   ✓ Networking
   ✓ Storage
   ✓ Secrets
   ✓ Configuration management
   ✓ Automatic restarts
   ✓ Scaling
   ✓ Load balancing
   ✓ Rolling updates
   ✓ Service discovery
```

### Kubernetes = Orchestrator

```
✓ Automates container deployment
✓ Manages distributed clusters
✓ Treats infrastructure as programmable system
✓ Declarative model: "I want 3 of service X"
✓ Self-healing: maintains desired state
```

### Why It Won

```
✓ Open source
✓ Cloud-agnostic (works anywhere)
✓ Strong community + ecosystem
✓ Battle-tested at scale (Google's heritage)
✓ Industry standard for containers
✓ Extensible (CRDs, operators)
```

### Kubernetes Architecture

```
   ┌─────────────────────────────────────────────────┐
   │            CONTROL PLANE                          │
   │  ┌─────────┐ ┌──────────┐ ┌──────────────────┐   │
   │  │ API     │ │ Scheduler│ │ Controller        │   │
   │  │ Server  │ │           │ │ Manager           │   │
   │  └─────────┘ └──────────┘ └──────────────────┘   │
   │  ┌──────────────────────────────────────────┐    │
   │  │            etcd (state store)             │    │
   │  └──────────────────────────────────────────┘    │
   └─────────────────────────────────────────────────┘
                          │
                          │ schedules pods
                          ▼
   ┌─────────────────────────────────────────────────┐
   │            WORKER NODES                           │
   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
   │  │ Pod  │ │ Pod  │ │ Pod  │ │ Pod  │ │ Pod  │    │
   │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘    │
   │  (each pod runs containers)                       │
   └─────────────────────────────────────────────────┘
```

---

## 4. What Kubernetes Provides

### Capability 1: Auto-Scaling & Load Balancing

```
✓ Horizontal Pod Autoscaler (HPA)
   - Based on CPU, memory, custom metrics
✓ Vertical Pod Autoscaler (VPA)
   - Adjusts resources per pod
✓ Cluster Autoscaler
   - Adds/removes nodes
✓ Built-in load balancing across pods
```

### Capability 2: Rolling Updates & Rollbacks

```
Deploy new version:
   ✓ Gradually replace old pods with new
   ✓ Zero downtime
   ✓ Automatic rollback on failure
   ✓ Can pause/resume mid-deploy
```

### Capability 3: Service Discovery & Networking

```
✓ Internal DNS (service.namespace.svc.cluster.local)
✓ Services find each other dynamically
✓ Built-in load balancing
✓ Network policies (microsegmentation)
✓ Ingress for external access
```

### Capability 4: Resource Limits & Isolation

```
Per container:
   ✓ CPU limits + requests
   ✓ Memory limits + requests
   ✓ Storage limits
   ✓ Network isolation
   
Result:
   ✓ No noisy neighbors
   ✓ Predictable performance
   ✓ Cluster stability
```

### Capability 5: Self-Healing

```
Kubernetes constantly monitors:
   ✗ Pod crashed? → Restart it
   ✗ Pod unhealthy? → Replace it
   ✗ Node failed? → Reschedule pods
   ✗ Deployment broken? → Stop rollout
   
Maintains DESIRED STATE automatically.
```

### Other Built-In Features

```
✓ Secrets management
✓ ConfigMap (configuration)
✓ Persistent Volumes (storage)
✓ Jobs / CronJobs (batch + scheduled)
✓ StatefulSets (stateful apps)
✓ DaemonSets (one pod per node)
✓ Resource quotas
✓ RBAC (role-based access)
```

---

## 5. Architectural Implications

### Implication 1: Enables Microservices

```
Without K8s:
   ✗ Microservices = ops nightmare
   ✗ Each service needs orchestration

With K8s:
   ✓ Each service in own container
   ✓ K8s manages all of them
   ✓ True modularity
```

### Implication 2: Horizontal Scaling

```
Add more pods:
   $ kubectl scale deployment myapp --replicas=10

Auto-scale on load:
   $ kubectl autoscale deployment myapp \
       --min=2 --max=20 --cpu-percent=70

No manual intervention needed.
```

### Implication 3: Fault Isolation

```
✓ Pod crashes → other pods unaffected
✓ Node fails → pods reschedule
✓ Bad deploy → rollback automatically
✓ High availability built in
```

### Implication 4: CI/CD Friendly

```
Container + K8s = perfect CI/CD:
   ✓ Build image in CI
   ✓ Push to registry
   ✓ Update K8s deployment
   ✓ K8s handles the rest

Tools:
   ✓ GitHub Actions
   ✓ ArgoCD (GitOps)
   ✓ Flux
   ✓ Jenkins X
```

### Implication 5: Cloud-Native & Hybrid

```
✓ Runs anywhere K8s runs:
   - AWS EKS
   - Google GKE
   - Azure AKS
   - On-premises
   - Edge devices
   - Your laptop (minikube)

✓ Same config + manifests work everywhere
✓ Multi-cloud + hybrid strategies viable
```

---

## 6. Kubernetes Ecosystem

### Distributions

```
✓ Vanilla Kubernetes (kubernetes.io)
✓ AWS EKS
✓ Google GKE
✓ Azure AKS
✓ Red Hat OpenShift
✓ Rancher
✓ k3s (lightweight)
✓ minikube (local dev)
```

### Tools

```
PACKAGE MANAGEMENT:
   ✓ Helm (the package manager)
   ✓ Kustomize

DEPLOYMENT:
   ✓ ArgoCD (GitOps)
   ✓ Flux

OBSERVABILITY:
   ✓ Prometheus + Grafana
   ✓ Jaeger / Zipkin
   ✓ Datadog

NETWORKING:
   ✓ Istio / Linkerd (service mesh)
   ✓ Cilium (eBPF networking)

SECURITY:
   ✓ OPA (policies)
   ✓ Falco (runtime security)
   ✓ Trivy (image scanning)

STORAGE:
   ✓ Rook (Ceph)
   ✓ Longhorn
   ✓ CSI drivers
```

---

## 7. When to Use Docker + K8s

### ✅ Good Fit

```
✓ Microservices architecture
✓ Cloud-native applications
✓ Multi-environment deployments
✓ Need horizontal scaling
✓ Multiple teams deploying independently
✓ Container-first development culture
✓ Hybrid / multi-cloud strategies
```

### ❌ Bad Fit

```
✗ Single-team, single-app systems (overhead too high)
✗ Tiny scale (just a few users)
✗ When PaaS would do (Heroku, Render)
✗ Strict latency requirements (network overhead)
✗ Truly stateful workloads (challenging)
```

### Hierarchy of Complexity

```
SIMPLEST → MOST COMPLEX

1. SaaS (Heroku, Render)         ← Easiest
2. Container service (Cloud Run, Fargate)
3. Managed K8s (EKS, GKE, AKS)
4. Self-hosted K8s                ← Hardest

→ Don't jump to step 4 unless needed!
```

---

## 8. Migration Path

### Phase 1: Containerize

```
Step 1: Create Dockerfile for app
Step 2: Build + push image to registry
Step 3: Run locally with docker run
Step 4: Run with docker-compose

→ Foundation for everything else
```

### Phase 2: Use Managed Container Service

```
Step 1: AWS ECS, Cloud Run, or App Service
Step 2: Deploy via container service
Step 3: Use managed networking + LB

→ Simpler than K8s, often enough!
```

### Phase 3: Adopt Kubernetes

```
Step 1: Use managed K8s (EKS, GKE, AKS)
Step 2: Migrate workload manifests
Step 3: Add Helm for packaging
Step 4: Add observability stack
Step 5: Add service mesh (if needed)

→ Full cloud-native journey
```

### Phase 4: Advanced K8s

```
Step 1: GitOps (ArgoCD)
Step 2: Custom operators
Step 3: Multi-cluster
Step 4: Multi-region
Step 5: Edge clusters

→ Enterprise scale
```

---

## 9. Common Anti-Patterns

### Anti-Pattern 1: Premature K8s

```
❌ "We're a 3-person startup - let's use K8s!"

Result:
   ✗ Spend 80% time on infrastructure
   ✗ 20% on actual product
   ✗ Burnout

✅ Start with PaaS / managed services
✅ Move to K8s when it makes business sense
```

### Anti-Pattern 2: Stateful in Pods

```
❌ Putting databases in regular pods

Problem:
   ✗ Pods are ephemeral
   ✗ Data loss on restart
   ✗ Complex state management

✅ Use StatefulSets (purpose-built)
✅ Or use managed services (RDS, etc.)
```

### Anti-Pattern 3: Monolithic Images

```
❌ One huge image with everything

Result:
   ✗ Slow builds
   ✗ Slow pulls
   ✗ Hard to scale parts independently

✅ Split into microservices
✅ Each with own focused image
```

### Anti-Pattern 4: Hand-Crafted Manifests

```
❌ Maintaining 100+ raw YAML files by hand

Problem:
   ✗ Duplication everywhere
   ✗ Drift between environments

✅ Use Helm charts
✅ Use Kustomize for environment overlays
```

### Anti-Pattern 5: No Resource Limits

```
❌ No CPU/memory limits on pods

Result:
   ✗ One bad pod can crash node
   ✗ Noisy neighbors
   ✗ Unpredictable performance

✅ Always set resources.limits + requests
```

---

## 10. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Docker packages apps with all dependencies                 │
│  ✅ Containers run consistently across environments            │
│  ✅ Lightweight + fast vs VMs                                  │
│  ✅ Kubernetes orchestrates containers at scale                │
│  ✅ Provides: scaling, healing, networking, deployment         │
│  ✅ Declarative model: define desired state                    │
│  ✅ Self-healing: maintains state automatically                │
│  ✅ Enables true microservices architecture                    │
│  ✅ Cloud-agnostic: runs anywhere                              │
│  ✅ Choose K8s based on actual needs, not hype                 │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Containerize FIRST (Docker basics)
2. Use docker-compose for local dev
3. Try managed container services before K8s
4. Use managed K8s (EKS/GKE/AKS) when needed
5. Always set resource limits
6. Use Helm for packaging
7. Adopt GitOps for deployments
8. Statefuls require StatefulSets or managed services
9. Monitor everything (Prometheus + Grafana)
10. K8s is powerful — use only when needed
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll dive into **Load Balancing and Auto Scaling** — making cloud-native apps responsive and cost-efficient.

> **Practical file:** [04_Practical_Hands_On.md](04_Practical_Hands_On.md)

---

## 📚 References

- *Kubernetes in Action* — Marko Lukša
- *Docker Deep Dive* — Nigel Poulton
- Kubernetes documentation
- Cloud Native Computing Foundation (CNCF)
- *Programming Kubernetes* — Michael Hausenblas
