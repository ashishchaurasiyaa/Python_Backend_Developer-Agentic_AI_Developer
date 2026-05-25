"""
============================================================
CONTRACT TESTING with PACT — Practical
============================================================
Install:
    pip install pact-python

Run broker:
    docker run -d -p 9292:9292 pactfoundation/pact-broker
"""


# ============================================================
# 1. CONSUMER TEST (Frontend → User API)
# ============================================================
CONSUMER_TEST = '''
# tests/contract/test_user_api_contract.py

import pytest
import requests
from pact import Consumer, Provider, Like, EachLike, Term

# Setup pact mock service
PACT_BROKER_URL = "http://localhost:9292"


@pytest.fixture(scope="module")
def pact():
    """Pact mock server for tests."""
    pact = Consumer("FrontendApp").has_pact_with(
        Provider("UserAPI"),
        host_name="localhost",
        port=1234,
        pact_dir="./pacts",
    )
    pact.start_service()
    yield pact
    pact.stop_service()


def test_get_user_success(pact):
    """Consumer expects GET /users/42 to return user data."""
    expected = {
        "id": Like(42),                     # any int
        "name": Like("Alice"),               # any string
        "email": Term(r'^.+@.+\..+$', "alice@example.com"),
        "tier": Term(r'^(free|pro|enterprise)$', "pro"),
        "created_at": Term(r'\d{4}-\d{2}-\d{2}.*', "2024-01-01T00:00:00Z"),
        "tags": EachLike("tag1"),            # array
    }

    (pact
        .given("user 42 exists with pro tier")
        .upon_receiving("a request for user 42")
        .with_request("GET", "/users/42",
                      headers={"Authorization": Like("Bearer xyz")})
        .will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected,
        ))

    with pact:
        # Real HTTP call — pact mock intercepts
        response = requests.get(
            "http://localhost:1234/users/42",
            headers={"Authorization": "Bearer xyz"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data


def test_get_user_not_found(pact):
    """Consumer expects 404 for non-existent user."""
    (pact
        .given("user 999 does not exist")
        .upon_receiving("a request for user 999")
        .with_request("GET", "/users/999")
        .will_respond_with(
            status=404,
            body={"error": "User not found"},
        ))

    with pact:
        response = requests.get("http://localhost:1234/users/999")
        assert response.status_code == 404


def test_create_user(pact):
    """Consumer expects POST /users to create + return user."""
    request_body = {
        "name": "Bob",
        "email": "bob@example.com",
    }
    response_body = {
        "id": Like(43),
        "name": "Bob",
        "email": "bob@example.com",
        "created_at": Term(r'\d{4}-\d{2}-\d{2}.*', "2024-05-24T10:00:00Z"),
    }

    (pact
        .given("no user with email bob@example.com")
        .upon_receiving("a request to create user Bob")
        .with_request("POST", "/users",
                      headers={"Content-Type": "application/json"},
                      body=request_body)
        .will_respond_with(status=201, body=response_body))

    with pact:
        response = requests.post(
            "http://localhost:1234/users",
            json=request_body,
        )
        assert response.status_code == 201
'''


# ============================================================
# 2. PUBLISH PACT TO BROKER
# ============================================================
PUBLISH_PACT = """
# After consumer tests pass, publish pact to broker

# Via CLI
pact-broker publish ./pacts \\
    --broker-base-url=http://broker:9292 \\
    --consumer-app-version=$GIT_SHA \\
    --tag=$BRANCH_NAME

# Or use environment variables
export PACT_BROKER_BASE_URL=http://broker:9292
export PACT_BROKER_USERNAME=admin
export PACT_BROKER_PASSWORD=secret
pact-broker publish ./pacts \\
    --consumer-app-version=$GIT_SHA \\
    --branch=$BRANCH_NAME

# Python API
from pact import Broker
broker = Broker(
    broker_base_url="http://broker:9292",
    broker_username="admin",
    broker_password="secret",
)
broker.publish_pact("./pacts/frontendapp-userapi.json",
                    consumer_version="abc123",
                    tags=["main", "v1.2.0"])
"""


