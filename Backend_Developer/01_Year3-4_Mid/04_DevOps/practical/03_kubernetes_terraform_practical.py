"""
Phase3_DevOps — Kubernetes + Terraform Practical
=================================================
Topics covered:
  1. Kubernetes manifests (Deployment, Service, Ingress, ConfigMap, Secret)
  2. HPA (Horizontal Pod Autoscaler)
  3. Kubernetes resource management + health probes
  4. Terraform HCL for AWS (EC2, RDS, VPC)
  5. Terraform modules pattern
  6. kubernetes Python client demo
  7. Helm chart structure

Run:
  pip install kubernetes
  python 03_kubernetes_terraform_practical.py
"""

import os

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Kubernetes Deployment YAML
# INTERVIEW: Pod specs, replicas, resource limits, health probes
# ─────────────────────────────────────────────────────────────────────────────

K8S_DEPLOYMENT = """\
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-app
  namespace: production
  labels:
    app: fastapi
spec:
  replicas: 3

  # INTERVIEW: RollingUpdate strategy (zero downtime)
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge:       1    # create 1 extra pod during update
      maxUnavailable: 0    # never reduce below desired count

  selector:
    matchLabels:
      app: fastapi

  template:
    metadata:
      labels:
        app: fastapi
    spec:
      # INTERVIEW: Graceful shutdown (wait for in-flight requests)
      terminationGracePeriodSeconds: 30

      containers:
        - name: fastapi
          image: 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:v1.2.3
          ports:
            - containerPort: 8000

          # Environment from ConfigMap + Secret
          envFrom:
            - configMapRef:
                name: fastapi-config
            - secretRef:
                name: fastapi-secrets

          # INTERVIEW: Resource limits = prevent one pod starving others
          resources:
            requests:           # minimum guaranteed
              cpu:    "100m"    # 0.1 CPU core
              memory: "128Mi"
            limits:             # maximum allowed
              cpu:    "500m"    # 0.5 CPU core (container throttled at limit)
              memory: "512Mi"   # OOMKilled if exceeded

          # INTERVIEW: 3 probe types
          # livenessProbe: is container alive? If fails → restart container
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds:       15
            failureThreshold:    3

          # readinessProbe: is container ready for traffic? If fails → remove from Service
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds:       5
            failureThreshold:    3

          # startupProbe: slow startup apps (give more time)
          startupProbe:
            httpGet:
              path: /health
              port: 8000
            failureThreshold:    30   # 30 * 2s = 60s max startup time
            periodSeconds:       2

      # INTERVIEW: Affinity = control where pods are scheduled
      affinity:
        podAntiAffinity:          # Spread pods across nodes
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: fastapi
                topologyKey: kubernetes.io/hostname
"""

K8S_SERVICE_INGRESS = """\
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
  namespace: production
spec:
  # INTERVIEW: Service types:
  # ClusterIP = internal only (default)
  # NodePort  = expose on node's port (dev/testing)
  # LoadBalancer = creates cloud LB (production)
  type: ClusterIP
  selector:
    app: fastapi
  ports:
    - port: 80
      targetPort: 8000

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fastapi-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "10"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
    - hosts: [api.example.com]
      secretName: api-tls-cert
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: fastapi-service
                port:
                  number: 80

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fastapi-config
  namespace: production
data:
  APP_ENV:          "production"
  LOG_LEVEL:        "INFO"
  WORKERS:          "4"
  REDIS_URL:        "redis://redis-service:6379/0"

---
# k8s/secret.yaml
# INTERVIEW: Secrets are base64 encoded (NOT encrypted by default)
# Use External Secrets Operator or Vault for real encryption
apiVersion: v1
kind: Secret
metadata:
  name: fastapi-secrets
  namespace: production
type: Opaque
data:
  DATABASE_URL: cG9zdGdyZXNxbDovLy4uLg==    # base64 encoded
  SECRET_KEY:   c2VjcmV0LWtleS12YWx1ZQ==
"""

