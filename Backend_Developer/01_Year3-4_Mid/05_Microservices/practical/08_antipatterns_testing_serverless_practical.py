"""
Phase3_Microservices — Anti-Patterns + Testing + Serverless Practical
========================================================================
Topics covered:
  1. Detecting distributed monolith
  2. Detecting Death Star architecture
  3. Identifying wrong service boundaries
  4. Contract testing with Pact pattern
  5. Service virtualization (mock downstream)
  6. Chaos engineering basics
  7. Test pyramid implementation
  8. Lambda with Mangum (FastAPI on Lambda)
  9. Step Functions workflow
  10. EventBridge event routing

Run:
  python 08_antipatterns_testing_serverless_practical.py
"""

import asyncio
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Callable

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Distributed Monolith Detection
# INTERVIEW: Common anti-pattern signals
# ─────────────────────────────────────────────────────────────────────────────

DISTRIBUTED_MONOLITH_SIGNS = {
    "deployment_coupling": "Must deploy services in specific order",
    "shared_database": "Multiple services share same DB tables",
    "synchronous_chains": "A → B → C → D → E sync calls per request",
    "test_coupling": "Change one service requires testing 5 others",
    "performance": "Latency 5x of monolith equivalent",
    "release_lockstep": "All services release together",
    "no_independent_rollback": "Can't roll back one service safely",
}


def check_distributed_monolith(service_metrics: dict) -> list:
    """
    INTERVIEW: Programmatic detection of distributed monolith.
    """
    issues = []

    # Check 1: Coupled deployments
    if service_metrics.get("deployments_with_other_services") > 0.7:
        issues.append("HIGH: >70% deployments couple with other services (distributed monolith)")

    # Check 2: Many services per request
    avg_services = service_metrics.get("avg_services_per_request", 1)
    if avg_services > 10:
        issues.append(f"HIGH: {avg_services} services per request (death star)")

    # Check 3: Sync call depth
    max_depth = service_metrics.get("max_sync_call_depth", 1)
    if max_depth > 5:
        issues.append(f"MEDIUM: Sync call depth {max_depth} (consider async)")

    # Check 4: Shared DB connections
    if service_metrics.get("services_sharing_db", 0) > 1:
        issues.append("CRITICAL: Shared database between services")

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Wrong Boundary Detection
# INTERVIEW: Signs of bad service splits
# ─────────────────────────────────────────────────────────────────────────────

WRONG_BOUNDARY_PATTERNS = {
    "split_by_layer": [
        "user-controller-service",
        "user-service-service",
        "user-dao-service",
    ],
    "split_by_crud": [
        "user-create-service",
        "user-read-service",
        "user-update-service",
        "user-delete-service",
    ],
    "split_by_data_type": [
        "string-validator-service",
        "integer-validator-service",
    ],
    "too_small": [
        "send-email-service",      # Single function as service
        "log-event-service",
    ],
    "good_examples": [
        "user-service",
        "order-service",
        "payment-service",
        "notification-service",
    ],
}


def evaluate_service_boundaries(service_names: list) -> dict:
    """
    INTERVIEW: Detect bad service boundaries.
    """
    results = {"good": [], "bad": [], "warnings": []}

    for name in service_names:
        # Check for technical layer suffixes
        if any(suffix in name for suffix in ["controller", "service-service", "dao", "repository"]):
            results["bad"].append(f"{name}: split by technical layer")

        # Check for CRUD splits
        elif any(verb in name for verb in ["-create-", "-read-", "-update-", "-delete-"]):
            results["bad"].append(f"{name}: split by CRUD operation")

        # Check for "and" in name
        elif " and " in name or "-and-" in name:
            results["warnings"].append(f"{name}: 'and' suggests too much responsibility")

        else:
            results["good"].append(name)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Contract Testing (Pact Pattern)