# ============================================================
# 3. PROVIDER VERIFICATION (User API team)
# ============================================================
PROVIDER_VERIFICATION = '''
# tests/provider/test_provider_contracts.py

import pytest
from pact import Verifier

@pytest.fixture(scope="module", autouse=True)
def start_api(scope="module"):
    """Start the actual User API server before tests."""
    import subprocess, time
    proc = subprocess.Popen(["uvicorn", "myapp.main:app", "--port", "8000"])
    time.sleep(2)
    yield
    proc.terminate()


def test_provider_satisfies_consumer():
    """Verify our API satisfies the consumer's pact."""
    verifier = Verifier(
        provider="UserAPI",
        provider_base_url="http://localhost:8000",
    )

    # Option A: verify from broker (recommended)
    exit_code, _ = verifier.verify_with_broker(
        broker_url="http://broker:9292",
        broker_username="admin",
        broker_password="secret",
        provider_version="abc-sha-123",
        publish_verification_results=True,
        consumer_version_selectors=[
            {"latest": True, "branch": "main"},
            {"deployedOrReleased": True},   # all deployed versions
        ],
        provider_states_setup_url="http://localhost:8000/_pact/provider_states",
    )

    # Option B: verify local pact files
    # exit_code, _ = verifier.verify_pacts(
    #     "./pacts/frontendapp-userapi.json",
    #     provider_states_setup_url="http://localhost:8000/_pact/provider_states",
    # )

    assert exit_code == 0, "Provider does not satisfy consumer's contract"
'''


# ============================================================
# 4. PROVIDER STATE SETUP ENDPOINT
# ============================================================
PROVIDER_STATE_HANDLER = '''
# myapp/main.py — add provider states endpoint (PROD-DISABLED!)

import os
from fastapi import FastAPI, HTTPException

app = FastAPI()

# Provider state setup — ONLY in test environment
@app.post("/_pact/provider_states", include_in_schema=False)
async def setup_provider_state(payload: dict):
    if os.getenv("ENV") != "test":
        raise HTTPException(403, "Provider states only available in test env")

    state = payload.get("state")
    params = payload.get("params", {})

    # Set up database to match state
    if state == "user 42 exists with pro tier":
        async with db.transaction():
            await db.execute("DELETE FROM users WHERE id = 42")
            await db.execute(
                "INSERT INTO users (id, name, email, tier, created_at) "
                "VALUES (42, 'Alice', 'alice@example.com', 'pro', NOW())"
            )

    elif state == "user 999 does not exist":
        await db.execute("DELETE FROM users WHERE id = 999")

    elif state == "no user with email bob@example.com":
        await db.execute("DELETE FROM users WHERE email = 'bob@example.com'")

    elif state == "100 users exist":
        await db.execute_many(
            "INSERT INTO users (name) VALUES (:name)",
            [{"name": f"User-{i}"} for i in range(100)],
        )

    else:
        raise HTTPException(400, f"Unknown state: {state}")

    return {"ok": True, "state": state}
'''


# ============================================================
# 5. CI WORKFLOW
# ============================================================
CI_WORKFLOWS = """
# ============================================================
# CONSUMER CI (.github/workflows/consumer.yml)
# ============================================================
name: Frontend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: pip install -e ".[test]"

      # 1. Run consumer contract tests
      - name: Run consumer tests
        run: pytest tests/contract/

      # 2. Publish pact to broker
      - name: Publish pact
        run: |
          pact-broker publish ./pacts \\
            --broker-base-url=${{ secrets.PACT_BROKER_URL }} \\
            --broker-username=${{ secrets.PACT_BROKER_USERNAME }} \\
            --broker-password=${{ secrets.PACT_BROKER_PASSWORD }} \\
            --consumer-app-version=${{ github.sha }} \\
            --branch=${{ github.ref_name }}

      # 3. Check can deploy
      - name: Can-I-Deploy
        if: github.ref == 'refs/heads/main'
        run: |
          pact-broker can-i-deploy \\
            --pacticipant=FrontendApp \\
            --version=${{ github.sha }} \\
            --to-environment=production


# ============================================================
# PROVIDER CI (.github/workflows/provider.yml)
# ============================================================
name: API Tests

on:
  push:
  pact_changed:                # webhook from broker
  workflow_dispatch:

jobs:
  verify:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test }
        ports: ["5432:5432"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5

      - run: pip install -e ".[test]"

      # Start API for verification
      - name: Start API server
        run: |
          ENV=test uvicorn myapp.main:app --port 8000 &
          sleep 2

      # Verify pacts from broker
      - name: Verify contracts
        run: |
          pact-broker verify \\
            --broker-base-url=${{ secrets.PACT_BROKER_URL }} \\
            --provider=UserAPI \\
            --provider-base-url=http://localhost:8000 \\
            --provider-app-version=${{ github.sha }} \\
            --consumer-version-selectors='[{"latest": true}, {"deployedOrReleased": true}]' \\
            --provider-states-setup-url=http://localhost:8000/_pact/provider_states \\
            --publish-verification-results
"""


