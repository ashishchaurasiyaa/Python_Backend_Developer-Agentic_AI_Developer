# Kubernetes Architecture & Core Objects
**DevOps Track · Phase 6: Kubernetes**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/06_kubernetes_helm.md (app-deployment angle) — this covers the full cluster architecture and object model.

## Quick Concepts

- **Cluster** = a set of machines (nodes) running Kubernetes, managed as one unit
- **Node** = a single machine (VM or bare metal) in the cluster — either a control plane node or a worker node
- **Control Plane** = the brain: makes global decisions (scheduling, scaling, reacting to failures)
- **Worker Node** = where your actual application containers (Pods) run
- **Pod** = smallest deployable unit — one or more tightly coupled containers sharing network/storage
- **ReplicaSet** = ensures N identical Pod replicas are running at all times
- **Deployment** = manages ReplicaSets, adds rolling updates + rollback on top
- **StatefulSet** = like a Deployment, but for Pods needing stable identity and stable storage
- **DaemonSet** = ensures exactly one Pod runs on every (or a selected subset of) node
- **Job** = runs Pods to completion, then stops (batch work)
- **CronJob** = runs a Job on a schedule
- **Namespace** = a virtual cluster-within-a-cluster — scopes names, RBAC, quotas, and NetworkPolicies
- **Probe** (liveness/readiness/startup) = a periodic health check the kubelet runs against a container to decide whether to restart it or route traffic to it
- **Init container** = runs to completion BEFORE a Pod's main containers start, sequentially, one at a time
- **`kubectl apply`** = declarative create-or-update, idempotent, safe to re-run — what GitOps/CI pipelines actually use
- **Context** = a named combination of cluster + user + default namespace in a kubeconfig — what `kubectl config use-context` switches between

---

## Why This Matters

```
Docker Compose solves "run my containers on ONE machine."
Kubernetes solves "run my containers across a FLEET of machines,
self-heal when they crash, scale them under load, and roll out
changes without downtime."

An infra engineer needs the architecture picture because 90% of
production K8s debugging is "which component owns this decision":
   - Pod stuck Pending          → scheduler / resource capacity
   - Pod CrashLoopBackOff        → kubelet + container runtime, app logs
   - Service not routing traffic → kube-proxy, endpoints, labels/selectors
   - Cluster state looks wrong   → etcd, API server
```

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              CONTROL PLANE                │
                         │  (usually 3 nodes for HA, or managed by    │
                         │   cloud provider — EKS/GKE/AKS)            │
                         │                                             │
                         │  ┌───────────────┐   ┌──────────────────┐ │
  kubectl ──REST/TLS──►  │  │  kube-apiserver │◄─│      etcd         │ │
                         │  │  (front door,   │  │ (distributed KV    │ │
                         │  │  auth, validate,│  │  store — cluster's │ │
                         │  │  the ONLY thing │  │  single source of   │ │
                         │  │  touching etcd) │  │  truth)             │ │
                         │  └────────┬────────┘   └──────────────────┘ │
                         │           │                                  │
                         │  ┌────────▼────────┐  ┌───────────────────┐ │
                         │  │  kube-scheduler  │  │ controller-manager │ │
                         │  │  (assigns Pods   │  │ (runs control      │ │
                         │  │   to nodes)      │  │  loops: replicas,   │ │
                         │  │                  │  │  nodes, jobs, etc.) │ │
                         │  └──────────────────┘  └───────────────────┘ │
                         └─────────────────────────────────────────────┘
                                          │
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
              ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
              │  WORKER NODE 1 │  │  WORKER NODE 2 │  │  WORKER NODE 3 │
              │                │  │                │  │                │
              │  kubelet       │  │  kubelet       │  │  kubelet       │
              │  (talks to API │  │                │  │                │
              │   server, runs │  │                │  │                │
              │   Pods via CRI)│  │                │  │                │
              │                │  │                │  │                │
              │  kube-proxy    │  │  kube-proxy    │  │  kube-proxy    │
              │  (Service IP   │  │                │  │                │
              │   routing)     │  │                │  │                │
              │                │  │                │  │                │
              │  container     │  │  container     │  │  container     │
              │  runtime       │  │  runtime       │  │  runtime       │
              │  (containerd)  │  │  (containerd)  │  │  (containerd)  │
              │                │  │                │  │                │
              │  [Pod] [Pod]   │  │  [Pod] [Pod]   │  │  [Pod]         │
              └──────────────┘  └──────────────┘  └──────────────┘
