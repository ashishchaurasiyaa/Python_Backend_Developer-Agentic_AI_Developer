# Cluster Autoscaling & Karpenter
**DevOps Track · Phase 6: Kubernetes**

## Quick Concepts

- **HPA (Horizontal Pod Autoscaler)** = adds/removes **Pods** based on metrics (CPU, memory, custom) — pod-level scaling
- **VPA (Vertical Pod Autoscaler)** = resizes a Pod's CPU/memory **requests** — right-sizing, not more replicas
- **Cluster Autoscaler (CA)** = adds/removes **nodes** by resizing pre-defined node groups (ASGs on AWS) when Pods are Pending
- **Karpenter** = modern node autoscaler (AWS-built, now CNCF) — provisions **individual, right-sized nodes directly** from the full EC2 catalog instead of resizing fixed node groups
- **NodePool** = Karpenter CRD defining *what* nodes it may create (instance families, capacity type, limits)
- **EC2NodeClass** = Karpenter CRD defining *how* AWS-specific node config looks (AMI, subnets, security groups, IAM role)
- **Consolidation** = Karpenter actively replacing/removing under-utilized nodes to cut cost — CA only removes empty-ish nodes

---

## Why This Matters

```
HPA answers: "traffic doubled — run more Pods."
But more Pods need somewhere to RUN. When the scheduler can't place
them, they sit Pending. Node autoscaling answers: "add machines."

The two layers work together:
  traffic ↑ → HPA adds Pods → Pods Pending → node autoscaler adds nodes
  traffic ↓ → HPA removes Pods → nodes under-utilized → nodes removed

Cluster Autoscaler does this by nudging a fixed Auto Scaling Group:
same instance type, +1 / -1. Karpenter instead looks at the ACTUAL
pending Pods and provisions the cheapest instance(s) that fit them —
in seconds, from hundreds of instance types, spot or on-demand.
That's why "Karpenter" is what AWS shops actually run in 2025+,
and why interviewers ask about it by name.
```

---

## The Three Autoscaling Layers Compared

| | HPA | VPA | CA / Karpenter |
|---|---|---|---|
| **Scales** | Pod replica count | Pod resource requests | Nodes |
| **Trigger** | Metrics (CPU %, custom/KEDA) | Historical usage | Pending Pods / empty nodes |
| **Typical use** | Traffic spikes | Right-sizing requests | Capacity to back HPA |
| **Gotcha** | Needs `resources.requests` set or CPU % is meaningless | Restarts Pods to apply; don't combine with HPA on the same metric | Wrong requests → wrong node decisions (garbage in, garbage out) |

```yaml
# HPA quick reference (v2) — the layer above node autoscaling
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## Cluster Autoscaler vs Karpenter

| | Cluster Autoscaler | Karpenter |
|---|---|---|
| **Unit of scaling** | Pre-defined node group (ASG) | Individual nodes, chosen per pending Pods |
| **Instance selection** | Fixed per node group | Any allowed type from the live EC2 catalog — picks cheapest that fits |
| **Provisioning speed** | Minutes (ASG round-trip) | Seconds (direct EC2 API) |
| **Spot handling** | Separate node groups per purchase type | Mixed spot/on-demand in one NodePool; handles interruption notices |
| **Bin-packing / cost** | Passive — removes near-empty nodes | Active **consolidation** — replaces 3 half-empty nodes with 1 right-sized one |
| **Cloud support** | All major clouds | AWS first-class; Azure support growing |
| **Config lives in** | ASG definitions (Terraform) + flags | Kubernetes CRDs (`NodePool`, `EC2NodeClass`) |

---

## Karpenter Configuration

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]     # prefer spot, fall back to on-demand
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64", "arm64"]        # Graviton allowed = cheaper
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m", "r"]           # compute/general/memory families
  limits:
    cpu: "200"                              # hard cap — cost guardrail
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
```

```yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiSelectorTerms:
    - alias: al2023@latest                  # Amazon Linux 2023, auto-updated
  role: KarpenterNodeRole-my-cluster        # IAM role nodes assume
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster  # discover subnets by tag
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
```

```
Flow when a Pod goes Pending:

  Pending Pod (requests: 2 CPU, 4Gi)
        │
        ▼
  Karpenter batches pending Pods (~seconds)
        │
        ▼
  Solves: cheapest allowed instance(s) that fit → e.g. one spot m7g.xlarge
        │
        ▼
  Direct EC2 launch → node Ready in ~40-60s → Pods scheduled
```

### Protecting workloads from consolidation

Consolidation means Karpenter **will** evict Pods to shrink the cluster. Protect what can't move:

```yaml
# On the Pod: never evict me (e.g. a batch job mid-run)
metadata:
  annotations:
    karpenter.sh/do-not-disrupt: "true"
```

```yaml
# PodDisruptionBudget: evict, but keep N alive at all times
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api
```

---

## Senior Tip

```
Karpenter's decisions are only as good as your resource REQUESTS.
It bin-packs against requests, not actual usage — Pods that request
4Gi but use 400Mi force it to buy 10x the memory you need, and no
autoscaler can fix that. Right-size requests first (VPA in
recommend-mode / Goldilocks), then let Karpenter optimize nodes.

Second footgun: spot + consolidation together means nodes churn.
Anything stateful, slow-starting, or singleton needs a PDB or
do-not-disrupt annotation, or you'll debug "random" restarts that
are actually Karpenter doing its job.

Cost levers, in order of impact: (1) fix requests, (2) allow spot +
arm64/Graviton in the NodePool, (3) enable consolidation, (4) set
NodePool limits so a runaway HPA can't buy unbounded compute.
```

---

## Interview Angle

**Q: HPA vs Cluster Autoscaler vs Karpenter — how do they relate?**
Different layers, complementary. HPA scales Pod replicas from metrics; when new Pods can't be scheduled they go Pending, and a node autoscaler (CA or Karpenter) adds capacity. CA scales pre-defined node groups up/down; Karpenter replaces CA by provisioning right-sized individual instances directly from the pending Pods' requirements — faster, cheaper, no node-group management.

**Q: Why did Karpenter largely replace Cluster Autoscaler on AWS?**
Three reasons: speed (direct EC2 API, seconds vs ASG minutes), flexibility (chooses from the whole instance catalog per workload instead of one fixed type per node group), and cost (active consolidation + first-class spot/Graviton mixing). Operationally it also moves node config into Kubernetes CRDs instead of Terraform-managed ASGs.

**Q: Karpenter keeps evicting my Pods — what's happening and what do you do?**
Consolidation: it found a cheaper node arrangement and is draining under-utilized nodes (or a spot node got an interruption notice). Fixes: PodDisruptionBudgets for availability floors, `karpenter.sh/do-not-disrupt` on Pods that must not move, `consolidationPolicy: WhenEmpty` if churn is unacceptable, and on-demand capacity type for the workloads that can't tolerate spot reclaims.

**Q: You enabled HPA + Karpenter but scaling is still "wrong" — first thing you check?**
`resources.requests` on the Pods. HPA percentage targets are computed against requests, and Karpenter bin-packs against requests. Missing or wildly wrong requests break both layers — everything downstream is garbage-in, garbage-out.

---

## Related
- HPA/VPA basics + RBAC → [04_scaling_security_rbac.md](04_scaling_security_rbac.md)
- The deeper deployment-focused K8s material (incl. GitOps) → [`../../Backend_Developer/01_Year3-4_Mid/04_DevOps/`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/)
- AWS EC2/ASG fundamentals → [../07_Cloud_AWS/01_iam_compute_ec2.md](../07_Cloud_AWS/01_iam_compute_ec2.md)
