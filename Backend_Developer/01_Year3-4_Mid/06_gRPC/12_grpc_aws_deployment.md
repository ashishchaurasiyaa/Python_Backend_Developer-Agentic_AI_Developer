# gRPC on AWS — ALB, App Mesh, ECS Fargate, Service Discovery

## Quick Concepts

**WHAT:**
- **ALB with gRPC** = Application LB supports gRPC since 2020 (requires specific config)
- **AWS App Mesh** = AWS-managed service mesh (Envoy-based)
- **ECS Fargate** = serverless container hosting for gRPC services
- **AWS Cloud Map** = service discovery (DNS-based)
- **PrivateLink** = private connectivity across VPCs

**WHY AWS-specific gRPC needs care:**
- ALB requires HTTP/2 + HTTPS for gRPC
- NLB doesn't do L7 LB (per-connection only)
- Cross-AZ gRPC traffic has cost implications
- Long-lived connections + Fargate task replacement = special handling

**HOW AWS gRPC architecture:**
```
                  ┌─────────────┐
                  │  Route 53   │  api.example.com
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │     ALB     │  HTTPS + HTTP/2 + gRPC
                  │ (protocol:  │
                  │   GRPC)     │
                  └──────┬──────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
       ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
       │ Fargate │  │ Fargate │  │ Fargate │
       │ Task 1  │  │ Task 2  │  │ Task 3  │
       │ gRPC    │  │ gRPC    │  │ gRPC    │
       │ :50051  │  │ :50051  │  │ :50051  │
       └─────────┘  └─────────┘  └─────────┘
```

---

## Interview Questions & Answers

### Q1: AWS ALB ke saath gRPC kaise deploy karein? Step-by-step?

**Answer:**

**WHAT:** ALB supports gRPC since Oct 2020 with proper config.

**WHY ALB over NLB for gRPC:**
- ✅ Per-request LB (true HTTP/2 multiplexing distributes load)
- ✅ Path-based routing per gRPC method
- ✅ WAF integration
- ✅ TLS termination
- ❌ Slightly higher latency than NLB (~1-2ms)

**HOW — Full Terraform setup:**

```hcl
# 1. VPC + Subnets (skipped — assume exists)

# 2. ACM Certificate (HTTPS required for HTTP/2)
resource "aws_acm_certificate" "grpc" {
  domain_name       = "api.example.com"
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

# 3. Security Group (allow ALB → ECS tasks)
resource "aws_security_group" "ecs_grpc" {
  name = "grpc-service-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 50051
    to_port         = 50051
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 4. ALB
resource "aws_lb" "main" {
  name               = "grpc-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = 4000   # ⭐ For long-running streams (default 60s too short)
}

# 5. Target Group (CRITICAL settings)
resource "aws_lb_target_group" "grpc" {
  name             = "grpc-tg"
  port             = 50051
  protocol         = "HTTP"
  protocol_version = "GRPC"     # ⭐ CRITICAL: GRPC (not HTTP2)
  target_type      = "ip"        # ⭐ ip (for Fargate)
  vpc_id           = aws_vpc.main.id

  health_check {
    enabled             = true
    protocol            = "HTTP"
    path                = "/grpc.health.v1.Health/Check"  # ⭐ gRPC health endpoint
    matcher             = "0"                              # ⭐ gRPC OK status = 0
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
  }

  deregistration_delay = 30   # Graceful task removal
}

# 6. ALB Listener (HTTPS REQUIRED for HTTP/2)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-Res-2019-08"
  certificate_arn   = aws_acm_certificate.grpc.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grpc.arn
  }
}

# 7. ECS Cluster
resource "aws_ecs_cluster" "grpc" {
  name = "grpc-cluster"
}

# 8. ECS Task Definition
resource "aws_ecs_task_definition" "grpc" {
  family                   = "grpc-user-service"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "grpc-user-service"
    image = "${aws_ecr_repository.grpc.repository_url}:latest"

    portMappings = [{
      containerPort = 50051
      protocol      = "tcp"
    }]

    environment = [
      { name = "GRPC_PORT", value = "50051" },
      { name = "ENV", value = "production" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/grpc-user-service"
        awslogs-region        = "ap-south-1"
        awslogs-stream-prefix = "grpc"
      }
    }

    healthCheck = {
      command  = ["CMD-SHELL", "grpc_health_probe -addr=:50051 || exit 1"]
      interval = 30
      timeout  = 5
      retries  = 3
      startPeriod = 30
    }

    stopTimeout = 30   # ⭐ Graceful shutdown time
  }])
}

# 9. ECS Service
resource "aws_ecs_service" "grpc" {
  name            = "grpc-user-service"
  cluster         = aws_ecs_cluster.grpc.id
  task_definition = aws_ecs_task_definition.grpc.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_grpc.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.grpc.arn
    container_name   = "grpc-user-service"
    container_port   = 50051
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_configuration {
    minimum_healthy_percent = 100
    maximum_percent         = 200
  }

  # ⭐ Health check grace period (allow time for grpc_health_probe)
  health_check_grace_period_seconds = 60
}

# 10. Auto-scaling
resource "aws_appautoscaling_target" "grpc" {
  max_capacity       = 10
  min_capacity       = 3
  resource_id        = "service/${aws_ecs_cluster.grpc.name}/${aws_ecs_service.grpc.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "grpc_cpu" {
  name               = "cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.grpc.resource_id
  scalable_dimension = aws_appautoscaling_target.grpc.scalable_dimension
  service_namespace  = aws_appautoscaling_target.grpc.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70
  }
}
```