# INTERVIEW: Consumer-driven contracts
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PactContract:
    """
    INTERVIEW: Simulated Pact contract.
    Consumer defines what they expect, provider verifies.
    """
    consumer: str
    provider: str
    interactions: List[dict] = field(default_factory=list)

    def add_interaction(
        self,
        description: str,
        method: str,
        path: str,
        response_status: int,
        response_body: dict,
        provider_state: str = "",
    ):
        self.interactions.append({
            "description": description,
            "request": {"method": method, "path": path},
            "response": {"status": response_status, "body": response_body},
            "provider_state": provider_state,
        })

    def to_json(self) -> str:
        return json.dumps({
            "consumer": {"name": self.consumer},
            "provider": {"name": self.provider},
            "interactions": self.interactions,
        }, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Service Virtualization (Mock Downstream)
# INTERVIEW: Test in isolation without real dependencies
# ─────────────────────────────────────────────────────────────────────────────

class MockServiceRegistry:
    """
    INTERVIEW: Mock downstream services for testing.
    Like WireMock but in-process.
    """
    def __init__(self):
        self._mocks: Dict[str, dict] = {}
        self._call_history: List[dict] = []

    def setup_mock(self, service: str, method: str, path: str,
                    response: dict, status: int = 200):
        key = f"{service}:{method}:{path}"
        self._mocks[key] = {"response": response, "status": status}

    async def call(self, service: str, method: str, path: str, **kwargs) -> dict:
        # Record call
        self._call_history.append({
            "service": service, "method": method, "path": path,
            "kwargs": kwargs, "timestamp": time.time()
        })

        # Return mock
        key = f"{service}:{method}:{path}"
        mock = self._mocks.get(key)
        if not mock:
            raise Exception(f"No mock for {service}:{method}:{path}")

        if mock["status"] >= 500:
            raise Exception(f"Mock 5xx: {mock['response']}")

        return mock["response"]

    def get_calls(self, service: Optional[str] = None) -> list:
        if service:
            return [c for c in self._call_history if c["service"] == service]
        return self._call_history


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Chaos Engineering
# INTERVIEW: Inject failures, verify resilience
# ─────────────────────────────────────────────────────────────────────────────

class ChaosInjector:
    """
    INTERVIEW: Chaos engineering primitives.
    Inject failures + verify system handles gracefully.
    """
    def __init__(self):
        self.failure_rate = 0.0
        self.latency_ms = 0
        self.cascade_failure = False

    async def maybe_fail(self):
        """Randomly fail based on configured rate."""
        if random.random() < self.failure_rate:
            raise Exception("ChaosInjector: simulated failure")

    async def maybe_slow(self):
        """Add latency."""
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000)


class ResilientServiceCall:
    """
    INTERVIEW: Service call with chaos resilience patterns.
    - Retry with exponential backoff
    - Circuit breaker
    - Timeout
    - Fallback
    """
    def __init__(self, max_retries: int = 3, timeout: float = 5.0):
        self.max_retries = max_retries
        self.timeout = timeout
        self.failures = 0
        self.circuit_open_until = 0

    async def call(self, func: Callable, fallback: Optional[Callable] = None):
        # Circuit breaker check
        if time.time() < self.circuit_open_until:
            if fallback:
                return await fallback()
            raise Exception("Circuit breaker OPEN")

        for attempt in range(self.max_retries):
            try:
                # Timeout
                async with asyncio.timeout(self.timeout):
                    result = await func()
                    self.failures = 0
                    return result
            except (asyncio.TimeoutError, Exception) as e:
                self.failures += 1

                # Trip circuit after 5 consecutive failures
                if self.failures >= 5:
                    self.circuit_open_until = time.time() + 30
                    print("  ⚠️ Circuit breaker OPENED")

                # Exponential backoff
                if attempt < self.max_retries - 1:
                    backoff = 0.1 * (2 ** attempt) + random.uniform(0, 0.05)
                    await asyncio.sleep(backoff)
                    continue

                # Final fallback
                if fallback:
                    print(f"  Using fallback after {self.max_retries} retries")
                    return await fallback()
                raise

        raise Exception("Max retries exceeded")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Test Pyramid
# INTERVIEW: Right ratio of test types
# ─────────────────────────────────────────────────────────────────────────────