# ============================================================
# 6. PACT BROKER UI
# ============================================================
PACT_BROKER_SETUP = """
# docker-compose.yml — Local Pact Broker
version: '3'
services:
  broker:
    image: pactfoundation/pact-broker:latest
    ports: ["9292:9292"]
    environment:
      PACT_BROKER_DATABASE_URL: postgres://postgres:postgres@db:5432/broker
      PACT_BROKER_BASIC_AUTH_USERNAME: admin
      PACT_BROKER_BASIC_AUTH_PASSWORD: admin
      PACT_BROKER_PUBLIC_HEARTBEAT: 'true'
    depends_on: [db]

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: broker
    volumes:
      - pact-broker-db:/var/lib/postgresql/data

volumes:
  pact-broker-db:

# Open: http://localhost:9292
# Shows: Consumers, Providers, Latest Pacts, Matrix view
"""


# ============================================================
# 7. CAN-I-DEPLOY
# ============================================================
CAN_I_DEPLOY = """
# Check if it's safe to deploy
pact-broker can-i-deploy \\
    --pacticipant=UserAPI \\
    --version=abc-sha-123 \\
    --to-environment=production

# Returns:
# - exit 0: all consumers' contracts verified against this version → SAFE
# - exit 1: some consumer's contract NOT verified → UNSAFE

# Use as deploy gate:
if pact-broker can-i-deploy --pacticipant=UserAPI --version=$SHA --to=prod; then
    deploy_to_production
else
    echo "Cannot deploy — pact verification failed"
    exit 1
fi
"""


# ============================================================
# 8. MATRIX VIEW
# ============================================================
MATRIX_VIEW = """
# Pact Broker matrix shows compatibility:

         FrontendApp v1.0   v1.1   v1.2
UserAPI v2.0:     ✅       ✅     ✅
UserAPI v2.1:     ✅       ✅     ❌   (v1.2 needs new field)
UserAPI v2.2:     ✅       ✅     ✅

# Helps decide:
# - Can we deploy UserAPI v2.1 to prod where FrontendApp v1.2 runs? NO
# - Roll forward FrontendApp first, or revert UserAPI change
"""


# ============================================================
# 9. ALTERNATIVE: OPENAPI-BASED CONTRACTS
# ============================================================
OPENAPI_APPROACH = """
# Schema-first approach (lighter than Pact):

# 1. Provider publishes OpenAPI spec
@app.get("/users/{id}", response_model=UserResponse)
async def get_user(id: int):
    ...

# fastapi generates /openapi.json

# 2. Consumer generates client from spec
openapi-generator-cli generate \\
    -i http://api.example.com/openapi.json \\
    -g python \\
    -o ./generated_client

# 3. CI checks: if OpenAPI changes break consumers
openapi-diff old_openapi.json new_openapi.json
# Fails on breaking changes (removed endpoints, required → optional)

# Pros: simpler, no broker
# Cons: doesn't verify provider actually implements spec
"""


# ============================================================
# 10. WHEN TO USE PACT vs ALTERNATIVES
# ============================================================
WHEN_TO_USE = """
================================================================
DECISION TREE
================================================================

Have multiple microservices?
├── No → Don't need contract testing
└── Yes:
    ↓
    Are services HTTP/JSON?
    ├── Yes:
    │   ├── Internal services (you own all)?  → PACT
    │   ├── Public API?                       → OpenAPI + Diff
    │   └── GraphQL?                          → Apollo Studio
    └── No:
        ├── gRPC?         → proto buf compatibility
        ├── Kafka?        → Schema Registry (Apicurio / Confluent)
        └── REST + GraphQL mix? → Pact + Apollo
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CONTRACT TESTING with PACT")
    print("=" * 60)

    print("\n--- 1. CONSUMER TEST ---")
    print(CONSUMER_TEST)
    print("\n--- 2. PUBLISH PACT ---")
    print(PUBLISH_PACT)
    print("\n--- 3. PROVIDER VERIFICATION ---")
    print(PROVIDER_VERIFICATION)
    print("\n--- 4. PROVIDER STATE HANDLER ---")
    print(PROVIDER_STATE_HANDLER)
    print("\n--- 5. CI WORKFLOWS ---")
    print(CI_WORKFLOWS)
    print("\n--- 6. PACT BROKER SETUP ---")
    print(PACT_BROKER_SETUP)
    print("\n--- 7. CAN-I-DEPLOY ---")
    print(CAN_I_DEPLOY)
    print("\n--- 8. MATRIX VIEW ---")
    print(MATRIX_VIEW)
    print("\n--- 9. OPENAPI ALTERNATIVE ---")
    print(OPENAPI_APPROACH)
    print(WHEN_TO_USE)
