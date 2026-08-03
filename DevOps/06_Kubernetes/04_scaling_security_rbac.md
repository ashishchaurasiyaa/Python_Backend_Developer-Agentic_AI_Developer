# Kubernetes Scaling & Security (RBAC)
**DevOps Track · Phase 6: Kubernetes**

## Quick Concepts

- **HPA (Horizontal Pod Autoscaler)** = adds/removes Pod replicas based on observed metrics (CPU, memory, custom)
- **VPA (Vertical Pod Autoscaler)** = adjusts a Pod's CPU/memory requests+limits automatically, doesn't change replica count
- **PDB (PodDisruptionBudget)** = a floor on how many/what fraction of a workload's Pods may be voluntarily evicted at once (node drains, cluster upgrades) — does NOT protect against involuntary disruption (node crash, OOM kill)
- **Taint** = a marker on a NODE that repels Pods unless they have a matching toleration
- **Toleration** = a marker on a POD that permits it to be scheduled onto a matching tainted node
- **Node affinity** = a Pod's preference/requirement for particular nodes, based on node labels
- **ResourceQuota** = a namespace-wide ceiling on total CPU/memory/object counts
- **LimitRange** = per-container default and min/max resource bounds within a namespace
- **RBAC (Role-Based Access Control)** = who can do what, on which resources — the K8s permission model
- **Role** = a set of permissions scoped to ONE namespace
- **ClusterRole** = a set of permissions scoped cluster-wide (or reusable across namespaces)
- **RoleBinding** = grants a Role (or ClusterRole) to a user/group/ServiceAccount, within one namespace
- **ClusterRoleBinding** = grants a ClusterRole cluster-wide
- **ServiceAccount** = an identity for a Pod/process to authenticate to the API server (not a human identity)

---

## Why This Matters

```
Scaling: HPA is how you avoid choosing between "over-provisioned and
wasting money" and "under-provisioned and falling over under load" —
it's the standard mechanism for a stateless API tier to survive
traffic spikes without manual intervention.

RBAC: the default behavior in many clusters people copy-paste from
tutorials is dangerously permissive — a Pod's default ServiceAccount,
if bound to cluster-admin "just to get it working," means a single
compromised container can read/modify anything in the entire cluster.
Least-privilege RBAC is not optional in any real production cluster.
```

---

## Horizontal Pod Autoscaler (HPA)

Watches a metric, scales `replicas` up or down on a Deployment/StatefulSet/ReplicaSet to keep that metric near a target.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-deployment
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70      # scale up if avg CPU > 70% of requested
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # wait 5 min of low load before scaling down
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60             # remove at most 1 Pod per minute
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60             # add up to 4 Pods per minute
```

### Custom Metrics (Beyond CPU/Memory)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: queue-worker
  minReplicas: 2
  maxReplicas: 30
  metrics:
    - type: External
      external:
        metric:
          name: sqs_queue_depth        # exposed via a custom metrics adapter
          selector:
            matchLabels:
              queue: order-processing
        target:
          type: AverageValue
          averageValue: "100"          # target ~100 messages per Pod
```

```
CPU/memory-based HPA requires the Metrics Server add-on installed.
Custom/external metrics (queue depth, request latency, requests/sec)
require a metrics adapter — Prometheus Adapter is the common choice —
feeding the custom.metrics.k8s.io / external.metrics.k8s.io API.
```

```bash
kubectl get hpa
kubectl describe hpa api-hpa           # shows current vs target metric, scaling events
kubectl top pods                        # requires Metrics Server
```

### Vertical Pod Autoscaler (VPA)

Instead of changing replica COUNT, VPA adjusts each Pod's CPU/memory `requests`/`limits` based on observed usage history — useful for workloads that can't easily scale horizontally (a single StatefulSet replica, batch jobs) or to right-size initial resource requests.

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: postgres-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: StatefulSet
    name: postgres
  updatePolicy:
    updateMode: "Auto"    # Off (recommend-only) | Initial | Recreate | Auto
  resourcePolicy:
    containerPolicies:
      - containerName: postgres
        minAllowed:
          cpu: "250m"
          memory: "512Mi"
        maxAllowed:
          cpu: "4"
          memory: "8Gi"
