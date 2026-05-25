# gRPC Observability — OpenTelemetry, Prometheus, Tracing, Reflection

## Quick Concepts

**WHAT:**
- **Metrics** = aggregated numbers (request rate, latency, errors)
- **Logs** = discrete events with context (request_id, errors)
- **Traces** = request flow across services (distributed tracing)
- **gRPC Reflection** = runtime API introspection (like Postman for gRPC)
- **grpcurl** = command-line tool for testing gRPC (like curl for HTTP)
- **Channelz** = gRPC internal state inspection

**WHY observability for gRPC:**
- gRPC is **opaque** without tooling (binary protocol, not curl-able)
- Long-lived connections + streaming = different metrics needed
- Distributed microservices = need trace correlation across hops
- Production issues hard to debug without right metrics

**HOW the 3 pillars compose:**
```
Request arrives
  ↓
[Metrics]  → count++, latency histogram
  ↓
[Logs]     → request_id, params, user_id (structured)
  ↓
[Traces]   → span created, propagated to downstream calls
  ↓
Response sent
```

---

## Interview Questions & Answers

### Q1: OpenTelemetry kya hai? gRPC mein kaise instrument karte ho?

**Answer:**

**WHAT:** OpenTelemetry (OTel) = open-source observability framework. Replaces OpenTracing + OpenCensus.

**WHY OTel for gRPC:**
- ✅ Vendor-neutral (works with Jaeger, Tempo, Datadog, AWS X-Ray)
- ✅ Auto-instrumentation for gRPC server + client
- ✅ Trace context auto-propagated via gRPC metadata
- ✅ Industry standard (CNCF graduated)

**HOW — Server-side instrumentation:**

```python
# pip install opentelemetry-api opentelemetry-sdk
#     opentelemetry-instrumentation-grpc
#     opentelemetry-exporter-otlp

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.grpc import server_interceptor, GrpcAioInstrumentorServer
import grpc

# 1. Setup tracer
resource = Resource(attributes={
    SERVICE_NAME: "user-service",
    "service.version": "1.2.0",
    "deployment.environment": "production",
})
trace.set_tracer_provider(TracerProvider(resource=resource))

# 2. Configure exporter (sends spans to backend)
otlp_exporter = OTLPSpanExporter(
    endpoint="otel-collector:4317",
    insecure=True,
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

# 3. Auto-instrument gRPC server
GrpcAioInstrumentorServer().instrument()

# 4. Create server (auto-instrumentation now active)
async def serve():
    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

**HOW — Client-side instrumentation:**

```python
from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient

# Auto-instrument client (must be before channel creation)
GrpcAioInstrumentorClient().instrument()

# Now ALL gRPC calls automatically traced
channel = grpc.aio.secure_channel("user-service:50051", credentials)
stub = user_service_pb2_grpc.UserServiceStub(channel)

# Every call creates span, propagates trace context via metadata
response = await stub.GetUser(GetUserRequest(user_id=123))
```

**HOW — Custom spans for business logic:**

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class UserServiceServicer(user_service_pb2_grpc.UserServiceServicer):

    async def CreateUser(self, request, context):
        # Auto span: "userservice.UserService/CreateUser" (from instrumentation)

        # ⭐ Add child span for DB operation
        with tracer.start_as_current_span("db.insert_user") as span:
            span.set_attribute("user.email", request.email)
            span.set_attribute("db.system", "postgresql")
            user = await db.create_user(request.email, request.name)
            span.set_attribute("user.id", user.id)

        # Another child span
        with tracer.start_as_current_span("send_welcome_email") as span:
            span.set_attribute("messaging.system", "smtp")
            await send_email(user.email)

        return self._user_to_proto(user)
```

---

### Q2: Prometheus metrics gRPC ke liye kaise expose karte ho?

**Answer:**

**WHAT:** Prometheus = time-series metrics database. Scrapes `/metrics` HTTP endpoint.

**WHY for gRPC:**
- ✅ Industry standard for metrics
- ✅ Grafana integration
- ✅ Alerting via Alertmanager
- ✅ Pre-built dashboards for gRPC

**HOW — Add Prometheus to gRPC server:**

