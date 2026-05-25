# 13 — GitOps with ArgoCD & Flux

> Declarative deployment where Git is the single source of truth. Modern Kubernetes deployment standard.

---

## What is GitOps

**Principle:** Desired state of system is described in Git. An automated process reconciles actual cluster state to match Git.

```
Engineer commits → Git → ArgoCD/Flux watches → Applies to cluster
```

vs traditional CI/CD:
```
Engineer pushes → CI pipeline → kubectl apply
```

GitOps is **pull-based**; cluster pulls config. Traditional is push-based.

---

## Why GitOps

### Single source of truth
What's in Git = what's running.

### Audit trail
Every change is a Git commit. Who changed what, when, why.

### Rollback = git revert
```bash
git revert abc123  # rollback that change
```

### Multi-cluster sync
One Git repo can drive 100 clusters.

### Disaster recovery
Cluster gone? Re-create from Git.

### RBAC via Git permissions
PR approval = deploy approval.

---

## ArgoCD

The dominant GitOps tool.

### Install
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### Connect to Git repo

```yaml
# Application CRD
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/me/my-config.git
    path: apps/my-app
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated:
      prune: true       # delete resources not in Git
      selfHeal: true    # revert manual changes
    syncOptions:
      - CreateNamespace=true
```

### Sync
- **Manual:** dev clicks "Sync" in UI.
- **Auto:** ArgoCD polls Git every 3 min; auto-applies changes.

### UI
```
http://argocd-server.argocd.svc:8080
```
Web UI shows:
- App health (running, degraded, missing).
- Diff between Git and cluster.
- Rollout history.
- Sync logs.

---

## Repository Structure (Best Practice)

```
my-config/
├── apps/
│   ├── api/
│   │   ├── base/
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── kustomization.yaml
│   │   └── overlays/
│   │       ├── dev/
│   │       │   └── kustomization.yaml
│   │       ├── staging/
│   │       │   └── kustomization.yaml
│   │       └── prod/
│   │           └── kustomization.yaml
│   └── worker/
│       └── ...
├── infra/
│   ├── monitoring/
│   ├── ingress/
│   └── secrets/
└── applications.yaml   # ArgoCD apps
```

**App of Apps pattern:** one ArgoCD Application manages many Applications.

---

## Kustomize Overlays (per environment)

```yaml
# apps/api/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 1
  ...

# apps/api/overlays/prod/kustomization.yaml
namespace: prod
resources:
  - ../../base
patches:
  - target: { kind: Deployment, name: api }
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 5
images:
  - name: api
    newTag: v1.2.3
```

Same base, different replicas and image tag per environment.

---

## Helm Charts via ArgoCD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prometheus
spec:
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: prometheus
    targetRevision: 25.0.0
    helm:
      values: |
        server:
          retention: 30d
        alertmanager:
          enabled: true
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
```

Use community Helm charts; override values via Git.

---

## Image Updates

GitOps requires image tags in Git. Workflow:

```
1. CI builds image: v1.2.3
2. CI commits to config repo: kustomization image tag = v1.2.3
3. ArgoCD detects Git change → applies → new pod rolls out
```

### Image Updater
ArgoCD Image Updater auto-updates tags based on rules.

```yaml
annotations:
  argocd-image-updater.argoproj.io/image-list: api=myregistry/api
  argocd-image-updater.argoproj.io/api.update-strategy: semver
```

Polls registry, auto-bumps to latest matching semver, commits to Git.

---

## Secrets in GitOps

Plaintext secrets in Git = disaster.

### Sealed Secrets (Bitnami)
Encrypt secrets with cluster's public key; commit encrypted form.

```bash
echo -n 's3cr3t' | kubeseal --raw --from-file=/dev/stdin --name=mysecret
# → AgB...encrypted...==
```

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: my-secret
spec:
  encryptedData:
    password: AgB...encrypted...==
```

Only cluster's controller can decrypt.

### External Secrets Operator (preferred)
Sync from external secret store (Vault, AWS Secrets Manager).

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-secret
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: api-secret
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: prod/api/database_url
```

Secret never in Git. Operator fetches at runtime.

---

## Flux

Alternative to ArgoCD; pioneered GitOps. CLI-driven, no UI by default.

### Install
```bash
flux bootstrap github \
  --owner=me \
  --repository=my-config \
  --branch=main \
  --path=clusters/prod
```

Flux installs itself + commits its own config to your repo. Self-managing.

### Resources
- `GitRepository`: tracks Git source.
- `Kustomization`: applies Kustomize/manifests from a path.
- `HelmRelease`: applies Helm chart.

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: api
  namespace: flux-system
spec:
  interval: 10m
  path: ./apps/api/overlays/prod
  sourceRef:
    kind: GitRepository
    name: my-config
  targetNamespace: prod
```

