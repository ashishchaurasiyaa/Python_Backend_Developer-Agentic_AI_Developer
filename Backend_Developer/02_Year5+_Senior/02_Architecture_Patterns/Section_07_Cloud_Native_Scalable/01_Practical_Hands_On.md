# Lecture 1 — Practical Hands-On: Cloud Service Models

> **Theory file:** [01_Cloud_Service_Models.md](01_Cloud_Service_Models.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Hands-on with all cloud service models:

1. ✅ **IaaS** — Launch EC2 instance + deploy app
2. ✅ **PaaS** — Deploy to Heroku / Render
3. ✅ **SaaS** integration — call third-party SaaS APIs
4. ✅ **Serverless** — AWS Lambda function
5. ✅ **Container** deployment to ECS Fargate
6. ✅ **CDN setup** with Cloudflare/CloudFront
7. ✅ **Multi-cloud** comparison
8. ✅ **Cost comparison** across models
9. ✅ **Hybrid deployment** demo
10. ✅ **Production-ready** sample app

By end: aap **production cloud deployment** kar sakte ho across multiple service models.

---

## 1. Project Structure

```
cloud_models_demo/
├── README.md
│
├── iaas_example/
│   ├── terraform/             # AWS EC2 via Terraform
│   ├── deploy.sh
│   └── app/
│
├── paas_example/
│   ├── heroku/                # Heroku deployment
│   ├── render/                # Render alternative
│   └── app.py
│
├── serverless_example/
│   ├── lambda/
│   │   ├── handler.py
│   │   ├── serverless.yml     # Serverless Framework
│   │   └── requirements.txt
│   └── tests/
│
├── container_example/
│   ├── Dockerfile
│   ├── ecs-task-definition.json
│   └── deploy.sh
│
└── cdn_example/
    ├── cloudflare-setup.md
    └── nginx-with-cdn.conf
```

---

## 2. 🏗 IaaS Example: AWS EC2 with Terraform

### `iaas_example/terraform/main.tf`

```hcl
# Terraform - AWS EC2 deployment
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# Security group
resource "aws_security_group" "app_sg" {
  name        = "app-security-group"
  description = "Security group for app server"
  
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["YOUR_IP/32"]  # SSH from your IP only
  }
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# EC2 Instance
resource "aws_instance" "app_server" {
  ami           = "ami-0c55b159cbfafe1f0"  # Ubuntu 22.04
  instance_type = "t3.micro"
  
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  
  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y python3-pip nginx
              
              # Deploy app
              mkdir -p /opt/app
              cat > /opt/app/app.py <<'PYEOF'
              from flask import Flask
              app = Flask(__name__)
              
              @app.route('/')
              def hello():
                  return {"message": "Hello from IaaS!", "instance": "EC2"}
              
              if __name__ == '__main__':
                  app.run(host='0.0.0.0', port=8000)
              PYEOF
              
              # Install + start
              pip3 install flask gunicorn
              cd /opt/app
              gunicorn --bind 0.0.0.0:8000 app:app --daemon
              
              # Nginx reverse proxy
              cat > /etc/nginx/sites-available/app <<'NGINXEOF'
              server {
                  listen 80;
                  location / {
                      proxy_pass http://localhost:8000;
                  }
              }
              NGINXEOF
              ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/
              rm /etc/nginx/sites-enabled/default
              systemctl restart nginx
              EOF
  
  tags = {
    Name = "app-server"
  }
}

output "public_ip" {
  value = aws_instance.app_server.public_ip
}
```

### Deploy

```bash
$ cd iaas_example/terraform
$ terraform init
$ terraform plan
$ terraform apply

# Output: public_ip = 54.123.45.67
$ curl http://54.123.45.67
# {"message": "Hello from IaaS!", "instance": "EC2"}

# YOU manage:
# - OS updates (security patches!)
# - Application server (gunicorn)
# - Reverse proxy (nginx)
# - SSL certificates
# - Scaling (manually add more instances)
# - Monitoring
```

### Cost Analysis

```
t3.micro on-demand: ~$7.50/month
+ EBS storage (8 GB): ~$0.80/month
+ Data transfer (10 GB out): ~$0.90/month
TOTAL: ~$10/month
```

---

## 3. 🚀 PaaS Example: Heroku Deployment

### Project Structure

```
paas_example/heroku/
├── app.py
├── requirements.txt
├── Procfile           # Heroku-specific
├── runtime.txt        # Python version
└── README.md
```

### `app.py`

```python
"""Simple Flask app for Heroku PaaS"""
from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({
        "message": "Hello from PaaS!",
        "platform": "Heroku",
        "dyno": os.getenv("DYNO", "local"),
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
```

### `Procfile`

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

### `requirements.txt`

```
flask>=2.3.0
gunicorn>=21.0.0
```

### `runtime.txt`

```
python-3.11.5
```

### Deploy

```bash
# Install Heroku CLI
$ heroku login

# Create app
$ heroku create my-paas-app

# Deploy (just push code!)
$ git push heroku main

# That's it. Heroku handles:
# ✓ OS provisioning
# ✓ Runtime installation
# ✓ Dependency installation
# ✓ Application server
# ✓ SSL certificates
# ✓ Auto-scaling (with paid dynos)
# ✓ Monitoring
# ✓ Logging

# Access
$ curl https://my-paas-app.herokuapp.com
# {"message": "Hello from PaaS!", "platform": "Heroku", "dyno": "web.1"}

# Scale
$ heroku ps:scale web=3

# Logs
$ heroku logs --tail

# Add Postgres add-on (managed!)
$ heroku addons:create heroku-postgresql:mini
```

### Cost Analysis

```
Basic dyno: $7/month
+ Postgres mini: $5/month
TOTAL: $12/month
✓ Includes: SSL, monitoring, scaling controls
✓ No DevOps work
```

---

## 4. ⚡ Serverless Example: AWS Lambda

### `serverless_example/lambda/handler.py`

```python
"""AWS Lambda function - serverless API endpoint"""
import json

def hello_handler(event, context):
    """
    Triggered by API Gateway.
    Runs only when invoked, scales automatically.
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': json.dumps({
            'message': 'Hello from Serverless!',
            'function': context.function_name,
            'request_id': context.aws_request_id,
            'remaining_ms': context.get_remaining_time_in_millis(),
        })
    }

def s3_trigger_handler(event, context):
    """
    Triggered by S3 upload.
    Process file when uploaded.
    """
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        print(f"Processing: s3://{bucket}/{key}")
        
        # Do something (e.g., resize image, analyze content)
        # ...
    
    return {'statusCode': 200}

def scheduled_handler(event, context):
    """
    Triggered by EventBridge cron schedule.
    e.g., run every hour for batch processing.
    """
    print(f"Scheduled job ran at {context.invoked_function_arn}")
    # ... batch logic ...
```

### `serverless_example/lambda/serverless.yml`

```yaml
# Serverless Framework configuration
service: my-serverless-api

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  
  # Memory + timeout
  memorySize: 256
  timeout: 30
  
  # Environment variables
  environment:
    LOG_LEVEL: INFO

functions:
  # API endpoint
  hello:
    handler: handler.hello_handler
    events:
      - httpApi:
          path: /hello
          method: get
  
  # S3 trigger (process uploads)
  process_upload:
    handler: handler.s3_trigger_handler
    events:
      - s3:
          bucket: my-upload-bucket
          event: s3:ObjectCreated:*
  
  # Scheduled job
  hourly_job:
    handler: handler.scheduled_handler
    events:
      - schedule: rate(1 hour)
```

### Deploy

```bash
$ npm install -g serverless

$ cd serverless_example/lambda
$ serverless deploy

# Output:
# Service Information
# service: my-serverless-api
# stage: dev
# region: us-east-1
# stack: my-serverless-api-dev
# functions:
#   hello: my-serverless-api-dev-hello
#   process_upload: my-serverless-api-dev-process_upload
# endpoints:
#   GET - https://abc123.execute-api.us-east-1.amazonaws.com/hello

$ curl https://abc123.execute-api.us-east-1.amazonaws.com/hello
# {
#   "message": "Hello from Serverless!",
#   "function": "my-serverless-api-dev-hello",
#   "request_id": "...",
#   "remaining_ms": 29950
# }
```

### Cost Analysis

```
1 million requests/month: $0.20
+ 200ms avg execution at 256MB: ~$0.83
TOTAL: ~$1.03/month for 1M requests!

Free tier: 1M requests + 400,000 GB-seconds FREE

→ Way cheaper than EC2 for sporadic traffic!
```

---

## 5. 🐳 Container Example: AWS ECS Fargate

### `container_example/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY app.py .

# Run as non-root user
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
```

### `app.py`

```python
"""Containerized Python app"""
from flask import Flask, jsonify
import socket
import os

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({
        "message": "Hello from Container!",
        "hostname": socket.gethostname(),
        "instance": os.getenv("AWS_REGION", "local"),
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200
```

### Build and Push

```bash
# Build image
$ docker build -t my-app:latest .

# Test locally
$ docker run -p 8000:8000 my-app:latest
$ curl http://localhost:8000

# Push to ECR (Elastic Container Registry)
$ aws ecr create-repository --repository-name my-app
$ aws ecr get-login-password | docker login --username AWS --password-stdin \
    123456789.dkr.ecr.us-east-1.amazonaws.com
$ docker tag my-app:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/my-app:latest
$ docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/my-app:latest
```

### `container_example/ecs-task-definition.json`

```json
{
  "family": "my-app-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "my-app",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/my-app:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/my-app",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "app"
        }
      }
    }
  ]
}
```

### Deploy to Fargate

```bash
# Register task definition
$ aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create cluster
$ aws ecs create-cluster --cluster-name my-cluster

