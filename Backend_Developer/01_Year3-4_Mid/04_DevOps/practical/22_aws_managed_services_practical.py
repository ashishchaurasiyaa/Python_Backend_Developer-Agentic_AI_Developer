"""
Phase3_DevOps — AWS Managed Services Practical
================================================
Companion to 22_aws_managed_services.md. Covers the AWS services BEYOND
EC2/S3/RDS/SQS/SNS (those are in 02_cicd_aws_practical.py).

Topics covered:
  1. Lambda        — handler pattern, cold start, Mangum (FastAPI on Lambda)
  2. API Gateway   — REST vs HTTP API, throttling, Lambda authorizer
  3. EventBridge   — event bus, content-based routing rules, cron scheduling
  4. CloudWatch    — custom metrics, alarms, Logs Insights
  5. Secrets Manager — fetch + cache secrets, rotation model
  6. ECS vs EKS    — decision matrix, Fargate task definition

Runs OFFLINE — no AWS credentials needed. All boto3 calls are shown as code
patterns; live calls are guarded so the file executes end-to-end anywhere.

Run:
  pip install boto3            # optional (only for real calls)
  python 22_aws_managed_services_practical.py
"""

import json


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Lambda — Serverless Functions
# INTERVIEW: cold start, 15-min limit, event/context signature
# ─────────────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """A real Lambda entrypoint. event = trigger payload, context = runtime info.

    This same function shape works whether the trigger is API Gateway, SQS,
    EventBridge, or a direct invoke — only `event` structure changes.
    """
    params = event.get("queryStringParameters") or {}
    name = params.get("name", "world")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": f"Hello, {name}!"}),
    }


def demo_lambda():
    print("\n[Lambda Demo]")

    # We can actually invoke our handler locally — it's just a function.
    sample_event = {"queryStringParameters": {"name": "Ashish"}}
    result = lambda_handler(sample_event, context=None)
    print(f"  Local invoke result: {result['statusCode']} → {result['body']}")

    print("\n  Cold start — kaise minimize karo:")
    cold_start_tips = {
        "Provisioned Concurrency": "N warm instances always ready (extra cost, zero cold start)",
        "Small package":           "Lazy-import heavy deps (pandas/numpy) inside the function",
        "More memory":             "CPU scales with memory → function finishes faster",
        "SnapStart (Java)":        "Resume from pre-initialized snapshot",
    }
    for k, v in cold_start_tips.items():
        print(f"    {k:<24}: {v}")

    print("\n  FastAPI on Lambda (Mangum adapter):")
    mangum_code = """\
    from fastapi import FastAPI
    from mangum import Mangum

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    handler = Mangum(app)   # API Gateway → this handler → FastAPI routing
    """
    print(mangum_code)

    print("  INTERVIEW: Lambda kab NOT use karo?")
    print("    - Request > 15 min (hard limit)")
    print("    - Persistent WebSockets / long-lived connections → ECS/EKS")
    print("    - Steady high-throughput → containers cheaper than per-invoke")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: API Gateway
# INTERVIEW: REST API vs HTTP API, throttling, authorizer
# ─────────────────────────────────────────────────────────────────────────────

def demo_api_gateway():
    print("\n[API Gateway Demo]")

    comparison = {
        "HTTP API":  "~70% cheaper, lower latency, built for Lambda-proxy — DEFAULT choice",
        "REST API":  "More features (request transform, API keys, WAF) but costlier + slower",
    }
    for k, v in comparison.items():
        print(f"  {k:<10}: {v}")

    print("\n  Usage plan (rate limiting) — boto3 pattern:")
    throttle_code = """\
    import boto3
    apigw = boto3.client("apigateway")
    apigw.create_usage_plan(
        name="basic-plan",
        throttle={"burstLimit": 50, "rateLimit": 20},   # 20 req/s steady, 50 burst
        quota={"limit": 10000, "period": "MONTH"},
    )
    """
    print(throttle_code)

    # Simulate the request-validation layer that API Gateway does before Lambda.
    def validate_request(body: dict, schema: dict) -> list:
        """Toy version of API Gateway's JSON-schema request validation."""
        errors = []
        for field in schema.get("required", []):
            if field not in body:
                errors.append(f"missing required field: {field}")
        return errors

    order_schema = {"required": ["order_id", "amount"]}
    good = {"order_id": "123", "amount": 499}
    bad = {"order_id": "123"}
    print(f"  validate(good) → {validate_request(good, order_schema) or 'OK'}")
    print(f"  validate(bad)  → {validate_request(bad, order_schema)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: EventBridge — Event Bus + Routing
# INTERVIEW: EventBridge vs SNS, content-based routing, cron scheduling
# ─────────────────────────────────────────────────────────────────────────────

def matches_rule(event: dict, rule: dict) -> bool:
    """Mini EventBridge rule matcher — mirrors AWS event-pattern semantics.

    AWS matches an event against a rule if EVERY key in the rule pattern matches.
    Here we support: list-membership (source/detail-type) and numeric operators.
    """
    def field_matches(event_val, rule_val):
        if isinstance(rule_val, list):
            for cond in rule_val:
                if isinstance(cond, dict) and "numeric" in cond:
                    op, threshold = cond["numeric"][0], cond["numeric"][1]
                    ops = {">": event_val > threshold, "<": event_val < threshold,
                           ">=": event_val >= threshold, "<=": event_val <= threshold,
                           "=": event_val == threshold}
                    if ops.get(op):
                        return True
                elif event_val == cond:
                    return True
            return False
        return event_val == rule_val

    for key, rule_val in rule.items():
        if key == "detail":
            for dk, dv in rule_val.items():
                if not field_matches(event.get("detail", {}).get(dk), dv):
                    return False
        else:
            if not field_matches(event.get(key), rule_val):
                return False
    return True


def demo_eventbridge():
    print("\n[EventBridge Demo]")

    print("  EventBridge vs SNS:")
    print("    SNS         : simple fan-out, same msg to all subscribers (limited filtering)")
    print("    EventBridge : content-based routing rules + built-in SaaS/AWS sources")

    print("\n  put_events — boto3 pattern:")
    publish_code = """\
    import boto3, json
    eb = boto3.client("events")
    eb.put_events(Entries=[{
        "Source": "myapp.orders",
        "DetailType": "OrderPlaced",
        "Detail": json.dumps({"order_id": "123", "amount": 499}),
        "EventBusName": "default",
    }])
    """
    print(publish_code)

    # Demonstrate the routing decision locally.
    rule = {
        "source": ["myapp.orders"],
        "detail-type": ["OrderPlaced"],
        "detail": {"amount": [{"numeric": [">", 100]}]},
    }
    events = [
        {"source": "myapp.orders", "detail-type": "OrderPlaced", "detail": {"amount": 499}},
        {"source": "myapp.orders", "detail-type": "OrderPlaced", "detail": {"amount": 50}},
        {"source": "myapp.users",  "detail-type": "UserSignup",  "detail": {"amount": 999}},
    ]
    print("  Rule: source=myapp.orders AND type=OrderPlaced AND amount > 100")
    for e in events:
        routed = matches_rule(e, rule)
        print(f"    {e['source']:<14} amount={e['detail']['amount']:<4} → {'ROUTE ✓' if routed else 'skip ✗'}")

    print("\n  Cron scheduling (EventBridge Scheduler):")
    print("    rate(5 minutes)              → invoke Lambda every 5 min")
    print("    cron(0 9 * * ? *)            → every day at 09:00 UTC")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: CloudWatch — Metrics, Alarms, Logs
# INTERVIEW: custom metrics, alarm thresholds, Logs Insights
# ─────────────────────────────────────────────────────────────────────────────

def demo_cloudwatch():
    print("\n[CloudWatch Demo]")

    print("  put_metric_data — custom business metric:")
    metric_code = """\
    import boto3
    cw = boto3.client("cloudwatch")
    cw.put_metric_data(
        Namespace="MyApp/Orders",
        MetricData=[{"MetricName": "OrdersPlaced", "Value": 1, "Unit": "Count"}],
    )
    """
    print(metric_code)

    # Simulate alarm evaluation logic (Threshold + EvaluationPeriods).
    def evaluate_alarm(datapoints, threshold, eval_periods, comparison="GreaterThanThreshold"):
        """Return True (ALARM) if the last `eval_periods` datapoints all breach."""
        recent = datapoints[-eval_periods:]
        if len(recent) < eval_periods:
            return False  # INSUFFICIENT_DATA
        if comparison == "GreaterThanThreshold":
            return all(dp > threshold for dp in recent)
        return all(dp < threshold for dp in recent)

    # 5xx errors per minute over last 4 minutes; alarm if >10 for 2 consecutive.
    error_series = [2, 4, 15, 20]
    fired = evaluate_alarm(error_series, threshold=10, eval_periods=2)
    print(f"  5xx series {error_series}, threshold>10 x2 → alarm={'FIRE 🔴' if fired else 'ok'}")

    calm_series = [2, 4, 15, 3]
    fired2 = evaluate_alarm(calm_series, threshold=10, eval_periods=2)
    print(f"  5xx series {calm_series}, threshold>10 x2 → alarm={'FIRE 🔴' if fired2 else 'ok (last dp recovered)'}")

    print("\n  Logs Insights query (structured log search):")
    print("    fields @timestamp, @message")
    print("    | filter @message like /ERROR/")
    print("    | sort @timestamp desc | limit 20")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Secrets Manager
# INTERVIEW: why not plain env vars, rotation, caching
# ─────────────────────────────────────────────────────────────────────────────

_secret_cache: dict = {}


def get_secret(secret_name: str, _mock_store: dict | None = None) -> dict:
    """Fetch + cache a secret. Real version calls boto3; here a mock store is used
    so the demo runs offline. Fetch ONCE at startup — never per-request.
    """
    if secret_name in _secret_cache:
        return _secret_cache[secret_name]

    if _mock_store is not None:                 # offline demo path
        value = _mock_store[secret_name]
    else:                                       # real AWS path
        import boto3
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=secret_name)
        value = json.loads(resp["SecretString"])

    _secret_cache[secret_name] = value
    return value


