# gRPC Testing — Unit, Integration, Load Testing, Mocking

## Quick Concepts

**WHAT:**
- **Unit tests** = test individual servicer methods in isolation (no network)
- **Integration tests** = test with real gRPC server (`grpc.aio.server()`)
- **Mock client** = fake stub for testing services that depend on gRPC
- **Load testing** = `ghz` (gRPC equivalent of Apache Bench / wrk)
- **Contract testing** = ensure .proto changes don't break clients (Buf)
- **Snapshot testing** = lock down response shape across releases

**WHY gRPC testing is different from REST:**
- Can't just use `requests` library — need gRPC stub
- Streaming methods need async iteration testing
- Auto-generated code means more setup boilerplate
- Mocking servicers vs mocking channels — different patterns

**HOW testing layers stack:**
```
┌──────────────────────────────────────────┐
│  Unit Tests (fast, no I/O)               │  ← Most tests here
├──────────────────────────────────────────┤
│  Integration Tests (real gRPC server)    │  ← Critical paths
├──────────────────────────────────────────┤
│  Contract Tests (.proto compatibility)    │  ← CI/CD gate
├──────────────────────────────────────────┤
│  Load Tests (ghz)                        │  ← Pre-release
├──────────────────────────────────────────┤
│  E2E Tests (full stack)                  │  ← Few, expensive
└──────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: gRPC servicer ka unit test kaise likhte ho?

**Answer:**

**WHAT:** Test servicer method directly, mock dependencies, no actual gRPC server.

**WHY:**
- ✅ Fast (no network setup)
- ✅ Isolates logic from gRPC plumbing
- ✅ Easy to test edge cases

**HOW — Pure unit test (no gRPC server):**

```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
import grpc
from app.servicers import UserServiceServicer
from generated import user_service_pb2

class FakeContext:
    """
    Minimal fake of grpc.aio.ServicerContext for unit tests.
    """
    def __init__(self):
        self.code = None
        self.details = None
        self.metadata = []
        self.aborted = False

    async def abort(self, code, details):
        self.code = code
        self.details = details
        self.aborted = True
        raise grpc.RpcError(details)

    def invocation_metadata(self):
        return self.metadata

    def time_remaining(self):
        return 30.0


@pytest.mark.asyncio
async def test_get_user_success():
    # Arrange — mock the DB layer
    mock_db = AsyncMock()
    mock_db.get_user.return_value = MagicMock(
        id=1, name="Alice", email="alice@example.com", role="user", is_active=True
    )
    servicer = UserServiceServicer(db=mock_db)

    request = user_service_pb2.GetUserRequest(user_id=1)
    context = FakeContext()

    # Act
    response = await servicer.GetUser(request, context)

    # Assert
    assert response.id == 1
    assert response.name == "Alice"
    mock_db.get_user.assert_awaited_once_with(1)
    assert not context.aborted


@pytest.mark.asyncio
async def test_get_user_not_found():
    mock_db = AsyncMock()
    mock_db.get_user.return_value = None  # User doesn't exist
    servicer = UserServiceServicer(db=mock_db)

    request = user_service_pb2.GetUserRequest(user_id=999)
    context = FakeContext()

    # Act & Assert
    with pytest.raises(grpc.RpcError):
        await servicer.GetUser(request, context)

    assert context.code == grpc.StatusCode.NOT_FOUND
    assert "999" in context.details


@pytest.mark.asyncio
async def test_create_user_validation_error():
    servicer = UserServiceServicer(db=AsyncMock())

    request = user_service_pb2.CreateUserRequest(name="Alice", email="")  # Empty email!
    context = FakeContext()

    with pytest.raises(grpc.RpcError):
        await servicer.CreateUser(request, context)

    assert context.code == grpc.StatusCode.INVALID_ARGUMENT
```

---

### Q2: Integration test kaise likhte ho real gRPC server ke saath?

**Answer:**

**WHAT:** Start real gRPC server in test, real client connects, real network (in-process).

**WHY:**
- ✅ Tests actual serialization/deserialization
- ✅ Tests interceptors
- ✅ Catches issues unit tests miss

**HOW — pytest fixture for gRPC server:**

```python
# tests/integration/conftest.py
import pytest_asyncio
import grpc
from generated import user_service_pb2_grpc
from app.servicers import UserServiceServicer
from app.database import AsyncSessionLocal, Base, engine

