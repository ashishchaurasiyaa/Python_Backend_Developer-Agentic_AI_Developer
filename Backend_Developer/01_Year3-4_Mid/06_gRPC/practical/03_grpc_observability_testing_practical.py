"""
Phase3_gRPC — Observability + Testing Practical
=================================================
Topics covered:
  1. OpenTelemetry tracing setup (auto + manual spans)
  2. Prometheus metrics (built-in + custom business metrics)
  3. Structured logging with request_id correlation
  4. Trace context propagation across services
  5. Unit testing servicers (with FakeContext)
  6. Integration testing with real gRPC server
  7. Streaming tests (cancellation, backpressure)
  8. Mocking gRPC clients
  9. Snapshot testing for response shapes
  10. ghz load testing patterns

Install:
  pip install opentelemetry-api opentelemetry-sdk
              opentelemetry-instrumentation-grpc
              prometheus-client py-grpc-prometheus
              structlog pytest pytest-asyncio

Run:
  python 03_grpc_observability_testing_practical.py
"""

import asyncio
import grpc
import json
import time
import uuid
from typing import Optional, AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: OpenTelemetry Setup
# INTERVIEW: One-line auto-instrumentation + manual spans
# ─────────────────────────────────────────────────────────────────────────────

OTEL_SETUP_CODE = """
# observability.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.grpc import (
    GrpcAioInstrumentorServer,
    GrpcAioInstrumentorClient,
)

def setup_tracing(service_name: str, version: str):
    # Resource = identity of this service
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "service.version": version,
        "deployment.environment": "production",
    })
    trace.set_tracer_provider(TracerProvider(resource=resource))

    # Exporter sends spans to backend (Jaeger, Tempo, X-Ray)
    exporter = OTLPSpanExporter(
        endpoint="otel-collector:4317",
        insecure=True,
    )
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(exporter)
    )

    # ⭐ Auto-instrument gRPC (server + client)
    GrpcAioInstrumentorServer().instrument()
    GrpcAioInstrumentorClient().instrument()

# Call once at startup
setup_tracing("user-service", "1.2.0")
"""

# Manual spans in business logic
MANUAL_SPAN_PATTERN = """
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class UserServiceServicer:
    async def CreateUser(self, request, context):
        # ⭐ Auto span from instrumentation:
        # "userservice.UserService/CreateUser"

        # Child span for DB operation
        with tracer.start_as_current_span("db.insert_user") as span:
            span.set_attribute("user.email", request.email)
            span.set_attribute("db.system", "postgresql")
            user = await db.create_user(...)
            span.set_attribute("user.id", user.id)

        # Another child span
        with tracer.start_as_current_span("send_welcome_email") as span:
            span.set_attribute("messaging.system", "smtp")
            await send_email(user.email)

        return user_to_proto(user)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Prometheus Metrics
# INTERVIEW: Built-in + custom business metrics
# ─────────────────────────────────────────────────────────────────────────────

PROMETHEUS_SETUP = """
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from py_grpc_prometheus.prometheus_server_interceptor import PromServerInterceptor

# ⭐ Built-in gRPC metrics via interceptor
grpc_interceptor = PromServerInterceptor(enable_handling_time_histogram=True)
# Metrics auto-created:
# - grpc_server_started_total
# - grpc_server_handled_total{grpc_code="OK|UNAVAILABLE|..."}
# - grpc_server_handling_seconds (histogram)