---

### Q2: AWS App Mesh kya hai? gRPC ke liye kab use karein?

**Answer:**

**WHAT:** AWS-managed service mesh (Envoy-based) — provides traffic management, observability, security.

**WHY for gRPC:**
- ✅ True per-request LB (not just per-connection like ALB)
- ✅ mTLS automatic (cert rotation)
- ✅ Retries + circuit breakers at proxy level
- ✅ Detailed metrics in CloudWatch
- ❌ Adds Envoy sidecar to every task (memory overhead)
- ❌ Steeper learning curve

**HOW — App Mesh architecture:**

```
┌──────────────────┐         ┌──────────────────┐
│  ECS Task        │         │  ECS Task        │
│  ┌────────────┐  │         │  ┌────────────┐  │
│  │ App        │  │         │  │ App        │  │
│  └──────┬─────┘  │         │  └──────┬─────┘  │
│         │        │         │         │        │
│  ┌──────▼─────┐  │  mTLS   │  ┌──────▼─────┐  │
│  │  Envoy     │◄─┼─────────┼──┤  Envoy     │  │
│  │  Sidecar   │  │         │  │  Sidecar   │  │
│  └────────────┘  │         │  └────────────┘  │
└──────────────────┘         └──────────────────┘
       Service A                    Service B
```

**HOW — Terraform setup:**

```hcl
# 1. Create mesh
resource "aws_appmesh_mesh" "main" {
  name = "production-mesh"

  spec {
    egress_filter {
      type = "ALLOW_ALL"
    }
  }
}

# 2. Virtual Node (represents your service)
resource "aws_appmesh_virtual_node" "user_service" {
  name      = "user-service-vn"
  mesh_name = aws_appmesh_mesh.main.id

  spec {
    listener {
      port_mapping {
        port     = 50051
        protocol = "grpc"        # ⭐ gRPC protocol
      }

      health_check {
        protocol            = "grpc"
        port                = 50051
        path                = "/grpc.health.v1.Health/Check"
        healthy_threshold   = 2
        unhealthy_threshold = 3
        interval_millis     = 30000
        timeout_millis      = 5000
      }

      tls {
        mode = "STRICT"   # ⭐ Force mTLS
        certificate {
          acm {
            certificate_arn = aws_acm_certificate.service.arn
          }
        }
      }
    }

    service_discovery {
      aws_cloud_map {
        service_name   = aws_service_discovery_service.user.name
        namespace_name = aws_service_discovery_private_dns_namespace.main.name
      }
    }
  }
}

# 3. Virtual Service (logical service name)
resource "aws_appmesh_virtual_service" "user" {
  name      = "user-service.local"
  mesh_name = aws_appmesh_mesh.main.id

  spec {
    provider {
      virtual_node {
        virtual_node_name = aws_appmesh_virtual_node.user_service.name
      }
    }
  }
}

# 4. Add Envoy sidecar to ECS task
resource "aws_ecs_task_definition" "with_envoy" {
  # ... existing config

  container_definitions = jsonencode([
    {
      name = "app"
      # ... your gRPC service
    },
    {
      # ⭐ Envoy sidecar (auto-injected)
      name      = "envoy"
      image     = "840364872350.dkr.ecr.ap-south-1.amazonaws.com/aws-appmesh-envoy:v1.27.0.0-prod"
      essential = true
      environment = [
        { name = "APPMESH_RESOURCE_ARN", value = aws_appmesh_virtual_node.user_service.arn },
        { name = "ENVOY_LOG_LEVEL", value = "info" },
      ]
      user = "1337"  # Required for App Mesh
      healthCheck = {
        command  = ["CMD-SHELL", "curl -s http://localhost:9901/server_info | grep state | grep -q LIVE"]
        interval = 5
        retries  = 3
        startPeriod = 10
      }
    }
  ])

  proxy_configuration {
    type           = "APPMESH"
    container_name = "envoy"
    properties = {
      AppPorts         = "50051"
      EgressIgnoredIPs = "169.254.170.2,169.254.169.254"
      IgnoredUID       = "1337"
      ProxyEgressPort  = "15001"
      ProxyIngressPort = "15000"
    }
  }
}
```

