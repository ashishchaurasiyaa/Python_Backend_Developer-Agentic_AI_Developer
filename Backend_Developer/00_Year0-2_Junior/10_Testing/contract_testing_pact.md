# Testing — Contract Testing with Pact (Consumer-Driven Contracts)
**Testing · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **Contract testing** = verify service A and service B agree on the API contract
- **Why** = end-to-end tests are slow, brittle. Mocks lie. Contract tests catch real breaks.
- **Consumer-Driven Contracts (CDC)** = consumer defines what it needs; provider verifies it can deliver
- **Pact** = most popular CDC framework (originally Ruby, now multi-lang)
- **Pact Broker** = central server that stores + shares contracts between teams
- **Provider verification** = provider replays consumer's expectations against real implementation
- **Can-I-deploy** = CI gate — "can consumer deploy if provider X is on version Y?"

---

## The Problem Contract Testing Solves

```
WITHOUT contract tests:
─────────────────────
Consumer team writes: API will return {"orderId": 42, "total": 99.99}
Provider team changes: total → totalAmount (refactor)
Provider deploys → consumer breaks in prod
Postmortem says: "we should have communicated"

WITH contract tests:
───────────────────
Consumer test publishes contract: "I expect {'orderId': N, 'total': F}"
Provider CI verifies: "Can my code satisfy this contract?"
Provider's CI FAILS because their response is now {'totalAmount': ...}
Breaking change caught BEFORE deploy.
```

---

## Architecture

```
┌─────────────┐     1. Test runs, generates    ┌─────────────┐
│  Consumer   │ ──────── pact JSON ──────────→  │ Pact Broker │
│   Service   │                                  │  (central)  │
└─────────────┘                                  └─────────────┘
                                                       │
                                                       │ 2. Provider pulls
                                                       ↓
                                                ┌─────────────┐
                                                │  Provider   │
                                                │   Service   │
                                                │             │ 3. Replays expectations
                                                │             │    against real code
                                                └─────────────┘
                                                       │
                                                       │ 4. Pass/Fail reported
                                                       ↓
                                                ┌─────────────┐
                                                │ Pact Broker │
                                                │ (verified)  │
                                                └─────────────┘
```

---

## Interview Questions & Answers

### Q1: Pact se consumer test kaise likhte hain (Python)?

**Answer:** `pact-python` library — define expectations, generate pact file.

```bash
pip install pact-python
```

```python
# tests/test_order_consumer_contract.py
import atexit
import unittest
from pact import Consumer, Provider, Like, Term
import requests

# Initialize Pact
pact = Consumer("notification-service").has_pact_with(
    Provider("order-service"),
    host_name="localhost",
    port=1234,
    pact_dir="./pacts",
)
pact.start_service()
atexit.register(pact.stop_service)


class TestOrderServiceContract(unittest.TestCase):
    def test_get_order_returns_expected_shape(self):
        expected = {
            "orderId": Like(42),                    # any int
            "userId": Like(7),
            "total": Like(99.99),                   # any float
            "status": Term(
                r"pending|shipped|delivered",       # regex match
                "pending"                            # example
            ),
            "items": Like([
                {"productId": Like("p1"), "quantity": Like(1)}
            ]),
            "createdAt": Term(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                "2026-05-25T10:30:00"
            ),
        }

        (pact
            .given("order 42 exists for user 7")
            .upon_receiving("a request for order 42")
            .with_request("get", "/orders/42")
            .will_respond_with(200, body=expected, headers={
                "Content-Type": "application/json"
            }))

        with pact:
            # Hit the local mock that Pact spun up
            response = requests.get("http://localhost:1234/orders/42")
            assert response.status_code == 200
            data = response.json()
            assert "orderId" in data
            assert isinstance(data["orderId"], int)
            assert "status" in data

    def test_order_not_found(self):
        (pact
            .given("order 999 does not exist")
            .upon_receiving("a request for non-existent order")
            .with_request("get", "/orders/999")
            .will_respond_with(404, body={
                "error": Like("Order not found")
            }))

        with pact:
            response = requests.get("http://localhost:1234/orders/999")
            assert response.status_code == 404
```