# ⭐ Custom business metrics
USER_CREATED = Counter(
    "users_created_total",
    "Total users created",
    ["role"]
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query latency",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

ACTIVE_STREAMS = Gauge(
    "grpc_active_streams",
    "Currently active streaming connections",
    ["service", "method"]
)

# Start Prometheus HTTP server (separate port)
start_http_server(9090)   # /metrics endpoint
"""


# Custom metrics usage in servicer
METRICS_USAGE_PATTERN = """
class UserServiceServicer:
    async def CreateUser(self, request, context):
        # ⭐ Time DB operation
        with DB_QUERY_DURATION.labels(operation="insert", table="users").time():
            user = await db.create_user(...)

        # ⭐ Count business event
        USER_CREATED.labels(role=request.role).inc()

        return user_to_proto(user)

    async def ListUsers(self, request, context):
        # ⭐ Track active streams
        ACTIVE_STREAMS.labels(service="UserService", method="ListUsers").inc()
        try:
            async for user in stream_users(request.page_size):
                yield user
        finally:
            ACTIVE_STREAMS.labels(service="UserService", method="ListUsers").dec()
"""


# Key PromQL queries
PROMQL_QUERIES = {
    "Request rate by service":
        'sum(rate(grpc_server_started_total[5m])) by (grpc_service)',

    "Error rate percentage":
        'sum(rate(grpc_server_handled_total{grpc_code!="OK"}[5m]))\n'
        '  / sum(rate(grpc_server_handled_total[5m])) * 100',

    "p99 latency per method":
        'histogram_quantile(0.99,\n'
        '  sum(rate(grpc_server_handling_seconds_bucket[5m])) by (grpc_method, le))',

    "Active streams":
        'sum(grpc_active_streams) by (service, method)',

    "Top 5 slowest methods":
        'topk(5, avg(rate(grpc_server_handling_seconds_sum[5m])\n'
        '  / rate(grpc_server_handling_seconds_count[5m])) by (grpc_method))',
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Structured Logging with Context Propagation
# INTERVIEW: request_id + trace_id in every log line
# ─────────────────────────────────────────────────────────────────────────────

# Context variables for request-scoped data (works with async)
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class SimpleStructLogger:
    """
    Simulated structlog — produces JSON output with auto-context.
    """
    def _emit(self, level, event, **kwargs):
        log_data = {
            "level": level,
            "event": event,
            "timestamp": time.time(),
            **kwargs,
        }

        # ⭐ Auto-inject context variables
        if rid := request_id_var.get():
            log_data["request_id"] = rid
        if uid := user_id_var.get():
            log_data["user_id"] = uid

        print(json.dumps(log_data))

    def info(self, event, **kwargs):
        self._emit("info", event, **kwargs)

    def error(self, event, **kwargs):
        self._emit("error", event, **kwargs)


log = SimpleStructLogger()


class LoggingInterceptor:
    """
    INTERVIEW: Server interceptor that binds request_id to context.
    All logs in handler automatically have request_id.
    """
    async def intercept(self, method_name: str, metadata: dict, handler):
        # Get or generate request_id
        request_id = metadata.get("x-request-id", str(uuid.uuid4()))

        # ⭐ Bind to context (all subsequent logs include it)
        token = request_id_var.set(request_id)

        start = time.time()
        log.info("rpc_started", method=method_name)

        try:
            response = await handler()
            duration_ms = (time.time() - start) * 1000
            log.info("rpc_completed", method=method_name, duration_ms=round(duration_ms, 2))
            return response
        except Exception as e:
            log.error("rpc_failed", method=method_name, error=str(e))
            raise
        finally:
            # ⭐ Reset context
            request_id_var.reset(token)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Trace Context Propagation
# INTERVIEW: Pass trace_id across service boundaries via metadata
# ─────────────────────────────────────────────────────────────────────────────

TRACE_PROPAGATION_CODE = """
from opentelemetry import propagate
from opentelemetry.propagators.b3 import B3MultiFormat

# Optional: use B3 propagator (Zipkin-compatible)
# propagate.set_global_textmap(B3MultiFormat())

# Server side: extract trace context from incoming metadata
class TraceServerInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)

        # ⭐ Extract trace context
        ctx = propagate.extract(metadata)
        token = context.attach(ctx)

        try:
            return await continuation(handler_call_details)
        finally:
            context.detach(token)


