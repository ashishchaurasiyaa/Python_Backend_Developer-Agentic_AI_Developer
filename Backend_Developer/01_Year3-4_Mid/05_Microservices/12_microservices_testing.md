# Microservices Testing — Contract Testing, Chaos Engineering, Test Pyramid

## Quick Concepts

**WHAT:**
- **Test Pyramid** = Unit (most) → Integration → E2E (fewest)
- **Contract Testing** = Verify API compatibility between consumer + provider (Pact)
- **Service Virtualization** = Fake downstream services (WireMock)
- **Chaos Engineering** = Inject failures to test resilience
- **Consumer-Driven Contracts** = Consumer defines what they need from provider
- **Schema Testing** = Verify event schemas don't break consumers

**WHY microservices testing is hard:**
- Many moving parts (10+ services)
- E2E tests slow + flaky
- Each service has different language/team
- Network failures real
- Asynchronous events hard to test

**HOW testing pyramid for microservices:**

```
        ┌────────────────────┐
        │   Chaos Tests       │  Rarely (production-like env)
       │      (1-2%)          │
       ├──────────────────────┤
       │   E2E Tests          │  Few (5%)
       │  (full system)        │
      ├────────────────────────┤
      │ Contract Tests          │  Many (15%)
      │ (per consumer-provider) │
     ├──────────────────────────┤
     │ Integration Tests        │  Moderate (25%)
     │ (service + dependencies) │
    ├────────────────────────────┤
    │     Unit Tests              │ Most (55%)
    │  (function/class level)     │
    └─────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Test pyramid microservices ke liye kaise modify hota hai?

**Answer:**

**WHAT:** Classic test pyramid + contract tests + chaos tests.

**WHY:**
- Unit tests alone don't catch integration bugs
- E2E tests too slow (10+ services)
- Contract tests fill gap (verify integration without spinning up everything)

**HOW — Each level explained:**

**1. Unit Tests (most, fast)**

```python
# tests/unit/test_order_service.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_create_order_calculates_total():
    """Test pure business logic — no I/O."""
    mock_db = AsyncMock()
    mock_inventory = AsyncMock()
    mock_inventory.check_availability.return_value = True

    service = OrderService(db=mock_db, inventory=mock_inventory)

    order = await service.create_order(
        user_id=1,
        items=[
            {"product_id": 10, "quantity": 2, "unit_price": 50},
            {"product_id": 20, "quantity": 1, "unit_price": 100},
        ]
    )

    assert order.total == 200  # 2*50 + 1*100
    mock_db.save_order.assert_called_once()


# Aim: 70%+ code coverage from unit tests
# Run in < 5 seconds (entire suite)
```

**2. Integration Tests (moderate)**

```python
# tests/integration/test_order_repository.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

@pytest.fixture
async def db():
    """Real DB for integration test."""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_save_and_retrieve_order(db):
    """Test actual DB interaction."""
    repo = OrderRepository(db)

    order = Order(user_id=1, total=200, status="pending")
    saved = await repo.save(order)

    retrieved = await repo.get(saved.id)
    assert retrieved.total == 200
```

**3. Contract Tests (covered in Q2)**

**4. E2E Tests (few, slow)**

```python
# tests/e2e/test_checkout_flow.py
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_checkout_flow(api_client):
    """Test entire user journey across all services."""
    # 1. Create user
    user_resp = await api_client.post("/api/users", json={
        "email": "test@example.com",
        "password": "secret"
    })
    user_id = user_resp.json()["id"]

    # 2. Login
    auth_resp = await api_client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "secret"
    })
    token = auth_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Add to cart
    await api_client.post("/api/cart/items", json={
        "product_id": 1, "quantity": 2
    }, headers=headers)

    # 4. Checkout
    order_resp = await api_client.post("/api/checkout", headers=headers)
    order_id = order_resp.json()["order_id"]

    # 5. Verify order created
    await asyncio.sleep(2)  # Allow async events to process
    order_resp = await api_client.get(f"/api/orders/{order_id}", headers=headers)
    assert order_resp.json()["status"] == "confirmed"