**Output:** `pacts/notification-service-order-service.json` — the contract file.

```json
{
  "consumer": {"name": "notification-service"},
  "provider": {"name": "order-service"},
  "interactions": [
    {
      "description": "a request for order 42",
      "providerState": "order 42 exists for user 7",
      "request": {"method": "GET", "path": "/orders/42"},
      "response": {
        "status": 200,
        "headers": {"Content-Type": "application/json"},
        "body": {"orderId": 42, "userId": 7, ...},
        "matchingRules": {
          "$.body.orderId": {"match": "type"},
          "$.body.status": {"match": "regex", "regex": "pending|shipped|delivered"}
        }
      }
    }
  ]
}
```

---

### Q2: Provider verification — code-side?

**Answer:** Provider runs Pact verifier against real service.

```python
# tests/test_order_provider_contract.py
from pact import Verifier

def test_against_pact_broker():
    verifier = Verifier(
        provider="order-service",
        provider_base_url="http://localhost:8000",  # your running service
    )

    success, logs = verifier.verify_with_broker(
        broker_url="https://pact-broker.acme.com",
        broker_username="ci",
        broker_password="...",
        provider_version="1.4.2",
        provider_version_branch="main",
        publish_verification_results=True,
        consumer_version_selectors=[
            {"mainBranch": True},                       # latest from consumer main
            {"deployedOrReleased": True},               # currently in prod
            {"matchingBranch": True},                   # if PR branch exists
        ],
    )

    assert success == 0, logs
```

**Provider state setup** — Pact says "given order 42 exists" → provider must seed DB.

```python
# tests/provider_states.py
from fastapi import FastAPI

state_app = FastAPI()  # separate state-setup endpoint

@state_app.post("/_pact/provider_states")
async def setup_state(state: dict):
    name = state["state"]

    if name == "order 42 exists for user 7":
        await db.execute(
            "INSERT INTO orders (id, user_id, total, status) VALUES (42, 7, 99.99, 'pending') ON CONFLICT DO NOTHING"
        )
    elif name == "order 999 does not exist":
        await db.execute("DELETE FROM orders WHERE id = 999")
    else:
        return {"error": "Unknown state"}, 400

    return {"ok": True}
```

Run state-setup app alongside main app:
```bash
uvicorn main:app --port 8000 &
uvicorn provider_states:state_app --port 8001 &
pytest tests/test_order_provider_contract.py
```

---

### Q3: Pact Broker setup (production)?

**Answer:** Self-host with Docker, or use PactFlow (managed).

```yaml
# docker-compose.yml
version: '3'
services:
  pact-broker:
    image: pactfoundation/pact-broker
    ports: ["9292:9292"]
    depends_on: [postgres]
    environment:
      PACT_BROKER_DATABASE_URL: postgres://postgres:postgres@postgres/pact_broker
      PACT_BROKER_BASIC_AUTH_USERNAME: admin
      PACT_BROKER_BASIC_AUTH_PASSWORD: ${BROKER_PASSWORD}

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: pact_broker
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pact_data:/var/lib/postgresql/data

volumes:
  pact_data:
```

**Publish from consumer CI:**
```bash
# After running consumer tests (pact file generated)
pact-broker publish ./pacts \
  --consumer-app-version="${GIT_SHA}" \
  --branch="${GIT_BRANCH}" \
  --broker-base-url="https://pact-broker.acme.com" \
  --broker-username="ci" \
  --broker-password="${BROKER_PASS}"
```

---

### Q4: Can-I-Deploy gate in CI?

**Answer:** Ask broker: "can consumer X version Y deploy alongside provider Z?"

```bash
# In consumer's CI, before deploy
pact-broker can-i-deploy \
  --pacticipant="notification-service" \
  --version="${GIT_SHA}" \
  --to-environment="production" \
  --broker-base-url="https://pact-broker.acme.com" \
  --broker-username="ci" \
  --broker-password="${BROKER_PASS}"

# Exits 0 if safe, non-zero if any provider hasn't verified
```