---

### Q3: AWS Cloud Map se gRPC service discovery kaise karein?

**Answer:**

**WHAT:** AWS managed service discovery — DNS-based, integrates with ECS.

**WHY:**
- ✅ Service auto-registers on start, deregisters on stop
- ✅ DNS-based (works with any gRPC client)
- ✅ Health-aware (only healthy instances returned)

**HOW — Terraform setup:**

```hcl
# 1. Private DNS namespace
resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "internal.local"
  description = "Internal service discovery"
  vpc         = aws_vpc.main.id
}

# 2. Service registration
resource "aws_service_discovery_service" "user_grpc" {
  name = "user-grpc"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10   # ⭐ Low TTL for fast pod removal awareness
      type = "A"
    }
    routing_policy = "MULTIVALUE"  # Returns multiple A records
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# 3. ECS Service references it
resource "aws_ecs_service" "user_grpc" {
  # ... existing config

  service_registries {
    registry_arn = aws_service_discovery_service.user_grpc.arn
  }
}
```

**HOW — Client uses DNS:**

```python
# DNS resolves to all healthy task IPs
channel = grpc.aio.secure_channel(
    "user-grpc.internal.local:50051",   # ⭐ Cloud Map DNS
    credentials,
    options=[
        ("grpc.lb_policy_name", "round_robin"),
        ("grpc.dns_min_time_between_resolutions_ms", 5000),
    ]
)
```

**HOW — Programmatic discovery (alternative to DNS):**

```python
import boto3

sd = boto3.client("servicediscovery")

response = sd.discover_instances(
    NamespaceName="internal.local",
    ServiceName="user-grpc",
    HealthStatus="HEALTHY"
)

instances = response["Instances"]
endpoints = [
    f"{i['Attributes']['AWS_INSTANCE_IPV4']}:{i['Attributes']['AWS_INSTANCE_PORT']}"
    for i in instances
]
# Build channel pool from endpoints
```

---

### Q4: Cross-region gRPC traffic ka cost optimization kaise karein?

**Answer:**

**WHAT:** Inter-region/AZ data transfer costs add up.

**WHY watch costs:**
- Inter-AZ: $0.01/GB
- Inter-region: $0.02-0.09/GB
- Heavy gRPC traffic can mean thousands of $$/month

**HOW — Cost analysis:**

```
Example: 100 RPS, avg 5KB request + 50KB response = 55KB/req
- Per second: 5.5 MB
- Per day: 475 GB
- Per month: ~14 TB
- Inter-AZ cost: 14000 × $0.01 = $140/month
- Inter-region cost: 14000 × $0.02 = $280/month
```

**HOW — Optimizations:**

```hcl
# 1. Place gRPC server + client in SAME AZ
resource "aws_ecs_service" "user_grpc" {
  # ... config
  placement_constraints {
    type       = "memberOf"
    expression = "attribute:ecs.availability-zone == ${var.preferred_az}"
  }
}

# 2. Use VPC Endpoint (PrivateLink) for cross-VPC
resource "aws_vpc_endpoint_service" "grpc" {
  acceptance_required        = false
  network_load_balancer_arns = [aws_lb.nlb.arn]
}

# Other VPC creates endpoint, traffic stays within AWS network
resource "aws_vpc_endpoint" "grpc_consumer" {
  service_name      = aws_vpc_endpoint_service.grpc.service_name
  vpc_id            = aws_vpc.consumer.id
  vpc_endpoint_type = "Interface"
  subnet_ids        = aws_subnet.consumer_private[*].id
}

# 3. Enable compression on gRPC channel
# (already covered in 08_grpc_performance_tuning.md)

# 4. Use Aurora Global Database for cross-region (avoid data transfer)
# vs. cross-region gRPC calls
```