TEST_PYRAMID_DISTRIBUTION = {
    "Unit Tests": {
        "percentage": 65,
        "speed": "Very fast (<1ms each)",
        "scope": "Single function/class",
        "tools": "pytest, unittest, mock",
        "example": "test_calculate_total()",
    },
    "Integration Tests": {
        "percentage": 25,
        "speed": "Medium (10-100ms)",
        "scope": "Service + DB/Redis",
        "tools": "pytest + testcontainers",
        "example": "test_save_order_to_db()",
    },
    "Contract Tests": {
        "percentage": 5,
        "speed": "Medium",
        "scope": "Service A + Service B contract",
        "tools": "Pact, pact-python",
        "example": "test_order_service_satisfies_consumer()",
    },
    "E2E Tests": {
        "percentage": 5,
        "speed": "Slow (seconds)",
        "scope": "Full system",
        "tools": "pytest + real services",
        "example": "test_complete_checkout_flow()",
    },
    "Chaos Tests": {
        "percentage": "rare",
        "speed": "Variable",
        "scope": "Production-like",
        "tools": "LitmusChaos, Gremlin",
        "example": "test_system_survives_pod_failure()",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Serverless — FastAPI on Lambda
# INTERVIEW: Mangum adapter pattern
# ─────────────────────────────────────────────────────────────────────────────

MANGUM_PATTERN = """
# app/main.py
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"id": user_id, "name": "Alice"}

# ⭐ Lambda handler
handler = Mangum(app, lifespan="off")
"""

SAM_TEMPLATE = """
# template.yaml (AWS SAM)
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.12
      Handler: app.main.handler
      MemorySize: 1024
      Timeout: 30
      Architectures: [arm64]            # ⭐ 20% cheaper
      ProvisionedConcurrencyConfig:
        ProvisionedConcurrentExecutions: 5    # ⭐ Pre-warm

      Events:
        Api:
          Type: HttpApi                  # ⭐ Cheaper than REST API
          Properties:
            Path: /{proxy+}
            Method: ANY

      Layers:
        - !Ref DepsLayer                 # ⭐ Heavy deps in layer

  DepsLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: layers/deps/
      CompatibleRuntimes: [python3.12]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Step Functions Workflow
# INTERVIEW: Orchestrate Lambda functions
# ─────────────────────────────────────────────────────────────────────────────

STEP_FUNCTIONS_DEFINITION = """
{
  "Comment": "Order processing workflow",
  "StartAt": "ValidateOrder",
  "States": {
    "ValidateOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:validate-order",
      "Next": "ChargePayment",
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }],
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "OrderFailed"
      }]
    },

    "ChargePayment": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:charge-payment",
      "Next": "ReserveInventory"
    },

    "ReserveInventory": {
      "Type": "Parallel",
      "Branches": [
        {"StartAt": "ReserveWarehouseA", "States": {...}},
        {"StartAt": "ReserveWarehouseB", "States": {...}}
      ],
      "Next": "ShipOrder"
    },

    "OrderFailed": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:refund-order",
      "End": true
    }
  }
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: EventBridge — Event Routing
# INTERVIEW: Decoupled event-driven serverless
# ─────────────────────────────────────────────────────────────────────────────

EVENTBRIDGE_PRODUCER = """
import boto3
import json

events_client = boto3.client('events')

def publish_order_event(order_id: int, user_id: int, total: float):
    response = events_client.put_events(
        Entries=[{
            'Source': 'order-service',
            'DetailType': 'order.placed',
            'Detail': json.dumps({
                'order_id': order_id,
                'user_id': user_id,
                'total': total,
                'timestamp': time.time()
            }),
            'EventBusName': 'app-events'
        }]
    )
    return response['Entries'][0]['EventId']
"""

EVENTBRIDGE_RULE = """
# Multiple targets for one event
OrderPlacedRule:
  Type: AWS::Events::Rule
  Properties:
    EventBusName: app-events
    EventPattern:
      source: ["order-service"]
      detail-type: ["order.placed"]
    Targets:
      - Arn: !GetAtt SendEmailFunction.Arn
        Id: SendEmail
      - Arn: !GetAtt UpdateInventoryFunction.Arn
        Id: UpdateInventory
      - Arn: !GetAtt AnalyticsQueue.Arn
        Id: Analytics
      - Arn: !Ref OrderEventTopic
        Id: BroadcastSNS
"""

# ─────────────────────────────────────────────────────────────────────────────
# Demos
# ─────────────────────────────────────────────────────────────────────────────

