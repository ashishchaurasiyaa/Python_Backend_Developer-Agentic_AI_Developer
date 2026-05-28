"""
Phase3_gRPC — Production Deployment + Security + Resilience Practical
=======================================================================
Topics covered:
  1. gRPC Health Check Protocol implementation
  2. Graceful shutdown with SIGTERM handling
  3. mTLS server + client (with cert generation)
  4. JWT authentication interceptors (server + client)
  5. OAuth2 token provider with refresh
  6. Retry policy with exponential backoff + jitter
  7. Circuit breaker pattern
  8. Idempotency key deduplication
  9. Bulkhead pattern
  10. Deadline propagation

Install:
  pip install grpcio grpcio-tools grpcio-health-checking
              pyjwt cryptography httpx pybreaker

Run:
  python 02_grpc_production_practical.py
"""

import asyncio
import grpc
import jwt
import time
import random
import uuid
import signal
import hashlib
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: gRPC Health Check Protocol
# INTERVIEW: Standard for K8s/ALB probes — NOT HTTP health check
# ─────────────────────────────────────────────────────────────────────────────

HEALTH_CHECK_PROTO = """
// health.proto — Standard gRPC Health Check Service
// Defined by gRPC (don't create yourself, use grpcio-health-checking)
syntax = "proto3";
package grpc.health.v1;

service Health {
  rpc Check(HealthCheckRequest) returns (HealthCheckResponse);
  rpc Watch(HealthCheckRequest) returns (stream HealthCheckResponse);
}

message HealthCheckRequest {
  string service = 1;  // Empty string = check OVERALL server health
}

message HealthCheckResponse {
  enum ServingStatus {
    UNKNOWN = 0;
    SERVING = 1;
    NOT_SERVING = 2;
    SERVICE_UNKNOWN = 3;
  }
  ServingStatus status = 1;
}
"""

HEALTH_SERVER_PATTERN = """
# server.py — Adding Health Service
from grpc_health.v1 import health, health_pb2_grpc, health_pb2
import grpc

async def serve():
    server = grpc.aio.server()

    # 1. Add your business services
    # user_service_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)

    # 2. ⭐ Add Health Service
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    # 3. Mark services as SERVING
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)  # Overall
    health_servicer.set(
        "userservice.UserService",
        health_pb2.HealthCheckResponse.SERVING
    )

    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Graceful Shutdown Pattern
# INTERVIEW: Critical for zero-downtime deployments
# ─────────────────────────────────────────────────────────────────────────────

class GracefulServer:
    """
    INTERVIEW: Production gRPC server with graceful shutdown.
    On SIGTERM:
      1. Mark health as NOT_SERVING (LB stops sending new requests)
      2. Wait for in-flight requests to complete
      3. Stop server after grace period
    """
    def __init__(self):
        self.server = None
        self.health_servicer = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        # Setup server (pseudo-code — actual servicers omitted)
        # self.server = grpc.aio.server()
        # self.health_servicer = HealthServicer()
        # ... add services
        # self.server.add_insecure_port("[::]:50051")
        # await self.server.start()

        # Register signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

        print("✅ Server started on :50051")

    async def shutdown(self, sig):
        print(f"🛑 Received {sig.name}, starting graceful shutdown...")

        # ⭐ Step 1: Mark unhealthy (LB stops sending traffic)
        # self.health_servicer.set("", NOT_SERVING)

        # ⭐ Step 2: Wait for LB to detect (deregistration_delay)
        await asyncio.sleep(5)
        print("🚦 LB notified, draining connections...")

        # ⭐ Step 3: Stop with grace period (in-flight requests finish)
        # await self.server.stop(grace=30)
        await asyncio.sleep(2)  # Simulated

        print("✅ Server shut down cleanly")
        self._shutdown_event.set()

    async def wait(self):
        await self._shutdown_event.wait()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: mTLS — Mutual TLS Setup
# INTERVIEW: Server + Client cert verification
# ─────────────────────────────────────────────────────────────────────────────

MTLS_CERT_GENERATION = """
# generate-certs.sh — Generate CA + server + client certificates