@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Fresh database per test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def grpc_server():
    """Start real gRPC server on random port."""
    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(db=AsyncSessionLocal()),
        server
    )
    port = server.add_insecure_port("[::]:0")   # ⭐ :0 = random port
    await server.start()

    yield f"localhost:{port}"

    await server.stop(grace=None)


@pytest_asyncio.fixture(scope="function")
async def grpc_stub(grpc_server):
    """Real gRPC client stub."""
    channel = grpc.aio.insecure_channel(grpc_server)
    stub = user_service_pb2_grpc.UserServiceStub(channel)
    yield stub
    await channel.close()
```

```python
# tests/integration/test_user_service_integration.py
import pytest
import grpc
from generated import user_service_pb2

@pytest.mark.asyncio
async def test_create_and_get_user(grpc_stub, test_db):
    # Create user
    create_response = await grpc_stub.CreateUser(
        user_service_pb2.CreateUserRequest(
            name="Alice", email="alice@example.com", password="secret"
        )
    )
    assert create_response.id > 0

    # Get user back
    get_response = await grpc_stub.GetUser(
        user_service_pb2.GetUserRequest(user_id=create_response.id)
    )
    assert get_response.name == "Alice"
    assert get_response.email == "alice@example.com"


@pytest.mark.asyncio
async def test_get_nonexistent_user(grpc_stub, test_db):
    with pytest.raises(grpc.RpcError) as exc_info:
        await grpc_stub.GetUser(user_service_pb2.GetUserRequest(user_id=99999))
    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_duplicate_email(grpc_stub, test_db):
    # First call succeeds
    await grpc_stub.CreateUser(
        user_service_pb2.CreateUserRequest(
            name="Alice", email="dup@example.com", password="x"
        )
    )

    # Second call fails
    with pytest.raises(grpc.RpcError) as exc_info:
        await grpc_stub.CreateUser(
            user_service_pb2.CreateUserRequest(
                name="Bob", email="dup@example.com", password="y"
            )
        )
    assert exc_info.value.code() == grpc.StatusCode.ALREADY_EXISTS
```

---

### Q3: Streaming endpoint ka test kaise likhte ho?

**Answer:**

**WHAT:** Streaming = async iterator on both sides. Need to iterate to consume.

**HOW — Server streaming:**

```python
@pytest.mark.asyncio
async def test_list_users_streaming(grpc_stub, test_db):
    # Seed data
    for i in range(5):
        await grpc_stub.CreateUser(
            user_service_pb2.CreateUserRequest(
                name=f"User{i}", email=f"user{i}@x.com", password="x"
            )
        )

    # ⭐ Consume streaming response
    received_users = []
    async for user in grpc_stub.ListUsers(
        user_service_pb2.ListUsersRequest(page_size=10)
    ):
        received_users.append(user)

    assert len(received_users) == 5
    assert all(u.email.endswith("@x.com") for u in received_users)
```

**HOW — Client streaming:**

```python
@pytest.mark.asyncio
async def test_bulk_import_streaming(grpc_stub, test_db):
    # ⭐ Send stream of requests
    async def request_generator():
        for i in range(100):
            yield user_service_pb2.CreateUserRequest(
                name=f"Bulk{i}",
                email=f"bulk{i}@x.com",
                password="secret"
            )

    response = await grpc_stub.BulkImportUsers(request_generator())
    assert response.total == 100
```

**HOW — Bidirectional streaming:**

```python
@pytest.mark.asyncio
async def test_sync_users_bidirectional(grpc_stub, test_db):
    received_responses = []

    async def request_generator():
        for i in range(3):
            yield user_service_pb2.User(id=i, name=f"User{i}")

    call = grpc_stub.SyncUsers(request_generator())

    async for response in call:
        received_responses.append(response)

    assert len(received_responses) == 3
```

**HOW — Test streaming cancellation:**

```python
@pytest.mark.asyncio
async def test_stream_cancellation(grpc_stub, test_db):
    """Verify server handles client cancellation gracefully."""

    received = 0
    try:
        async for user in grpc_stub.ListUsers(
            user_service_pb2.ListUsersRequest(page_size=1000)
        ):
            received += 1
            if received >= 3:
                # ⭐ Cancel after 3 items
                break
    except grpc.RpcError:
        pass

    assert received == 3