# Client side: inject trace context into outgoing metadata
class TraceClientInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    async def intercept_unary_unary(self, continuation, client_call_details, request):
        new_metadata = dict(client_call_details.metadata or [])

        # ⭐ Inject current trace context
        propagate.inject(new_metadata)

        new_details = grpc.aio.ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=list(new_metadata.items()),
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
        )
        return await continuation(new_details, request)
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Unit Testing — FakeContext Pattern
# INTERVIEW: Test servicer methods in isolation (no gRPC server)
# ─────────────────────────────────────────────────────────────────────────────

class FakeContext:
    """
    INTERVIEW: Minimal fake of grpc.aio.ServicerContext for unit tests.
    Avoids needing real gRPC server for unit tests.
    """
    def __init__(self, metadata=None):
        self.code = None
        self.details = None
        self.metadata = metadata or []
        self.aborted = False

    async def abort(self, code, details):
        self.code = code
        self.details = details
        self.aborted = True
        raise Exception(f"Aborted: {code} - {details}")

    def invocation_metadata(self):
        return self.metadata

    def time_remaining(self):
        return 30.0

    def cancelled(self):
        return False


# Example servicer + test
class ExampleUserServicer:
    """Example servicer (would be auto-generated from .proto)."""
    def __init__(self, db):
        self.db = db

    async def GetUser(self, request, context):
        user = await self.db.get_user(request.user_id)
        if not user:
            await context.abort("NOT_FOUND", f"User {request.user_id} not found")
        return user

    async def CreateUser(self, request, context):
        if not request.get("email"):
            await context.abort("INVALID_ARGUMENT", "Email required")

        # Check duplicate
        if await self.db.email_exists(request["email"]):
            await context.abort("ALREADY_EXISTS", f"Email {request['email']} exists")

        return await self.db.create_user(request)


class FakeDB:
    """Test double for DB."""
    def __init__(self):
        self.users = {}
        self.next_id = 1

    async def get_user(self, user_id):
        return self.users.get(user_id)

    async def email_exists(self, email):
        return any(u["email"] == email for u in self.users.values())

    async def create_user(self, data):
        user = {"id": self.next_id, **data}
        self.users[self.next_id] = user
        self.next_id += 1
        return user


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Integration Testing Pattern
# INTERVIEW: Real gRPC server, test full request/response cycle
# ─────────────────────────────────────────────────────────────────────────────

INTEGRATION_TEST_FIXTURES = """
# tests/integration/conftest.py
import pytest_asyncio
import grpc
from app.servicers import UserServiceServicer
from generated import user_service_pb2_grpc

@pytest_asyncio.fixture
async def grpc_server():
    \"\"\"Real gRPC server on random port (in-process).\"\"\"
    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(),
        server
    )
    port = server.add_insecure_port("[::]:0")   # ⭐ :0 = random port
    await server.start()

    yield f"localhost:{port}"

    await server.stop(grace=None)


@pytest_asyncio.fixture
async def grpc_stub(grpc_server):
    \"\"\"Real gRPC client stub.\"\"\"
    channel = grpc.aio.insecure_channel(grpc_server)
    stub = user_service_pb2_grpc.UserServiceStub(channel)
    yield stub
    await channel.close()


# tests/integration/test_user_service.py
import pytest
import grpc
from generated import user_service_pb2

@pytest.mark.asyncio
async def test_create_and_get_user(grpc_stub):
    # Create
    user = await grpc_stub.CreateUser(
        user_service_pb2.CreateUserRequest(
            name="Alice", email="alice@x.com", password="secret"
        )
    )
    assert user.id > 0

    # Get back
    fetched = await grpc_stub.GetUser(
        user_service_pb2.GetUserRequest(user_id=user.id)
    )
    assert fetched.email == "alice@x.com"


@pytest.mark.asyncio
async def test_get_nonexistent_user(grpc_stub):
    with pytest.raises(grpc.RpcError) as exc_info:
        await grpc_stub.GetUser(
            user_service_pb2.GetUserRequest(user_id=99999)
        )
    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Streaming Tests
# INTERVIEW: Test server streaming, cancellation, large streams
# ─────────────────────────────────────────────────────────────────────────────

STREAMING_TEST_PATTERNS = """
# tests/integration/test_streaming.py

