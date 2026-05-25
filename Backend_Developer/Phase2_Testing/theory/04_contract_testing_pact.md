# Contract Testing (Pact)

> **Interview angle:** "Microservices A → B → C. B deploy karta hai, A-C break ho jata. Integration tests slow. Solution?"

---

## 1. The Microservices Testing Problem

3 services: Frontend → API → Auth.

**Unit tests:** Each service tests itself. Doesn't catch interface mismatch.
**End-to-end:** Slow, flaky, brittle, hard to maintain.
**Integration:** Spinning up all services per PR = expensive.

**Real bug:** API team renames `userId` → `user_id`. Frontend tests pass (mocked). API tests pass (own contract). **Production breaks.**

---

## 2. What is Contract Testing?

Both sides agree on a **contract**: what request looks like, what response looks like.

- **Consumer** defines what it expects
- **Provider** verifies it can satisfy
- Contract stored in shared **broker**
- Both sides test against contract independently

**Result:** Catches mismatches BEFORE production, without running full stack.

---

## 3. Pact — The Tool

**Pact** = consumer-driven contract testing framework.

### Workflow
```
1. CONSUMER writes Pact test → generates pact JSON
2. Upload pact to Pact Broker
3. PROVIDER fetches pact → runs against real API
4. If both pass: safe to deploy
```

### Pact JSON example
```json
{
  "consumer": {"name": "FrontendApp"},
  "provider": {"name": "UserAPI"},
  "interactions": [
    {
      "description": "get user by ID",
      "providerState": "user 42 exists",
      "request": {
        "method": "GET",
        "path": "/users/42"
      },
      "response": {
        "status": 200,
        "headers": {"Content-Type": "application/json"},
        "body": {"id": 42, "name": "Alice"}
      }
    }
  ]
}
```

---

## 4. Consumer Test (Python)

```bash
pip install pact-python
```

```python
import pytest
from pact import Consumer, Provider, EachLike, Like

@pytest.fixture(scope="module")
def pact():
    pact = Consumer("FrontendApp").has_pact_with(
        Provider("UserAPI"),
        host_name="localhost",
        port=1234,
    )
    pact.start_service()
    yield pact
    pact.stop_service()


def test_get_user(pact):
    # Define expected interaction
    expected = {"id": 42, "name": "Alice", "email": "a@x.com"}

    (pact
        .given("user 42 exists")                    # provider state
        .upon_receiving("a request for user 42")
        .with_request("GET", "/users/42")
        .will_respond_with(200, body=expected))

    with pact:
        # Make actual HTTP call to the mock
        import requests
        response = requests.get("http://localhost:1234/users/42")
        assert response.json() == expected
```

After this test, **pact JSON** generated in `pacts/` directory.

---

## 5. Provider Verification

API team gets the pact, verifies their service satisfies it.

```python
from pact import Verifier

verifier = Verifier(
    provider="UserAPI",
    provider_base_url="http://localhost:8000",   # real API running
)

# Run verification
exit_code, _ = verifier.verify_pacts(
    "./pacts/frontendapp-userapi.json",
    provider_states_setup_url="http://localhost:8000/_pact/provider_states",
)
assert exit_code == 0
```

### Provider state setup
API needs to set up specific state before each interaction:
```python
# /_pact/provider_states endpoint
@app.post("/_pact/provider_states")
async def setup_state(state: dict):
    if state["state"] == "user 42 exists":
        await db.execute("INSERT INTO users VALUES (42, 'Alice', 'a@x.com') ON CONFLICT DO NOTHING")
    return {"ok": True}
```

---

## 6. Pact Broker

Shared storage for contracts between teams.

```bash
docker run -d -p 9292:9292 pactfoundation/pact-broker
```

### Workflow
1. Consumer test → publishes pact to broker
2. Provider verifies → publishes verification result
3. CI checks `can-i-deploy` before deploy

```bash
# Publish pact
pact-broker publish ./pacts \
    --broker-base-url=http://broker:9292 \
    --consumer-app-version=$GIT_SHA

# Verify (provider side)
pact-broker verify --consumer-version-selectors='[{"latest":true}]'

# Check can-i-deploy
pact-broker can-i-deploy \
    --pacticipant=UserAPI \
    --version=$GIT_SHA \
    --to=production
# Exits 0 if all required consumers' pacts verified
```

---

## 7. Matchers (Flexible Matching)

Don't pin exact values — use type matchers:

```python
from pact import Like, EachLike, Term

(pact
    .upon_receiving("get user")
    .with_request("GET", "/users/42")
    .will_respond_with(200, body={
        "id": Like(42),              # any int
        "name": Like("Alice"),        # any string
        "email": Term(
            r"^.+@.+\..+$",            # regex match
            "alice@example.com",
        ),
        "tags": EachLike("tag1"),     # array of strings
        "address": Like({
            "city": "Bengaluru",
            "zip": "560001",
        }),
    }))
```

---

## 8. Provider States

Provider must set up specific scenarios before tests run.

```python
# Consumer test
(pact.given("user 42 exists")
     .upon_receiving("get user 42")
     .with_request("GET", "/users/42")
     .will_respond_with(200, body={"id": 42}))

(pact.given("user 999 does not exist")
     .upon_receiving("get user 999")
     .with_request("GET", "/users/999")
     .will_respond_with(404))
```

### Provider state handlers
```python
from fastapi import FastAPI

app = FastAPI()
PROVIDER_STATES = {}

@app.post("/_pact/provider_states")
async def setup_state(payload: dict):
    state = payload.get("state")

    if state == "user 42 exists":
        await db.execute("INSERT INTO users (id, name) VALUES (42, 'Alice')")
    elif state == "user 999 does not exist":
        await db.execute("DELETE FROM users WHERE id = 999")
    # ... other states

    return {"ok": True}
```