```

**HPA vs VPA — don't combine on the same metric:** running both against CPU on the same workload simultaneously causes conflicting resize/scale decisions. Common pattern: VPA in `Off` mode just to get sizing *recommendations*, while HPA does the actual live scaling.

---

## Taints, Tolerations, and Node Affinity — Controlling WHERE Pods Land

HPA/VPA control HOW MANY replicas and HOW MUCH resource each gets. This section controls WHICH nodes a Pod is even allowed to run on — the scheduler's placement decision, made concrete.

### Taints and Tolerations — Repelling Pods From a Node

A **taint** on a node repels Pods, unless the Pod has a matching **toleration**. This is the opposite of a selector: a selector says "I want to run HERE"; a taint says "nothing may run here UNLESS it explicitly tolerates this."

```bash
# Taint a node — e.g. reserve it for GPU workloads only
kubectl taint nodes gpu-node-1 workload=gpu:NoSchedule
```

```yaml
# Only a Pod with THIS toleration can be scheduled onto that tainted node
apiVersion: v1
kind: Pod
metadata:
  name: ml-training-job
spec:
  tolerations:
    - key: "workload"
      operator: "Equal"
      value: "gpu"
      effect: "NoSchedule"
  containers:
    - name: trainer
      image: myrepo/ml-trainer:1.0
```

```
Taint effects:
  NoSchedule         → new Pods without a matching toleration are
                         never scheduled here (existing Pods untouched)
  PreferNoSchedule    → scheduler AVOIDS it if possible, but will use
                          the node if there's genuinely no alternative
  NoExecute             → EVICTS existing Pods without the toleration
                            too, not just blocking new ones — used for
                            things like "node is about to be drained"
                            or "node just went NotReady"
```

**Real-world use:** dedicating expensive GPU nodes to only GPU workloads (untainted Pods never land there and waste that capacity), or automatically evicting Pods from a node the moment it's marked `NotReady` (Kubernetes adds a built-in `NoExecute` taint for this automatically — that's what actually triggers Pods rescheduling off a failing node, tied to `tolerationSeconds` controlling how long a Pod tolerates the node being unreachable before giving up).

### Node Affinity — Attracting Pods TO Specific Nodes

Where taints REPEL, affinity ATTRACTS — a Pod expressing a preference or requirement for particular nodes, based on node labels.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:    # HARD requirement
        nodeSelectorTerms:
          - matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: ["ap-south-1a", "ap-south-1b"]
      preferredDuringSchedulingIgnoredDuringExecution:     # SOFT preference
        - weight: 80
          preference:
            matchExpressions:
              - key: node-type
                operator: In
                values: ["compute-optimized"]
  containers:
    - name: api
      image: myrepo/api:1.4.2
```

```
required...  → the scheduler WON'T place the Pod anywhere that doesn't
               match — same hard-failure behavior as an unsatisfiable
               resource request (Pod stays Pending)
preferred... → the scheduler TRIES to honor it (weighted against other
               preferences) but will still schedule the Pod elsewhere
               rather than leave it Pending

"...IgnoredDuringExecution" (on both) means this is only evaluated at
SCHEDULING time — if node labels change AFTER a Pod is already running
there, Kubernetes does NOT evict/reschedule it to re-satisfy the rule.
```

### Pod Affinity/Anti-Affinity — Relative to OTHER Pods, Not Nodes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchExpressions:
                  - key: app
                    operator: In
                    values: ["api"]
              topologyKey: "kubernetes.io/hostname"   # never 2 api Pods on the SAME node
```

```
podAntiAffinity here spreads a Deployment's own replicas across
DIFFERENT nodes — so a single node failure can't take out every
replica simultaneously. This is the actual mechanism behind "high
availability" for a Deployment beyond just "replicas: 3" — without
anti-affinity, the scheduler is free to (and sometimes will) place
all 3 replicas on the same node, defeating the redundancy entirely.

podAffinity (not anti-) does the opposite — co-locate Pods together,
e.g. scheduling a cache Pod on the SAME node as the API Pod that reads
it most, minimizing network hops for latency-sensitive pairs.
```

**Senior framing — taints/tolerations vs affinity, the distinction that matters in interviews:** taints/tolerations are node-centric ("this node repels most things") — the right tool for dedicating/reserving nodes. Affinity is Pod-centric ("this Pod wants/needs specific nodes, or wants to be near/away from other Pods") — the right tool for spreading replicas or co-locating dependent workloads. Production clusters commonly use BOTH together: a taint reserves GPU nodes, and a toleration + node affinity on the ML Pod both reserves the node AND actively targets it (a toleration alone only permits scheduling there, it doesn't request it).

---

## Resource Governance — ResourceQuota and LimitRange

Individual Pod `resources.requests`/`limits` (Phase 5/6 throughout this track) control ONE Pod. **ResourceQuota** and **LimitRange** operate at the **Namespace** level (Phase 6's architecture file) — the governance layer that stops one team/namespace from starving every other tenant sharing the same cluster.

### ResourceQuota — A Namespace-Wide Ceiling

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-alpha-quota
  namespace: team-alpha
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "50"                    # max Pod COUNT, regardless of size
    persistentvolumeclaims: "10"
    services.loadbalancers: "2"     # cap expensive cloud LB provisioning too
```

