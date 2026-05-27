# Lecture 5 — Practical Hands-On: Load Balancing & Auto Scaling

> **Theory file:** [05_Load_Balancing_Auto_Scaling.md](05_Load_Balancing_Auto_Scaling.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Complete LB + Auto-scaling setup:

1. ✅ **Nginx** load balancer (multiple algorithms)
2. ✅ **AWS Application Load Balancer** setup
3. ✅ **Health checks** + connection draining
4. ✅ **Kubernetes HPA** (CPU, memory, custom metrics)
5. ✅ **Cluster Autoscaler** for node scaling
6. ✅ **Canary deployment** via Istio
7. ✅ **Blue-green** deployment
8. ✅ **Multi-region** routing
9. ✅ **Load testing** with k6
10. ✅ **Monitoring** scale events

By end: aap **production load balancing + auto scaling** kar sakte ho.

---

## 1. 🔀 Nginx Load Balancer

### `nginx.conf` — Round Robin

```nginx
events {
    worker_connections 1024;
}

http {
    # Define backend pool
    upstream backend {
        # Default: round-robin
        server backend1.example.com:8000;
        server backend2.example.com:8000;
        server backend3.example.com:8000;
    }
    
    server {
        listen 80;
        
        location / {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
```

### Different Algorithms

```nginx
# Least connections
upstream backend {
    least_conn;
    server backend1.example.com:8000;
    server backend2.example.com:8000;
}

# IP hash (sticky sessions)
upstream backend {
    ip_hash;
    server backend1.example.com:8000;
    server backend2.example.com:8000;
}

# Weighted
upstream backend {
    server backend1.example.com:8000 weight=3;  # Gets 3x traffic
    server backend2.example.com:8000 weight=1;
}

# Health checks (Nginx Plus or open-source variants)
upstream backend {
    server backend1.example.com:8000 max_fails=3 fail_timeout=30s;
    server backend2.example.com:8000 max_fails=3 fail_timeout=30s;
}
```

### Active Health Checks

```nginx
upstream backend {
    server backend1.example.com:8000;
    server backend2.example.com:8000;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://backend;
        proxy_next_upstream error timeout http_500 http_502 http_503;
        proxy_connect_timeout 5s;
    }
    
    # Health check endpoint
    location /health-check {
        access_log off;
        return 200 "OK";
    }
}
```

---

## 2. ☁️ AWS Application Load Balancer

### Terraform Configuration

```hcl
# ALB
resource "aws_lb" "main" {
  name               = "myapp-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.public.ids
  
  enable_deletion_protection = true
}

# Target group
resource "aws_lb_target_group" "app" {
  name        = "myapp-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.main.id
  target_type = "ip"  # For Fargate; use "instance" for EC2
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }
  
  # Connection draining
  deregistration_delay = 30
  
  # Sticky sessions (use sparingly!)
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = false  # Off by default
  }
}

# Listener (HTTPS)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.cert.arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Listener (HTTP → HTTPS redirect)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Path-based routing
resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  
  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}
```

---

## 3. 📈 Auto Scaling Group (AWS)

### Terraform

```hcl
# Launch template
resource "aws_launch_template" "app" {
  name_prefix   = "myapp-"
  image_id      = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.medium"
  
  user_data = base64encode(<<-EOF
              #!/bin/bash
              docker run -d -p 80:8000 myapp:latest
              EOF
  )
}

# Auto Scaling Group
resource "aws_autoscaling_group" "app" {
  name                = "myapp-asg"
  min_size            = 2  # Always at least 2 (HA)
  max_size            = 20
  desired_capacity    = 3
  
  vpc_zone_identifier = data.aws_subnets.private.ids  # Multi-AZ
  target_group_arns   = [aws_lb_target_group.app.arn]
  health_check_type   = "ELB"  # Use LB health check
  health_check_grace_period = 300
  
  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }
  
  # Instance refresh on launch template update
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }
}

# Scale-up policy (CPU > 70%)
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "scale-up"
  scaling_adjustment     = 2  # Add 2 instances
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.app.name
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "myapp-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 70
  
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }
  
  alarm_actions = [aws_autoscaling_policy.scale_up.arn]
}
```

### Scheduled Scaling

```hcl
# Scale up before peak hours
resource "aws_autoscaling_schedule" "scale_up_morning" {
  scheduled_action_name  = "scale-up-morning"
  min_size               = 5
  max_size               = 20
  desired_capacity       = 10
  recurrence             = "0 8 * * MON-FRI"  # 8 AM Mon-Fri
  autoscaling_group_name = aws_autoscaling_group.app.name
}

# Scale down at night
resource "aws_autoscaling_schedule" "scale_down_evening" {
  scheduled_action_name  = "scale-down-evening"
  min_size               = 2
  max_size               = 20
  desired_capacity       = 3
  recurrence             = "0 22 * * *"  # 10 PM daily
  autoscaling_group_name = aws_autoscaling_group.app.name
}
```

---

## 4. ☸️ Kubernetes HPA (Horizontal Pod Autoscaler)

### CPU-Based HPA

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
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 100         # Double pod count
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 min before scaling down
      policies:
      - type: Percent
        value: 50           # Halve pod count
        periodSeconds: 60
```

### Multi-Metric HPA

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
  maxReplicas: 50
  
  metrics:
  # CPU
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  # Memory
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  
  # Custom metric: requests per second (via Prometheus Adapter)
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"  # 1000 req/sec per pod
  
  # External metric: SQS queue depth
  - type: External
    external:
      metric:
        name: sqs_queue_size
        selector:
          matchLabels:
            queue: my-queue
      target:
        type: Value
        value: "100"  # Scale based on queue size
```

### Custom Metrics with Prometheus

```yaml
# Prometheus Adapter for custom metrics
apiVersion: v1
kind: ConfigMap
metadata:
  name: adapter-config
data:
  config.yaml: |
    rules:
    - seriesQuery: 'http_requests_total'
      resources:
        overrides:
          namespace:
            resource: namespace
          pod:
            resource: pod
      name:
        matches: "http_requests_total"
        as: "http_requests_per_second"
      metricsQuery: 'rate(http_requests_total[2m])'
```

### Verify

```bash
$ kubectl get hpa
NAME         REFERENCE          TARGETS            MINPODS   MAXPODS   REPLICAS
myapp-hpa    Deployment/myapp   45%/70%, 60%/80%   2         50        5

# Watch scaling in real-time
$ kubectl get hpa -w

# View scaling events
$ kubectl describe hpa myapp-hpa
```

---

## 5. 🚀 Cluster Autoscaler

### Adds/Removes Nodes Automatically

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
spec:
  template:
    spec:
      containers:
      - image: k8s.gcr.io/autoscaling/cluster-autoscaler:v1.27.0
        name: cluster-autoscaler
        command:
        - ./cluster-autoscaler
        - --v=4
        - --stderrthreshold=info
        - --cloud-provider=aws
        - --skip-nodes-with-local-storage=false
        - --expander=least-waste
        - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/my-cluster
        - --balance-similar-node-groups
        - --scale-down-enabled=true
        - --scale-down-delay-after-add=10m
        - --scale-down-unneeded-time=10m
```

### How It Works

```
Pods scheduled but no node fits?
   → Cluster Autoscaler adds node
   
Node sitting idle for 10 min?
   → Cluster Autoscaler removes it

→ Combined with HPA = full elasticity
```

---

## 6. 🐤 Canary Deployment with Istio

### Install Istio

```bash
$ istioctl install --set profile=demo -y
$ kubectl label namespace default istio-injection=enabled
```

### VirtualService for Canary

```yaml
# Two deployments: v1 (stable) + v2 (canary)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-v1
spec:
  replicas: 9
  selector:
    matchLabels:
      app: myapp
      version: v1
  template:
    metadata:
      labels:
        app: myapp
        version: v1
    spec:
      containers:
      - name: app
        image: myapp:1.0

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-v2
spec:
  replicas: 1  # 10% of total
  selector:
    matchLabels:
      app: myapp
      version: v2
  template:
    metadata:
      labels:
        app: myapp
        version: v2
    spec:
      containers:
      - name: app
        image: myapp:2.0  # New version

---
# Service routes to both
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp  # Selects BOTH v1 and v2
  ports:
  - port: 80
    targetPort: 8000

---
# DestinationRule defines subsets
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: myapp
spec:
  host: myapp
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2

---
# VirtualService controls traffic split
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts:
  - myapp
  http:
  - route:
    - destination:
        host: myapp
        subset: v1
      weight: 90  # 90% to v1
    - destination:
        host: myapp
        subset: v2
      weight: 10  # 10% to v2 (canary)
```

### Progressive Rollout

```bash
# Phase 1: 90/10
$ kubectl apply -f virtualservice-90-10.yaml
$ # Monitor for 24h...

# Phase 2: 75/25
$ kubectl apply -f virtualservice-75-25.yaml
$ # Monitor for 24h...

# Phase 3: 50/50
$ kubectl apply -f virtualservice-50-50.yaml
$ # Monitor for 24h...

# Phase 4: 0/100 (full cutover)
$ kubectl apply -f virtualservice-0-100.yaml
```

### Header-Based Canary (Internal Testing)

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts:
  - myapp
  http:
  # Internal team: route to v2
  - match:
    - headers:
        x-internal-user:
          exact: "true"
    route:
    - destination:
        host: myapp
        subset: v2
  
  # Everyone else: route to v1
  - route:
    - destination:
        host: myapp
        subset: v1
```

---

## 7. 💙💚 Blue-Green Deployment

### Strategy

```
BLUE = current production (live)
GREEN = new version (testing)

Deploy GREEN alongside BLUE.
Test GREEN thoroughly.
Switch all traffic to GREEN instantly.
BLUE becomes standby (for rollback).
```

### Kubernetes Implementation

```yaml
# BLUE deployment (current)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
  labels:
    color: blue
spec:
  replicas: 10
  selector:
    matchLabels:
      app: myapp
      color: blue
  template:
    metadata:
      labels:
        app: myapp
        color: blue
    spec:
      containers:
      - name: app
        image: myapp:1.0

---
# GREEN deployment (new)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
  labels:
    color: green
spec:
  replicas: 10
  selector:
    matchLabels:
      app: myapp
      color: green
  template:
    metadata:
      labels:
        app: myapp
        color: green
    spec:
      containers:
      - name: app
        image: myapp:2.0

---
# Service routes to ONE color at a time
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    color: blue  # ← SWITCH THIS for cutover
  ports:
  - port: 80
    targetPort: 8000
```

### Cutover

```bash
# Test GREEN via internal endpoint
$ curl http://myapp-green.internal/health

# When ready, SWITCH:
$ kubectl patch service myapp \
    -p '{"spec":{"selector":{"color":"green"}}}'

# Instant traffic shift!

# If issues, rollback in seconds:
$ kubectl patch service myapp \
    -p '{"spec":{"selector":{"color":"blue"}}}'
```

---

## 8. 🌐 Multi-Region Routing

### AWS Route 53 Geolocation

```hcl
resource "aws_route53_record" "geo_us" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.example.com"
  type    = "A"
  
  geolocation_routing_policy {
    continent = "NA"  # North America
  }
  
  alias {
    name                   = aws_lb.us_alb.dns_name
    zone_id                = aws_lb.us_alb.zone_id
    evaluate_target_health = true
  }
  
  set_identifier = "us"
}

resource "aws_route53_record" "geo_eu" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.example.com"
  type    = "A"
  
  geolocation_routing_policy {
    continent = "EU"
  }
  
  alias {
    name                   = aws_lb.eu_alb.dns_name
    zone_id                = aws_lb.eu_alb.zone_id
    evaluate_target_health = true
  }
  
  set_identifier = "eu"
}

# Default (anywhere not matched above)
resource "aws_route53_record" "geo_default" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.example.com"
  type    = "A"
  
  geolocation_routing_policy {
    country = "*"  # Default
  }
  
  alias {
    name                   = aws_lb.us_alb.dns_name
    zone_id                = aws_lb.us_alb.zone_id
    evaluate_target_health = true
  }
  
  set_identifier = "default"
}
```

---

## 9. 🧪 Load Testing with k6

### `loadtest.js`

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // Ramp to 100 users
    { duration: '5m', target: 100 },   // Stay at 100
    { duration: '2m', target: 500 },   // Ramp to 500
    { duration: '5m', target: 500 },   // Stay at 500
    { duration: '2m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95% under 500ms
    http_req_failed: ['rate<0.01'],     // < 1% errors
  },
};

