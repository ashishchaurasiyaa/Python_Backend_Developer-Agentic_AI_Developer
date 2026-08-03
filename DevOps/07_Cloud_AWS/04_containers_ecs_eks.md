# Cloud (AWS) — Containers: ECS, EKS, ECR
**DevOps Track · Phase 7: Cloud (AWS)**

## Quick Concepts

- **ECS** = Elastic Container Service — AWS's own container orchestrator
- **EKS** = Elastic Kubernetes Service — AWS-managed Kubernetes control plane
- **ECR** = Elastic Container Registry — AWS's private Docker image registry
- **Task Definition (ECS)** = the blueprint for a container (or group of containers) — image, CPU/memory, ports, env vars
- **Task** = a running instance of a task definition
- **Service (ECS)** = keeps a desired count of tasks running, integrates with a load balancer
- **Fargate** = serverless compute for containers — no EC2 instances to manage
- **EC2 launch type (ECS)** = you manage the underlying EC2 instances (a cluster) that tasks run on
- **Node group (EKS)** = the EC2 instances (or Fargate profile) that back a Kubernetes cluster's worker nodes
- **Pod** = smallest deployable Kubernetes unit — one or more tightly coupled containers

---

## ECS — Elastic Container Service

### Fargate vs EC2 Launch Type

| | Fargate | EC2 Launch Type |
|---|---|---|
| Underlying infrastructure | Fully managed by AWS — you never see an instance | You provision and manage the EC2 instances (an ECS "cluster" of hosts) |
| Scaling unit | Per-task, billed per vCPU/memory-second | Per-instance — you must right-size the fleet under your tasks |
| Patching / AMI management | None — AWS handles it | Your responsibility (or use the ECS-optimized AMI + managed scaling) |
| Cost model | Higher per-unit cost, zero idle waste | Cheaper at high, steady utilization if you pack instances tightly |
| Startup time | Slightly slower cold start (pulls its own micro-VM) | Instances are already warm if the cluster has capacity |
| Use when | Variable load, small teams, "don't want to think about servers" | Predictable heavy load, need GPU instances, need to squeeze cost via Reserved/Spot fleet |
| Networking | `awsvpc` mode only — every task gets its own ENI | Supports `bridge`, `host`, and `awsvpc` modes |

**The practical default in 2026**: start on Fargate. Move specific workloads to the EC2 launch type only when you have a concrete reason — GPU requirements Fargate doesn't support well, or a cost model where you're already running a large, well-utilized EC2 fleet and the per-task Fargate premium adds up.

### Task Definition

```json
{
  "family": "orders-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/orders-api-task-role",
  "containerDefinitions": [
    {
      "name": "orders-api",
      "image": "123456789012.dkr.ecr.ap-south-1.amazonaws.com/orders-api:v42",
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "environment": [
        {"name": "ENV", "value": "production"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:ap-south-1:123456789012:secret:orders-db-url"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/orders-api",
          "awslogs-region": "ap-south-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

```
executionRoleArn  → permissions ECS itself needs (pull the image from ECR,
                     write logs to CloudWatch, fetch secrets)
taskRoleArn       → permissions the APPLICATION CODE inside the container
                     gets (e.g. write to S3, read from DynamoDB) — this is
                     the same "prefer a role over static keys" principle
                     from the IAM file, applied at the container level

secrets (not environment) → pulled from Secrets Manager/Parameter Store at
                     task launch, never baked into the image or task
                     definition JSON in plaintext
```

### Service — Keeping Tasks Running and Load-Balanced

```bash
aws ecs create-service \
  --cluster prod-cluster \
  --service-name orders-api \
  --task-definition orders-api:42 \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-aaa", "subnet-bbb", "subnet-ccc"],
      "securityGroups": ["sg-0123456789abcdef0"],
      "assignPublicIp": "DISABLED"
    }
  }' \
  --load-balancers '[{
    "targetGroupArn": "arn:aws:elasticloadbalancing:...:targetgroup/orders-api-tg",
    "containerName": "orders-api",
    "containerPort": 8000
  }]' \
  --deployment-configuration '{
    "maximumPercent": 200,
    "minimumHealthyPercent": 100
  }'
```

```
maximumPercent: 200, minimumHealthyPercent: 100
  → during a deployment, ECS can run up to 2x desired count (new + old
    tasks side by side) while never dropping below 100% of desired count
    healthy — this is what gives you a zero-downtime rolling deployment
    without you writing any deployment orchestration yourself
```

ECS Service Auto Scaling attaches the same target-tracking concept from EC2 Auto Scaling to a service's task count — e.g., "keep average CPU across tasks at 60%" and ECS adjusts `desired-count` automatically.

---

## EKS — Elastic Kubernetes Service

### What "Managed Control Plane" Means

```
Standard self-hosted Kubernetes:
  You run + patch + scale + secure: etcd, API server, scheduler,
  controller-manager — across multiple master nodes for HA. This is a
  real operational burden most teams underestimate.