K8S_HPA = """\
# k8s/hpa.yaml — Horizontal Pod Autoscaler
# INTERVIEW: HPA scales pods based on CPU/memory/custom metrics
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-app
  minReplicas: 2
  maxReplicas: 20

  metrics:
    # CPU-based scaling
    - type: Resource
      resource:
        name: cpu
        target:
          type:               AverageUtilization
          averageUtilization: 70    # scale up when avg CPU > 70%

    # Memory-based scaling
    - type: Resource
      resource:
        name: memory
        target:
          type:           AverageValue
          averageValue:   400Mi

    # Custom metric (requests per second via Prometheus)
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type:         AverageValue
          averageValue: "100"

  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60    # Wait 60s before scaling up again
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300   # Wait 5min before scaling down
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Terraform — AWS Infrastructure
# INTERVIEW: Infrastructure as Code (IaC)
# ─────────────────────────────────────────────────────────────────────────────

TERRAFORM_MAIN = """\
# main.tf — AWS infrastructure with Terraform
# INTERVIEW: Terraform: plan → apply → state file tracks resources

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # INTERVIEW: Remote state = team collaboration, no local .tfstate
  backend "s3" {
    bucket         = "myapp-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"   # prevent concurrent applies
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "myapp"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ── Variables ──────────────────────────────────────────────────
variable "aws_region"   { default = "us-east-1" }
variable "environment"  { default = "production" }
variable "db_password"  {
  sensitive = true    # INTERVIEW: sensitive = not shown in plan output
}

# ── VPC Module ─────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "myapp-vpc"
  cidr = "10.0.0.0/16"

  azs              = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets   = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"
}

# ── RDS (PostgreSQL) ───────────────────────────────────────────
resource "aws_db_instance" "postgres" {
  identifier           = "myapp-${var.environment}"
  engine               = "postgres"
  engine_version       = "16.3"
  instance_class       = "db.t3.medium"
  allocated_storage    = 100
  storage_type         = "gp3"
  storage_encrypted    = true    # encryption at rest

  db_name  = "myapp"
  username = "appuser"
  password = var.db_password   # from secrets manager in CI/CD

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  # INTERVIEW: Multi-AZ = standby in another AZ, auto-failover
  multi_az               = var.environment == "production"
  backup_retention_period = 7
  skip_final_snapshot    = var.environment != "production"

  lifecycle {
    prevent_destroy = true   # INTERVIEW: prevent accidental deletion
  }
}

# ── ElastiCache (Redis) ────────────────────────────────────────
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "myapp-redis"
  description          = "Redis for myapp"

  node_type             = "cache.t3.medium"
  num_cache_clusters    = 2      # primary + 1 replica
  automatic_failover_enabled = true

  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
}

