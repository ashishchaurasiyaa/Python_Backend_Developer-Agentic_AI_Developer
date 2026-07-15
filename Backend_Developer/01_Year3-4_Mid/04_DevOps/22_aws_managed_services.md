# AWS Managed Services — Lambda, API Gateway, EventBridge, CloudWatch, Secrets Manager, ECS, EKS

**DevOps · Year 3-4 | Senior Backend + Agentic AI**

> Note: EC2/S3/RDS/SQS/SNS/IAM already covered in [04_aws_ec2_s3_rds.md](04_aws_ec2_s3_rds.md). Ye file un baaki AWS managed services ko cover karti hai jo backend interviews me poochhe jaate hain.

---

## Quick Concepts
- **Lambda** = serverless function — code upload karo, AWS server manage karta hai, sirf execution time ka billing
- **API Gateway** = managed HTTP entrypoint — Lambda/backend ke aage REST/HTTP API expose karta hai (auth, throttling, request validation built-in)
- **EventBridge** = managed event bus — services ke beech events route karta hai (SNS se zyada powerful routing rules)
- **CloudWatch** = logs + metrics + alarms — production monitoring ka backbone
- **Secrets Manager** = encrypted secret storage with auto-rotation (vs plain env vars)
- **ECS** = AWS ka own container orchestrator (Fargate = serverless containers, EC2 launch type = self-managed nodes)
- **EKS** = managed Kubernetes — same K8s API, AWS control plane manage karta hai

---

## Part 1: Lambda — Serverless Functions

### Q1: Lambda function kaise likhte hain aur deploy karte hain?
**Answer:**
```python
# lambda_function.py
import json

def lambda_handler(event, context):
    """AWS Lambda entrypoint — event = trigger payload, context = runtime info"""
    name = event.get("queryStringParameters", {}).get("name", "world")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": f"Hello, {name}!"})
    }
```
```bash
# Package + deploy
zip function.zip lambda_function.py
aws lambda create-function \
    --function-name my-function \
    --runtime python3.12 \
    --handler lambda_function.lambda_handler \
    --role arn:aws:iam::123456789:role/lambda-execution-role \
    --zip-file fileb://function.zip \
    --timeout 10 \
    --memory-size 256

# Update code (redeploy)
aws lambda update-function-code --function-name my-function --zip-file fileb://function.zip

# Invoke directly (testing)
aws lambda invoke --function-name my-function --payload '{"queryStringParameters":{"name":"Ashish"}}' out.json
```

### Q2: Lambda cold start kya hai? Kaise minimize karte hain?
**Answer:**
- **Cold start** = pehli invocation (ya idle ke baad) me naya execution environment banta hai — container init + runtime boot + code load = latency spike (100ms–several seconds, especially Java/large deps)
- **Warm start** = same container reuse — subsequent calls fast (single-digit ms overhead)

**Minimize karne ke tareeke:**
```
1. Provisioned Concurrency — N warm instances hamesha ready rakho (extra cost, zero cold start)
2. Package size chhota rakho — heavy imports (pandas, numpy) lazy-load karo function ke andar
3. Memory badhao — CPU proportional hai memory ke saath, chhota function bhi fast complete hota hai
4. Keep-alive ping — scheduled EventBridge rule har 5 min pe dummy invoke (hacky, provisioned concurrency better hai)
5. Lambda SnapStart (Java) — pre-initialized snapshot se resume
```

### Q3: Lambda ko kab use karo vs ECS/EKS?
**Answer:**
| Criteria | Lambda | ECS/EKS |
|---|---|---|
| Request duration | <15 min (hard limit) | unlimited |
| Traffic pattern | spiky/unpredictable | steady/high-throughput |
| Cold start tolerance | OK (sub-second acceptable) | not applicable (always running) |
| Billing | per-invocation + duration | per-container-hour (always running) |
| Best for | event handlers, webhooks, cron, glue code | full APIs, long-running services, WebSockets |

