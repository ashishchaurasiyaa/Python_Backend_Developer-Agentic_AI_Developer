# GitOps + ArgoCD + Flux

## Why This Matters (Market Context)
60% of Senior DevOps / Platform Engineer JDs in 2026 mention GitOps.
Companies like Razorpay, Zepto, Swiggy, Meesho, CRED all use ArgoCD in production.

---

## What is GitOps?

GitOps = Git as the single source of truth for infrastructure AND application deployments.

**4 core principles (OpenGitOps standard):**
```
1. Declarative   — desired state written in files (YAML), not scripts
2. Versioned     — Git stores every change, full history, rollback anytime
3. Pulled        — agent inside cluster pulls from Git (not push from CI)
4. Reconciled    — agent continuously checks: actual state == desired state?
```

**Traditional CI/CD (push model):**
```
Code push → CI pipeline runs → kubectl apply → done (fire and forget)
Problem: no one watches if cluster drifts from what was deployed
```

**GitOps (pull model):**
```
Code push → Git updated → ArgoCD detects diff → ArgoCD syncs cluster
Benefit: cluster is ALWAYS reconciled with Git, drift detected + fixed automatically
```

---

## ArgoCD

### Architecture
```
┌─────────────────────────────────────────────┐
│              Kubernetes Cluster              │
│                                             │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  Repo Server │    │ App Controller   │   │
│  │  (clone Git, │    │ (watches cluster,│   │
│  │   render     │    │  reconciles)     │   │
│  │   manifests) │    └──────────────────┘   │
│  └──────────────┘                           │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  API Server  │    │  Dex (OIDC auth) │   │
│  │  (UI + CLI)  │    └──────────────────┘   │
│  └──────────────┘                           │
└─────────────────────────────────────────────┘
           ↑ pulls from
    ┌──────────────┐
    │  Git Repo    │
    │  (manifests) │
    └──────────────┘
```

### Install ArgoCD (local / Minikube)
```bash
# 1. Create namespace
kubectl create namespace argocd

# 2. Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 3. Wait for pods
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s

# 4. Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 5. Port forward UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# 6. Install ArgoCD CLI (Mac)
brew install argocd

# 7. Login via CLI
argocd login localhost:8080 --username admin --password <password> --insecure
```

### ArgoCD Application CRD
The core object — tells ArgoCD WHAT to deploy and WHERE:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-fastapi-app
  namespace: argocd
spec:
  project: default

  # WHERE to get the manifests (source of truth)
  source:
    repoURL: https://github.com/yourorg/k8s-manifests
    targetRevision: main           # branch, tag, or commit SHA
    path: apps/fastapi-prod        # folder inside the repo

  # WHERE to deploy (target cluster + namespace)
  destination:
    server: https://kubernetes.default.svc   # in-cluster
    namespace: production

  # HOW to sync
  syncPolicy:
    automated:
      prune: true        # delete resources removed from Git
      selfHeal: true     # fix manual changes to cluster
    syncOptions:
      - CreateNamespace=true
```

Apply it:
```bash
kubectl apply -f application.yaml
# ArgoCD immediately starts syncing your app
```

### Sync Policies

| Mode | What it does | When to use |
|------|-------------|-------------|
| Manual | You trigger sync from UI/CLI | Staging — human approval |
| Automated | ArgoCD syncs on every Git commit | Production with confidence |
| Auto-prune | Deletes resources removed from Git | Keeps cluster clean |
| Self-heal | Reverts manual `kubectl` changes | Enforces Git as truth |

```bash
# Manually sync via CLI
argocd app sync my-fastapi-app

# Check sync status
argocd app get my-fastapi-app

# Rollback to previous version
argocd app rollback my-fastapi-app 1   # 1 = history index
```

### Health Checks
ArgoCD knows the health of every K8s resource:
```
Healthy   — pods running, service endpoints exist
Degraded  — CrashLoopBackOff, ImagePullError
Progressing — rolling update in progress
Suspended — cronJob paused
```

You can write custom health checks in Lua for your CRDs.

---

## GitOps Repository Structure

**Option 1 — App repo + Manifest repo (recommended):**
```
app-repo/              ← developers commit code here
├── src/
├── Dockerfile
└── .github/workflows/
    └── ci.yaml        ← builds image, pushes to registry,
                          updates image tag in manifest-repo