# 1. Generate CA (Certificate Authority)
openssl req -x509 -newkey rsa:4096 -keyout ca.key -out ca.crt \\
    -days 365 -nodes -subj "/CN=myorg-ca"

# 2. Server certificate
openssl req -newkey rsa:4096 -keyout server.key -out server.csr \\
    -nodes -subj "/CN=user-service.local"

# SAN (Subject Alternative Name) — required for K8s DNS
cat > server.ext <<EOF
subjectAltName = DNS:user-service.local,DNS:localhost,IP:127.0.0.1
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \\
    -CAcreateserial -out server.crt -days 365 -extfile server.ext

# 3. Client certificate (for mTLS)
openssl req -newkey rsa:4096 -keyout client.key -out client.csr \\
    -nodes -subj "/CN=order-service"     # CN = client identity

openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key \\
    -CAcreateserial -out client.crt -days 365
"""


def build_mtls_server_credentials(cert_dir: str = "./certs"):
    """
    INTERVIEW: Server-side mTLS — verifies CLIENT cert.
    require_client_auth=True enables mTLS.
    """
    with open(f"{cert_dir}/server.key", "rb") as f:
        private_key = f.read()
    with open(f"{cert_dir}/server.crt", "rb") as f:
        cert_chain = f.read()
    with open(f"{cert_dir}/ca.crt", "rb") as f:
        ca_cert = f.read()

    return grpc.ssl_server_credentials(
        [(private_key, cert_chain)],
        root_certificates=ca_cert,
        require_client_auth=True,    # ⭐ CRITICAL: enables mTLS
    )


def build_mtls_client_credentials(cert_dir: str = "./certs"):
    """
    INTERVIEW: Client-side mTLS — sends client cert to server.
    """
    with open(f"{cert_dir}/ca.crt", "rb") as f:
        ca_cert = f.read()
    with open(f"{cert_dir}/client.key", "rb") as f:
        client_key = f.read()
    with open(f"{cert_dir}/client.crt", "rb") as f:
        client_cert = f.read()

    return grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=client_key,
        certificate_chain=client_cert,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: JWT Authentication Interceptors
# INTERVIEW: Server validates, Client provides
# ─────────────────────────────────────────────────────────────────────────────

class JWTServerInterceptor:
    """
    INTERVIEW: Validates JWT on every incoming RPC.
    Excluded paths: health check, reflection.
    """
    EXCLUDED_PATHS = [
        "/grpc.health.v1.Health/Check",
        "/grpc.reflection.v1alpha.ServerReflection/ServerReflectionInfo",
    ]

    def __init__(self, secret_key: str, required_scopes: dict = None):
        self.secret_key = secret_key
        self.required_scopes = required_scopes or {}

    def _validate_jwt(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise PermissionError("Token expired")
        except jwt.InvalidTokenError as e:
            raise PermissionError(f"Invalid token: {e}")

    async def intercept(self, method_name, metadata):
        """Simulated interception (real interceptor uses grpc.aio.ServerInterceptor)."""
        if method_name in self.EXCLUDED_PATHS:
            return  # Skip auth

        auth_header = metadata.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise PermissionError("Missing Bearer token")

        token = auth_header.replace("Bearer ", "")
        payload = self._validate_jwt(token)

        # Check scopes for this method
        required = self.required_scopes.get(method_name)
        if required and required not in payload.get("scope", []):
            raise PermissionError(f"Missing scope: {required}")

        return payload


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: OAuth2 Token Provider (Client Credentials flow)
# INTERVIEW: Service-to-service auth with token caching + refresh
# ─────────────────────────────────────────────────────────────────────────────

class OAuth2TokenProvider:
    """
    INTERVIEW: Caches token, auto-refreshes before expiry.
    Used for service-to-service authentication.
    """
    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: Optional[str] = None
        self._expires_at: float = 0

    async def get_token(self) -> str:
        # Return cached if valid (60s buffer before expiry)
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        # Fetch new token (would use httpx in real code)
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(self.token_url, data={
        #         "grant_type": "client_credentials",
        #         "client_id": self.client_id,
        #         "client_secret": self.client_secret,
        #         "scope": self.scope,
        #     })
        # data = response.json()

        # Simulated response
        data = {"access_token": f"fake-token-{uuid.uuid4()}", "expires_in": 3600}

        self._token = data["access_token"]
        self._expires_at = time.time() + data["expires_in"]
        return self._token


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Retry with Exponential Backoff + Jitter
# INTERVIEW: gRPC service config OR custom logic
# ─────────────────────────────────────────────────────────────────────────────

GRPC_SERVICE_CONFIG_RETRY = """
# Service config (JSON) for built-in gRPC retries
{
    "methodConfig": [{
        "name": [{"service": "userservice.UserService"}],
        "retryPolicy": {
            "maxAttempts": 5,
            "initialBackoff": "0.1s",
            "maxBackoff": "10s",
            "backoffMultiplier": 2,
            "retryableStatusCodes": [
                "UNAVAILABLE",
                "DEADLINE_EXCEEDED",
                "RESOURCE_EXHAUSTED"
            ]
        }
    }]
}