@pytest.mark.asyncio
async def test_server_streaming(grpc_stub):
    \"\"\"Consume entire stream, verify count.\"\"\"
    results = []
    async for user in grpc_stub.ListUsers(ListUsersRequest(page_size=5)):
        results.append(user)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_stream_cancellation(grpc_stub):
    \"\"\"Cancel after N items.\"\"\"
    received = 0
    async for user in grpc_stub.ListUsers(ListUsersRequest(page_size=1000)):
        received += 1
        if received >= 3:
            break  # ⭐ Cancels stream
    assert received == 3


@pytest.mark.asyncio
async def test_client_streaming(grpc_stub):
    \"\"\"Send stream of requests, verify single response.\"\"\"
    async def request_gen():
        for i in range(100):
            yield CreateUserRequest(name=f"Bulk{i}", email=f"bulk{i}@x.com")

    response = await grpc_stub.BulkImportUsers(request_gen())
    assert response.total == 100


@pytest.mark.asyncio
async def test_bidirectional_streaming(grpc_stub):
    \"\"\"Both sides stream messages.\"\"\"
    async def request_gen():
        for i in range(3):
            yield User(id=i, name=f"User{i}")

    received = []
    async for response in grpc_stub.SyncUsers(request_gen()):
        received.append(response)

    assert len(received) >= 3


@pytest.mark.asyncio
async def test_stream_timeout(grpc_stub):
    \"\"\"Stream with timeout cancellation.\"\"\"
    with pytest.raises(grpc.RpcError) as exc_info:
        async with asyncio.timeout(2):
            async for _ in grpc_stub.LongStream(LongRequest()):
                pass
    assert exc_info.value.code() == grpc.StatusCode.CANCELLED
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Mocking gRPC Clients (when testing services that call others)
# ─────────────────────────────────────────────────────────────────────────────

MOCK_CLIENT_PATTERNS = """
# Service depends on another gRPC client
class OrderServicer:
    def __init__(self, user_stub):
        self.user_stub = user_stub

    async def CreateOrder(self, request, context):
        user = await self.user_stub.GetUser(GetUserRequest(user_id=request.user_id))
        if not user:
            await context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
        # ... create order


# tests/unit/test_order_service.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_create_order_user_not_found():
    # ⭐ Mock the stub
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

    with pytest.raises(Exception):
        await servicer.CreateOrder(
            CreateOrderRequest(user_id=999, amount=100),
            context
        )

    assert context.code == grpc.StatusCode.NOT_FOUND
    mock_user_stub.GetUser.assert_awaited_once()


# OR use Fake (more realistic than Mock)
class FakeUserStub:
    \"\"\"Stateful fake — better for complex test scenarios.\"\"\"
    def __init__(self):
        self.users = {}
        self.calls = []

    async def GetUser(self, request, timeout=None, metadata=None):
        self.calls.append(("GetUser", request))
        if request.user_id not in self.users:
            raise grpc.aio.AioRpcError(
                code=grpc.StatusCode.NOT_FOUND,
                details=f"User {request.user_id} not found",
                initial_metadata=None,
                trailing_metadata=None,
            )
        return self.users[request.user_id]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: ghz Load Testing
# INTERVIEW: Load test gRPC services (Apache Bench equivalent)
# ─────────────────────────────────────────────────────────────────────────────

GHZ_COMMANDS = """
# Install ghz
brew install ghz

# 1. Basic unary load test
ghz --insecure \\
    --proto ./protos/user_service.proto \\
    --call userservice.UserService/GetUser \\
    --data '{"user_id": 1}' \\
    -n 1000 \\         # Total requests
    -c 50 \\           # Concurrency
    localhost:50051