---

## ArgoCD vs Flux

| | ArgoCD | Flux |
|---|---|---|
| UI | ✓ rich | minimal |
| RBAC | ✓ built-in | via K8s RBAC |
| Multi-tenancy | ✓ projects | ✓ but more setup |
| Image automation | Plugin | Built-in |
| Helm support | ✓ | ✓ |
| Kustomize | ✓ | ✓ |
| Learning curve | Easier | Steeper |
| Preferred for | Most teams | Pure CLI / automation-heavy |

Both production-grade. ArgoCD more popular in mid-market.

---

## Progressive Delivery (Argo Rollouts / Flagger)

Beyond GitOps: control HOW deploys happen.

### Argo Rollouts
Provides Rollout CRD: canary, blue-green, with metric-based progression.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: api
spec:
  strategy:
    canary:
      steps:
        - setWeight: 10
        - pause: { duration: 5m }
        - analysis:
            templates:
              - templateName: success-rate
        - setWeight: 50
        - pause: { duration: 10m }
        - setWeight: 100
```

Auto-rollback if metrics fail.

### Flagger (Flux side)
Similar: canary + metric-based promotion.

---

## Multi-Cluster GitOps

One Git repo → many clusters.

```yaml
# applications.yaml — App of Apps
- name: api-staging
  cluster: staging
  path: apps/api/overlays/staging
- name: api-prod-us
  cluster: prod-us
  path: apps/api/overlays/prod-us
- name: api-prod-eu
  cluster: prod-eu
  path: apps/api/overlays/prod-eu
```

ArgoCD has cluster registration; can manage clusters from one control plane.

---

## Drift Detection

Manual `kubectl edit` deviates cluster from Git.

ArgoCD shows drift; with `selfHeal: true` reverts within minutes.

For "lab" or "break-glass" scenarios:
```yaml
syncPolicy:
  automated:
    selfHeal: false   # alert but don't auto-fix
```

Or use `ignoreDifferences` for fields that shouldn't be reconciled (HPA scaling, etc.).

---

## Audit & Compliance

- Every K8s change = Git commit with author.
- Code review (PR approval) = production change approval.
- Easy to answer "who changed what, when".
- Comply with SOC 2, ISO 27001 by enforcing PR review.

---

## Disaster Recovery

Cluster gone? GitOps DR is trivial:
1. Provision new cluster.
2. Install ArgoCD / Flux.
3. Point at Git repo.
4. Wait for sync.

Stateful workloads (DBs) restored separately.

**Without GitOps:** dozens of manual `kubectl apply` commands; high chance of drift.

---

## Common Pitfalls

### 1. Git push directly to main
Bypasses code review.
**Fix:** branch protection + required PR review.

### 2. Secrets in plaintext
**Fix:** Sealed Secrets or External Secrets Operator.

### 3. Inconsistent environments
Hand-edited cluster diverges from Git.
**Fix:** `selfHeal: true`.

### 4. Slow sync (large repo)
**Fix:** structure repo per app; multiple ArgoCD apps instead of monolithic.

### 5. Mass deletion via Git
Delete folder from repo → ArgoCD prunes all resources.
**Fix:** `prune: false` for risky apps; review carefully.

### 6. CI also applies kubectl
Conflicts with GitOps; cluster oscillates.
**Fix:** CI only updates Git; ArgoCD does the apply.

### 7. Dev experimentation
Developers can't easily try things in prod.
**Fix:** offer ephemeral environments via PRs.

---

## Workflow Example

```
Dev edits image tag in apps/api/overlays/prod/kustomization.yaml → branch
  ↓
PR opened → CI lints, validates Kustomize builds
  ↓
PR approved → merge to main
  ↓
ArgoCD (within 3 min) detects change → applies to prod cluster
  ↓
New pods rolling out, health monitored
  ↓
If failure, alert; revert PR = rollback
```

Total turnaround: 5-10 minutes typical.

---

## Real-World Adoption

- **GitHub:** uses Flux + custom tooling for internal infra.
- **Intuit:** open-sourced ArgoCD.
- **Spotify:** Flux at scale.
- **Disney:** ArgoCD for thousands of microservices.
- **Many startups:** ArgoCD for simplicity.

---

## TL;DR

- Git is source of truth; cluster reconciles to match.
- ArgoCD = dominant, UI-driven. Flux = CLI/automation-driven.
- Use Kustomize for environment overlays.
- Sealed Secrets or External Secrets Operator for secrets.
- Argo Rollouts / Flagger for progressive delivery.
- DR + audit + multi-cluster benefits dramatic.
- Avoid manual `kubectl` after adopting.