**Output:**
```
Computer says yes \o/

CONSUMER                | C.VERSION | PROVIDER       | P.VERSION | SUCCESS?
notification-service    | abc123    | order-service  | def456    | true
notification-service    | abc123    | user-service   | xyz789    | true

All required verification results are published and successful.
```

**OR failing case:**
```
Computer says no ¯\_(ツ)_/¯

The verification between version abc123 of notification-service and version
def456 of order-service has not been performed.

Please make sure the provider has run its verification tests.
```

---

### Q5: FastAPI provider — full pipeline example?

**Answer:**
```python
# main.py — order-service
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    order = await fetch_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return {
        "orderId": order.id,
        "userId": order.user_id,
        "total": float(order.total),
        "status": order.status,
        "items": [{"productId": i.product_id, "quantity": i.quantity} for i in order.items],
        "createdAt": order.created_at.isoformat(),
    }
```

```python
# provider_states.py
from fastapi import FastAPI, Request
from app.db import get_session

state_app = FastAPI()

@state_app.post("/_pact/provider_states")
async def setup_state(body: dict):
    state = body.get("state")
    params = body.get("params", {})

    async with get_session() as db:
        if state == "order 42 exists for user 7":
            await db.execute(
                """
                INSERT INTO orders (id, user_id, total, status, created_at)
                VALUES (42, 7, 99.99, 'pending', NOW())
                ON CONFLICT (id) DO UPDATE SET total = 99.99
                """
            )
            await db.execute(
                "INSERT INTO order_items (order_id, product_id, quantity) VALUES (42, 'p1', 1) ON CONFLICT DO NOTHING"
            )
            await db.commit()

        elif state == "order 999 does not exist":
            await db.execute("DELETE FROM orders WHERE id = 999")
            await db.commit()

    return {"ok": True}
```

```yaml
# .github/workflows/contract-tests.yml
name: Provider Contract Verification
on:
  push:
    branches: [main]
  pull_request:

jobs:
  verify:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: alembic upgrade head

      - name: Start services
        run: |
          uvicorn main:app --port 8000 &
          uvicorn provider_states:state_app --port 8001 &
          sleep 5

      - name: Verify contracts
        env:
          PACT_BROKER_URL: ${{ secrets.PACT_BROKER_URL }}
          PACT_BROKER_USERNAME: ${{ secrets.PACT_BROKER_USERNAME }}
          PACT_BROKER_PASSWORD: ${{ secrets.PACT_BROKER_PASSWORD }}
        run: pytest tests/test_order_provider_contract.py

      - name: Can-I-Deploy check
        if: github.ref == 'refs/heads/main'
        run: |
          pact-broker can-i-deploy \
            --pacticipant="order-service" \
            --version="${{ github.sha }}" \
            --to-environment="production"
```

---

### Q6: Message contracts (Kafka, RabbitMQ) — not just HTTP?

**Answer:** Pact supports async via `MessagePact`.

```python
# Consumer test for Kafka message
from pact import MessageConsumer, Provider, Like

pact = MessageConsumer("analytics-service").has_pact_with(Provider("order-service"))

def test_order_created_event_shape():
    expected_payload = {
        "orderId": Like("uuid-123"),
        "userId": Like(7),
        "total": Like(99.99),
        "createdAt": Like("2026-05-25T10:00:00"),
    }

    (pact
        .given("an order is created")
        .expects_to_receive("an OrderCreated event")
        .with_content(expected_payload)
        .with_metadata({"content-type": "application/json"}))

    with pact:
        # Your actual message handler
        from app.consumers import handle_order_created
        # Simulate receiving the message
        handle_order_created(expected_payload)
        # Assert handler processed it correctly
```

**Provider side** publishes the event and Pact verifies the payload:
```python
def test_publishes_order_created():
    from pact import MessageProvider

    def message_producer():
        # Trigger your real producer code
        return await order_service.publish_order_created(order_id=42)

    provider = MessageProvider(
        message_providers={"an OrderCreated event": message_producer},
        provider="order-service",
        consumer="analytics-service",
        pact_dir="./pacts",
    )

    with provider:
        provider.verify_with_broker(broker_url="...")
```

---

### Q7: Contract testing vs schema validation vs integration tests?