# Apply to channel:
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        ("grpc.service_config", json.dumps(service_config)),
        ("grpc.enable_retries", 1),
    ]
)
"""


# Retryable error codes (subset of grpc.StatusCode names)
RETRYABLE_CODES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED"}


async def retry_with_backoff(
    operation: Callable,
    max_attempts: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
    jitter_factor: float = 0.3,
):
    """
    INTERVIEW: Custom retry with exponential backoff + jitter.
    Use jitter to prevent thundering herd.
    """
    last_error = None
    previous_delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except Exception as e:
            last_error = e

            # Check if retryable (in real code, check grpc.RpcError code)
            error_code = getattr(e, "code_name", "UNKNOWN")
            if error_code not in RETRYABLE_CODES:
                raise

            if attempt == max_attempts:
                raise

            # ⭐ Exponential backoff
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)

            # ⭐ Add jitter (decorrelated style)
            jittered = random.uniform(base_delay, previous_delay * 3)
            actual_delay = min(jittered, max_delay)
            previous_delay = actual_delay

            print(f"  Attempt {attempt} failed ({error_code}), retrying in {actual_delay:.2f}s")
            await asyncio.sleep(actual_delay)

    raise last_error


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Circuit Breaker Pattern
# INTERVIEW: Prevent cascading failures
# ─────────────────────────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing — reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class AsyncCircuitBreaker:
    """
    INTERVIEW: Simple async circuit breaker.
    Trips OPEN after N consecutive failures.
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = 0
        self._lock = asyncio.Lock()

    @property
    def state(self):
        return self._state

    async def call(self, func: Callable, *args, **kwargs):
        async with self._lock:
            # Check if circuit should transition OPEN → HALF_OPEN
            if self._state == CircuitState.OPEN:
                if time.time() - self._opened_at > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    print(f"  Circuit HALF_OPEN — testing recovery")
                else:
                    raise Exception(
                        f"Circuit OPEN — retry after {self._opened_at + self.recovery_timeout - time.time():.0f}s"
                    )

        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.time()
                    print(f"  Circuit OPENED after {self._failures} failures")
            raise

        # Success — reset
        async with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED
        return result


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Idempotency Key Deduplication
# INTERVIEW: Safe retries for mutating operations
# ─────────────────────────────────────────────────────────────────────────────

class IdempotencyStore:
    """
    INTERVIEW: Server-side dedup using idempotency key.
    In production: use Redis with TTL.
    """
    def __init__(self):
        self._store = {}   # key → (timestamp, response)
        self._ttl = 86400  # 24 hours

    def get(self, key: str):
        if key not in self._store:
            return None

        timestamp, response = self._store[key]
        if time.time() - timestamp > self._ttl:
            del self._store[key]
            return None

        return response

    def set(self, key: str, response):
        self._store[key] = (time.time(), response)


async def create_order_idempotent(idempotency_key: str, order_data: dict, store: IdempotencyStore):
    """
    INTERVIEW: Check idempotency cache before processing.
    """
    # ⭐ Check cache first
    cached = store.get(idempotency_key)
    if cached:
        print(f"  Idempotent return: cached response for {idempotency_key[:8]}...")
        return cached

    # First time — process
    order_id = f"order-{uuid.uuid4()}"
    response = {"order_id": order_id, "status": "created", **order_data}

    # ⭐ Cache for future retries
    store.set(idempotency_key, response)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Bulkhead Pattern (Concurrent Call Limit)
