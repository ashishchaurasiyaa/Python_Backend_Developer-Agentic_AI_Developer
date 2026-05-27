# Lecture 4 — Practical Hands-On: Docker & Kubernetes

> **Theory file:** [04_Docker_Kubernetes.md](04_Docker_Kubernetes.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Complete Docker + Kubernetes setup:

1. ✅ **Dockerfile** best practices (multi-stage, security)
2. ✅ **docker-compose** for local dev
3. ✅ **Minikube** local Kubernetes
4. ✅ **K8s manifests** (Deployment, Service, Ingress)
5. ✅ **ConfigMaps** + Secrets
6. ✅ **HPA** auto-scaling
7. ✅ **Helm** for packaging
8. ✅ **Kustomize** for environments
9. ✅ **GitOps** with ArgoCD
10. ✅ **Production-grade** deployment

By end: aap **production K8s deployments** kar sakte ho.

---

## 1. 🐳 Production-Grade Dockerfile

### `Dockerfile`

```dockerfile
# Multi-stage build - smaller final image
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────
# Production stage
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Security: non-root user
RUN useradd -m -u 1000 appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

WORKDIR /app

# Copy app code (with proper ownership)
COPY --chown=appuser:appuser . .

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Use exec form (handles SIGTERM properly)
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
```

### `.dockerignore`

```
# Don't include these in image
.git
.env
.venv
__pycache__
*.pyc
.pytest_cache
tests/
docs/
*.md
```

### Build & Optimize

```bash
# Build
$ docker build -t myapp:1.0 .

# Check size
$ docker images myapp
# myapp     1.0    abc123    150MB  ← Good!

# Multi-platform build (for ARM Macs etc)
$ docker buildx build --platform linux/amd64,linux/arm64 -t myapp:1.0 .

# Scan for vulnerabilities
$ docker scout cves myapp:1.0
```

---

## 2. 🐙 Docker Compose for Local Dev

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      DEBUG: "true"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./app:/app/app  # Hot reload for dev
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
  
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: myapp
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

volumes:
  postgres_data:
```

```bash
$ docker-compose up
# Everything starts together!

$ docker-compose logs -f app
# Stream logs

$ docker-compose exec app python scripts/migrate.py
# Run admin task in same env
```

---

## 3. ☸️ Minikube Local Kubernetes

```bash
# Install minikube
$ brew install minikube  # macOS

# Start cluster
$ minikube start --cpus=4 --memory=8192

# Verify
$ kubectl get nodes
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   1m    v1.28.0

# Enable addons
$ minikube addons enable ingress
$ minikube addons enable metrics-server
```

### Build & Use Local Image

```bash
# Point Docker to minikube's daemon
$ eval $(minikube docker-env)

# Now docker build inside minikube
$ docker build -t myapp:1.0 .

# Use in K8s (no registry needed for local!)
imagePullPolicy: Never  # In manifest
```

---

## 4. 📋 K8s Manifests

### `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  labels:
    app: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      # Graceful shutdown
      terminationGracePeriodSeconds: 30
      
      containers:
      - name: myapp
        image: myapp:1.0
        imagePullPolicy: IfNotPresent
        
        ports:
        - containerPort: 8000
          name: http
        
        # Resource limits (CRITICAL!)
        resources:
          requests:
            cpu: 100m       # 0.1 CPU
            memory: 128Mi
          limits:
            cpu: 500m       # 0.5 CPU
            memory: 512Mi
        
        # Health checks
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 3
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
        
        startupProbe:
          httpGet:
            path: /health
            port: 8000
          failureThreshold: 30
          periodSeconds: 5
        
        # Environment variables
        env:
        - name: PORT
          value: "8000"
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: log_level
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database_url
        
        # Graceful shutdown
        lifecycle:
          preStop:
            exec:
              command: ["sleep", "5"]  # Wait for LB to drain
```

### `k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP   # Internal only
```

### `k8s/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: myapp
            port:
              number: 80
  tls:
  - hosts:
    - myapp.example.com
    secretName: myapp-tls
```

### Apply

```bash
$ kubectl apply -f k8s/

$ kubectl get pods
NAME                     READY   STATUS    RESTARTS   AGE
myapp-7d9f8b5c4-abc12    1/1     Running   0          1m
myapp-7d9f8b5c4-def34    1/1     Running   0          1m
myapp-7d9f8b5c4-ghi56    1/1     Running   0          1m

$ kubectl get svc
NAME    TYPE        CLUSTER-IP      PORT(S)   AGE
myapp   ClusterIP   10.96.123.45    80/TCP    1m

$ kubectl logs -l app=myapp -f
# Stream logs from all pods
```

---

## 5. ⚙️ ConfigMaps + Secrets

### `k8s/configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  log_level: "INFO"
  workers: "4"
  feature_flag_new_signup: "true"
  
  # Multi-line config
  app.conf: |
    server.host = 0.0.0.0
    server.port = 8000
    cache.ttl = 300
```

### `k8s/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  database_url: "postgresql://app:secret@db:5432/myapp"
  stripe_secret_key: "sk_live_..."
  jwt_secret: "your-jwt-signing-key"
```

### Better: Sealed Secrets (Encrypted)

```yaml
# Install Sealed Secrets controller
$ helm install sealed-secrets sealed-secrets/sealed-secrets

# Encrypt secret
$ kubectl create secret generic app-secrets \
    --dry-run=client \
    --from-literal=database_url='postgresql://...' \
    -o yaml | kubeseal -o yaml > sealed-secrets.yaml

# Now safe to commit to git!
```

---

## 6. 📈 Horizontal Pod Autoscaler

### `k8s/hpa.yaml`

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  
  minReplicas: 2
  maxReplicas: 20
  
  metrics:
  # Scale on CPU
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  # Scale on memory
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  
  # Custom metric (requires Prometheus Adapter)
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 1000
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 100         # Double instances
        periodSeconds: 30
      - type: Pods
        value: 4            # Or add 4 pods
        periodSeconds: 30
      selectPolicy: Max     # Use whichever scales more
    
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 min stability
      policies:
      - type: Percent
        value: 50           # Halve instances
        periodSeconds: 60
```

### Apply & Test

```bash
$ kubectl apply -f k8s/hpa.yaml

$ kubectl get hpa
NAME         REFERENCE          TARGETS    MINPODS   MAXPODS   REPLICAS
myapp-hpa    Deployment/myapp   45%/70%    2         20        3

# Generate load
$ kubectl run -it load-test --image=busybox -- /bin/sh
> while true; do wget -q -O- http://myapp; done

# Watch scaling
$ kubectl get hpa -w
# REPLICAS increases as load grows!
```

---

## 7. 🎯 Helm for Packaging

### Initialize Chart

```bash
$ helm create myapp
# Creates myapp/ directory with templates
```

### `myapp/Chart.yaml`

```yaml
apiVersion: v2
name: myapp
description: My production app
type: application
version: 1.0.0
appVersion: "1.0"
```

### `myapp/values.yaml`

```yaml
replicaCount: 3

image:
  repository: myapp
  tag: "1.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

ingress:
  enabled: true
  className: nginx
  host: myapp.example.com
```

### `myapp/templates/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
      - name: app
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
```

### Deploy

```bash
# Install
$ helm install myapp ./myapp

# With custom values
$ helm install myapp ./myapp \
    --set image.tag=2.0 \
    --set replicaCount=5

# Upgrade
$ helm upgrade myapp ./myapp --set image.tag=1.1

# Rollback
$ helm rollback myapp 1

# List releases
$ helm list
```

---

## 8. 🌐 Kustomize for Environments

### Structure

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   └── patches/
    │       └── replica-count.yaml
    ├── staging/
    │   └── kustomization.yaml
    └── prod/
        ├── kustomization.yaml
        └── patches/
            └── replica-count.yaml
```

### `base/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- deployment.yaml
- service.yaml
- ingress.yaml

commonLabels:
  app: myapp
```

### `overlays/prod/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
- ../../base

namePrefix: prod-

patches:
- target:
    kind: Deployment
    name: myapp
  patch: |-
    - op: replace
      path: /spec/replicas
      value: 10

configMapGenerator:
- name: app-config
  literals:
  - log_level=INFO
  - environment=production
```

### Apply

```bash
# Dev
$ kubectl apply -k k8s/overlays/dev

# Staging
$ kubectl apply -k k8s/overlays/staging

# Production
$ kubectl apply -k k8s/overlays/prod
```

---

## 9. 🚀 GitOps with ArgoCD

### Install ArgoCD

```bash
$ kubectl create namespace argocd
$ kubectl apply -n argocd \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access UI
$ kubectl port-forward svc/argocd-server -n argocd 8080:443
# https://localhost:8080
```

### `argocd/application.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/myapp-config
    targetRevision: main
    path: k8s/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true        # Auto-delete removed resources
      selfHeal: true     # Auto-fix drift
    syncOptions:
    - CreateNamespace=true
```

### Apply

```bash
$ kubectl apply -f argocd/application.yaml

# Now ArgoCD watches the git repo
# Any change pushed → automatically deployed
# Drift detected → automatically corrected
```

### GitOps Workflow

```
1. Developer pushes code change
2. CI builds + pushes Docker image
3. CI updates k8s manifest with new image tag
4. CI commits to config repo
5. ArgoCD detects change
6. ArgoCD deploys to cluster
7. Done!

✓ Git is single source of truth
✓ Audit trail of all changes
✓ Easy rollback (git revert)
```

---

## 10. 📊 Monitoring Stack

### Prometheus + Grafana via Helm

```bash
$ helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
$ helm install monitoring prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace

# Access Grafana
$ kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
# Default: admin / prom-operator
```

### Application Metrics

```python
# Expose Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'Request duration')

@app.middleware("http")
async def metrics_middleware(request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_DURATION.observe(duration)
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### ServiceMonitor (Prometheus Operator)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp
spec:
  selector:
    matchLabels:
      app: myapp
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
```

---

## 11. Key Learnings Summary

```
✅ Multi-stage Dockerfile + non-root user
✅ docker-compose for parity in local dev
✅ Minikube for local K8s
✅ Deployment + Service + Ingress = basic K8s
✅ Resource limits prevent runaway pods
✅ Liveness + readiness probes for self-healing
✅ ConfigMaps + Secrets for config separation
✅ HPA for auto-scaling
✅ Helm for packaging + reusability
✅ Kustomize for environment overlays
✅ ArgoCD for GitOps deployments
✅ Prometheus + Grafana for observability

🎯 Production K8s stack:
   Docker images → Container registry
   → K8s cluster (EKS/GKE/AKS)
   → Helm charts deployed via ArgoCD
   → Monitored by Prometheus + Grafana
   → Auto-scaled by HPA
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll dive into **Load Balancing and Auto Scaling** patterns.

> **Next lecture:** [05_Load_Balancing_Auto_Scaling.md](05_Load_Balancing_Auto_Scaling.md)

---

## 📚 Try It Yourself

1. Deploy full app stack on minikube
2. Set up HPA with custom metrics
3. Use Helm to package + parameterize
4. Implement blue-green deployment
5. Set up ArgoCD for GitOps