# Output includes:
# - Average, fastest, slowest
# - p10, p25, p50, p75, p90, p95, p99 latency
# - Response time histogram
# - Status code distribution

# 2. Rate-limited (constant RPS)
ghz --insecure --rps 100 -z 60s \\   # 100 req/sec for 60s
    --proto user_service.proto \\
    --call userservice.UserService/GetUser \\
    --data '{"user_id": 1}' \\
    localhost:50051

# 3. Ramp-up load
ghz --insecure \\
    --concurrency-schedule line \\    # Linear ramp
    --concurrency-start 1 \\
    --concurrency-end 100 \\
    --concurrency-step 10 \\
    --concurrency-step-duration 10s \\
    -z 100s ...

# 4. Random data from file
ghz --insecure \\
    --data-file requests.json \\      # JSON array, picks randomly
    ...

# 5. With auth metadata
ghz --insecure \\
    --metadata '{"authorization":"Bearer TOKEN"}' \\
    ...

# 6. JSON output for CI
ghz --insecure \\
    --format json \\
    --output report.json \\
    -n 5000 -c 50 \\
    ...

# 7. CI threshold check (using jq)
P99=$(jq '.latencyDistribution[] | select(.percentage == 99) | .latency' report.json)
P99_MS=$(echo "$P99 / 1000000" | bc -l)
if (( $(echo "$P99_MS > 500" | bc -l) )); then
    echo "❌ p99 ${P99_MS}ms > 500ms threshold"
    exit 1
fi
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Demo Functions
# ─────────────────────────────────────────────────────────────────────────────

async def demo_request_id_propagation():
    print("\n[Request ID Propagation Demo]")

    interceptor = LoggingInterceptor()

    async def handle_request():
        log.info("processing_user_data", user_count=42)
        await asyncio.sleep(0.01)
        log.info("data_processed", result="success")
        return {"status": "ok"}

    # Simulate request with metadata
    metadata = {"x-request-id": str(uuid.uuid4())[:8]}
    result = await interceptor.intercept("/UserService/GetUser", metadata, handle_request)
    print(f"\n  Result: {result}")


async def demo_unit_test():
    print("\n[Unit Test Demo (FakeContext)]")

    db = FakeDB()
    servicer = ExampleUserServicer(db)

    # Test 1: Create user (success)
    context1 = FakeContext()
    user = await servicer.CreateUser(
        {"name": "Alice", "email": "alice@example.com"},
        context1
    )
    print(f"  ✅ Created user: {user}")

    # Test 2: Duplicate email (error)
    context2 = FakeContext()
    try:
        await servicer.CreateUser(
            {"name": "Bob", "email": "alice@example.com"},
            context2
        )
    except Exception:
        print(f"  ✅ Correctly rejected duplicate: {context2.code} - {context2.details}")

    # Test 3: Get non-existent user
    context3 = FakeContext()
    try:
        await servicer.GetUser(type("Req", (), {"user_id": 99999})(), context3)
    except Exception:
        print(f"  ✅ Correctly returned NOT_FOUND: {context3.code} - {context3.details}")


def demo_metrics_examples():
    print("\n[Prometheus Metrics Examples]")
    print("  Built-in (via PromServerInterceptor):")
    print("    - grpc_server_started_total")
    print("    - grpc_server_handled_total{grpc_code=...}")
    print("    - grpc_server_handling_seconds_bucket")
    print("\n  Custom business metrics:")
    print("    - users_created_total{role=...}")
    print("    - db_query_duration_seconds{operation, table}")
    print("    - grpc_active_streams{service, method}")

    print("\n  Key PromQL queries:")
    for name, query in list(PROMQL_QUERIES.items())[:3]:
        print(f"\n  {name}:")
        for line in query.split("\n"):
            print(f"    {line}")