# INTERVIEW: Isolate failures per downstream service
# ─────────────────────────────────────────────────────────────────────────────

class BulkheadClient:
    """
    INTERVIEW: Limit concurrent calls per downstream.
    Prevents one slow service from starving others.
    """
    def __init__(self):
        self.semaphores = {
            "user_service":    asyncio.Semaphore(50),
            "payment_service": asyncio.Semaphore(20),  # Critical, limited
            "analytics":       asyncio.Semaphore(10),  # Low priority
        }
        self.timeouts = {
            "user_service":    5.0,
            "payment_service": 10.0,
            "analytics":       2.0,
        }

    async def call(self, service: str, operation):
        sem = self.semaphores.get(service)
        timeout = self.timeouts.get(service, 5.0)

        if not sem:
            raise ValueError(f"Unknown service: {service}")

        # ⭐ Bound by semaphore acquisition
        try:
            await asyncio.wait_for(sem.acquire(), timeout=1.0)
        except asyncio.TimeoutError:
            raise Exception(f"Bulkhead full for {service}")

        try:
            return await asyncio.wait_for(operation, timeout=timeout)
        finally:
            sem.release()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Demo functions
# ─────────────────────────────────────────────────────────────────────────────

class SimulatedError(Exception):
    def __init__(self, message, code_name="UNAVAILABLE"):
        super().__init__(message)
        self.code_name = code_name


async def demo_retry_with_backoff():
    print("\n[Retry with Backoff Demo]")

    attempt_count = {"n": 0}

    async def flaky_operation():
        attempt_count["n"] += 1
        if attempt_count["n"] < 3:
            raise SimulatedError("Service temporarily down")
        return {"result": "success"}

    try:
        result = await retry_with_backoff(flaky_operation, max_attempts=5)
        print(f"  ✅ Succeeded after {attempt_count['n']} attempts: {result}")
    except Exception as e:
        print(f"  ❌ Failed permanently: {e}")


async def demo_circuit_breaker():
    print("\n[Circuit Breaker Demo]")

    breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=2)

    async def failing_op():
        raise SimulatedError("Downstream broken")

    # Trip the breaker
    for i in range(5):
        try:
            await breaker.call(failing_op)
        except Exception as e:
            print(f"  Call {i+1}: {type(e).__name__}: {str(e)[:50]}")

    print(f"  Circuit state: {breaker.state.value}")

    # Wait for recovery
    print("  ⏳ Waiting for recovery timeout (2s)...")
    await asyncio.sleep(2.5)

    # Should attempt half-open
    async def succeeding_op():
        return "ok"

    try:
        result = await breaker.call(succeeding_op)
        print(f"  ✅ Recovery: {result}, state: {breaker.state.value}")
    except Exception as e:
        print(f"  ❌ Still failing: {e}")


async def demo_idempotency():
    print("\n[Idempotency Demo]")

    store = IdempotencyStore()
    key = str(uuid.uuid4())

    # First call: actually creates order
    result1 = await create_order_idempotent(key, {"amount": 100}, store)
    print(f"  Call 1: {result1['order_id']}")

    # Retry with SAME key: returns cached
    result2 = await create_order_idempotent(key, {"amount": 100}, store)
    print(f"  Call 2: {result2['order_id']}")

    # Different key: new order
    result3 = await create_order_idempotent(str(uuid.uuid4()), {"amount": 200}, store)
    print(f"  Call 3 (diff key): {result3['order_id']}")

    assert result1["order_id"] == result2["order_id"]
    assert result1["order_id"] != result3["order_id"]
    print("  ✅ Idempotency works correctly")


async def demo_bulkhead():
    print("\n[Bulkhead Demo]")

    bulkhead = BulkheadClient()

    async def slow_payment_call():
        await asyncio.sleep(0.5)
        return "payment_processed"

    # Spawn many concurrent payment calls
    tasks = [
        bulkhead.call("payment_service", slow_payment_call())
        for _ in range(25)
    ]

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start

    successes = sum(1 for r in results if not isinstance(r, Exception))
    failures = sum(1 for r in results if isinstance(r, Exception))

    print(f"  25 concurrent calls (semaphore limit: 20)")
    print(f"  Succeeded: {successes}, Failed: {failures}")
    print(f"  Elapsed: {elapsed:.2f}s (sequential would take ~12.5s)")