def demo_secrets_manager():
    print("\n[Secrets Manager Demo]")

    print("  Env vars vs Secrets Manager:")
    rows = {
        "Rotation":            "manual        →  automatic (RDS pw every 30d)",
        "Access audit":        "none          →  CloudTrail logs every read",
        "Encryption at rest":  "plaintext     →  KMS-encrypted",
        "Fine-grained access": "no            →  IAM policy per-secret",
    }
    for k, v in rows.items():
        print(f"    {k:<20}: {v}")

    # Offline demo of fetch + cache + build DATABASE_URL.
    mock = {"prod/myapp/db": {"username": "admin", "password": "s3cr3t",
                              "host": "mydb.rds.amazonaws.com", "dbname": "myapp"}}
    creds = get_secret("prod/myapp/db", _mock_store=mock)
    db_url = f"postgresql://{creds['username']}:***@{creds['host']}/{creds['dbname']}"
    print(f"\n  Built DATABASE_URL (password masked): {db_url}")

    # Second call hits the cache — no second AWS round-trip.
    get_secret("prod/myapp/db", _mock_store=mock)
    print(f"  Cache after 2 calls: {list(_secret_cache.keys())} (1 fetch, 1 cache hit)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: ECS vs EKS
# INTERVIEW: when to pick which, Fargate serverless
# ─────────────────────────────────────────────────────────────────────────────

ECS_VS_EKS = {
    "Orchestration API": ("AWS proprietary (task definitions)", "standard Kubernetes API"),
    "Learning curve":    ("lower — simpler concepts",           "higher — full K8s"),
    "Portability":       ("AWS-only",                           "multi-cloud (GKE/AKS)"),
    "Ecosystem":         ("AWS-native tools",                   "Helm/ArgoCD/Istio"),
    "Best for":          ("AWS-only, simpler microservices",    "multi-cloud, complex networking"),
}


def demo_ecs_eks():
    print("\n[ECS vs EKS Demo]")
    print(f"  {'Dimension':<20} {'ECS':<38} EKS")
    print(f"  {'-'*20} {'-'*38} {'-'*30}")
    for dim, (ecs, eks) in ECS_VS_EKS.items():
        print(f"  {dim:<20} {ecs:<38} {eks}")

    print("\n  ECS Fargate task definition (serverless — no EC2 to manage):")
    task_def = {
        "family": "my-api",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256", "memory": "512",
        "containerDefinitions": [{
            "name": "api",
            "image": "123456789.dkr.ecr.ap-south-1.amazonaws.com/my-api:latest",
            "portMappings": [{"containerPort": 8000}],
            "logConfiguration": {"logDriver": "awslogs"},
        }],
    }
    print(json.dumps(task_def, indent=2))

    print("\n  INTERVIEW: 'Why EKS over ECS?'")
    print("    Only if: already have K8s expertise / multi-cloud / complex service mesh.")
    print("    Otherwise ECS Fargate is simpler + cheaper for the same use case.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("AWS MANAGED SERVICES PRACTICAL")
    print("(Lambda · API Gateway · EventBridge · CloudWatch ·")
    print(" Secrets Manager · ECS/EKS)")
    print("=" * 60)

    demo_lambda()
    demo_api_gateway()
    demo_eventbridge()
    demo_cloudwatch()
    demo_secrets_manager()
    demo_ecs_eks()

    print("\n" + "=" * 60)
    print("AWS INTERVIEW QUICK ANSWERS:")
    print("  Q: Lambda cold start fix?")
    print("     Provisioned Concurrency + small package + more memory.")
    print("  Q: HTTP API vs REST API?")
    print("     HTTP API cheaper/faster (default); REST API for transforms/WAF/API keys.")
    print("  Q: EventBridge vs SNS?")
    print("     EventBridge = content-based routing rules; SNS = simple fan-out.")
    print("  Q: Secrets Manager vs env vars?")
    print("     Auto-rotation + KMS encryption + CloudTrail audit + per-secret IAM.")
    print("  Q: ECS vs EKS?")
    print("     ECS = AWS-native, simpler/cheaper. EKS = portable K8s, multi-cloud.")
    print("=" * 60)


if __name__ == "__main__":
    main()