```

### Control Plane Components

| Component | Responsibility |
|---|---|
| **kube-apiserver** | The only component that talks to etcd directly. Validates and processes all REST requests (from `kubectl`, controllers, kubelets). Everything goes through it. |
| **etcd** | Distributed, consistent key-value store — the cluster's entire state (every object's desired + current spec) lives here. Losing etcd = losing the cluster's memory. |
| **kube-scheduler** | Watches for newly created Pods with no assigned node, picks the best node based on resource requests, affinity/anti-affinity, taints/tolerations, then writes the binding back via the API server. |
| **controller-manager** | Runs many independent control loops in one binary (Node controller, ReplicaSet controller, Job controller, etc.) — each continuously compares desired state (in etcd) to actual state and acts to reconcile them. |
| **cloud-controller-manager** | (Managed clusters) Talks to the cloud provider's API — provisions LoadBalancers, attaches disks, labels nodes with cloud metadata. |

### Worker Node Components

| Component | Responsibility |
|---|---|
| **kubelet** | The primary "node agent." Watches the API server for Pods assigned to its node, tells the container runtime to start/stop containers accordingly, reports node/Pod status back. |
| **kube-proxy** | Implements the Service abstraction on each node — programs iptables/IPVS rules so traffic to a Service's virtual IP gets load-balanced to the right backing Pods. |
| **Container runtime** | containerd (or CRI-O) — actually pulls images and runs containers, via the CRI (Container Runtime Interface) that kubelet talks to. |

### The Reconciliation Loop (Core K8s Mental Model)

```
Every controller does the same pattern, forever:

   1. WATCH  desired state in etcd (via API server)
   2. OBSERE actual state in the cluster
   3. DIFF   desired vs actual
   4. ACT    take steps to close the gap
   5. repeat

Example: you set replicas: 5 on a Deployment.
   - ReplicaSet controller sees desired=5, actual=3 (one node died)
   - it creates 2 new Pods
   - scheduler assigns them to healthy nodes
   - kubelets on those nodes start the containers
   - actual becomes 5 again — loop goes quiet until state drifts again

This is why Kubernetes is "declarative" — you never issue an
imperative "start 2 more Pods" command; you declare replicas: 5 and
the system continuously works to make that true.
```

---

## kubectl Basics — Applying, Managing, and Editing Resources

Every YAML example in this file needs to actually get INTO the cluster somehow — the commands that do that, before the deeper object model below.

### `kubectl apply` vs `kubectl create` vs `kubectl delete`

```bash
kubectl apply -f deployment.yaml          # create OR update — DECLARATIVE, idempotent,
                                             # re-running it with a changed file just
                                             # applies the diff. This is the one you'll
                                             # use 95% of the time, and what every
                                             # CI/CD pipeline and GitOps tool uses.
kubectl apply -f ./manifests/                 # apply every YAML file in a directory at once
kubectl apply -f https://raw.githubusercontent.com/.../deploy.yaml   # apply straight from a URL

kubectl create -f deployment.yaml           # create ONLY — IMPERATIVE, fails loudly
                                               # if the resource already exists (no
                                               # update semantics at all)
kubectl create deployment nginx --image=nginx:1.27   # quick one-off, no YAML file needed —
                                                         # fine for a throwaway test, not for
                                                         # anything you want tracked in git