```python
# pip install prometheus-client py-grpc-prometheus

from prometheus_client import start_http_server, Counter, Histogram, Gauge
from py_grpc_prometheus.prometheus_server_interceptor import PromServerInterceptor
import grpc

# 1. Default gRPC metrics via interceptor
interceptor = PromServerInterceptor(enable_handling_time_histogram=True)

# Built-in metrics:
# - grpc_server_started_total
# - grpc_server_handled_total{grpc_code="OK|UNAVAILABLE|..."}
# - grpc_server_msg_received_total
# - grpc_server_msg_sent_total
# - grpc_server_handling_seconds (histogram)

# 2. Custom business metrics
USER_CREATED_COUNTER = Counter(
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

# 3. Use in service
class UserServiceServicer(user_service_pb2_grpc.UserServiceServicer):

    async def CreateUser(self, request, context):
        with DB_QUERY_DURATION.labels(operation="insert", table="users").time():
            user = await db.create_user(request.email, request.name, request.role)

        USER_CREATED_COUNTER.labels(role=request.role).inc()
        return self._user_to_proto(user)

    async def ListUsers(self, request, context):
        ACTIVE_STREAMS.labels(
            service="UserService", method="ListUsers"
        ).inc()
        try:
            async for user in stream_users(request.page_size):
                yield user
        finally:
            ACTIVE_STREAMS.labels(
                service="UserService", method="ListUsers"
            ).dec()


async def serve():
    # ⭐ Start Prometheus HTTP server on separate port
    start_http_server(9090)   # /metrics endpoint

    server = grpc.aio.server(
        interceptors=[interceptor]
    )
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

**HOW — Prometheus scrape config:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'user-service'
    static_configs:
      - targets: ['user-service:9090']
    metrics_path: /metrics
    scrape_interval: 15s
```

**HOW — Key Prometheus queries (PromQL):**

```promql
# Request rate per service
sum(rate(grpc_server_started_total[5m])) by (grpc_service)

# Error rate (% of all requests)
sum(rate(grpc_server_handled_total{grpc_code!="OK"}[5m]))
  / sum(rate(grpc_server_handled_total[5m])) * 100

# p99 latency per method
histogram_quantile(0.99,
  sum(rate(grpc_server_handling_seconds_bucket[5m])) by (grpc_method, le)
)

# Active streams
sum(grpc_active_streams) by (service, method)

# Slow methods (avg latency > 1s)
avg(rate(grpc_server_handling_seconds_sum[5m])
  / rate(grpc_server_handling_seconds_count[5m])) by (grpc_method) > 1
```

---

### Q3: Distributed tracing gRPC microservices mein kaise kaam karta hai?

**Answer:**

**WHAT:** Trace = end-to-end request flow with timing across services.

**WHY for gRPC microservices:**
```
User request → API Gateway → Service A → Service B → Service C → DB
                                                                  ↓
                                                                Slow!

Without tracing: "Where's the slowness?"
With tracing: "Service C → DB took 800ms" (visible in waterfall)
```

**HOW — Trace context propagation:**

```
Client sends:
  gRPC metadata:
    traceparent: 00-{trace_id}-{span_id}-01
    tracestate: ...

Server receives → continues trace → adds child spans → propagates downstream
```

**HOW — Manual trace context (when auto-instrumentation insufficient):**

```python
from opentelemetry import trace, propagate
from opentelemetry.propagators.b3 import B3MultiFormat

# Set propagator (B3 for Zipkin, default is W3C TraceContext)
propagate.set_global_textmap(B3MultiFormat())

# Server side: extract incoming trace context
class TraceServerInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)

        # Extract trace context from gRPC metadata
        ctx = propagate.extract(metadata)

        # Set as current context
        token = context.attach(ctx)
        try:
            return await continuation(handler_call_details)
        finally:
            context.detach(token)


# Client side: inject trace context
class TraceClientInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    async def intercept_unary_unary(self, continuation, client_call_details, request):
        new_metadata = dict(client_call_details.metadata or [])

        # ⭐ Inject current trace context into outgoing metadata
        propagate.inject(new_metadata)

        new_details = grpc.aio.ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=list(new_metadata.items()),
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
        )
        return await continuation(new_details, request)
```

**HOW — View traces in Jaeger UI:**

```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"   # UI
      - "4317:4317"     # OTLP gRPC receiver
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

Access `http://localhost:16686` → search by service → see waterfall.

---

### Q4: Structured logging gRPC mein with request_id correlation?

**Answer:**

**WHAT:** Each log line has request_id, user_id, trace_id for correlation across services.