```
Once this quota exists in "team-alpha", EVERY Pod created there MUST
specify resources.requests/limits explicitly — a Pod with no resource
requests is REJECTED outright (Kubernetes can't enforce a quota
against an unspecified amount). This is often how a quota gets
noticed for the first time: a previously-fine Pod manifest suddenly
fails to deploy the moment a ResourceQuota is added to its namespace,
because it never had explicit requests/limits before.
```

```bash
kubectl describe resourcequota team-alpha-quota -n team-alpha    # current usage vs hard limits
kubectl get resourcequota -n team-alpha
```

### LimitRange — Default and Bounds PER Pod/Container

Where ResourceQuota caps the NAMESPACE total, **LimitRange** sets defaults and min/max bounds for EACH individual Pod/container — filling in for the "Pod with no resources.requests gets rejected" problem above.

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: team-alpha-limits
  namespace: team-alpha
spec:
  limits:
    - type: Container
      default:                 # applied if a container specifies NO limits
        cpu: "500m"
        memory: "512Mi"
      defaultRequest:            # applied if a container specifies NO requests
        cpu: "100m"
        memory: "128Mi"
      max:                         # hard ceiling — a container CANNOT request more than this
        cpu: "2"
        memory: "4Gi"
      min:                           # hard floor — a container CANNOT request less than this
        cpu: "50m"
        memory: "64Mi"
```

```
ResourceQuota + LimitRange together, the common pairing:
  LimitRange    → every Pod AUTOMATICALLY gets sane default requests/
                   limits even if the developer forgot to set them,
                   AND is bounded from requesting something absurd
                   (0 CPU, or 64 cores)
  ResourceQuota  → the NAMESPACE as a whole can never exceed its
                    allocated share of the cluster, regardless of how
                    many individual Pods try to fit under it
```

**Interview framing:** "how do you prevent one team from starving the whole shared cluster" is answered by this pair, not by HPA/VPA (which only manage ONE workload's own scaling) — ResourceQuota/LimitRange is the multi-tenancy governance layer that makes a shared cluster safe to run multiple teams' workloads on at all.

---

## PodDisruptionBudget (PDB) — Surviving Voluntary Disruptions

HPA/VPA answer "how much capacity do we need." PDB answers a different question: "when someone (a node drain, a cluster upgrade, `kubectl drain`) wants to voluntarily evict our Pods, how many can go at once without breaking us?"

```
Voluntary disruption   → node drain for maintenance, cluster autoscaler
                          scaling a node down, a `kubectl drain` command,
                          a rolling node upgrade
Involuntary disruption → node hardware failure, kernel panic, OOM kill —
                          PDB has NO effect on these, nothing can "budget"
                          around a crash
```

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2          # OR use maxUnavailable — not both
  selector:
    matchLabels:
      app: orders-api
```

```yaml
# Percentage form — scales naturally as replicas change
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb-percent
spec:
  maxUnavailable: 25%
  selector:
    matchLabels:
      app: orders-api
```

```
minAvailable: 2       → eviction API refuses to evict a Pod if doing so
                         would drop healthy Pods below 2 — the node
                         drain/upgrade process BLOCKS and waits (or
                         retries) instead of taking down your capacity
maxUnavailable: 25%    → at most a quarter of replicas may be down for
                         voluntary eviction at once — the more common
                         choice when replica count changes over time
                         (via HPA), since a fixed minAvailable can
                         become too strict or too loose as replicas scale
```

**Why this matters in practice:** without a PDB, a cluster upgrade or a `kubectl drain` on a node running 6 of your 10 API replicas can evict all 6 simultaneously — Kubernetes' default eviction has no concept of "how many is too many for this specific app." A PDB is what makes `kubectl drain` cooperative instead of a potential self-inflicted outage during routine maintenance.

```bash
kubectl get pdb
kubectl describe pdb api-pdb    # shows current healthy count vs the budget

# What actually happens during a drain with a PDB in place:
kubectl drain node-3 --ignore-daemonsets
# → for each Pod on node-3 matching a PDB's selector, the drain calls the
#   Eviction API instead of a raw delete; if evicting would violate the
#   PDB, the eviction is REJECTED and drain retries/waits, it does not
#   silently proceed and break your minAvailable guarantee
```

