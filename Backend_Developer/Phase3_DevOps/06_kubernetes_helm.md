# Kubernetes + Helm — Deployments, Services, ConfigMaps, Secrets, HPA

## Quick Concepts
- **Kubernetes (K8s)** = container orchestration — automatically containers manage karta hai
- **Pod** = K8s ka smallest unit — ek ya zyada containers
- **Deployment** = desired state define karo, K8s achieve karta hai
- **Service** = Pods ko network access deta hai (stable IP/DNS)
- **ConfigMap** = non-secret config data store karo
- **Secret** = sensitive data (passwords, tokens) store karo
- **HPA** = Horizontal Pod Autoscaler — traffic ke hisab se pods badhao/ghatao
- **Helm** = K8s ka package manager — templates se deployment karo

---

## Interview Questions & Answers

### Q1: Kubernetes mein FastAPI app deploy kaise karte hain?
**Answer:**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-app
  namespace: production
  labels:
    app: fastapi
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0       # zero downtime deploy
  template:
    metadata:
      labels:
        app: fastapi
    spec:
      containers:
        - name: fastapi
          image: myuser/myapp:1.2.0
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
            - name: ENV
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: environment
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
```

---

### Q2: Service types kya hain? Kab kaunsa use karte hain?
**Answer:**
```yaml
# ClusterIP — sirf cluster ke andar (default)
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
spec:
  selector:
    app: fastapi
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP

---
# NodePort — external access via node IP:port (dev/testing)
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 8000
      nodePort: 30080   # 30000-32767

---
# LoadBalancer — cloud provider external LB (production AWS/GCP)
spec:
  type: LoadBalancer
  ports:
    - port: 80
      targetPort: 8000
```

**Production mein:** LoadBalancer ya Ingress use karo.

---

### Q3: Ingress kya hai? Nginx Ingress Controller kaise kaam karta hai?
**Answer:**
```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.myapp.com
      secretName: myapp-tls
  rules:
    - host: api.myapp.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: fastapi-service
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

---

### Q4: ConfigMap aur Secret kaise use karte hain?
**Answer:**
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  environment: "production"
  log_level: "INFO"
  allowed_origins: "https://myapp.com"

---
# secret.yaml (values base64 encoded)
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
data:
  database-url: cG9zdGdyZXNxbDovL3VzZXI6cGFzc0Bob3N0...  # base64
  secret-key: c3VwZXJzZWNyZXRrZXk=
```

```bash
# Secret create karo directly (base64 manual nahi karna padega)
kubectl create secret generic app-secrets \
  --from-literal=database-url="postgresql://user:pass@host:5432/db" \
  --from-literal=secret-key="supersecretkey"

# Ya .env file se
kubectl create secret generic app-secrets --from-env-file=.env.production
```

---

### Q5: HPA (Horizontal Pod Autoscaler) kaise kaam karta hai?
**Answer:**
```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-app
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70      # CPU 70% se zyada → scale up
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300  # scale down conservative hai
```

```bash
# Metrics Server install karna padega HPA ke liye
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl get hpa                    # HPA status dekho
kubectl describe hpa fastapi-hpa  # detail
```

---

### Q6: Helm kya hai? Chart kaise use karte hain?
**Answer:**
Helm = K8s ka package manager. Templates se different environments mein easily deploy karo.

```bash
# Helm install karo
brew install helm

# Chart add karo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# PostgreSQL deploy karo
helm install my-postgres bitnami/postgresql \
  --set auth.postgresPassword=mysecret \
  --set primary.persistence.size=20Gi \
  --namespace databases --create-namespace

# Custom values file se
helm install my-postgres bitnami/postgresql -f values.yaml

# Upgrade karo
helm upgrade my-postgres bitnami/postgresql --set image.tag=16.2.0

# Status
helm list -A
helm status my-postgres

# Rollback
helm rollback my-postgres 1
```

**Custom chart banao:**
```
myapp/
  Chart.yaml          # chart metadata
  values.yaml         # default values
  templates/
    deployment.yaml   # {{ .Values.image.tag }} templating
    service.yaml
    ingress.yaml
    configmap.yaml
    _helpers.tpl      # reusable template functions
```

```yaml
# values.yaml
replicaCount: 3
image:
  repository: myuser/myapp
  tag: "1.0.0"
  pullPolicy: IfNotPresent
service:
  type: ClusterIP
  port: 80
resources:
  limits:
    cpu: 500m
    memory: 512Mi
```

---

### Q7: Zero-downtime deployment kaise ensure karte hain?
**Answer:**
```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1         # naye pod pehle aate hain
      maxUnavailable: 0   # koi purana pod tab tak down nahi hoga jab tak naya ready nahi
  template:
    spec:
      containers:
        - readinessProbe:    # Traffic sirf ready pods ko milta hai
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5"]  # graceful shutdown
```

---

## Useful kubectl Commands

```bash
# Deployment
kubectl apply -f deployment.yaml
kubectl get pods -n production -w          # watch
kubectl describe pod fastapi-app-xxx
kubectl logs fastapi-app-xxx -f --tail=100
kubectl exec -it fastapi-app-xxx -- /bin/bash

# Scaling
kubectl scale deployment fastapi-app --replicas=5
kubectl rollout status deployment/fastapi-app
kubectl rollout undo deployment/fastapi-app  # rollback

# Debugging
kubectl get events --sort-by=.metadata.creationTimestamp
kubectl top pods                             # CPU/memory usage
kubectl port-forward service/fastapi-service 8080:80  # local testing
```