# Run on staging, not on every PR
# Aim: 10-20 critical user journeys total
```

**5. Chaos Tests (rarely, ops-led)**

Covered in Q5.

---

### Q2: Contract Testing with Pact — kaise kaam karta hai?

**Answer:**

**WHAT:** Verify API compatibility between consumer (caller) and provider (callee).

**WHY:**
- ✅ Faster than E2E (no full system needed)
- ✅ Catches breaking changes early
- ✅ Consumer-driven (provider must support what consumers need)
- ✅ Reduces coordination overhead

**HOW — Pact workflow:**

```
1. Consumer team writes test:
   "When I call GET /users/1, I expect {id: 1, name: 'Alice'}"
   → Generates contract file (JSON)

2. Contract uploaded to Pact Broker (or shared file)

3. Provider team's CI:
   - Pulls contract
   - Spins up real provider
   - Replays consumer's expected calls
   - Verifies responses match contract

4. If provider changes break contract → CI fails
5. Provider team coordinates with consumer
```

**HOW — Python implementation:**

```python
# pip install pact-python

# ─── Consumer side ─────────────────────────────────────────────
# tests/contracts/test_user_service_contract.py
import pytest
from pact import Consumer, Provider, Like, EachLike

# Define contract
pact = Consumer('order-service').has_pact_with(
    Provider('user-service'),
    pact_dir='./pacts'
)

@pytest.fixture(scope='module')
def pact_mock():
    pact.start_service()
    yield pact
    pact.stop_service()


def test_get_user_contract(pact_mock):
    """Consumer expectation: GET /users/{id} returns specific shape."""

    expected_response = {
        "id": 1,
        "name": Like("Alice"),         # ⭐ Like = matches any string
        "email": Like("alice@x.com"),
        "created_at": Like("2024-01-15T10:30:00Z"),
    }

    (pact_mock
        .given('user 1 exists')
        .upon_receiving('a request for user 1')
        .with_request('GET', '/users/1')
        .will_respond_with(200, body=expected_response))

    with pact_mock:
        # Call mock provider with same code we use in production
        import httpx
        response = httpx.get(f'{pact_mock.uri}/users/1')

        assert response.status_code == 200
        user = response.json()
        assert user['id'] == 1
        # Use the data in your service
        # (this validates you actually USE the contracted fields)


# Run test → generates pacts/order-service-user-service.json
```

**HOW — Provider side verification:**

```python
# tests/contracts/test_provider_satisfies_contracts.py
from pact import Verifier

def test_user_service_satisfies_consumers():
    """
    Provider verifies it satisfies all consumer contracts.
    """
    verifier = Verifier(
        provider='user-service',
        provider_base_url='http://localhost:8000',
    )

    output, _ = verifier.verify_pacts(
        './pacts/order-service-user-service.json',
        # Or from Pact Broker:
        # broker_url='https://pact-broker.example.com',
        # provider_states_setup_url='http://localhost:8000/pact/provider-states',
    )

    assert output == 0   # Exit code 0 = success
```

**HOW — Provider state setup:**

```python
# Provider needs to set up state for each test scenario
@app.post("/pact/provider-states")
async def setup_pact_state(state: dict):
    """
    Set up DB state before contract test runs.
    """
    if state["state"] == "user 1 exists":
        await db.users.delete_all()
        await db.users.create(id=1, name="Alice", email="alice@x.com")
    elif state["state"] == "no users exist":
        await db.users.delete_all()

    return {"status": "ready"}
```

**HOW — Pact Broker (CI/CD integration):**

```bash
# Consumer CI: publish contract
pact-broker publish ./pacts \
  --consumer-app-version=1.2.0 \
  --broker-base-url=https://pact-broker.example.com