**INTERVIEW: FastAPI ko Lambda pe chala sakte ho?**
Haan — `Mangum` adapter se (`from mangum import Mangum; handler = Mangum(app)`). Lekin persistent WebSocket connections ya long-lived background tasks ke liye ECS/EKS better hai kyunki Lambda 15-min max aur connection reuse guarantee nahi karta.

---

## Part 2: API Gateway

### Q4: API Gateway Lambda ke saath kaise wire hota hai?
**Answer:**
```
Client → API Gateway (HTTP API/REST API) → Lambda → Response
              │
              ├── Auth (Cognito / Lambda authorizer / IAM)
              ├── Throttling (rate limit per API key)
              ├── Request validation (JSON schema)
              └── CORS handling
```
```bash
# HTTP API (cheaper, simpler than REST API) — create + route + integrate
aws apigatewayv2 create-api --name my-api --protocol-type HTTP --target arn:aws:lambda:ap-south-1:123456789:function:my-function

# Add usage plan for rate limiting
aws apigateway create-usage-plan \
    --name basic-plan \
    --throttle burstLimit=50,rateLimit=20 \
    --quota limit=10000,period=MONTH
```

**REST API vs HTTP API:** REST API = more features (request/response transformation, API keys, WAF integration) but costlier + slower. HTTP API = ~70% cheaper, lower latency, built for Lambda-proxy pattern — default choice unless you need REST API's extra features.

---

## Part 3: EventBridge

### Q5: EventBridge, SNS se kaise alag hai?
**Answer:**
- **SNS** = simple fan-out — ek topic, sab subscribers ko same message milta hai (filtering limited)
- **EventBridge** = content-based routing — rules define karo (event pattern match), sirf matching consumers ko route ho, multiple SaaS/AWS-service sources bhi built-in support karta hai

```python
import boto3, json

eventbridge = boto3.client("events", region_name="ap-south-1")

# Custom event publish karo
eventbridge.put_events(
    Entries=[{
        "Source": "myapp.orders",
        "DetailType": "OrderPlaced",
        "Detail": json.dumps({"order_id": "123", "amount": 499}),
        "EventBusName": "default",
    }]
)
```
```json
// Rule: sirf OrderPlaced events > amount 100 route karo Lambda ko
{
  "source": ["myapp.orders"],
  "detail-type": ["OrderPlaced"],
  "detail": { "amount": [{ "numeric": [">", 100] }] }
}
```

**Use case:** scheduled cron jobs (`rate(5 minutes)` / cron expression) bhi EventBridge Scheduler se hi banate hain — Lambda ko periodically trigger karne ka standard tareeka.

---

## Part 4: CloudWatch

### Q6: CloudWatch Logs + Metrics + Alarms kaise use karte hain?
**Answer:**
```python
import boto3, time

cloudwatch = boto3.client("cloudwatch", region_name="ap-south-1")

# Custom metric publish karo (e.g., business metric — orders per minute)
cloudwatch.put_metric_data(
    Namespace="MyApp/Orders",
    MetricData=[{
        "MetricName": "OrdersPlaced",
        "Value": 1,
        "Unit": "Count",
        "Timestamp": time.time(),
    }]
)

# Alarm banao — high error rate pe SNS notify
cloudwatch.put_metric_alarm(
    AlarmName="high-5xx-errors",
    MetricName="5XXError",
    Namespace="AWS/ApiGateway",
    Statistic="Sum",
    Period=60,
    EvaluationPeriods=2,
    Threshold=10,
    ComparisonOperator="GreaterThanThreshold",
    AlarmActions=["arn:aws:sns:ap-south-1:123456789:alerts-topic"],
)
```
```bash
# Logs tail karo (production debugging)
aws logs tail /aws/lambda/my-function --follow --format short

# Logs Insights query (structured log search)
aws logs start-query \
    --log-group-name /aws/lambda/my-function \
    --start-time $(date -d '1 hour ago' +%s) --end-time $(date +%s) \
    --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20'
```