def demo_test_pyramid():
    print("\n[Test Pyramid for gRPC]")
    print("""
     ┌─────────────────┐
     │   E2E (5%)      │  ← Full stack, slow, few
     │  - Docker compose
     ├─────────────────┤
     │ Load Tests (5%) │  ← ghz, pre-release
     ├─────────────────┤
     │ Integration     │  ← Real gRPC server
     │   (25%)         │     in-process
     ├─────────────────┤
     │  Unit (65%)     │  ← Fast, isolated
     │                 │     FakeContext, mocks
     └─────────────────┘
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

OBSERVABILITY_QA = [
    ("What are the 3 pillars of observability?",
     "Metrics: aggregated numbers (rate, latency) - Prometheus\n"
     "     Logs: discrete events (request_id, error) - structlog\n"
     "     Traces: request flow across services - OpenTelemetry"),

    ("How does trace context propagate across gRPC services?",
     "OpenTelemetry uses gRPC metadata to inject/extract trace context.\n"
     "     traceparent header carries trace_id + span_id.\n"
     "     Auto-instrumentation handles propagation transparently."),

    ("Why structured logs over plain text?",
     "Searchable (CloudWatch Insights, Loki, Datadog).\n"
     "     Auto-indexed fields (user_id, request_id, error_code).\n"
     "     Correlation with metrics + traces via shared IDs."),

    ("What is gRPC Reflection? Security concern?",
     "Reflection API exposes service definitions at runtime.\n"
     "     Useful: grpcurl, Postman without .proto file.\n"
     "     Security: disable in production OR require admin auth."),

    ("How to test gRPC servicer in isolation?",
     "Use FakeContext class implementing minimal ServicerContext interface.\n"
     "     No real gRPC server needed — fast unit tests.\n"
     "     Mock the DB/external dependencies."),

    ("How to test streaming RPCs?",
     "Server streaming: async for + collect results.\n"
     "     Client streaming: async generator → single response.\n"
     "     Test cancellation: break out of async for after N items."),

    ("ghz vs other load testing tools?",
     "ghz: Native gRPC, supports HTTP/2 + protobuf.\n"
     "     wrk/ab: HTTP only — won't work for gRPC.\n"
     "     Apache JMeter: heavier, supports gRPC plugin."),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("gRPC OBSERVABILITY + TESTING PRACTICAL")
    print("=" * 60)

    print("\n[1] Observability Stack:")
    stack = {
        "Metrics":    "Prometheus + Grafana (via py-grpc-prometheus)",
        "Logs":       "structlog (JSON) → CloudWatch / Loki",
        "Traces":     "OpenTelemetry → Jaeger / Tempo / X-Ray",
        "Errors":     "Sentry with release tagging",
        "Debug Tools": "grpcurl + reflection + channelz",
    }
    for k, v in stack.items():
        print(f"  {k:<10}: {v}")

    await demo_request_id_propagation()
    await demo_unit_test()
    demo_metrics_examples()
    demo_test_pyramid()

    print("\n[Testing Best Practices]")
    practices = [
        "Use FakeContext for unit tests (no real gRPC server)",
        "Real gRPC server fixture for integration tests",
        "Mock downstream gRPC clients with AsyncMock",
        "Test streaming cancellation explicitly",
        "Use ghz for load testing (NOT wrk/ab)",
        "Snapshot test response shapes to catch breaking changes",
        "Use buf to detect .proto breaking changes in CI",
    ]
    for p in practices:
        print(f"  ✓ {p}")

    print("\n[Q&A Summary]")
    for q, a in OBSERVABILITY_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  observability.py    → OTel setup, Prometheus metrics, structlog")
    print("  interceptors.py     → Logging + Trace context interceptors")
    print("  tests/unit/         → FakeContext-based unit tests")
    print("  tests/integration/  → Real gRPC server fixtures")
    print("  load_test.sh        → ghz command examples")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