**Senior tip:** set a PDB for anything that can't tolerate losing more than N replicas at once — especially StatefulSets (databases, queues) where "just reschedule elsewhere" isn't instant. A missing PDB is invisible in day-to-day operation and only bites during the exact moment you least want a surprise: a cluster upgrade or node maintenance window.

---

## RBAC

Kubernetes RBAC has four object types working together: `Role`/`ClusterRole` define WHAT is allowed, `RoleBinding`/`ClusterRoleBinding` define WHO gets it.

```
Role         → namespace-scoped permissions        (e.g., "read pods in 'staging'")
ClusterRole  → cluster-scoped OR reusable across ns (e.g., "read nodes" — nodes
                                                       aren't namespaced at all)

RoleBinding        → grants a Role/ClusterRole to a subject WITHIN one namespace
ClusterRoleBinding → grants a ClusterRole to a subject CLUSTER-WIDE
```

### Role — Namespace-Scoped

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: staging
rules:
  - apiGroups: [""]              # "" = core API group
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
```

### RoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-binding
  namespace: staging
subjects:
  - kind: User
    name: jane@example.com
    apiGroup: rbac.authorization.k8s.io
  - kind: ServiceAccount
    name: ci-deploy-bot
    namespace: staging
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

### ClusterRole — Cluster-Scoped

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
  - apiGroups: [""]
    resources: ["nodes"]         # nodes are NOT namespaced — needs a ClusterRole
    verbs: ["get", "list", "watch"]
```

```yaml
# A ClusterRole can also be bound via a RoleBinding, scoped down to ONE
# namespace — a common way to reuse a common permission set namespace-by-namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deploy-reader-binding
  namespace: production
subjects:
  - kind: Group
    name: deploy-team
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole       # ClusterRole, but bound only within 'production'
  name: deployment-manager
  apiGroup: rbac.authorization.k8s.io
```

### ClusterRoleBinding — Truly Cluster-Wide

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: node-reader-binding
subjects:
  - kind: Group
    name: sre-team
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: node-reader
  apiGroup: rbac.authorization.k8s.io
```

### Role vs ClusterRole — Quick Table

| | Role | ClusterRole |
|---|---|---|
| Scope | One namespace | Cluster-wide, or reusable per-namespace via RoleBinding |
| Can grant access to non-namespaced resources (nodes, PVs) | No | Yes |
| Bound via | RoleBinding only | RoleBinding (scoped to one ns) OR ClusterRoleBinding (cluster-wide) |

---

## Service Accounts

Every Pod authenticates to the API server as a ServiceAccount (a non-human identity), not as the human who deployed it.

### Default vs Custom

```
Every namespace auto-gets a ServiceAccount named "default".
Any Pod that doesn't specify serviceAccountName uses it.

PROBLEM: if "default" ever gets bound to broad permissions (directly
or via a ClusterRoleBinding to "system:authenticated"), EVERY Pod in
that namespace inherits those permissions — including Pods you never
intended to grant API access to at all.
```

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-deployer
  namespace: production
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      serviceAccountName: api-deployer   # explicit — not the namespace's "default"
      automountServiceAccountToken: false  # disable entirely if the Pod never
                                            # needs to call the K8s API at all
      containers:
        - name: api
          image: myrepo/api:1.4.2
```

### Least-Privilege Pattern

```yaml
# 1. Dedicated ServiceAccount per workload that actually needs API access
apiVersion: v1
kind: ServiceAccount
metadata:
  name: log-shipper
  namespace: production
---
# 2. Role with ONLY the permissions that workload needs
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: log-shipper-role
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get", "list"]
---
# 3. Bind ONLY that ServiceAccount to ONLY that Role
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: log-shipper-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: log-shipper
    namespace: production
roleRef:
  kind: Role
  name: log-shipper-role
  apiGroup: rbac.authorization.k8s.io
---
# 4. Pod uses the dedicated ServiceAccount, and Pods that DON'T need API
#    access at all disable automount entirely
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-shipper
  namespace: production
spec:
  template:
    spec:
      serviceAccountName: log-shipper
      containers:
        - name: fluent-bit
          image: fluent/fluent-bit:3.0
```

```bash
kubectl get serviceaccounts -n production
kubectl auth can-i list pods --as=system:serviceaccount:production:log-shipper
kubectl auth can-i --list --as=system:serviceaccount:production:default   # audit the default SA
```

### Senior Tip