kubectl delete -f deployment.yaml             # delete everything defined in that file
kubectl delete deployment api-deployment        # delete by name directly
kubectl delete pods -l app=api                    # delete every Pod matching a label selector
kubectl delete pod api-pod --grace-period=0 --force  # skip graceful termination entirely —
                                                        # emergency use only, bypasses the
                                                        # SIGTERM-then-wait behavior a
                                                        # normal delete respects
```

```
apply vs create — the distinction that actually matters: `apply`
tracks a "last-applied-configuration" annotation and computes a
three-way diff (last-applied vs your new file vs live cluster state)
on every run, which is WHY it can safely be re-run repeatedly (the
entire premise GitOps and CI/CD pipelines rely on). `create` has no
such tracking — running it twice against the same file just errors
"already exists" the second time.
```

### `kubectl edit` and `kubectl scale` — Quick Imperative Changes

```bash
kubectl edit deployment api-deployment      # opens the LIVE resource in your $EDITOR —
                                               # save and exit applies the change immediately.
                                               # Convenient for a quick fix; the change is
                                               # NOT reflected back into your YAML file/git,
                                               # so it silently drifts from source of truth
                                               # (exactly the "drift" problem GitOps solves)

kubectl scale deployment api-deployment --replicas=5    # imperative scale — works, but an
                                                            # HPA (Phase 6's scaling file) will
                                                            # immediately override it back to
                                                            # whatever ITS target computes, if
                                                            # one is configured on that Deployment
```

### `kubectl label` and `kubectl annotate`

Labels are the selector mechanism every Service, Deployment, and NetworkPolicy in this entire phase depends on — here's how you actually set one on a resource that already exists.

```bash
kubectl label pod api-pod tier=backend           # add a new label
kubectl label pod api-pod tier=backend --overwrite  # required if the key already exists
kubectl label pod api-pod tier-                    # trailing dash REMOVES a label

kubectl get pods -l app=api,tier=backend             # select by multiple labels (AND)
kubectl get pods --show-labels                         # see every label currently set

kubectl annotate deployment api-deployment description="owned by team-backend"
# annotations are NOT selectable (no kubectl get -l on them) — they're for
# metadata a human or tool reads (like the nginx.ingress.kubernetes.io/...
# annotations from the networking file), not for selection logic
```

### Multi-Cluster Context Switching

```bash
kubectl config get-contexts               # list every cluster/user/namespace combo
                                             # this kubeconfig knows about
kubectl config current-context              # which one is active RIGHT NOW —
                                               # the single most important command to
                                               # run before ANY destructive kubectl command,
                                               # since "I thought I was on staging" is a
                                               # real, common way to accidentally kubectl
                                               # delete something in production
kubectl config use-context prod-cluster       # switch active context
kubectl config set-context --current --namespace=staging   # also shown earlier — bind a
                                                               # default namespace to the
                                                               # current context so you stop
                                                               # typing -n every time

# View/merge multiple kubeconfig files (common when you have separate
# per-cluster kubeconfigs from different cloud accounts)
KUBECONFIG=~/.kube/config:~/.kube/prod-config kubectl config view --flatten > ~/.kube/merged-config
```

### Discovering the API — `kubectl explain`

```bash
kubectl explain deployment.spec.strategy          # full field-by-field schema documentation,
                                                     # straight from the API server — no need
                                                     # to look up docs online for "what fields
                                                     # does rollingUpdate accept"
kubectl explain pod.spec.containers.livenessProbe   # works for deeply nested fields too
kubectl api-resources                                 # list every resource TYPE the cluster
                                                          # supports (including any CRDs installed)