```

---

### Q4: gRPC client ka mock kaise karte ho (service jo dusre gRPC service ko call kare)?

**Answer:**

**WHAT:** Mock the gRPC stub when testing code that depends on it.

**WHY:**
- ✅ Test in isolation without spinning up downstream service
- ✅ Test error scenarios (downstream returns 500, timeout)
- ✅ Fast tests

**HOW — Mock the stub directly:**

```python
# app/order_service.py
class OrderServicer:
    def __init__(self, user_stub):
        self.user_stub = user_stub  # gRPC client to user service

    async def CreateOrder(self, request, context):
        # Call user service to validate user exists
        try:
            user = await self.user_stub.GetUser(
                GetUserRequest(user_id=request.user_id)
            )
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                await context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
            raise

        order = await db.create_order(request, user.id)
        return self._order_to_proto(order)
```

```python
# tests/unit/test_order_service.py
import pytest
from unittest.mock import AsyncMock
from grpc import RpcError
import grpc

@pytest.mark.asyncio
async def test_create_order_user_not_found():
    # ⭐ Mock the user_stub
    mock_user_stub = AsyncMock()

    # Simulate gRPC error
    error = grpc.aio.AioRpcError(
        code=grpc.StatusCode.NOT_FOUND,
        initial_metadata=grpc.aio.Metadata(),
        trailing_metadata=grpc.aio.Metadata(),
        details="User not found"
    )
    mock_user_stub.GetUser.side_effect = error

    servicer = OrderServicer(user_stub=mock_user_stub)
    context = FakeContext()

    with pytest.raises(grpc.RpcError):
        await servicer.CreateOrder(
            CreateOrderRequest(user_id=999, amount=100),
            context
        )

    assert context.code == grpc.StatusCode.NOT_FOUND
    mock_user_stub.GetUser.assert_awaited_once()
```

**HOW — Fake stub (more realistic than mock):**

```python
# tests/fakes/fake_user_stub.py
class FakeUserStub:
    """
    INTERVIEW: Fake stub stores state — more like real service.
    Useful when test needs multiple interactions.
    """
    def __init__(self):
        self.users = {}   # user_id → User
        self.calls = []   # Track method calls

    async def GetUser(self, request, timeout=None, metadata=None):
        self.calls.append(("GetUser", request))
        if request.user_id not in self.users:
            raise grpc.aio.AioRpcError(
                code=grpc.StatusCode.NOT_FOUND,
                details=f"User {request.user_id} not found",
                initial_metadata=None, trailing_metadata=None,
            )
        return self.users[request.user_id]

    def add_user(self, user_id, name):
        self.users[user_id] = User(id=user_id, name=name)


# Usage in test
async def test_with_fake():
    fake_user_stub = FakeUserStub()
    fake_user_stub.add_user(123, "Alice")

    servicer = OrderServicer(user_stub=fake_user_stub)
    # ... test with realistic interactions
```

---

### Q5: Load testing gRPC ke liye `ghz` tool kaise use karein?

**Answer:**

**WHAT:** `ghz` = HTTP/2 + gRPC load testing tool (like `wrk` but for gRPC).

**WHY ghz over alternatives:**
- ✅ Native gRPC support (handles HTTP/2, protobuf)
- ✅ Streaming RPC support
- ✅ Realistic load patterns
- ✅ JSON/HTML reports
- ✅ CI/CD integration

**HOW — Install + basic usage:**

```bash
# Install
brew install ghz

# Basic unary call
ghz --insecure \
  --proto ./protos/user_service.proto \
  --call userservice.UserService/GetUser \
  --data '{"user_id": 1}' \
  -n 1000 \                    # ⭐ Total requests
  -c 50 \                      # ⭐ Concurrency
  localhost:50051

# Output:
# Summary:
#   Count:        1000
#   Total:        2.34 s
#   Slowest:      125.43 ms
#   Fastest:      1.23 ms
#   Average:      45.67 ms
#   Requests/sec: 427.35
#
# Response time histogram:
#   1.234   [1]    |
#   ...
#
# Latency distribution:
#   10 %: 12.34 ms
#   25 %: 23.45 ms
#   50 %: 45.67 ms
#   75 %: 78.90 ms
#   90 %: 95.43 ms
#   95 %: 110.23 ms
#   99 %: 124.56 ms
```

**HOW — Realistic load test patterns:**

```bash
# 1. Rate-limited (constant load)
ghz --insecure --rps 100 -z 60s \   # 100 req/sec for 60 seconds
  --proto user_service.proto \
  --call userservice.UserService/GetUser \
  --data '{"user_id": 1}' \
  localhost:50051