---

### Q5: ECS Fargate graceful task replacement during deploys?

**Answer:**

**WHAT:** Replace tasks without dropping in-flight gRPC requests.

**WHY important:**
- gRPC = long-lived connections
- Force kill = client gets UNAVAILABLE → 500 to user
- Graceful = clients finish + auto-reconnect to new task

**HOW — ECS settings:**

```hcl
resource "aws_ecs_service" "grpc" {
  # ... existing config

  # ⭐ Rolling update
  deployment_configuration {
    minimum_healthy_percent = 100       # Always 100% capacity
    maximum_percent         = 200       # New tasks added FIRST
  }

  # ⭐ Health check grace period
  health_check_grace_period_seconds = 60

  # ⭐ Circuit breaker (auto-rollback if deployment fails)
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

resource "aws_ecs_task_definition" "grpc" {
  # ⭐ Stop timeout — time for graceful shutdown
  container_definitions = jsonencode([{
    # ...
    stopTimeout = 30   # ⭐ 30s to drain connections
  }])
}

resource "aws_lb_target_group" "grpc" {
  # ⭐ Deregistration delay — wait before removing target
  deregistration_delay = 30
}
```

**HOW — Application handles SIGTERM:**

```python
import asyncio
import grpc
import signal

async def serve():
    server = grpc.aio.server()
    # ... add services

    server.add_insecure_port("[::]:50051")
    await server.start()

    # ⭐ Graceful shutdown handler
    async def shutdown(sig):
        print(f"Received {sig.name}, shutting down gracefully...")
        # Mark health check as UNHEALTHY (ALB stops sending new requests)
        health_servicer.set("", health_pb2.HealthCheckResponse.NOT_SERVING)

        # Wait for ALB to deregister (~30s deregistration_delay)
        await asyncio.sleep(5)

        # Then stop server with grace period (existing requests complete)
        await server.stop(grace=30)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))

    await server.wait_for_termination()


asyncio.run(serve())
```

**Deploy sequence:**

```
1. ECS launches new task (200% capacity)
2. New task passes health check
3. ALB routes traffic to new task
4. ECS marks old task for stopping
5. ALB sends SIGTERM to old task
6. Old task: marks health as NOT_SERVING
7. ALB sees unhealthy → stops routing
8. Old task: completes active requests (30s grace)
9. Container exits cleanly
10. Total downtime: 0
```

---

### Q6: CloudWatch metrics + alarms gRPC ke liye?

**Answer:**

**HOW — Key metrics + alarms:**

```hcl
# 1. ALB error rate (5xx responses from targets)
resource "aws_cloudwatch_metric_alarm" "grpc_5xx_high" {
  alarm_name          = "grpc-high-5xx-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.grpc.arn_suffix
  }
}

# 2. Target health (any unhealthy)
resource "aws_cloudwatch_metric_alarm" "grpc_unhealthy_hosts" {
  alarm_name          = "grpc-unhealthy-hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 0

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.grpc.arn_suffix
  }
}

# 3. p99 latency from ALB
resource "aws_cloudwatch_metric_alarm" "grpc_high_latency" {
  alarm_name          = "grpc-p99-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p99"
  threshold           = 2.0   # 2 seconds
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# 4. ECS CPU
resource "aws_cloudwatch_metric_alarm" "ecs_high_cpu" {
  alarm_name          = "grpc-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
}

# 5. Active connection count (gRPC specific concern)
resource "aws_cloudwatch_metric_alarm" "grpc_active_connections" {
  alarm_name          = "grpc-too-many-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "ActiveConnectionCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10000
}
```

**HOW — CloudWatch Logs Insights queries:**