**WHY structured logs:**
- ✅ Searchable in CloudWatch Insights / Loki / Datadog
- ✅ Correlate logs ↔ metrics ↔ traces via shared IDs
- ✅ Filter by user_id, request_id, error_code

**HOW — structlog with context propagation:**

```python
import structlog
import uuid
from contextvars import ContextVar
from opentelemetry import trace as otel_trace

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,    # ⭐ Auto-inject context
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
)

log = structlog.get_logger()


# Server interceptor that binds context
class LoggingServerInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        # Extract request_id from metadata (or generate)
        metadata = dict(handler_call_details.invocation_metadata)
        request_id = metadata.get("x-request-id", str(uuid.uuid4()))

        # Get trace_id from OTel (if instrumented)
        span = otel_trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") if span else None

        # ⭐ Bind to contextvars — auto-injected in ALL logs from this point
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            method=handler_call_details.method,
        )

        try:
            log.info("rpc_started")
            response = await continuation(handler_call_details)
            log.info("rpc_completed")
            return response
        except Exception as e:
            log.error("rpc_failed", error=str(e), exc_info=True)
            raise
        finally:
            structlog.contextvars.clear_contextvars()


# In service method
class UserServiceServicer(user_service_pb2_grpc.UserServiceServicer):
    async def CreateUser(self, request, context):
        # ⭐ Log automatically has request_id, trace_id from contextvars
        log.info("creating_user", email=request.email, role=request.role)

        try:
            user = await db.create_user(...)
            log.info("user_created", user_id=user.id)
        except Exception as e:
            log.error("user_creation_failed", error=str(e))
            raise

        return self._user_to_proto(user)
```

**Sample log output:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "info",
  "event": "user_created",
  "user_id": 42,
  "request_id": "abc-123-def",
  "trace_id": "00f067aa0ba902b7",
  "method": "/userservice.UserService/CreateUser"
}
```

---

### Q5: gRPC Reflection API kya hai? Production mein safe hai?

**Answer:**

**WHAT:** Standard gRPC service `grpc.reflection.v1alpha.ServerReflection` — exposes service definitions at runtime.

**WHY useful:**
- ✅ Debug with `grpcurl` without .proto file
- ✅ API exploration tools (Bloomrpc, Postman, Kreya)
- ✅ Service mesh service discovery
- ⚠️ Security: exposes API schema (could help attackers)

**HOW — Enable reflection:**

```python
# pip install grpcio-reflection
from grpc_reflection.v1alpha import reflection
import grpc