# Run service (3 instances)
$ aws ecs create-service \
    --cluster my-cluster \
    --service-name my-app-service \
    --task-definition my-app-task \
    --desired-count 3 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345]}"
```

### Cost Analysis

```
Fargate: 0.25 vCPU + 512MB
$0.012/hour
3 instances × 720 hours = $26/month
+ Load balancer: $20/month
TOTAL: ~$46/month

vs EC2 equivalent: similar, but with auto-scaling
```

---

## 6. 🌐 CDN Setup with Cloudflare

### Set Up Domain

```bash
# 1. Add site to Cloudflare:
# https://dash.cloudflare.com → Add a Site

# 2. Update nameservers at registrar

# 3. Configure DNS:
# my-app.example.com → A → YOUR_SERVER_IP
#                      → Proxied (orange cloud) ← Important!
```

### Cache Configuration via API

```bash
# Set cache rules
$ curl -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/pagerules" \
    -H "Authorization: Bearer ${API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
      "targets": [{
        "target": "url",
        "constraint": {
          "operator": "matches",
          "value": "example.com/static/*"
        }
      }],
      "actions": [{
        "id": "cache_level",
        "value": "cache_everything"
      }, {
        "id": "edge_cache_ttl",
        "value": 86400
      }],
      "status": "active"
    }'