```
Never bind cluster-admin to a ServiceAccount "just to unblock a
deploy" — audit with `kubectl auth can-i --list` first, and grant
only the verbs/resources actually needed. A compromised container
with a namespace-scoped Role reading its own Pods is a contained
incident; a compromised container carrying cluster-admin is a
cluster-wide breach.
```

---

## Interview Angle

**Q: HPA isn't scaling up despite high load — what do you check?**
Whether Metrics Server (or the custom metrics adapter) is installed and reporting (`kubectl top pods`), whether the target Deployment's Pods actually have `resources.requests` set (HPA's percentage-based targets are meaningless without a request baseline to measure against), and `kubectl describe hpa` for scaling condition events (it reports exactly why it isn't acting, e.g., "unable to get metrics").

**Q: When would you use a Role instead of a ClusterRole, given a ClusterRole can also be scoped via RoleBinding?**
Use a plain `Role` when the permission set is genuinely specific to one namespace and you don't need to reuse it elsewhere — it's simpler to reason about and audit. Use a `ClusterRole` (even if bound via namespaced RoleBindings) when the same permission set needs to be granted repeatedly across multiple namespaces, or when it must reference non-namespaced resources like nodes or PersistentVolumes, which a plain Role cannot reference at all.

**Q: A cluster upgrade drained a node and took down 6 of your 10 API replicas at once, causing an outage — what was missing, and what would you add?**
A PodDisruptionBudget. Without one, `kubectl drain` (or the managed upgrade process behind it) has no constraint on how many of a given app's Pods it can evict simultaneously — it happily evicted every matching Pod on that node. Adding a PDB with `minAvailable: 8` (or `maxUnavailable: 20%`) makes the eviction API reject/retry any drain step that would breach it, forcing the drain to proceed node-by-node or pod-by-pod instead of all at once. Note this only covers voluntary disruption (drains/upgrades) — it does nothing for a node that simply crashes.

**Q: A Pod's default ServiceAccount token got leaked — what's the blast radius?**
Whatever RBAC permissions are bound (via RoleBinding/ClusterRoleBinding) to that namespace's `default` ServiceAccount — potentially nothing if least-privilege was followed, or the entire cluster if `default` was ever carelessly bound to a broad ClusterRole. This is exactly why explicit, dedicated ServiceAccounts per workload — and `automountServiceAccountToken: false` for Pods that never call the API — matter.

**Q: All 3 replicas of a Deployment ended up scheduled onto the SAME node, and that node just failed, taking down the whole service. How do you prevent this going forward?**
Add `podAntiAffinity` with `topologyKey: kubernetes.io/hostname` to the Deployment's Pod template — this tells the scheduler to never place two Pods matching the same label selector on the same node. Without it, `replicas: 3` only guarantees three Pod objects exist, not that they're spread across different nodes; the scheduler is free to co-locate all of them if nothing tells it otherwise.

**Q: You have a handful of expensive GPU nodes and want ONLY ML training workloads to use them — regular API Pods should never land there by accident. What's the mechanism?**
A taint on the GPU nodes (`kubectl taint nodes gpu-node-1 workload=gpu:NoSchedule`) repels every Pod that doesn't have a matching toleration — ordinary API Pods are never scheduled there. Add the matching toleration to the ML training Pods so they're specifically PERMITTED on those nodes; for a stronger guarantee that ML Pods actually PREFER those nodes (not just are allowed on them), pair the toleration with a `nodeAffinity` rule targeting the same node label.

**Q: A previously-working Pod manifest suddenly fails to deploy with no code change, right after a platform team added something to the namespace. What's the likely cause?**
A `ResourceQuota` was added to the namespace. Once a ResourceQuota exists, every Pod in that namespace MUST specify `resources.requests`/`limits` explicitly — a Pod with no resource requests is rejected outright, since Kubernetes can't enforce a quota against an unspecified amount. The fix is either adding explicit resources to the Pod spec, or having the platform team pair the ResourceQuota with a `LimitRange` that supplies sane defaults automatically for Pods that don't specify their own.

---

## Related

- [`01_architecture_objects.md`](01_architecture_objects.md) — the Namespace object ResourceQuota/LimitRange govern, and readinessProbe (which interacts with the RBAC/security posture of Service endpoints)
- [`../14_Security/03_iam_vuln_scanning.md`](../14_Security/03_iam_vuln_scanning.md) — auditing over-privileged ClusterRoleBindings, the same RBAC model applied to a real incident
- [`05_helm.md`](05_helm.md) — Helm charts that ship default `resources.requests`/`limits` values LimitRange can override or backstop