---

## 9. Bi-Directional Contract Testing

Pact also supports **bi-directional**:
- Consumer publishes expectation
- Provider publishes OpenAPI/Swagger
- Pact Broker compares automatically

```bash
# Provider side
pact-broker publish-provider-contract openapi.yaml \
    --provider=UserAPI \
    --provider-app-version=$GIT_SHA
```

---

## 10. CI/CD Integration

### Consumer CI
```yaml
test-consumer:
  steps:
    - run: pytest tests/contract/  # generates pact
    - run: |
        pact-broker publish ./pacts \
          --broker-base-url=${{ secrets.PACT_BROKER_URL }} \
          --consumer-app-version=${{ github.sha }} \
          --tag=${{ github.ref_name }}
```

### Provider CI
```yaml
verify-provider:
  steps:
    - run: docker-compose up -d   # start service
    - run: |
        pact-broker verify \
          --broker-base-url=${{ secrets.PACT_BROKER_URL }} \
          --consumer-version-selectors='[{"latest":true}]' \
          --publish-verification-results \
          --provider-app-version=${{ github.sha }}
```

### Deploy gate
```yaml
deploy:
  steps:
    - run: |
        pact-broker can-i-deploy \
          --pacticipant=UserAPI \
          --version=${{ github.sha }} \
          --to=production
    # Only proceeds if exit 0
```

---

## 11. Contract Testing Best Practices

### Practice 1: Consumer drives the contract
Consumer tests describe what THEY need. Provider must satisfy.

### Practice 2: Test interactions, not implementations
Verify request/response shapes. Don't replicate full API tests.

### Practice 3: Use type matchers
Don't pin exact values (timestamps, IDs). Use `Like()`, `Term()`.

### Practice 4: Version contracts
Each commit publishes a pact tagged with git SHA. Broker tracks compatibility.

### Practice 5: Provider states
Set up exact DB state before each verification.

### Practice 6: One pact per consumer-provider pair
Multiple frontends consuming same API = multiple pacts.

---

## 12. Pact vs Other Approaches

| Approach | Pros | Cons |
|---|---|---|
| **Unit tests** | Fast | Don't catch integration mismatches |
| **E2E tests** | Catch real bugs | Slow, flaky, expensive |
| **Contract (Pact)** | Catch mismatches early, no full stack | Setup overhead |
| **OpenAPI specs** | Documentation | No runtime verification |
| **gRPC proto** | Strict types | gRPC-only |

**Pact = middle ground.** Best for microservices with synchronous HTTP/JSON contracts.

---

## 13. When NOT to Use Pact

- **Monolith** (no service boundary)
- **Public API** (you don't own all consumers)
- **Asynchronous messaging** (better: schema registry like Apicurio)
- **GraphQL** (consider Apollo Studio)
- **Strongly typed RPC** (gRPC proto already does this)

---

## 14. Alternative: Schema-First

Some teams skip Pact, use OpenAPI:
- Provider publishes OpenAPI spec
- Consumer generates client code from spec
- Breaking changes detected via OpenAPI diff

**Pros:** No Pact overhead.
**Cons:** Doesn't verify provider actually implements spec correctly.

---

## 15. Common Pitfalls

### Pitfall 1: Pinning exact values
```python
body={"created_at": "2024-05-24T10:30:00Z"}   # ❌ fails on next run
body={"created_at": Term(r'\d{4}-\d{2}-\d{2}.*', "2024-05-24T10:30:00Z")}  # ✅
```

### Pitfall 2: Over-specifying response
Only test what consumer actually uses. Pact ignores extra fields.

### Pitfall 3: Provider state spaghetti
50 states with complex setup. Refactor: use scenarios.

### Pitfall 4: Forgetting to publish
Consumer test passes locally, never reaches broker. Provider unaware of new contract.

### Pitfall 5: Skipping `can-i-deploy`
Deploy provider without checking. Old consumer breaks.

---

## 16. Interview Questions

**Q1: Contract testing kya hai?**
Test interface between two services. Consumer defines expectation, provider verifies. Catches mismatches without full stack.

**Q2: Pact workflow?**
1. Consumer test generates pact JSON
2. Upload to broker
3. Provider fetches + verifies
4. CI gate via `can-i-deploy`

**Q3: Consumer-driven vs provider-driven?**
Consumer-driven (Pact default): consumer defines need. Provider implements. Better for evolving APIs.

**Q4: Pact vs E2E?**
Pact: cheap, catches API mismatch. E2E: slow but catches integration bugs Pact can't (e.g., DB constraints).

**Q5: Provider state?**
Setup data before each interaction. E.g., "user 42 exists" → insert user. State setup endpoint.

**Q6: Pact Broker?**
Shared storage for contracts. Tracks versions. Provides `can-i-deploy` API.

**Q7: When NOT to use Pact?**
Monolith, public APIs you don't control consumers of, async messaging, gRPC.

---

## 17. Best Practices

1. **Consumer-driven contracts** for evolving APIs
2. **Pact Broker** as shared source of truth
3. **Type matchers** (`Like`, `Term`) — don't pin values
4. **Provider states** for setup
5. **Per-commit pact publishing** with git SHA tag
6. **`can-i-deploy` gate** before production deploy
7. **One pact per consumer-provider pair**
8. **Don't replicate full API tests** — only contract shape
9. **Document state names** clearly
10. **Test the unhappy paths too** (404, 500, validation errors)

---

## Related
- [[01_pytest_advanced]]
- [[02_snapshot_testing]]
- [[../../Phase3_Microservices/]]