EKS:
  AWS runs the control plane (API server, etcd, scheduler) across
  multiple AZs, patches it, backs it up, scales it — you interact with
  it purely through the standard Kubernetes API (kubectl, same as any
  other cluster). You still own the worker nodes (unless using Fargate
  profiles) and everything you deploy onto the cluster.
```

### Node Groups — How Worker Capacity Is Provisioned

```
Managed Node Group   → AWS provisions and manages an ASG of EC2 instances
                        as Kubernetes worker nodes, handles node draining
                        during updates, integrates with cluster autoscaler

Self-Managed Nodes    → you build your own ASG + launch template + bootstrap
                        script (more control, more operational work)

Fargate Profile        → pods run on Fargate, no EC2 worker nodes at all for
                        matching pods — same "no server to manage" tradeoff
                        as ECS Fargate, at the pod level instead of task level
```

```bash
eksctl create nodegroup \
  --cluster prod-cluster \
  --name workers-general \
  --node-type m6i.large \
  --nodes 3 --nodes-min 2 --nodes-max 8 \
  --managed
```

### ECS vs EKS — the Question Behind the Question

| | ECS | EKS |
|---|---|---|
| Learning curve | Lower — AWS-native concepts, no separate Kubernetes knowledge required | Higher — full Kubernetes API surface, YAML manifests, Helm, CRDs |
| Portability | AWS-only, task definitions don't transfer elsewhere | Kubernetes is portable — same manifests broadly work on GKE, AKS, on-prem |
| Ecosystem | Smaller, AWS-curated integrations | Massive — the entire CNCF/Kubernetes ecosystem (Helm charts, operators, service meshes) |
| Team fit | Small-to-mid teams, AWS-only shops, simpler mental model wanted | Teams already fluent in Kubernetes, multi-cloud ambitions, need the broader ecosystem |
| Control plane cost | No separate charge for the ECS control plane | ~$0.10/hour per cluster flat fee for the managed control plane |

Interview framing: ECS is "less to learn, less portable"; EKS is "more to learn, fully portable and ecosystem-rich." Neither is universally correct — it's a team-capability and portability-requirement decision, not a technical superiority one.

---

## ECR — Elastic Container Registry

ECR itself (build/push/pull mechanics) is covered in the Docker phase — the piece specific to this phase is the **IAM/permission angle**: how ECS tasks and EKS pods actually get authorized to pull images.

### Repository Policy — Who Can Pull/Push

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowECSTaskExecutionPull",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole"},
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ]
    }
  ]
}
```

```
This is a RESOURCE-based policy (attached to the ECR repository itself),
same concept introduced in the IAM file — it grants a specific role pull
access to this specific repository, nothing broader.

Cross-account pulls (e.g. a shared "platform" account hosting images
consumed by multiple app accounts) are done the same way — add the
other account's role/account ARN as an allowed principal here, instead
of duplicating images across accounts.
```

### Image Scanning

```bash
aws ecr put-image-scanning-configuration \
  --repository-name orders-api \
  --image-scanning-configuration scanOnPush=true
```

`scanOnPush` runs a vulnerability scan (CVE database match against installed packages) automatically on every push — the security-pillar habit of catching a vulnerable base image or dependency before it ever reaches an ECS task or EKS pod, rather than discovering it in a later audit.

---

## Senior Tip

```
When asked "ECS or EKS?" in an interview, resist picking a side
immediately. The strong answer names the actual decision variables:

  "If the team already knows Kubernetes and we might go multi-cloud or
   need the CNCF ecosystem (service mesh, specific operators), EKS earns
   its complexity. If this is an AWS-only shop and the team wants the
   fastest path to a reliable deployment without owning a Kubernetes
   control plane's worth of concepts, ECS on Fargate gets there with
   far less operational surface area."

That's a design-tradeoff answer, which is what's actually being tested —
not "which one is more advanced."
```

## Interview Angle

**Q: An ECS Fargate task keeps failing to start with `CannotPullContainerError`. What do you check?**

1. `executionRoleArn` on the task definition — does it have `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`?
2. Networking — is the task in a subnet with a route to pull from ECR (ECR is accessed over the internet or via VPC endpoints; a private subnet with no NAT Gateway and no ECR VPC endpoint cannot reach it at all)?
3. Image tag — does the tag referenced in the task definition actually exist in the repository (typo, or image never pushed)?
4. ECR repository policy — if cross-account, is the pulling role listed as an allowed principal?

---

## Related

- [03_networking_dns_lb.md](03_networking_dns_lb.md) — ALB target groups for ECS services, VPC subnet placement for tasks/nodes
- [05_monitoring_messaging_secrets.md](05_monitoring_messaging_secrets.md) — CloudWatch Logs for `awslogs` driver, Secrets Manager references in task definitions
- [../05_Docker/](../05_Docker/) — Docker build/push mechanics, ECR login flow
- [../06_Kubernetes/](../06_Kubernetes/) — Kubernetes fundamentals that carry directly into EKS