```
# Slow gRPC methods
fields @timestamp, method, duration_ms
| filter duration_ms > 1000
| stats count(), avg(duration_ms), max(duration_ms) by method
| sort count desc

# Error rate by method
fields @timestamp, method, grpc_status
| filter grpc_status != "OK"
| stats count() by method, grpc_status

# p99 latency by service
fields @timestamp, method, duration_ms
| stats pct(duration_ms, 99) as p99 by method
```

---

### Q7: PrivateLink with gRPC — cross-account access?

**Answer:**

**WHAT:** Connect VPCs across accounts without VPC peering.

**WHY for gRPC:**
- ✅ Expose gRPC service to other AWS accounts privately
- ✅ Stays within AWS network (no internet)
- ✅ Granular permissions per consumer

**HOW — Provider setup:**

```hcl
# 1. NLB (PrivateLink requires NLB, not ALB)
resource "aws_lb" "grpc_nlb" {
  name               = "grpc-nlb"
  load_balancer_type = "network"
  internal           = true
  subnets            = aws_subnet.private[*].id
}

resource "aws_lb_target_group" "grpc_nlb" {
  name        = "grpc-nlb-tg"
  port        = 50051
  protocol    = "TCP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    protocol = "TCP"
    port     = "50051"
  }
}

# 2. VPC Endpoint Service
resource "aws_vpc_endpoint_service" "grpc" {
  acceptance_required        = true   # Manual approval per consumer
  network_load_balancer_arns = [aws_lb.grpc_nlb.arn]
  allowed_principals = [
    "arn:aws:iam::CONSUMER_ACCOUNT_ID:root"
  ]
}

output "service_name" {
  value = aws_vpc_endpoint_service.grpc.service_name
  # e.g., com.amazonaws.vpce.ap-south-1.vpce-svc-1234567890abcdef0
}
```

**HOW — Consumer setup (in different AWS account):**

```hcl
resource "aws_vpc_endpoint" "grpc_consumer" {
  vpc_id              = aws_vpc.consumer.id
  service_name        = "com.amazonaws.vpce.ap-south-1.vpce-svc-..."
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.consumer_private[*].id
  security_group_ids  = [aws_security_group.endpoint.id]
  private_dns_enabled = false   # Use returned DNS instead

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "*"
      Resource  = "*"
    }]
  })
}

output "endpoint_dns" {
  value = aws_vpc_endpoint.grpc_consumer.dns_entry[0].dns_name
}
```

**Client connects via PrivateLink DNS:**

```python
# Use the endpoint DNS from output
channel = grpc.aio.secure_channel(
    "vpce-xxx.vpce-svc-xxx.ap-south-1.vpce.amazonaws.com:50051",
    credentials
)
```

---

## AWS gRPC Production Checklist

```markdown
### ALB Configuration
- [ ] protocol_version = "GRPC" (not HTTP2)
- [ ] target_type = "ip" (for Fargate)
- [ ] Health check path = "/grpc.health.v1.Health/Check"
- [ ] Health check matcher = "0"
- [ ] HTTPS listener with valid cert
- [ ] idle_timeout = 4000 for long streams

### ECS Service
- [ ] grpc_health_probe in Docker image
- [ ] stopTimeout = 30s (graceful shutdown)
- [ ] deployment minimum_healthy_percent = 100
- [ ] Circuit breaker enabled
- [ ] Health check grace period = 60s

### Networking
- [ ] Security group allows ALB → ECS:50051 only
- [ ] ECS tasks in private subnets
- [ ] Cloud Map for service discovery (internal)
- [ ] PrivateLink for cross-account

### Observability
- [ ] CloudWatch alarms (5xx, latency, CPU)
- [ ] CloudWatch Logs Insights queries saved
- [ ] X-Ray tracing enabled (if using App Mesh)
- [ ] Custom metrics for business logic

### Cost
- [ ] Same AZ for client/server (avoid inter-AZ)
- [ ] Compression for large payloads
- [ ] Connection reuse (no per-request channels)
- [ ] PrivateLink for cross-VPC (vs peering)
```

---

## Cost Optimization Summary

| Strategy | Savings | Effort |
|---|---|---|
| Single AZ deployment | Up to $500/mo at scale | Low |
| Enable compression | 30-70% bandwidth | Low |
| Channel reuse | CPU + connection cost | Low |
| Reserved capacity | 30-50% on Fargate | Medium |
| App Mesh ARM-based Envoy | 20% cheaper | Low |
| PrivateLink vs peering | Variable | Medium |