```

### `kubectl cp` — Files In and Out of a Pod

```bash
kubectl cp api-pod:/app/logs/error.log ./error.log     # copy OUT of a Pod
kubectl cp ./config.yml api-pod:/app/config.yml          # copy INTO a Pod
kubectl cp api-pod:/app/data ./data -c sidecar-container   # multi-container Pod — specify WHICH one
```

```
kubectl cp is genuinely a last resort for debugging (grabbing a log
file, inspecting a generated config) — never a real deployment
mechanism. Anything that needs to persist should be a ConfigMap,
Secret, or PersistentVolume (Phase 6's storage file); a file copied in
via kubectl cp vanishes the moment the Pod is rescheduled, same as
anything else written to a container's ephemeral filesystem.
```

### Node Maintenance — `cordon`, `drain`, `uncordon`

```bash
kubectl cordon node-3          # mark node-3 UNSCHEDULABLE for NEW Pods —
                                  # existing Pods on it keep running untouched
kubectl drain node-3 --ignore-daemonsets --delete-emptydir-data
                                # cordons AND evicts existing Pods (respecting
                                  # any PodDisruptionBudget — Phase 6's scaling
                                  # file — so it can BLOCK/retry rather than
                                  # violate one), for planned maintenance
kubectl uncordon node-3           # mark it schedulable again once maintenance is done
```

```
cordon alone vs drain — cordon just stops NEW Pods from landing there
(existing ones stay put, useful when you want to gradually stop using
a node without disrupting what's already running). drain actively
EVICTS what's already there too — the actual "I'm about to take this
node down for real" command, and the one whose behavior a
PodDisruptionBudget constrains.
```

---

## Namespaces — Virtual Clusters Within a Cluster

Every object referenced so far (Pods, Deployments, Services, ConfigMaps, Secrets) is **namespaced** — it lives inside exactly one Namespace, whether or not you ever type `-n <namespace>` explicitly (the unset default is literally a namespace called `default`).

```bash
kubectl get namespaces
kubectl create namespace staging
kubectl get pods -n staging          # or --namespace staging
kubectl config set-context --current --namespace=staging   # stop typing -n every time
```

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: staging
```

```
What a Namespace actually scopes:
  - NAMES         → api-service can exist in BOTH "staging" and
                     "production" namespaces simultaneously, no
                     collision — names are unique per-namespace, not
                     cluster-wide
  - RBAC          → a Role (vs ClusterRole) applies to exactly one
                     namespace (Phase 14's RBAC content)
  - ResourceQuota  → CPU/memory/object-count ceilings, per-namespace (below)
  - NetworkPolicy   → the podSelector/namespaceSelector scoping in
                      Phase 6's NetworkPolicy content operates per-namespace

What a Namespace does NOT scope:
  - Nodes, PersistentVolumes (cluster-scoped — not namespaced)
  - ClusterRole/ClusterRoleBinding (also cluster-scoped by definition)
```

```
Common real convention: one namespace per environment (dev/staging/
production) OR per team/service-group in a shared cluster — never
per single microservice at fine granularity (that turns into hundreds
of namespaces with no real isolation benefit over just using labels).
Namespaces are a governance/blast-radius boundary, not a free-for-all
subdivision.
```

**Interview framing:** "why not just run separate clusters per environment instead of namespaces" is a real question — namespaces are cheaper (one control plane, shared nodes) but weaker isolation (a NetworkPolicy misconfiguration or a Node-level compromise can still cross namespace boundaries); separate clusters cost more but give a genuinely harder security/blast-radius boundary. Most teams use namespaces for dev/staging and either namespaces OR separate clusters for production, depending on compliance requirements.

---

## Core Objects

### Pod

The smallest deployable unit — normally you don't create bare Pods directly (a Deployment manages them), but every higher-level object ultimately creates Pods.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
  labels:
    app: nginx
spec:
  containers:
    - name: nginx
      image: nginx:1.27
      ports:
        - containerPort: 80
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "250m"
          memory: "256Mi"
```

### Probes — How Kubernetes Knows a Container Is Actually Healthy

Without a probe, the kubelet's only signal is "is the process still running" — a container can be alive but completely unable to serve traffic (deadlocked, stuck waiting on a dependency, still warming up a cache) and Kubernetes would have no way to know.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  containers:
    - name: api
      image: myrepo/api:1.4.2
      ports:
        - containerPort: 8000
      startupProbe:
        httpGet:
          path: /healthz
          port: 8000
        failureThreshold: 30      # allow up to 30 × periodSeconds to boot
        periodSeconds: 2            # before liveness/readiness even start checking
      livenessProbe:
        httpGet:
          path: /healthz
          port: 8000
        periodSeconds: 10
        failureThreshold: 3         # 3 consecutive failures → kubelet KILLS and restarts the container
      readinessProbe:
        httpGet:
          path: /ready
          port: 8000
        periodSeconds: 5
        failureThreshold: 2          # 2 consecutive failures → Pod removed from Service endpoints,
                                        # but the container is NOT killed or restarted
```

```
liveness   → "is this container STUCK and needs a restart?"
             Failing this KILLS the container (kubelet restarts it,
             same as a crash). Use for genuine deadlock/hang detection —
             a BAD liveness probe (checking a downstream DB it doesn't
             actually need to be "alive") causes needless restart loops.

readiness  → "can this container serve traffic RIGHT NOW?"
             Failing this REMOVES the Pod from the Service's endpoints
             (no traffic routed to it) WITHOUT killing/restarting the
             container — exactly the mechanism the zero-downtime
             deployment checklist in Phase 20 depends on. A Pod that's
             temporarily overloaded or still connecting to its DB
             should fail readiness, NOT liveness.

startup    → "has this SLOW-STARTING app finished booting yet?"
             While a startupProbe is defined and still failing, liveness
             AND readiness checks are SUSPENDED entirely — prevents a
             slow-booting app (large cache warm-up, JVM startup) from
             being killed by liveness for "taking too long," which is
             exactly what happens without a startupProbe and a
             liveness probe with too-short a failureThreshold.
```

```
The single most common REAL bug: liveness and readiness pointed at the
SAME endpoint with the SAME thresholds. If a container's DOWNSTREAM
database goes down, a liveness probe checking DB connectivity fails →
kubelet KILLS and restarts every replica → new replicas ALSO can't
reach the (still-down) database → they get killed again → a full
crash-loop across the entire deployment, caused BY the health check
mechanism, for a dependency the app itself can't fix by restarting.
The fix: liveness checks "is my own process responsive" (cheap, no
external dependency); readiness checks "can I actually serve a real
request right now" (can include the DB check) — only readiness should
ever depend on things a restart can't fix.
```

### Init Containers — Run-to-Completion Before the Main Event

An init container runs BEFORE a Pod's regular containers start, one at a time in order, and must exit 0 before the next one (or the main containers) begins.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  initContainers:
    - name: wait-for-db
      image: busybox:1.36
      command: ["sh", "-c", "until nc -z postgres 5432; do sleep 2; done"]
    - name: run-migrations
      image: myrepo/api:1.4.2
      command: ["python", "manage.py", "migrate", "--noinput"]
  containers:
    - name: api
      image: myrepo/api:1.4.2
      ports:
        - containerPort: 8000
```

```
Why NOT just do this inside the main container's entrypoint script
(the ENTRYPOINT pattern from Phase 5's Dockerfile file)? Both are
legitimate — init containers are the right call when:
  - the setup step needs a DIFFERENT image than the main container
    (a slim busybox for a network-wait check, vs the full app image)
  - you want the setup step's failure to be VISIBLE and DISTINCT in
    `kubectl get pods` (shows "Init:0/2" state) rather than buried in
    the main container's own startup logs
  - the setup MUST fully complete (exit 0) before the main container's
    readiness/liveness probes even start being evaluated at all

If a migration only needs to run ONCE per deploy (not once per Pod
replica), a Job (below) is usually the better fit than an init
container repeated across every replica of a Deployment.
```

### ReplicaSet

Ensures a fixed number of identical Pod replicas exist. You almost never write these by hand — Deployments create and manage them.

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: nginx-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx:1.27
```

### Deployment

Manages ReplicaSets, adds rolling updates and rollback. This is the default choice for stateless workloads.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1          # extra Pods allowed during rollout
      maxUnavailable: 0    # zero-downtime — never fewer than 3 healthy
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: myrepo/api:1.4.2
          ports:
            - containerPort: 8000
```

```bash
kubectl rollout status deployment/api-deployment
kubectl rollout undo deployment/api-deployment          # rollback to previous revision
kubectl rollout history deployment/api-deployment
```

### StatefulSet — vs Deployment

| | Deployment | StatefulSet |
|---|---|---|
| Pod identity | Interchangeable, random suffix (`api-7f9c-x2j4`) | Stable, ordinal (`db-0`, `db-1`, `db-2`) — survives rescheduling |
| Pod DNS | Not individually addressable | Each Pod gets a stable DNS name via a headless Service (`db-0.db-svc`) |
| Storage | Shared or none — Pods are disposable | Each Pod gets its OWN PersistentVolumeClaim, tied to its ordinal, reattached on reschedule |
| Startup/scale order | Parallel, any order | Sequential — `db-0` ready before `db-1` starts (configurable) |
| Use when | Stateless apps: web APIs, workers | Databases, Kafka/Zookeeper, anything needing "this exact instance keeps its exact disk and identity" |

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres-headless   # must point to a headless Service
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:            # ← the key difference from Deployment
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

### DaemonSet

Ensures exactly one Pod copy runs on every node (or a filtered subset via nodeSelector) — used for node-level infrastructure agents.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-collector
spec:
  selector:
    matchLabels:
      app: log-collector
  template:
    metadata:
      labels:
        app: log-collector
    spec:
      containers:
        - name: fluent-bit
          image: fluent/fluent-bit:3.0
          volumeMounts:
            - name: varlog
              mountPath: /var/log
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
```

**Real-world DaemonSet examples:** log shippers (Fluentd/Fluent Bit), node monitoring agents (node-exporter for Prometheus), CNI network plugins, storage daemons.

### Job

Runs Pods to completion for batch/one-off work — unlike a Deployment, it does NOT keep the Pod running or restart it after success.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
spec:
  backoffLimit: 3       # retries on failure before giving up
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: myrepo/api:1.4.2
          command: ["python", "manage.py", "migrate"]
```

### CronJob

Runs a Job on a schedule, using standard cron syntax.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-cleanup
spec:
  schedule: "0 2 * * *"     # 2 AM daily
  concurrencyPolicy: Forbid  # don't start a new run if the last one is still going
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: cleanup
              image: myrepo/cleanup-job:1.0
```

---

## Object Selection Cheat Sheet

```
Stateless web app / API           → Deployment
Database, Kafka, anything needing
  stable identity + own disk       → StatefulSet
One Pod per node (agents, log
  shippers, network plugins)       → DaemonSet
Run once and finish (migration,
  batch export)                    → Job
Run on a schedule                  → CronJob
Manually pinned exact replica
  count with no rollout logic
  (rare, low-level)                → ReplicaSet directly
```

---

## CRDs and Operators — Extending Kubernetes With Your Own Object Types

Every object in this file (Pod, Deployment, StatefulSet...) is a **built-in** resource. A **CustomResourceDefinition (CRD)** registers a brand-new object KIND with the API server — after that, `kubectl get postgresqlbackup` works exactly like `kubectl get pods` does, for a resource type Kubernetes never shipped with.

```yaml
# A CRD just DECLARES the schema — it does nothing by itself
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: postgresqlbackups.db.example.com
spec:
  group: db.example.com
  names:
    kind: PostgreSQLBackup
    plural: postgresqlbackups
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                schedule: { type: string }
                retentionDays: { type: integer }
```

```
A CRD alone is just a SCHEMA — creating a PostgreSQLBackup object
does nothing on its own, the same way creating an Ingress object does
nothing without an Ingress Controller watching it (Phase 6's
networking file). An OPERATOR is the controller that actually watches
for these custom objects and DOES something — runs the reconciliation
loop pattern from earlier in this file, but for a domain-specific
resource instead of a built-in one.

Real-world examples: the Prometheus Operator (watching a `ServiceMonitor`
CRD to auto-configure scraping), cert-manager (watching a `Certificate`
CRD to issue/renew TLS certs), the CloudNativePG or Zalando Postgres
Operator (watching a `Postgresql` CRD to manage backups/failover) — ArgoCD
itself is exactly this pattern too (an `Application` CRD + a controller
reconciling cluster state to match Git, per the GitOps file elsewhere
in this track).
```

**Why this matters even if you never write one yourself:** almost every "installed via Helm" piece of cluster infrastructure you'll consume (Prometheus stack, cert-manager, ArgoCD, most database-as-a-service-on-K8s tools) IS a CRD + Operator pair under the hood — recognizing that pattern is what lets you reason about a tool you've never seen before ("there's probably a CRD defining its config, and a controller Pod somewhere reconciling it") instead of treating it as unexplainable magic.

---

## kubectl Troubleshooting Cheat Sheet

Beyond `kubectl get`/`describe` shown throughout this file — the commands that actually resolve "why is this broken" fastest.

```bash
kubectl get pods -o wide                    # see WHICH NODE each Pod landed on, plus Pod IP
kubectl get events --sort-by=.lastTimestamp   # cluster-wide events, newest last — often shows
                                                 # the REAL reason before you even open `describe`
kubectl describe pod <name>                     # scheduling failures, probe failures, image
                                                   # pull errors — the single best first command

kubectl logs <pod>                                # current container's logs
kubectl logs <pod> --previous                       # PREVIOUS instance's logs — the only way to
                                                       # see why a container crashed, AFTER it
                                                       # already restarted and the new logs are clean
kubectl logs <pod> -c <container-name>                # multi-container Pod — logs are PER CONTAINER,
                                                         # not merged, always specify -c if >1 container
kubectl logs -f deployment/api                          # follow logs from any Pod behind this Deployment

kubectl exec -it <pod> -- /bin/sh                # shell into a running container (if it HAS a shell —
                                                    # distroless images from Phase 14 don't)
kubectl port-forward pod/<pod> 8080:8000           # tunnel a local port straight to a Pod, bypassing
                                                      # Service/Ingress entirely — isolates "is it the
                                                      # APP" from "is it the Service/networking layer"
kubectl top pods                                     # live CPU/memory usage (needs Metrics Server —
                                                        # see Phase 6's HPA content)
kubectl top nodes                                      # same, per NODE — spot an overloaded node fast

kubectl get pod <pod> -o yaml                    # full resolved spec — see EXACTLY what's running,
                                                    # including defaults you didn't set explicitly
kubectl diff -f deployment.yaml                    # what WOULD change if you applied this file,
                                                      # without actually applying it
```

```
Diagnostic order that actually works, fastest-signal first:
  1. kubectl get pods                → what STATE is it in (Pending/CrashLoopBackOff/Running)?
  2. kubectl get events --sort-by=...   → often names the exact cause already
  3. kubectl describe pod <name>          → scheduling/probe/image-pull detail
  4. kubectl logs <pod> [--previous]         → what did the APP itself say
  5. kubectl exec / port-forward                → interactive investigation, last resort
```

---

## Interview Angle

**Q: A Pod is stuck in `Pending` — where do you look first?**
The scheduler couldn't place it. Check `kubectl describe pod <name>` for scheduling events — usually insufficient node resources (CPU/memory requests exceed what any node can offer), an unsatisfiable nodeSelector/affinity rule, or a taint with no matching toleration.

**Q: Why can't you just scale a StatefulSet the same way you scale a Deployment?**
You can scale replica count the same way, but each new Pod gets a fresh PersistentVolumeClaim provisioned per its ordinal, and Pods start/terminate in strict sequential order by default — because identity and storage are pinned per-ordinal, not interchangeable across replicas like a Deployment's are.

**Q: If etcd is lost, what happens to running Pods?**
Already-running Pods keep running on their nodes (kubelets don't need continuous API server contact to keep existing containers alive), but the cluster loses its ability to schedule new work, reconcile drift, or serve `kubectl` reads/writes until etcd is restored from backup — which is why etcd backup is one of the most critical operational responsibilities in self-managed Kubernetes.

**Q: What's the actual difference between `kubectl apply` and `kubectl create`, and why do GitOps tools and CI/CD pipelines always use `apply`?**
`kubectl create` is purely imperative — it creates a resource once and errors "already exists" on any re-run against the same file. `kubectl apply` tracks a last-applied-configuration annotation and computes a three-way diff (last-applied vs new file vs live cluster state) every time it runs, which is what makes it safe and idempotent to re-run repeatedly — exactly the property GitOps (continuously re-applying the same repo state) and CI/CD pipelines (re-running the same deploy step) depend on.

**Q: Someone ran `kubectl edit` directly on a production Deployment to fix something quickly. What's the problem with this, even if the fix worked?**
The change only exists in the live cluster — it's not reflected back into the YAML file or git, so the cluster's actual state has now silently DRIFTED from whatever's checked into version control. The next `kubectl apply -f deployment.yaml` (or the next GitOps sync) will silently revert the live fix back to what's in the file, since neither Kubernetes nor Git has any record the manual edit ever happened. This is exactly the class of problem GitOps's continuous reconciliation is designed to catch and correct.

**Q: You're about to run a destructive `kubectl delete` command — what's the one command you should run first, every time, and why?**
`kubectl config current-context` — confirming which cluster you're actually pointed at. "I thought I was on staging" against a kubeconfig that was actually pointed at the production context is a real, common way to accidentally delete production resources; checking the active context first costs one command and prevents the entire class of mistake.

**Q: A downstream database outage causes EVERY replica of an unrelated Deployment to crash-loop. What misconfiguration causes this, and how do you fix it?**
The Deployment's `livenessProbe` is checking database connectivity (or something else the container itself can't fix by restarting). When the DB goes down, liveness fails on every replica, the kubelet kills and restarts all of them, the new replicas STILL can't reach the down DB, and they get killed again — an infinite crash-loop caused by the health check itself, not the original outage. Fix: liveness should only check "is my own process responsive" (cheap, no external dependency); the DB check belongs in `readinessProbe`, which pulls a Pod out of Service endpoints without killing/restarting the container.

**Q: Why use an init container instead of just handling setup (like waiting for a dependency, or running migrations) inside the main container's entrypoint script?**
Init containers let the setup step use a DIFFERENT image than the main app (a minimal image for a network-wait check instead of the full app image), make the setup failure visible and distinct in `kubectl get pods` (`Init:0/2` state) rather than buried in application logs, and guarantee the step fully completes before the main container's probes are even evaluated. That said, for something that should run ONCE per deploy rather than once per Pod replica (like a migration in a multi-replica Deployment), a Job is usually the better fit.

**Q: What's the practical difference between running two environments as separate Namespaces versus separate clusters?**
Namespaces share one control plane and node pool — cheaper, faster to spin up, but a NetworkPolicy misconfiguration or a node-level compromise can still cross namespace boundaries, since the underlying infrastructure is genuinely shared. Separate clusters cost more and add operational overhead (multiple control planes to manage/upgrade) but provide a much harder isolation boundary. Most teams use namespaces for dev/staging and reserve separate clusters for production only when compliance or security requirements demand real physical isolation.

---

## Related

- [`04_scaling_security_rbac.md`](04_scaling_security_rbac.md) — Taints/Tolerations/Node Affinity (which node a Pod lands on) and ResourceQuota/LimitRange (namespace-level governance building on the Namespace concept above)
- [`02_services_networking_ingress.md`](02_services_networking_ingress.md) — how readinessProbe failures interact with Service endpoints
- [`05_helm.md`](05_helm.md) — how CRDs + Operators are typically installed and versioned in practice
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — the zero-downtime rolling-update checklist that depends entirely on readinessProbe behaving correctly