**Answer:** Different layers, complementary.

| Approach | Catches | Misses | Speed |
|---|---|---|---|
| **JSON Schema validation** | Wrong field types in payload | Missing fields LLM/old code | Fast |
| **Contract testing (Pact)** | API contract drift between teams | Logic bugs | Fast (no real network) |
| **Integration testing** | Real network + DB issues | Cross-service contract drift | Slow |
| **E2E testing** | Whole-system bugs | Brittle, slow, expensive | Slowest |

**Pyramid in 2026:**
```
       /\
      /E2E\       few (10s)
     /─────\
    /  Int.  \    some (100s)
   /─────────\
  / Contract  \   many (1000s)
 /─────────────\
/   Unit/Prop   \ thousands
─────────────────
```

---

### Q8: Common gotchas with Pact?

**Answer:**

```python
# ❌ DON'T match exact values for dynamic fields
expected = {
    "orderId": 42,  # will break next test run
    "createdAt": "2026-05-25T10:00:00",  # timestamp drift
}

# ✅ DO use matchers
expected = {
    "orderId": Like(42),                              # any int
    "createdAt": Term(r"\d{4}-\d{2}-\d{2}T.*", "2026-05-25T10:00:00"),  # ISO format
}
```

```python
# ❌ DON'T have provider state side effects survive between tests
async def setup_state(state):
    if state == "order exists":
        await db.execute("INSERT INTO orders ...")
        # Doesn't clean up — next test sees stale data!

# ✅ DO clean up explicitly OR use transactions
async def setup_state(state):
    await db.execute("TRUNCATE orders CASCADE")  # reset
    if state == "order exists":
        await db.execute("INSERT INTO orders ...")
```

```python
# ❌ DON'T put business logic in contract tests
def test_order_total_is_correct():
    # This is unit test territory!
    assert response.json()["total"] == sum_items(items)

# ✅ DO only check structure/types
def test_order_response_shape():
    data = response.json()
    assert "total" in data
    assert isinstance(data["total"], (int, float))
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Contract too strict (exact values) | Use `Like()`, `Term()`, `EachLike()` matchers |
| Provider state leaks between tests | Cleanup before each state setup |
| Broker auth credentials in code | Use CI secrets |
| Can-I-deploy ignored in CI | Make it a required check |
| Stale contracts (consumer deprecated) | Tag with environments; broker prunes |
| Async (Kafka) contracts not tested | Use `MessagePact` / `MessageProvider` |
| Multiple consumer versions to verify | Use selectors (`mainBranch`, `deployedOrReleased`) |
| Provider can't satisfy two consumers | Document; coordinate; version API |

---

## When NOT to Use Contract Testing

- **Solo project** — overhead not worth it
- **Single consumer** — pair with provider team directly
- **Internal API rarely changing** — schema validation enough
- **Public REST API** — OpenAPI + automated client SDK is better
- **GraphQL** — schema is the contract; use GraphQL inspector instead

---

## Senior-level Checklist

- [ ] Consumer writes pact tests for each external dependency
- [ ] Pact files published to broker on every consumer build
- [ ] Provider verifies pacts on every push
- [ ] Can-I-deploy gate before production releases
- [ ] Provider state endpoints isolated from main API
- [ ] Matchers used (Like/Term/EachLike) instead of exact values
- [ ] State cleanup between tests
- [ ] Message pacts for Kafka/RabbitMQ events
- [ ] Broker auth via CI secrets
- [ ] Environment tags (`production`, `staging`) for can-i-deploy
- [ ] Documentation: which services have contracts with which

---

## Related Docs
- `01_Year3-4_Mid/05_Microservices/12_microservices_testing.md` — testing strategy
- `19_asyncapi_event_driven_spec.md` — async API specs
- `property_based_testing_hypothesis.md` — complementary testing
- `load_testing_locust_k6.md` — performance side
- `00_Year0-2_Junior/06_FastAPI/04_testing_sqlalchemy.md` — integration tests

## External References
- Pact docs: https://docs.pact.io
- pact-python: https://github.com/pact-foundation/pact-python
- PactFlow: https://pactflow.io (managed broker)