async def demo_oauth2():
    print("\n[OAuth2 Token Provider Demo]")

    provider = OAuth2TokenProvider(
        token_url="https://auth.example.com/oauth/token",
        client_id="order-service",
        client_secret="secret",
        scope="users:read",
    )

    # First call fetches token
    token1 = await provider.get_token()
    print(f"  Token 1: {token1[:20]}...")

    # Second call returns cached
    token2 = await provider.get_token()
    print(f"  Token 2 (cached): {token2[:20]}...")

    assert token1 == token2
    print("  ✅ Token caching works")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A Summary
# ─────────────────────────────────────────────────────────────────────────────

GRPC_PRODUCTION_QA = [
    ("Why is HTTP/2 required for gRPC on ALB?",
     "gRPC uses HTTP/2 trailers for status codes.\n"
     "     ALB protocol_version='GRPC' enables HTTP/2 + trailer support."),

    ("How is mTLS different from TLS?",
     "TLS: Client verifies server (HTTPS pattern).\n"
     "     mTLS: BOTH verify each other via certs.\n"
     "     Use mTLS for service-to-service in zero-trust networks."),

    ("Why exponential backoff with jitter?",
     "Exponential: avoids hammering broken service.\n"
     "     Jitter: prevents thundering herd when many clients retry."),

    ("When should circuit breaker open?",
     "After N consecutive failures (typical 5).\n"
     "     Stay OPEN for cooldown (60s), then HALF_OPEN to test recovery."),

    ("How to handle idempotency for mutating gRPC calls?",
     "Client generates UUID idempotency key in metadata.\n"
     "     Server caches response by key (Redis with TTL).\n"
     "     Retries return cached response (safe deduplication)."),

    ("What is bulkhead pattern?",
     "Separate resource pool per downstream service.\n"
     "     One slow service can't starve calls to other services."),

    ("Why need graceful shutdown on SIGTERM?",
     "Long-lived gRPC connections need to drain.\n"
     "     1. Mark health NOT_SERVING\n"
     "     2. Wait for LB to deregister (~5s)\n"
     "     3. server.stop(grace=30) — complete in-flight requests"),

    ("Where to validate JWT for microservices: gateway or each service?",
     "Hybrid: Gateway validates once + injects user context in metadata.\n"
     "     Each service can re-validate for defense in depth.\n"
     "     mTLS proves gateway identity → services trust injected headers."),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("gRPC PRODUCTION + SECURITY + RESILIENCE PRACTICAL")
    print("=" * 60)

    print("\n[1] gRPC Health Check Protocol:")
    print("  - Standard service: grpc.health.v1.Health")
    print("  - Methods: Check (unary), Watch (streaming)")
    print("  - Used by K8s readiness/liveness, ALB target health")
    print("  - Tool: grpc_health_probe binary")

    print("\n[2] Graceful Shutdown Steps:")
    steps = [
        "1. SIGTERM received",
        "2. Mark health.set(NOT_SERVING)",
        "3. Wait ~5s for LB deregistration",
        "4. server.stop(grace=30) — drain in-flight",
        "5. Container exits clean (exit code 0)",
    ]
    for step in steps:
        print(f"  {step}")

    print("\n[3] mTLS Setup:")
    print("  - Server: ssl_server_credentials(require_client_auth=True)")
    print("  - Client: ssl_channel_credentials(client_cert + key)")
    print("  - Both verify each other via CA-signed certs")

    await demo_retry_with_backoff()
    await demo_circuit_breaker()
    await demo_idempotency()
    await demo_bulkhead()
    await demo_oauth2()

    print("\n[Q&A Summary]")
    for q, a in GRPC_PRODUCTION_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  server.py        → grpc.aio.server() + Health service + graceful shutdown")
    print("  interceptors.py  → JWT + Logging + Retry interceptors")
    print("  client.py        → Channel + interceptors + token provider")
    print("  certs/           → CA + server.crt + client.crt for mTLS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