# Provider CI: verify
pact-verifier \
  --provider-app-version=2.1.0 \
  --provider-base-url=http://localhost:8000 \
  --broker-base-url=https://pact-broker.example.com \
  --publish-verification-results
```

---

### Q3: Service virtualization — WireMock / Mountebank?

**Answer:**

**WHAT:** Fake downstream services for testing.

**WHY:**
- Real services slow/unreliable in tests
- Don't want to make real API calls (cost)
- Test specific scenarios (5xx, slow response, timeout)

**HOW — WireMock (Java) for HTTP:**

```yaml
# wiremock-mappings/get_user.json
{
  "request": {
    "method": "GET",
    "urlPattern": "/users/[0-9]+"
  },
  "response": {
    "status": 200,
    "headers": {
      "Content-Type": "application/json"
    },
    "jsonBody": {
      "id": "{{request.path.[1]}}",
      "name": "Test User",
      "email": "test@example.com"
    }
  }
}
```

```bash
# Run WireMock
docker run -p 8080:8080 -v $(pwd)/wiremock-mappings:/home/wiremock/mappings \
  wiremock/wiremock:latest

# Now app uses http://wiremock:8080 instead of real service
```

**HOW — Python alternative (responses library):**

```python
import responses
import httpx
import pytest

@responses.activate
def test_get_user_with_mock():
    """Mock HTTP responses in unit tests."""
    responses.add(
        responses.GET,
        "https://user-service/users/1",
        json={"id": 1, "name": "Alice", "email": "alice@x.com"},
        status=200
    )

    # Code under test
    response = httpx.get("https://user-service/users/1")
    assert response.json()["name"] == "Alice"


@responses.activate
def test_handles_5xx():
    """Test error handling."""
    responses.add(
        responses.GET,
        "https://user-service/users/1",
        json={"error": "Internal Error"},
        status=500
    )

    # Verify code gracefully handles 5xx
    with pytest.raises(UserServiceError):
        get_user(1)


@responses.activate
def test_handles_slow_response():
    """Test timeout handling."""
    def slow_response(request):
        import time
        time.sleep(10)
        return (200, {}, '{"id": 1}')

    responses.add_callback(
        responses.GET,
        "https://user-service/users/1",
        callback=slow_response
    )

    # Code should timeout
    with pytest.raises(TimeoutError):
        get_user(1, timeout=2)
```

**HOW — VCR for record/replay:**

```python
# pip install vcrpy

import vcr

@vcr.use_cassette('cassettes/get_user.yaml')
def test_get_user_recorded():
    """First run: records real HTTP call.
    Subsequent runs: replays from cassette (no network)."""
    response = httpx.get("https://user-service/users/1")
    assert response.json()["id"] == 1
```

---

### Q4: Event-driven testing — async kaise test karein?

**Answer:**

**WHAT:** Test that services correctly produce + consume events.

**HOW — Pattern 1: Test consumer logic in isolation**

```python
# Consumer code
@event_handler("order.placed")
async def send_confirmation_email(event):
    user = await user_service.get_user(event["user_id"])
    await email_service.send(user.email, "Order Confirmed", ...)


# Test
@pytest.mark.asyncio
async def test_send_confirmation_email():
    """Test handler logic directly (no Kafka)."""
    mock_user_service = AsyncMock()
    mock_user_service.get_user.return_value = User(id=1, email="alice@x.com")

    mock_email_service = AsyncMock()

    # Inject mocks
    handler = make_handler(mock_user_service, mock_email_service)

    event = {"user_id": 1, "order_id": 100, "total": 200}
    await handler(event)

    mock_email_service.send.assert_called_once_with(
        "alice@x.com", "Order Confirmed", ANY
    )
```

**HOW — Pattern 2: Test producer correctly publishes**

```python
@pytest.mark.asyncio
async def test_order_placed_event_emitted():
    """Verify event published with correct shape."""
    mock_producer = AsyncMock()

    service = OrderService(producer=mock_producer)
    order = await service.place_order(user_id=1, items=[...])

    # Verify event published
    mock_producer.send.assert_called_once_with(
        "order.placed",
        {
            "order_id": order.id,
            "user_id": 1,
            "total": ANY,
            "timestamp": ANY,
        }
    )