# ── Outputs ───────────────────────────────────────────────────
output "rds_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = false
}
"""

TERRAFORM_COMMANDS = {
    "terraform init":                  "Initialize: download providers, configure backend",
    "terraform plan":                  "Show what WILL change (dry run) — review before apply",
    "terraform apply":                 "Apply changes (prompts confirmation)",
    "terraform apply -auto-approve":   "Apply without prompt (CI/CD only!)",
    "terraform destroy":               "DANGER: Destroy all resources",
    "terraform state list":            "List all tracked resources",
    "terraform import aws_s3... arn":  "Import existing resource into state",
    "terraform output":                "Show outputs from current state",
    "terraform workspace new staging": "Create isolated environment",
    "terraform fmt":                   "Format .tf files (like Black for Terraform)",
    "terraform validate":              "Validate syntax without connecting to cloud",
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: kubernetes Python Client
# INTERVIEW: Programmatic K8s management
# ─────────────────────────────────────────────────────────────────────────────

def demo_kubernetes_client():
    print("\n[Kubernetes Python Client Demo]")
    try:
        from kubernetes import client, config

        # Load config (in-cluster or kubeconfig)
        try:
            config.load_incluster_config()   # When running inside K8s
        except Exception:
            config.load_kube_config()        # Local kubectl config

        v1   = client.CoreV1Api()
        apps = client.AppsV1Api()

        # List pods in namespace
        pods = v1.list_namespaced_pod(namespace="default")
        print(f"  Pods in default: {len(pods.items)}")
        for pod in pods.items[:3]:
            print(f"    {pod.metadata.name}: {pod.status.phase}")

        # Scale deployment
        # apps.patch_namespaced_deployment_scale(
        #     name="fastapi-app",
        #     namespace="production",
        #     body={"spec": {"replicas": 5}}
        # )

        # Get deployment status
        # deploy = apps.read_namespaced_deployment("fastapi-app", "production")
        # print(f"  Ready replicas: {deploy.status.ready_replicas}")

    except ImportError:
        print("  kubernetes not installed: pip install kubernetes")
    except Exception as e:
        print(f"  K8s cluster not available: {type(e).__name__}")
        print("  In cluster: runs automatically with service account token")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("KUBERNETES + TERRAFORM PRACTICAL")
    print("=" * 60)

    print("\n[1] Kubernetes Key Concepts:")
    k8s_concepts = {
        "Pod":          "Smallest unit — 1+ containers sharing network/storage",
        "Deployment":   "Manages pod replicas, rolling updates, rollback",
        "Service":      "Stable IP/DNS for pods (ClusterIP/NodePort/LoadBalancer)",
        "Ingress":      "HTTP routing, SSL termination, rate limiting",
        "ConfigMap":    "Non-sensitive config (env vars, config files)",
        "Secret":       "Sensitive config (base64 encoded, use External Secrets for real encryption)",
        "HPA":          "Auto-scale pods based on CPU/memory/custom metrics",
        "Namespace":    "Virtual cluster for isolation (dev/staging/prod)",
    }
    for k, v in k8s_concepts.items():
        print(f"  {k:<12}: {v}")

    print("\n[2] Probe Types:")
    probes = {
        "livenessProbe":  "Is container alive? Fail → restart container",
        "readinessProbe": "Is container ready? Fail → remove from Service (no traffic)",
        "startupProbe":   "Slow startup? Fail → restart (disables liveness during startup)",
    }
    for k, v in probes.items():
        print(f"  {k:<18}: {v}")

    print("\n[3] Terraform Commands:")
    for cmd, desc in list(TERRAFORM_COMMANDS.items())[:6]:
        print(f"  {cmd:<40}: {desc}")

    print("\n[4] Terraform Key Concepts:")
    tf_concepts = {
        "State file":        ".tfstate tracks real world → desired config",
        "Remote backend":    "S3 + DynamoDB locking for team use",
        "sensitive = true":  "Variables not shown in plan output",
        "prevent_destroy":   "lifecycle block → protect production resources",
        "Multi-AZ RDS":      "Standby in another AZ, auto-failover on failure",
        "workspace":         "Isolated environments (dev/staging/prod) from one codebase",
    }
    for k, v in tf_concepts.items():
        print(f"  {k:<20}: {v}")

    demo_kubernetes_client()

    print("\n" + "=" * 60)
    print("INTERVIEW QUICK ANSWERS:")
    print("  Q: Deployment vs StatefulSet?")
    print("     Deployment: stateless apps. StatefulSet: databases (stable identity/storage)")
    print("  Q: Terraform plan vs apply?")
    print("     plan = dry run (shows changes). apply = executes changes to cloud.")
    print("  Q: K8s resource limits?")
    print("     requests = guaranteed minimum. limits = maximum (throttled/OOMKilled if exceeded)")
    print("  Q: Helm?")
    print("     Package manager for K8s. Chart = templates + values.yaml")
    print("=" * 60)


if __name__ == "__main__":
    main()