def demo_distributed_monolith_detection():
    print("\n[Distributed Monolith Detection Demo]")

    # Healthy microservices metrics
    healthy_metrics = {
        "deployments_with_other_services": 0.1,
        "avg_services_per_request": 3,
        "max_sync_call_depth": 2,
        "services_sharing_db": 0,
    }

    issues = check_distributed_monolith(healthy_metrics)
    print(f"\n  Healthy metrics — {len(issues)} issues")
    for issue in issues:
        print(f"    - {issue}")

    # Unhealthy (distributed monolith)
    unhealthy_metrics = {
        "deployments_with_other_services": 0.8,    # Always deploy together
        "avg_services_per_request": 15,              # Many services per request
        "max_sync_call_depth": 7,                    # Deep sync chains
        "services_sharing_db": 3,                    # Shared DB
    }

    issues = check_distributed_monolith(unhealthy_metrics)
    print(f"\n  Unhealthy metrics — {len(issues)} issues")
    for issue in issues:
        print(f"    - {issue}")


def demo_boundary_evaluation():
    print("\n[Service Boundary Evaluation Demo]")

    bad_services = [
        "user-controller-service",
        "user-create-service",
        "user-and-order-service",
        "string-validator-service",
    ]

    good_services = [
        "user-service",
        "order-service",
        "payment-service",
        "notification-service",
    ]

    all_services = bad_services + good_services
    results = evaluate_service_boundaries(all_services)

    print(f"\n  ❌ Bad ({len(results['bad'])}):")
    for s in results["bad"]:
        print(f"    {s}")

    print(f"\n  ⚠️ Warnings ({len(results['warnings'])}):")
    for s in results["warnings"]:
        print(f"    {s}")

    print(f"\n  ✅ Good ({len(results['good'])}):")
    for s in results["good"]:
        print(f"    {s}")


def demo_pact_contract():
    print("\n[Pact Contract Demo]")

    contract = PactContract(consumer="order-service", provider="user-service")

    contract.add_interaction(
        description="get user by id",
        method="GET",
        path="/users/1",
        response_status=200,
        response_body={
            "id": 1,
            "name": "Alice",
            "email": "alice@example.com",
        },
        provider_state="user 1 exists"
    )

    contract.add_interaction(
        description="get non-existent user",
        method="GET",
        path="/users/99999",
        response_status=404,
        response_body={"error": "User not found"},
        provider_state="no users exist"
    )

    print(f"  Generated contract with {len(contract.interactions)} interactions")
    print(f"\n  Contract JSON:\n{contract.to_json()[:500]}...")


async def demo_service_virtualization():
    print("\n[Service Virtualization Demo]")

    registry = MockServiceRegistry()

    # Setup mocks
    registry.setup_mock(
        service="user-service",
        method="GET",
        path="/users/1",
        response={"id": 1, "name": "Alice"}
    )

    registry.setup_mock(
        service="payment-service",
        method="POST",
        path="/charge",
        response={"charge_id": "ch_123", "status": "success"}
    )

    # Use in test
    user = await registry.call("user-service", "GET", "/users/1")
    print(f"  Mock user: {user}")

    charge = await registry.call("payment-service", "POST", "/charge", amount=100)
    print(f"  Mock charge: {charge}")

    # Verify calls
    calls = registry.get_calls()
    print(f"  Recorded {len(calls)} calls during test")


async def demo_chaos_resilience():
    print("\n[Chaos Resilience Demo]")

    # Simulated service with chaos
    chaos = ChaosInjector()
    chaos.failure_rate = 0.7    # 70% failure
    chaos.latency_ms = 100

    call_count = 0

    async def flaky_service():
        nonlocal call_count
        call_count += 1
        await chaos.maybe_slow()
        await chaos.maybe_fail()
        return {"data": "success"}

    async def fallback():
        return {"data": "cached_fallback"}

    resilient = ResilientServiceCall(max_retries=5, timeout=2.0)

    try:
        result = await resilient.call(flaky_service, fallback)
        print(f"  Result: {result}")
        print(f"  Total attempts: {call_count}")
    except Exception as e:
        print(f"  Failed: {e}")


