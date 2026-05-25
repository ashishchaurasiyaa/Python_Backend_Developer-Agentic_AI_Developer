"""
============================================================
OPENTELEMETRY + DISTRIBUTED TRACING — Practical
============================================================
Install:
  pip install opentelemetry-distro opentelemetry-exporter-otlp
  pip install opentelemetry-instrumentation-fastapi
  pip install opentelemetry-instrumentation-sqlalchemy
  pip install opentelemetry-instrumentation-httpx
  pip install opentelemetry-instrumentation-redis

Run Jaeger locally:
  docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest

Open UI: http://localhost:16686

Then run this file (would normally be a FastAPI app):
  python 14_opentelemetry_distributed_tracing.py
"""
import asyncio
import logging
import time
import os
import sys

# ============================================================
# 1. SETUP OPENTELEMETRY (must be done before app starts)
# ============================================================
def setup_tracing(service_name: str = "demo-service"):
    """Initialize OpenTelemetry with Jaeger/OTLP exporter."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        print("Install: pip install opentelemetry-sdk opentelemetry-api")
        return None

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENV", "dev"),
    })

    # 10% sampling — parent-based (continue trace if parent sampled)
    sampler = ParentBased(TraceIdRatioBased(1.0))   # 100% for demo
    provider = TracerProvider(resource=resource, sampler=sampler)

    # For demo: log spans to console
    # Production: use OTLPSpanExporter to send to collector
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Uncomment for real OTLP export:
    # from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    # provider.add_span_processor(BatchSpanProcessor(
    #     OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
    # ))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)


# ============================================================
# 2. FASTAPI APP WITH AUTO-INSTRUMENTATION (Reference)
# ============================================================
FASTAPI_AUTO_INSTRUMENT = """
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

app = FastAPI()

# Auto-instrument everything
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=db_engine)
RedisInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # Auto-traced span: GET /users/{user_id}
    user = await db.fetch_user(user_id)        # Auto-traced SQL span
    posts = await redis.get(f"posts:{user_id}") # Auto-traced Redis span

    async with httpx.AsyncClient() as client:
        ext = await client.get("https://api.example.com")  # Auto-traced
    return {"user": user, "posts": posts}
"""


# ============================================================
# 3. MANUAL SPANS — for business logic
# ============================================================
async def demo_manual_spans(tracer):
    """Show manual span creation for business operations."""
    if not tracer:
        return

    from opentelemetry.trace import Status, StatusCode

    print("\n--- Demo 1: Nested spans ---")
    with tracer.start_as_current_span("process_order") as parent:
        parent.set_attribute("order.id", 12345)
        parent.set_attribute("enduser.id", "user-42")

        with tracer.start_as_current_span("validate_inventory") as child1:
            child1.set_attribute("inventory.items", 3)
            await asyncio.sleep(0.05)

        with tracer.start_as_current_span("charge_payment") as child2:
            child2.set_attribute("payment.amount", 1500)
            child2.set_attribute("payment.currency", "INR")
            await asyncio.sleep(0.1)

        with tracer.start_as_current_span("send_email") as child3:
            child3.set_attribute("email.to", "user@example.com")
            try:
                await asyncio.sleep(0.02)
                # raise ValueError("SMTP down")   # uncomment to test error
            except Exception as e:
                child3.set_status(Status(StatusCode.ERROR, str(e)))
                child3.record_exception(e)
                raise


# ============================================================
# 4. CONTEXT PROPAGATION — between services
# ============================================================
async def demo_context_propagation(tracer):
    """Show how to propagate trace across service boundaries."""
    if not tracer:
        return
    from opentelemetry.propagate import inject, extract

    print("\n--- Demo 2: Context propagation ---")

    # Service A: starts trace, makes HTTP call to Service B
    with tracer.start_as_current_span("service-A-handler") as span:
        span.set_attribute("service", "A")
        # Inject trace context into headers
        headers = {}
        inject(headers)
        print(f"  Outgoing headers: {headers}")
        # Simulate sending to Service B
        await simulate_service_b(headers, tracer)


async def simulate_service_b(incoming_headers, tracer):
    """Simulates Service B receiving headers and continuing the trace."""
    from opentelemetry.propagate import extract
    ctx = extract(incoming_headers)
    with tracer.start_as_current_span(
        "service-B-handler",
        context=ctx,
    ) as span:
        span.set_attribute("service", "B")
        await asyncio.sleep(0.03)
        print(f"  Service B span trace_id matches Service A's")


# ============================================================
# 5. DECORATOR FOR ANY FUNCTION
# ============================================================
def traced(operation_name: str = None):
    """Decorator to auto-trace any function."""
    def decorator(func):
        import functools
        name = operation_name or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                from opentelemetry import trace
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(name):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                from opentelemetry import trace
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(name):
                    return func(*args, **kwargs)
            return sync_wrapper
    return decorator


@traced("business.calculate_discount")
async def calculate_discount(amount, tier):
    await asyncio.sleep(0.01)
    return amount * (0.1 if tier == "gold" else 0.05)


@traced("db.fetch_user_profile")
async def fetch_user_profile(user_id):
    await asyncio.sleep(0.02)
    return {"id": user_id, "name": "Ashish"}


async def demo_decorator():
    print("\n--- Demo 3: @traced decorator ---")
    discount = await calculate_discount(1000, "gold")
    profile = await fetch_user_profile(42)
    print(f"  discount={discount}, profile={profile}")


# ============================================================
# 6. INJECT TRACE_ID INTO LOGS
# ============================================================
def setup_trace_aware_logging():
    """Add trace_id and span_id to every log line."""
    from opentelemetry.trace import get_current_span

    class TraceIdFilter(logging.Filter):
        def filter(self, record):
            span = get_current_span()
            ctx = span.get_span_context()
            record.trace_id = format(ctx.trace_id, '032x') if ctx.is_valid else "-"
            record.span_id = format(ctx.span_id, '016x') if ctx.is_valid else "-"
            return True

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [trace=%(trace_id)s span=%(span_id)s] %(message)s",
    )
    for h in logging.getLogger().handlers:
        h.addFilter(TraceIdFilter())


async def demo_logging(tracer):
    if not tracer:
        return
    print("\n--- Demo 4: Trace ID in logs ---")
    setup_trace_aware_logging()
    logger = logging.getLogger("demo")
    with tracer.start_as_current_span("op-with-logs"):
        logger.info("Processing request")
        await asyncio.sleep(0.01)
        logger.info("Done")


# ============================================================
# 7. SAMPLING STRATEGIES
# ============================================================
SAMPLING_STRATEGIES = """
# OPTIONS:

# 1. Always sample (dev/staging)
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
provider = TracerProvider(sampler=ALWAYS_ON)

# 2. Never sample (disable)
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
provider = TracerProvider(sampler=ALWAYS_OFF)

# 3. 10% trace ID ratio
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
provider = TracerProvider(sampler=TraceIdRatioBased(0.1))

# 4. Parent-based (continue if parent sampled, else 10%)
from opentelemetry.sdk.trace.sampling import ParentBased
provider = TracerProvider(sampler=ParentBased(TraceIdRatioBased(0.1)))

# 5. Custom — always sample errors, 10% for others
class ErrorAlwaysSampler:
    def should_sample(self, parent_context, trace_id, name, ...):
        if "error" in name or attributes.get("error"):
            return SamplingResult(SamplingDecision.RECORD_AND_SAMPLE)
        return self.fallback.should_sample(...)
"""


# ============================================================
# 8. PRODUCTION CONFIG — env vars
# ============================================================
PROD_ENV_VARS = """
# Standard OTel env vars (no code change needed)
OTEL_SERVICE_NAME=user-api
OTEL_SERVICE_VERSION=1.2.3
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,team=platform
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
OTEL_LOGS_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp

# Run with auto-instrumentation:
opentelemetry-instrument uvicorn app:app --host 0.0.0.0 --port 8000
"""


# ============================================================
# 9. DOCKER COMPOSE FOR LOCAL OTEL STACK
# ============================================================
DOCKER_COMPOSE = """
version: '3'
services:
  app:
    build: .
    environment:
      - OTEL_SERVICE_NAME=my-app
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
    depends_on:
      - otel-collector

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-config.yaml"]
    volumes:
      - ./otel-config.yaml:/etc/otel-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"   # UI: http://localhost:16686
      - "14250:14250"   # gRPC

# otel-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
processors:
  batch:
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger]
"""


# ============================================================
# MAIN
# ============================================================
async def main():
    print("=" * 60)
    print("OpenTelemetry Distributed Tracing Demo")
    print("=" * 60)

    tracer = setup_tracing("demo-service")

    if tracer is None:
        print("\nOTel not installed — showing reference code only")
        print(FASTAPI_AUTO_INSTRUMENT)
        print(SAMPLING_STRATEGIES)
        return

    await demo_manual_spans(tracer)
    await demo_context_propagation(tracer)
    await demo_decorator()
    await demo_logging(tracer)

    print("\n" + "=" * 60)
    print("PRODUCTION SETUP")
    print("=" * 60)
    print(PROD_ENV_VARS)
    print(DOCKER_COMPOSE)


if __name__ == "__main__":
    asyncio.run(main())