```

**HOW — Pattern 3: Integration test with real Kafka (testcontainers)**

```python
# pip install testcontainers

from testcontainers.kafka import KafkaContainer
from kafka import KafkaProducer, KafkaConsumer
import json

@pytest.fixture(scope="module")
def kafka():
    """Real Kafka in Docker for integration tests."""
    with KafkaContainer() as kafka:
        yield kafka.get_bootstrap_server()


@pytest.mark.asyncio
async def test_order_event_flow_e2e(kafka):
    # Producer
    producer = KafkaProducer(
        bootstrap_servers=kafka,
        value_serializer=lambda v: json.dumps(v).encode()
    )

    # Consumer
    consumer = KafkaConsumer(
        "order.placed",
        bootstrap_servers=kafka,
        group_id="test-group",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
        consumer_timeout_ms=5000
    )

    # Produce event
    producer.send("order.placed", {"order_id": 1, "user_id": 100})
    producer.flush()

    # Verify received
    messages = list(consumer)
    assert len(messages) == 1
    assert messages[0].value["order_id"] == 1
```

**HOW — Pattern 4: Eventual consistency tests**

```python
@pytest.mark.asyncio
async def test_user_email_update_propagates():
    """Test eventual consistency."""
    # Update via primary service
    await user_service.update_email(user_id=1, new_email="new@x.com")

    # Wait for eventual consistency
    max_wait = 5  # seconds
    start = time.time()
    while time.time() - start < max_wait:
        # Check downstream service
        notif_user = await notification_service.get_user(user_id=1)
        if notif_user.email == "new@x.com":
            break
        await asyncio.sleep(0.1)
    else:
        pytest.fail("Email did not propagate within 5s")
```

---

### Q5: Chaos Engineering — Gremlin, Chaos Monkey?

**Answer:**

**WHAT:** Deliberately inject failures to test resilience.

**WHY:**
- ✅ Find weaknesses BEFORE production breaks
- ✅ Build confidence in recovery
- ✅ Document failure modes
- ✅ Netflix pioneer (Chaos Monkey)

**HOW — Principles:**

```
1. Hypothesize steady state (e.g., 99.9% requests succeed)
2. Vary real-world events (kill pod, network partition, slow DB)
3. Run experiment in production-like environment
4. Verify hypothesis or find weakness
5. Fix and repeat
```

**HOW — LitmusChaos (Kubernetes-native, free):**

```yaml
# Chaos experiment: Pod delete
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: order-service-pod-delete
spec:
  appinfo:
    appns: production
    applabel: app=order-service
    appkind: deployment
  chaosServiceAccount: litmus-admin

  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: '60'           # 60 seconds
            - name: CHAOS_INTERVAL
              value: '10'           # Kill pod every 10s
            - name: FORCE
              value: 'false'        # Graceful termination
```

**HOW — Custom Python chaos:**

```python
import asyncio
import random
import subprocess

class ChaosInjector:
    """
    INTERVIEW: Simple chaos injection for testing.
    """

    @staticmethod
    async def random_pod_kill(namespace: str, app_label: str):
        """Kill random pod every minute."""
        while True:
            await asyncio.sleep(60)

            # Get pods
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", namespace,
                 "-l", f"app={app_label}", "-o", "name"],
                capture_output=True, text=True
            )
            pods = result.stdout.strip().split("\n")

            if pods:
                victim = random.choice(pods)
                print(f"Killing {victim}")
                subprocess.run(["kubectl", "delete", "-n", namespace, victim])

    @staticmethod
    async def simulate_slow_network(latency_ms: int = 500):
        """Add latency to network (tc command)."""
        subprocess.run([
            "tc", "qdisc", "add", "dev", "eth0", "root",
            "netem", "delay", f"{latency_ms}ms"
        ])

        await asyncio.sleep(60)

        # Remove
        subprocess.run(["tc", "qdisc", "del", "dev", "eth0", "root"])

    @staticmethod
    async def cpu_stress(percentage: int = 80):
        """Stress CPU."""
        subprocess.Popen(["stress", "--cpu", "4", "--timeout", "60"])
        await asyncio.sleep(60)