def demo_test_pyramid():
    print("\n[Test Pyramid Distribution]")

    for test_type, info in TEST_PYRAMID_DISTRIBUTION.items():
        pct = info["percentage"]
        speed = info["speed"]
        print(f"\n  {test_type} ({pct}% of tests):")
        print(f"    Speed: {speed}")
        print(f"    Scope: {info['scope']}")
        print(f"    Tools: {info['tools']}")


def demo_lambda_decision():
    print("\n[Lambda vs ECS Decision]")
    scenarios = [
        ("Webhook handler (Stripe, GitHub)", "✅ Lambda"),
        ("REST API, sporadic traffic", "✅ Lambda"),
        ("S3 upload trigger (image processing)", "✅ Lambda"),
        ("Cron job (daily report)", "✅ Lambda + EventBridge"),
        ("WebSocket-heavy chat", "❌ Lambda → ECS"),
        ("Long-running ML inference (>15min)", "❌ Lambda → ECS"),
        ("High RPS, steady traffic", "❌ Lambda → ECS"),
        ("Long-lived connections", "❌ Lambda → ECS"),
        ("Step Functions orchestration", "✅ Lambda"),
        ("ETL pipeline (sporadic)", "✅ Lambda + Step Functions"),
    ]
    for scenario, decision in scenarios:
        print(f"  {scenario:<45} → {decision}")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

QA = [
    ("How detect distributed monolith?",
     "Signs: services deploy together, shared DB,\n"
     "     sync chains, can't roll back independently,\n"
     "     change one = test 5 others."),

    ("Death Star architecture — fix kaise?",
     "1. Map dependency graph (Jaeger trace)\n"
     "     2. Identify hot paths\n"
     "     3. Replace sync calls with async events\n"
     "     4. Add caching at boundaries\n"
     "     5. Apply DDD bounded contexts"),

    ("When to merge services back?",
     "Always deploy together >80% of time\n"
     "     Same team owns both\n"
     "     Cascading failures (B down = A down)\n"
     "     Performance issues from network calls"),

    ("Why contract testing > E2E?",
     "Faster (no full system spin-up)\n"
     "     Earlier feedback (per-PR)\n"
     "     Consumer-driven (provider must support what consumers need)"),

    ("Chaos engineering — kab start?",
     "AFTER good observability + monitoring\n"
     "     Start in non-prod (staging)\n"
     "     Game days quarterly with team"),

    ("Test pyramid — exact ratios?",
     "Unit: 65%, Integration: 25%, Contract: 5%, E2E: 5%\n"
     "     Aim: most tests fast (unit), few comprehensive (E2E)"),

    ("Lambda cold start mitigation?",
     "1. Provisioned Concurrency (always-warm)\n"
     "     2. ARM64 (Graviton) — faster + cheaper\n"
     "     3. Smaller package (Lambda Layers)\n"
     "     4. Module-level init (reuse connections)"),

    ("Step Functions vs SQS chain?",
     "Step Functions: workflow visibility, retry/error built-in, parallel\n"
     "     SQS chain: simpler, decoupled, but no orchestration\n"
     "     Step Functions for complex workflows."),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("ANTI-PATTERNS + TESTING + SERVERLESS PRACTICAL")
    print("=" * 60)

    demo_distributed_monolith_detection()
    demo_boundary_evaluation()
    demo_pact_contract()
    await demo_service_virtualization()
    await demo_chaos_resilience()
    demo_test_pyramid()
    demo_lambda_decision()

    print("\n[Top Anti-Patterns]")
    antipatterns = [
        "Distributed Monolith (services must deploy together)",
        "Death Star (10+ sync calls per request)",
        "Shared Database (cross-service joins)",
        "Synchronous Chains (A→B→C→D)",
        "Service Sprawl (100 services, 10 engineers)",
        "Wrong Boundaries (split by tech layer, not domain)",
        "Premature Microservices (5-eng startup with 30 services)",
    ]
    for ap in antipatterns:
        print(f"  ❌ {ap}")

    print("\n[Q&A Summary]")
    for q, a in QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  tests/contracts/      → Pact contracts")
    print("  tests/integration/    → testcontainers fixtures")
    print("  tests/chaos/          → Chaos experiments")
    print("  serverless/template.yaml → AWS SAM")
    print("  serverless/handler.py → Mangum FastAPI handler")
    print("  step-functions/order.json → workflow definition")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