manifest-repo/         ← ArgoCD watches this
├── apps/
│   ├── fastapi-prod/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   └── fastapi-staging/
│       └── ...
└── infrastructure/
    ├── monitoring/
    └── databases/
```

**CI workflow that updates manifest repo:**
```yaml
# .github/workflows/ci.yaml (in app-repo)
- name: Update image tag in manifest repo
  run: |
    git clone https://github.com/org/manifest-repo
    cd manifest-repo
    # Update the image tag in deployment.yaml
    sed -i "s|image: myapp:.*|image: myapp:${{ github.sha }}|" \
      apps/fastapi-prod/deployment.yaml
    git add . && git commit -m "Update image to ${{ github.sha }}"
    git push
    # ArgoCD detects the change and syncs automatically
```

**Option 2 — App of Apps pattern (manage multiple apps):**
```yaml
# root-app.yaml — one ArgoCD app that manages all other apps
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-app
spec:
  source:
    path: apps/           # this folder contains other Application YAMLs
  ...
```

---

## Secrets with GitOps

Never commit secrets to Git. Two solutions:

**Option 1 — Sealed Secrets (Bitnami):**
```bash
# Install kubeseal CLI
brew install kubeseal

# Seal a secret (encrypted with cluster public key)
kubectl create secret generic db-password \
  --from-literal=password=mysecret123 \
  --dry-run=client -o yaml | \
  kubeseal --format yaml > sealed-secret.yaml

# sealed-secret.yaml is safe to commit to Git
# Only the cluster can decrypt it
```

**Option 2 — External Secrets Operator (preferred in production):**
```yaml
# Fetches secrets from AWS Secrets Manager / HashiCorp Vault
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-password
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-password        # creates a K8s Secret with this name
  data:
    - secretKey: password
      remoteRef:
        key: prod/db/password  # key in AWS Secrets Manager
```

---

## Flux CD (Alternative to ArgoCD)

Flux is more GitOps-native, lighter weight. ArgoCD has better UI.

```bash
# Install Flux CLI
brew install fluxcd/tap/flux

# Bootstrap Flux into your cluster (links to GitHub)
flux bootstrap github \
  --owner=yourorg \
  --repository=fleet-infra \
  --branch=main \
  --path=clusters/production \
  --personal

# Flux creates a GitRepository and Kustomization object
# Automatically syncs every 1 minute
```

**Flux vs ArgoCD:**
| Feature | ArgoCD | Flux |
|---------|--------|------|
| UI | Rich UI | CLI-focused |
| Multi-cluster | Yes | Yes |
| Helm support | Yes | Yes |
| Image automation | Plugin | Built-in |
| Learning curve | Lower | Higher |
| Market adoption | Higher | Growing |

---

## End-to-End GitOps Workflow

```
Developer pushes code
    ↓
GitHub Actions: test → build Docker image → push to ECR/GHCR
    ↓
GitHub Actions: update image tag in manifest repo
    ↓
ArgoCD detects manifest change (polls every 3 minutes or webhook)
    ↓
ArgoCD compares: Git state vs Cluster state
    ↓
ArgoCD applies diff to cluster (kubectl apply internally)
    ↓
ArgoCD reports: Healthy / Degraded / Progressing
    ↓
Slack/PagerDuty alert if degraded
```

---

## Key Interview Questions

**Q: What is the difference between GitOps push model and pull model?**
Push: CI pipeline runs kubectl apply (no one monitors after). Pull: Agent inside cluster continuously pulls from Git and reconciles — drift is detected and fixed automatically.

**Q: What happens if someone runs kubectl apply manually on the cluster?**
With selfHeal=true, ArgoCD detects the drift within minutes and reverts the cluster back to the Git state.

**Q: How do you manage secrets in GitOps without committing them to Git?**
Sealed Secrets (encrypt in Git, decrypt only in cluster) or External Secrets Operator (fetch from AWS Secrets Manager/Vault at runtime).

**Q: What is the App of Apps pattern?**
One ArgoCD Application that manages multiple other Applications — useful for bootstrapping an entire cluster from a single Git commit.

**Q: ArgoCD vs Flux — which would you use?**
ArgoCD for teams that need a rich UI and easier onboarding. Flux for CLI-heavy GitOps-native teams. Both use the same principles. ArgoCD is more widely adopted currently.