```

### Nginx Origin Server with CDN Headers

```nginx
# nginx-with-cdn.conf
server {
    listen 80;
    server_name api.example.com;
    
    # Static files: cache aggressively at CDN
    location /static/ {
        alias /var/www/static/;
        
        # CDN caching headers
        add_header Cache-Control "public, max-age=31536000, immutable";
        add_header Vary "Accept-Encoding";
        
        # Cloudflare-specific
        add_header CF-Cache-Status "$upstream_cache_status";
    }
    
    # API: don't cache (dynamic)
    location /api/ {
        proxy_pass http://localhost:8000;
        
        # Don't cache API responses
        add_header Cache-Control "no-store, no-cache";
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
    }
}
```

### Verify CDN Working

```bash
# First request - cache miss
$ curl -I https://example.com/static/logo.png
# CF-Cache-Status: MISS

# Second request - cache hit (fast!)
$ curl -I https://example.com/static/logo.png
# CF-Cache-Status: HIT

# Test from different regions:
$ curl -I https://example.com/static/logo.png --resolve example.com:443:CLOUDFLARE_IP
```

### Cost Analysis

```
Cloudflare:
   ✓ Free plan: unlimited bandwidth + DDoS protection
   ✓ Pro: $20/month for advanced features
   
AWS CloudFront:
   ✓ Pay per GB transferred + per request
   ✓ ~$85/TB outbound
```

---

## 7. 🤝 SaaS Integration Example

### Using Multiple SaaS Services

```python
"""
Real-world: glue together SaaS services.
Often using serverless functions.
"""
from fastapi import FastAPI
import httpx
import os

app = FastAPI()

# All these are SaaS - we just USE them
STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
TWILIO_AUTH = (os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))

@app.post("/payments")
async def process_payment(amount: float, email: str, phone: str):
    """
    Process payment via Stripe (SaaS).
    Then notify via SendGrid (SaaS), Slack (SaaS), Twilio (SaaS).
    """
    async with httpx.AsyncClient() as client:
        # 1. Charge via Stripe
        stripe_response = await client.post(
            "https://api.stripe.com/v1/charges",
            auth=(STRIPE_KEY, ""),
            data={"amount": int(amount * 100), "currency": "usd"},
        )
        charge = stripe_response.json()
        
        # 2. Send email via SendGrid
        await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}"},
            json={
                "personalizations": [{"to": [{"email": email}]}],
                "from": {"email": "noreply@example.com"},
                "subject": "Payment received",
                "content": [{"type": "text/plain", "value": f"You paid ${amount}"}],
            }
        )
        
        # 3. Notify team via Slack
        await client.post(SLACK_WEBHOOK, json={
            "text": f"💰 New payment of ${amount} from {email}"
        })
        
        # 4. SMS via Twilio
        await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_AUTH[0]}/Messages.json",
            auth=TWILIO_AUTH,
            data={
                "From": "+15555551234",
                "To": phone,
                "Body": f"Payment of ${amount} processed!",
            }
        )
    
    return {"charge_id": charge["id"], "status": "success"}