```

**HOW — Chaos in CI (Toxiproxy for HTTP):**

```python
# pip install toxiproxy-python

import toxiproxy

@pytest.mark.chaos
async def test_circuit_breaker_opens_on_slow_downstream():
    """Test circuit breaker reacts to slow downstream."""
    client = toxiproxy.Toxiproxy()

    proxy = client.create(
        name="user-service",
        listen="0.0.0.0:8080",
        upstream="user-service:80"
    )

    # Inject 5s latency
    proxy.add_toxic("slow", "latency", "downstream", attributes={"latency": 5000})

    # Make calls — should trip circuit breaker after N timeouts
    for _ in range(10):
        try:
            await order_service.create_order(...)
        except CircuitBreakerOpen:
            break
    else:
        pytest.fail("Circuit breaker did not open")

    # Cleanup
    proxy.remove_toxic("slow")
```

---

### Q6: Schema testing — event schema breaking changes?

**Answer:**

**WHAT:** Verify event schema changes don't break consumers.

**HOW — Schema Registry with compatibility:**

```python
# Already covered in Kafka file — brief here

# Confluent Schema Registry checks compatibility:
# - BACKWARD: Old consumers can read new producer
# - FORWARD: New consumers can read old producer
# - FULL: Both

# Set in registry
schema_registry.update_compatibility(
    subject="order-events-value",
    level="BACKWARD"
)

# Register new schema → fails if breaking
try:
    schema_registry.register_schema(
        subject="order-events-value",
        schema=new_schema
    )
except CompatibilityError as e:
    print(f"Breaking change: {e}")
```

**HOW — Snapshot testing for messages:**

```python
# pip install syrupy

import pytest
from syrupy.assertion import SnapshotAssertion

def test_order_event_shape(snapshot: SnapshotAssertion):
    """Lock down event shape — alerts on accidental change."""
    order_service = OrderService()

    event = order_service.build_order_placed_event(
        order_id=1, user_id=100, total=200
    )

    # First run: saves snapshot
    # Future runs: fails if shape changes
    assert event == snapshot

# Snapshot file: tests/__snapshots__/test_events.ambr
# {
#   "event_type": "order.placed",
#   "version": "1.0",
#   "data": { ... }
# }
```

---

### Q7: Test data management — across services?

**Answer:**

**WHAT:** Coordinated test data across multiple services.

**HOW — Pattern 1: Per-test seed data**

```python
@pytest.fixture
async def test_user():
    """Create user in user-service for test."""
    response = await user_service_client.post("/users", json={
        "email": f"test-{uuid.uuid4()}@x.com",
        "name": "Test User"
    })
    user = response.json()
    yield user
    # Cleanup
    await user_service_client.delete(f"/users/{user['id']}")


@pytest.fixture
async def test_order(test_user):
    """Create order for test user."""
    response = await order_service_client.post("/orders", json={
        "user_id": test_user["id"],
        "items": [{"product_id": 1, "quantity": 1}]
    })
    yield response.json()
```

**HOW — Pattern 2: Shared test fixtures (factory)**

```python
# tests/factories.py
import factory
from faker import Faker

fake = Faker()

class UserFactory(factory.Factory):
    class Meta:
        model = User

    name = factory.LazyAttribute(lambda _: fake.name())
    email = factory.LazyAttribute(lambda _: fake.email())