# 2. Ramp-up load
ghz --insecure \
  --concurrency-schedule line \      # Linear ramp
  --concurrency-start 1 \
  --concurrency-end 100 \
  --concurrency-step 10 \
  --concurrency-step-duration 10s \
  -z 100s \
  ...

# 3. Variable data per request
ghz --insecure \
  --data-file requests.json \         # JSON array, randomly picks
  ...

# Example requests.json:
# [
#   {"user_id": 1},
#   {"user_id": 2},
#   {"user_id": 3}
# ]

# 4. With auth metadata
ghz --insecure \
  --metadata '{"authorization":"Bearer eyJhbGc..."}' \
  ...

# 5. TLS
ghz --cacert ca.crt \
  --cert client.crt --key client.key \
  --proto user_service.proto \
  --call userservice.UserService/GetUser \
  --data '{"user_id": 1}' \
  user-service.prod.com:443
```

**HOW — CI/CD integration:**

```yaml
# .github/workflows/load-test.yml
name: Load Test
on:
  pull_request:
    paths: ['protos/**', 'app/servicers/**']

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start service
        run: docker compose up -d
        env:
          ENV: staging

      - name: Wait for ready
        run: |
          until grpc_health_probe -addr=localhost:50051; do sleep 1; done

      - name: Install ghz
        run: |
          wget -q https://github.com/bojand/ghz/releases/download/v0.118.0/ghz-linux-x86_64.tar.gz
          tar -xzf ghz-linux-x86_64.tar.gz
          sudo mv ghz /usr/local/bin/

      - name: Run load test
        run: |
          ghz --insecure \
            --proto protos/user_service.proto \
            --call userservice.UserService/GetUser \
            --data '{"user_id": 1}' \
            -n 5000 -c 50 \
            --format json \
            --output report.json \
            localhost:50051

      - name: Check thresholds
        run: |
          P99=$(jq '.latencyDistribution[] | select(.percentage == 99) | .latency' report.json)
          P99_MS=$(echo "$P99 / 1000000" | bc -l)
          if (( $(echo "$P99_MS > 500" | bc -l) )); then
            echo "❌ p99 latency $P99_MS ms > 500ms threshold"
            exit 1
          fi
```

---

### Q6: Contract testing — .proto changes break karne se kaise rokein?

**Answer:**

**WHAT:** Verify .proto schema changes are backward compatible (don't break clients).

**WHY:**
- Mistake: rename field in .proto → all clients break
- Mistake: change field number → wire format breaks
- Solution: automated check before merge

**HOW — Use `buf` for schema linting + breaking change detection:**

```bash
# Install buf
brew install bufbuild/buf/buf

# Initialize config
buf mod init

# Create buf.yaml
cat > buf.yaml <<EOF
version: v1
name: buf.build/myorg/myapis
deps: []
lint:
  use:
    - DEFAULT
breaking:
  use:
    - FILE          # Check breaking changes per file
EOF

# Lint .proto files
buf lint
# Catches: bad field naming, package issues, etc.

# Check breaking changes vs main branch
buf breaking --against '.git#branch=main'
# Catches:
# - Field number changes
# - Field removal
# - Message type changes
# - Service method removal
```

**HOW — CI integration:**

```yaml
# .github/workflows/proto-check.yml
name: Proto Validation
on:
  pull_request:
    paths: ['protos/**']

jobs:
  buf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # Need full history for `buf breaking`

      - uses: bufbuild/buf-setup-action@v1

      - name: Lint
        run: buf lint

      - name: Check breaking changes
        run: buf breaking --against ".git#branch=main,subdir=protos"

      - name: Format check
        run: buf format --diff --exit-code
```

**Examples of breaking changes caught:**

```protobuf
// BEFORE (main branch)
message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
}

// AFTER (PR — BREAKING!)
message User {
  int32 id = 1;
  string username = 2;    // ❌ Renamed name → username
  string email = 4;       // ❌ Changed field number 3 → 4
  // Removed: string old_field = 5;  ❌ If old_field existed before
}
```

**Safe changes:**

```protobuf
// ✅ Adding new field (with new number)
message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
  string phone = 4;       // ✅ New optional field
}

// ✅ Reserving numbers when removing fields
message User {
  int32 id = 1;
  string name = 2;
  reserved 3;             // ✅ Prevents reuse of number 3
  reserved "email";       // ✅ Prevents reuse of name "email"
}
```

---

### Q7: Snapshot testing gRPC responses ke liye?

**Answer:**

**WHAT:** Lock response shape — fail test if structure changes unexpectedly.

**WHY:**
- ✅ Catches accidental API changes
- ✅ Documents expected response shape
- ✅ Easy to review (just check diff)

**HOW — pytest-snapshot:**

```python
# pip install syrupy