```

### Why This Is Powerful

```
We built a payment processing system using:
   ✓ Stripe (payments) — would take months to build
   ✓ SendGrid (email) — handles deliverability
   ✓ Slack (notifications) — team alerts
   ✓ Twilio (SMS) — global SMS reach

Total dev time: 2 hours
Total cost: pay-per-use SaaS pricing
Maintenance: ZERO infrastructure!
```

---

## 8. 💰 Cost Comparison Across Models

### Same App, Different Models

```
Scenario: Simple API serving 1M requests/month, 100ms avg response
```

```
┌────────────────┬──────────────┬─────────────────────────────────┐
│  MODEL          │  ~MONTHLY $  │  WHY                            │
├────────────────┼──────────────┼─────────────────────────────────┤
│ IaaS (EC2 t3)   │  ~$25         │ Always-on VM + LB              │
│ PaaS (Heroku)   │  ~$50         │ Per-dyno pricing               │
│ Containers (ECS)│  ~$50         │ Fargate + LB                   │
│ Serverless      │  ~$2          │ Pay per execution!             │
│ Edge functions  │  ~$5          │ CDN-level execution            │
└────────────────┴──────────────┴─────────────────────────────────┘
```

### When Each Wins

```
Low + bursty traffic     → Serverless (cheapest)
Steady moderate traffic  → IaaS or containers
Predictable + simple     → PaaS
Global latency critical  → Edge functions
Compliance heavy         → IaaS (dedicated hosts)
```

---

## 9. 🌈 Hybrid Architecture Example

### Real-World Stack

```
┌──────────────────────────────────────────────────────────┐
│                                                            │
│  Global CDN (Cloudflare)                                  │
│  ↓                                                         │
│  Edge Functions (Cloudflare Workers)                      │
│  ✓ Auth check                                              │
│  ✓ Geo routing                                             │
│  ↓                                                         │
│  Application (PaaS - Vercel for SPA)                      │
│  ↓                                                         │
│  API (Containers - AWS ECS)                                │
│  ↓                                                         │
│  Database (Managed PaaS - AWS RDS)                        │
│  ↓                                                         │
│  Background jobs (Serverless - Lambda)                    │
│  ↓                                                         │
│  Notifications (SaaS - SendGrid, Twilio)                  │
│  ↓                                                         │
│  Analytics (SaaS - Mixpanel)                              │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

### Choosing Per Workload

```
✓ Static assets (CSS, JS, images) → CDN
✓ Frontend SPA → PaaS (Vercel/Netlify)
✓ Backend API → Containers (steady traffic)
✓ Async jobs → Serverless (bursty)
✓ Email/SMS/Analytics → SaaS (commodity)
✓ Heavy compute → IaaS (full control)
```

---

## 10. Key Learnings Summary

```
✅ IaaS: full control, max DevOps work, Terraform-managed
✅ PaaS: focus on code, Heroku-style git push deployment
✅ Serverless: pay per execution, Lambda for event-driven
✅ Containers: portable + cloud-agnostic, ECS Fargate
✅ CDN: free with Cloudflare, dramatically faster globally
✅ SaaS: don't build commodity features, integrate them
✅ Cost varies 10x+ between models for same workload
✅ Hybrid approach is normal in production

🎯 Production cloud stack:
   CDN → Edge → PaaS frontend → Containers backend → 
   Serverless workers → Managed DB → SaaS integrations
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll learn **12-Factor App methodology** — principles for building apps that thrive in cloud environments.

> **Next lecture:** [02_12_Factor_App.md](02_12_Factor_App.md)

---

## 📚 Try It Yourself

1. Deploy same app to **3 different cloud models** and compare
2. Set up **CDN** in front of existing app and measure latency
3. Migrate a workload **from EC2 to Lambda** and compare costs
4. Build **hybrid stack** using 4+ different service models
5. Calculate **total cost of ownership** for your use case