**INTERVIEW: CloudWatch alarm vs OpenTelemetry/Grafana?** CloudWatch = AWS-native, zero extra infra, good default for AWS-only stacks. OTel+Grafana ([19_opentelemetry_distributed_tracing.md](19_opentelemetry_distributed_tracing.md)) = vendor-neutral, better for multi-cloud/distributed tracing across services — most senior setups use both (CloudWatch for AWS resource metrics, OTel for app-level traces).

---

## Part 5: Secrets Manager

### Q7: Secrets Manager env vars se better kyun hai?
**Answer:**
| | Plain env vars / `.env` | Secrets Manager |
|---|---|---|
| Rotation | manual | automatic (e.g., RDS password every 30 days) |
| Access audit | none | CloudTrail logs every read |
| Encryption at rest | no (plaintext in config) | KMS-encrypted |
| Fine-grained access | no | IAM policy per-secret |

```python
import boto3, json

def get_secret(secret_name: str) -> dict:
    client = boto3.client("secretsmanager", region_name="ap-south-1")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

# App startup ke time fetch karo, cache karo — har request pe mat call karo
db_creds = get_secret("prod/myapp/db")
DATABASE_URL = f"postgresql://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}/{db_creds['dbname']}"
```

**Rotation setup:** Secrets Manager ek Lambda function trigger karta hai jo naya password generate karke DB + secret dono update karta hai — app ko sirf latest version fetch karna hota hai, zero downtime.

---

## Part 6: ECS vs EKS

### Q8: ECS aur EKS me farak kya hai? Kab kaunsa choose karo?
**Answer:**
| | ECS | EKS |
|---|---|---|
| Orchestration API | AWS proprietary (task definitions) | standard Kubernetes API |
| Learning curve | lower — simpler concepts | higher — full K8s (pods, services, ingress, CRDs) |
| Portability | AWS-only | multi-cloud (same manifests on GKE/AKS) |
| Fargate (serverless) | yes | yes |
| Ecosystem | AWS-native tools only | huge K8s ecosystem (Helm, ArgoCD, Istio) |
| Best for | AWS-only shop, simpler microservices | multi-cloud strategy, existing K8s expertise, complex networking needs |

```bash
# ECS: task definition + service (Fargate — no EC2 to manage)
aws ecs register-task-definition --cli-input-json file://task-def.json
aws ecs create-service \
    --cluster my-cluster --service-name my-api \
    --task-definition my-api:1 --desired-count 3 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-abc],securityGroups=[sg-xyz],assignPublicIp=ENABLED}"

# EKS: cluster create then kubectl as usual (see 06_kubernetes_helm.md for K8s internals)
eksctl create cluster --name my-cluster --region ap-south-1 --fargate
kubectl apply -f deployment.yaml
```

**INTERVIEW: Simple answer for "why EKS over ECS"?** "Hume already Kubernetes expertise hai / multi-cloud jaana hai / complex service-mesh chahiye" — warna ECS Fargate simpler + cheaper hai same use case ke liye. K8s deep concepts already [06_kubernetes_helm.md](06_kubernetes_helm.md) me hain, ye sirf ECS-vs-EKS decision layer hai.

---

## AWS Services Quick Reference (this file)

| Service | Use Case | Python Library |
|---|---|---|
| Lambda | serverless functions, event handlers | boto3 lambda / Mangum for FastAPI |
| API Gateway | managed HTTP entrypoint | boto3 apigatewayv2 |
| EventBridge | content-based event routing, cron scheduling | boto3 events |
| CloudWatch | logs, metrics, alarms | boto3 cloudwatch / logs |
| Secrets Manager | encrypted secrets with rotation | boto3 secretsmanager |
| ECS | AWS-native container orchestration | aws ecs CLI |
| EKS | managed Kubernetes | kubectl / eksctl |

See [04_aws_ec2_s3_rds.md](04_aws_ec2_s3_rds.md) for EC2/S3/RDS/SQS/SNS/IAM.

**Runnable practical:** [practical/22_aws_managed_services_practical.py](practical/22_aws_managed_services_practical.py) — offline demos (Lambda local invoke, EventBridge rule matching, CloudWatch alarm evaluation, secret caching). `python 22_aws_managed_services_practical.py`