export default function () {
  const response = http.get('https://api.example.com/users');
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  sleep(1);
}
```

### Run

```bash
$ k6 run loadtest.js

# Watch K8s HPA respond
$ kubectl get hpa -w

# Watch pods scale
$ kubectl get pods -w
```

---

## 10. 📊 Monitoring Scale Events

### Prometheus Alerts

```yaml
# alerting-rules.yaml
groups:
- name: scaling
  rules:
  - alert: HPAAtMaxReplicas
    expr: kube_horizontalpodautoscaler_status_current_replicas == kube_horizontalpodautoscaler_spec_max_replicas
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "HPA {{ $labels.horizontalpodautoscaler }} at max replicas"
      description: "Consider increasing maxReplicas"
  
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Error rate > 1%"
  
  - alert: HighLatency
    expr: histogram_quantile(0.99, http_request_duration_seconds_bucket) > 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "P99 latency > 2s"
```

### Grafana Dashboard JSON

```
Key panels:
   ✓ Pod count over time
   ✓ Requests per second
   ✓ P50/P95/P99 latency
   ✓ Error rate
   ✓ CPU utilization
   ✓ Memory utilization
   ✓ HPA target vs current
   ✓ Auto-scaling events (annotations)
```

---

## 11. Key Learnings Summary

```
✅ Nginx LB with multiple algorithms
✅ AWS ALB with health checks + draining
✅ Auto Scaling Group with policies
✅ Scheduled scaling for known patterns
✅ Kubernetes HPA: CPU, memory, custom
✅ Cluster Autoscaler for node scaling
✅ Istio for canary + traffic splitting
✅ Blue-green with service selector
✅ Route 53 geo routing
✅ k6 for load testing
✅ Prometheus alerts on scale events

🎯 Production scaling stack:
   Route 53 (geo) → CloudFront (CDN)
   → ALB (LB) → Auto Scaling Group
   → K8s with HPA + Cluster Autoscaler
   → Istio for canary/blue-green
   → Prometheus monitoring
```

---

## 🎬 What's Next?

In **Lecture 6**, we'll explore **Edge Architecture** — CDNs and edge functions.

> **Next lecture:** [06_Edge_Architecture.md](06_Edge_Architecture.md)

---

## 📚 Try It Yourself

1. Set up **multi-tier auto-scaling** (HPA + Cluster Autoscaler)
2. Run **canary deployment** with progressive rollout
3. Implement **blue-green** with zero downtime
4. Load test and tune **thresholds**
5. Build **multi-region** active-active setup