import pytest
from syrupy.assertion import SnapshotAssertion

@pytest.mark.asyncio
async def test_get_user_response_shape(grpc_stub, test_db, snapshot: SnapshotAssertion):
    # Create user
    user = await grpc_stub.CreateUser(
        user_service_pb2.CreateUserRequest(name="Alice", email="alice@x.com", password="x")
    )

    # Get user response
    response = await grpc_stub.GetUser(user_service_pb2.GetUserRequest(user_id=user.id))

    # Convert to dict (protobuf to dict)
    from google.protobuf.json_format import MessageToDict
    response_dict = MessageToDict(response)

    # ⭐ Compare to snapshot
    # First run: saves snapshot
    # Subsequent runs: fails if changed
    assert response_dict == snapshot
```

**Generated snapshot file:**
```python
# tests/__snapshots__/test_user_service.ambr
# serializer version: 1
# name: test_get_user_response_shape
{
    "id": 1,
    "name": "Alice",
    "email": "alice@x.com",
    "role": "user",
    "isActive": True,
    "createdAt": "2024-01-15T10:30:00Z"
}
# ---
```

To update snapshots after intentional changes:
```bash
pytest --snapshot-update
```

---

### Q8: gRPC test coverage best practices kya hain?

**Answer:**

**WHAT to test:**

| Test Type | What to Cover | How Many |
|---|---|---|
| **Unit** | Each servicer method (happy + error paths) | Many (fast) |
| **Integration** | Critical user flows end-to-end | Few-medium |
| **Contract** | All .proto changes | Auto in CI |
| **Load** | Critical endpoints under stress | Pre-release |
| **Failover** | Retry, circuit breaker, timeouts | Critical paths |

**HOW — Test pyramid for gRPC:**

```python
# 70% Unit tests (fast)
# Test: business logic, validation, error mapping
# Tools: pytest, AsyncMock, FakeContext

# 25% Integration tests (medium)
# Test: real gRPC server + client, real DB, interceptors
# Tools: pytest fixtures, testcontainers

# 5% E2E tests (slow)
# Test: full stack with real downstream services
# Tools: Docker Compose, ghz for smoke load test
```

**Critical test scenarios:**

```python
# 1. Happy path
async def test_create_user_success(): ...

# 2. Input validation
async def test_create_user_invalid_email(): ...
async def test_create_user_password_too_short(): ...

# 3. Business rules
async def test_create_user_duplicate_email(): ...
async def test_admin_can_delete_user(): ...
async def test_regular_user_cannot_delete(): ...

# 4. Edge cases
async def test_get_user_with_large_id(): ...
async def test_list_users_empty_result(): ...
async def test_list_users_pagination(): ...

# 5. Error handling
async def test_db_connection_error(): ...
async def test_downstream_service_timeout(): ...

# 6. Streaming edge cases
async def test_stream_cancellation(): ...
async def test_stream_with_empty_data(): ...

# 7. Auth
async def test_missing_token(): ...
async def test_expired_token(): ...
async def test_wrong_scope(): ...

# 8. Concurrent operations
async def test_concurrent_updates_no_race(): ...

# 9. Metadata
async def test_request_id_propagation(): ...
async def test_idempotency_key_dedup(): ...
```

---

## Testing Checklist

```markdown
### Unit Tests
- [ ] Each servicer method tested (happy path)
- [ ] Each servicer method tested (error paths)
- [ ] Validation errors return correct status codes
- [ ] Downstream service errors mapped correctly

### Integration Tests
- [ ] Real gRPC server fixture (in-process)
- [ ] Database isolation per test
- [ ] Streaming methods tested
- [ ] Interceptors tested (auth, logging)
- [ ] Reflection works

### Contract Tests
- [ ] buf lint passes
- [ ] buf breaking check in CI
- [ ] Generated code committed (for IDE support)

### Load Tests
- [ ] ghz baseline for each critical endpoint
- [ ] p99 latency thresholds defined
- [ ] CI runs load test on PRs

### Resilience Tests
- [ ] Retry behavior tested
- [ ] Circuit breaker triggers
- [ ] Timeout propagation works
- [ ] Idempotency dedup verified
```