async def serve():
    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)

    # ⭐ Enable reflection
    SERVICE_NAMES = (
        user_service_pb2.DESCRIPTOR.services_by_name["UserService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

**HOW — Use with grpcurl:**

```bash
# Install grpcurl
brew install grpcurl   # macOS

# List all services
grpcurl -plaintext localhost:50051 list
# Output:
# grpc.health.v1.Health
# grpc.reflection.v1alpha.ServerReflection
# userservice.UserService

# List methods in a service
grpcurl -plaintext localhost:50051 list userservice.UserService
# Output:
# userservice.UserService.CreateUser
# userservice.UserService.GetUser
# userservice.UserService.ListUsers

# Describe a method
grpcurl -plaintext localhost:50051 describe userservice.UserService.CreateUser

# Call a method
grpcurl -plaintext -d '{"name": "Alice", "email": "alice@example.com"}' \
  localhost:50051 userservice.UserService/CreateUser

# With auth metadata
grpcurl -plaintext \
  -H "authorization: Bearer eyJhbGc..." \
  -d '{"user_id": 123}' \
  localhost:50051 userservice.UserService/GetUser

# Use with TLS
grpcurl -d '{"user_id": 123}' \
  -cacert ca.crt \
  user-service.prod.com:443 userservice.UserService/GetUser
```

**SECURITY: Production considerations:**

```python
# Option 1: Disable reflection in production
if os.getenv("ENV") != "production":
    reflection.enable_server_reflection(SERVICE_NAMES, server)

# Option 2: Restrict reflection to internal network
# - Don't expose port via ALB
# - Only accessible from VPC

# Option 3: Require auth for reflection
class ReflectionAuthInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        if "ServerReflection" in handler_call_details.method:
            metadata = dict(handler_call_details.invocation_metadata)
            if not _is_admin_token(metadata.get("authorization", "")):
                async def deny(req, ctx):
                    await ctx.abort(grpc.StatusCode.PERMISSION_DENIED, "Admin only")
                return grpc.unary_unary_rpc_method_handler(deny)
        return await continuation(handler_call_details)
```

---

### Q6: gRPC channelz — debugging tool kab use karein?

**Answer:**

**WHAT:** Channelz = built-in gRPC service exposing internal state (channels, sockets, servers).

**WHY useful for debugging:**
- ✅ See active connections
- ✅ Per-channel stats (RPCs sent, errors)
- ✅ Diagnose connection pooling issues
- ✅ Stream-level stats

**HOW — Enable channelz:**

```python
from grpc_channelz.v1 import channelz

async def serve():
    server = grpc.aio.server()
    # ... add services

    # ⭐ Enable channelz
    channelz.add_channelz_servicer(server)

    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

**HOW — Query channelz with grpcurl:**

```bash
# List top-level channels
grpcurl -plaintext localhost:50051 \
  grpc.channelz.v1.Channelz/GetTopChannels

# Get specific channel details
grpcurl -plaintext -d '{"channel_id": "1"}' localhost:50051 \
  grpc.channelz.v1.Channelz/GetChannel

# List sockets
grpcurl -plaintext localhost:50051 \
  grpc.channelz.v1.Channelz/GetServerSockets
```

**HOW — Channelz with web UI:**

```bash
# Run channelz-ng (web UI)
docker run -p 8080:8080 channelz-ng \
  --grpc_endpoint=localhost:50051
```

---

### Q7: Production observability stack kya hai gRPC ke liye?

**Answer:**

**Recommended stack:**

```
┌─────────────────────────────────────────────────────────────┐
│  Application                                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Prometheus     │  │ OpenTelemetry│  │ structlog      │  │
│  │ /metrics       │  │ spans        │  │ JSON logs      │  │
│  └────────┬───────┘  └──────┬───────┘  └────────┬───────┘  │
└───────────┼─────────────────┼───────────────────┼──────────┘
            │                 │                   │
            ↓                 ↓                   ↓
┌───────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Prometheus        │ │ OTel Collector   │ │ Fluent Bit       │
│ (scrape /metrics) │ │ (receive spans)  │ │ (ship logs)      │
└─────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
          │                    │                    │
          ↓                    ↓                    ↓
┌──────────────────┐  ┌──────────────────┐ ┌──────────────────┐
│ Grafana          │  │ Jaeger / Tempo   │ │ Loki / CloudWatch│
│ (dashboards)     │  │ (trace UI)       │ │ (log search)     │
└──────────────────┘  └──────────────────┘ └──────────────────┘
```

**Alerting rules (PrometheusRule):**

```yaml
# alerts.yml
groups:
  - name: grpc_alerts
    rules:
      - alert: HighGrpcErrorRate
        expr: |
          sum(rate(grpc_server_handled_total{grpc_code!="OK"}[5m])) by (grpc_service)
            / sum(rate(grpc_server_handled_total[5m])) by (grpc_service) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.grpc_service }} has > 5% error rate"

      - alert: HighGrpcLatency
        expr: |
          histogram_quantile(0.99,
            sum(rate(grpc_server_handling_seconds_bucket[5m])) by (grpc_service, le)
          ) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.grpc_service }} p99 latency > 2s"

      - alert: GrpcServerDown
        expr: up{job=~".*grpc.*"} == 0
        for: 1m
        labels:
          severity: critical
```

---

## Observability Checklist

```markdown
### Metrics (Prometheus)
- [ ] /metrics endpoint exposed
- [ ] Standard gRPC metrics (via py-grpc-prometheus)
- [ ] Custom business metrics
- [ ] Alerts configured (error rate, latency, down)

### Tracing (OpenTelemetry)
- [ ] OTel SDK initialized
- [ ] gRPC server auto-instrumented
- [ ] gRPC client auto-instrumented
- [ ] Custom spans for business logic
- [ ] Exporter configured (Jaeger/Tempo/X-Ray)

### Logging
- [ ] Structured JSON logs (structlog)
- [ ] Request ID in every log
- [ ] Trace ID linked to logs
- [ ] User context bound (user_id, tenant_id)

### Debug Tools
- [ ] gRPC Reflection enabled (dev/staging)
- [ ] Health Check Service
- [ ] Channelz for connection debugging
- [ ] grpcurl available in dev environment
```