class OrderFactory(factory.Factory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    total = factory.LazyAttribute(lambda _: fake.pydecimal(positive=True))
    status = "pending"


# Usage
def test_order_processing():
    order = OrderFactory()
    assert order.user.name
```

**HOW — Pattern 3: Test data tagging**

```python
# Mark test data clearly
TEST_PREFIX = "TEST_AUTO_"

async def create_test_user(**kwargs):
    return await user_service.create_user(
        email=f"{TEST_PREFIX}{uuid.uuid4()}@x.com",
        name=f"{TEST_PREFIX}{fake.name()}",
        **kwargs
    )


# Cleanup job
@celery.task
async def cleanup_test_data_nightly():
    """Delete leftover test data."""
    await db.users.delete_where(name__startswith=TEST_PREFIX)
```

---

### Q8: Production-like environments — kab + kaise?

**Answer:**

**WHAT:** Test environment that mirrors production.

**WHY:**
- Catch issues that only appear at scale
- Test deployments end-to-end
- Performance testing
- Pen testing

**HOW — Environment tiers:**

```
Local (Docker Compose):
- Fast feedback
- Limited fidelity
- Single dev

Dev (K8s cluster, small):
- Shared by devs
- Latest code
- Some real services

Staging (K8s, production-like):
- Mirrors prod
- Pre-release testing
- Performance tests

Production:
- Real users
- Real data
- Continuous monitoring
```

**HOW — Synthetic load testing in staging:**

```python
# Use Locust for load testing
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login
        response = self.client.post("/api/auth/login", json={
            "email": "loadtest@example.com",
            "password": "secret"
        })
        self.token = response.json()["token"]

    @task(10)
    def browse_products(self):
        self.client.get("/api/products", headers={
            "Authorization": f"Bearer {self.token}"
        })

    @task(3)
    def add_to_cart(self):
        self.client.post("/api/cart/items", headers={
            "Authorization": f"Bearer {self.token}"
        }, json={
            "product_id": random.randint(1, 100),
            "quantity": random.randint(1, 5)
        })

    @task(1)
    def checkout(self):
        self.client.post("/api/checkout", headers={
            "Authorization": f"Bearer {self.token}"
        })

# Run: locust -f loadtest.py --host=https://staging.example.com
```

---

## Microservices Testing Checklist

```markdown
### Unit Tests
- [ ] 70%+ code coverage
- [ ] Pure logic isolated (mock I/O)
- [ ] Fast (< 5s for full suite)
- [ ] Run on every commit

### Integration Tests
- [ ] Test with real DB (testcontainers)
- [ ] Test with real Redis/Kafka
- [ ] Each service has its own integration suite
- [ ] Run in CI per service

### Contract Tests
- [ ] Pact for HTTP APIs between services
- [ ] Pact Broker in CI/CD
- [ ] Consumer team creates contracts
- [ ] Provider CI verifies compatibility
- [ ] Schema Registry for events

### E2E Tests
- [ ] 10-20 critical user journeys
- [ ] Run on staging (not every PR)
- [ ] Use synthetic data
- [ ] Cleanup after tests

### Performance Tests
- [ ] Locust for load testing
- [ ] Define SLO thresholds
- [ ] Run before major releases
- [ ] Profile slow endpoints

### Chaos Tests
- [ ] LitmusChaos for K8s
- [ ] Run in production-like env
- [ ] Schedule monthly game days
- [ ] Document failure modes

### Test Data
- [ ] Per-test cleanup
- [ ] Or test data tagging + nightly cleanup
- [ ] No PII in test data
- [ ] Factories for consistent data
```

---

## Common Testing Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Only unit tests | Miss integration bugs | Add contract + integration |
| Only E2E tests | Slow, flaky | Test pyramid (unit-heavy) |
| Mocking real HTTP everywhere | Mock != reality | Contract tests |
| No event testing | Async bugs in prod | Test producer + consumer |
| Shared test data | Test interference | Per-test fixtures |
| No chaos testing | Surprises in prod | Schedule game days |
| Test only happy path | Edge cases break prod | Test error scenarios |
| No load testing | Capacity surprises | Locust before releases |
