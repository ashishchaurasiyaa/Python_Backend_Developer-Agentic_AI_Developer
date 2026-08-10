# GitOps Lab — ArgoCD Hands-On

## Prerequisites
- Minikube or any local Kubernetes cluster
- kubectl installed
- Docker installed
- GitHub account

---

## Lab 1 — Install ArgoCD and Deploy Your First App

### Step 1: Start local cluster
```bash
minikube start --memory=4096 --cpus=2
```

### Step 2: Install ArgoCD
```bash
kubectl create namespace argocd

kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for all pods to be ready
kubectl wait --for=condition=Ready pod --all -n argocd --timeout=180s

# Verify
kubectl get pods -n argocd
```

### Step 3: Access the UI
```bash
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo

# Port forward
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

# Open browser: https://localhost:8080
# Username: admin
# Password: (from step above)
```

### Step 4: Install ArgoCD CLI
```bash
# Mac
brew install argocd

# Login
argocd login localhost:8080 \
  --username admin \
  --password <your-password> \
  --insecure
```

---

## Lab 2 — Deploy a Sample App via ArgoCD

### Step 5: Create an ArgoCD Application pointing to a public repo
```bash
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default

# Check status
argocd app get guestbook
```

### Step 6: Sync (deploy) the app
```bash
# Manual sync first time
argocd app sync guestbook

# Watch status
argocd app wait guestbook --health

# Check in cluster
kubectl get pods -n default
kubectl get svc -n default
```

### Step 7: Access the app
```bash
kubectl port-forward svc/guestbook-ui 8888:80 &
# Open http://localhost:8888
```

---

## Lab 3 — Create Your Own GitOps Repo (Full Flow)

### Step 8: Create a manifest repo on GitHub
```
my-k8s-manifests/
└── apps/
    └── my-app/
        ├── deployment.yaml
        ├── service.yaml
        └── namespace.yaml
```

Create these files:

**namespace.yaml:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-app
```

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: my-app
        image: nginx:1.25       # we'll change this in Lab 4
        ports:
        - containerPort: 80
```

**service.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-app
spec:
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

Push these to GitHub.

### Step 9: Create ArgoCD App pointing to your repo
```bash
argocd app create my-app \
  --repo https://github.com/<your-username>/my-k8s-manifests \
  --path apps/my-app \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace my-app \
  --sync-policy automated \
  --auto-prune \
  --self-heal

argocd app sync my-app
argocd app get my-app
```

---

## Lab 4 — Simulate a GitOps Deploy (Change → Auto Sync)

### Step 10: Update image tag in Git
```bash
# In your manifest repo
# Edit deployment.yaml — change nginx:1.25 to nginx:1.26
# Commit and push

git add .
git commit -m "Update nginx to 1.26"
git push origin main
```

### Step 11: Watch ArgoCD auto-detect and sync
```bash
# Watch ArgoCD detect the change (polls every 3 minutes by default)
watch argocd app get my-app

# Or force a refresh
argocd app get my-app --refresh

# Observe: ArgoCD shows OutOfSync → syncing → Synced + Healthy
kubectl get pods -n my-app   # shows new pods rolling out
```

---

## Lab 5 — Test Self-Healing

### Step 12: Manually change something in the cluster
```bash
# Scale deployment manually (bypassing Git)
kubectl scale deployment my-app -n my-app --replicas=5

# Watch ArgoCD detect drift and revert
watch kubectl get pods -n my-app
# Within ~30 seconds: goes back to 2 replicas (as defined in Git)

argocd app get my-app
# Shows: selfHeal reverted manual change
```

---

## Lab 6 — Rollback

### Step 13: Rollback to previous version
```bash
# List history
argocd app history my-app

# Rollback to previous deployment
argocd app rollback my-app 1    # 1 = history ID

# Verify
argocd app get my-app
kubectl get pods -n my-app
```

---

## Lab 7 — Cleanup
```bash
argocd app delete my-app
argocd app delete guestbook
kubectl delete namespace argocd
minikube stop
```

---

## Checklist — What You Should Be Able to Do Now

- [ ] Install ArgoCD in a Kubernetes cluster
- [ ] Create an ArgoCD Application pointing to a Git repo
- [ ] Manually sync and auto-sync an application
- [ ] Update a manifest in Git and watch ArgoCD deploy it
- [ ] Observe self-healing when cluster drifts from Git
- [ ] Roll back to a previous version
- [ ] Explain GitOps pull vs push model in an interview
