"""
Microservices — API Gateway & Service Communication Patterns
Standalone runnable demo — koi external service nahi chahiye

Usage:
  python 02_api_gateway_service_comm.py gateway
  python 02_api_gateway_service_comm.py service_client
  python 02_api_gateway_service_comm.py events
  python 02_api_gateway_service_comm.py docker_compose
  python 02_api_gateway_service_comm.py all
"""

import asyncio
import json
import random
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

# ──────────────────────────────────────────────────────────────
# SECTION 1 — API GATEWAY (FastAPI-based, mock downstream)
# ──────────────────────────────────────────────────────────────

def demo_api_gateway():
    """
    FastAPI API Gateway demo:
    - JWT auth at gateway
    - Routing by path prefix
    - Correlation ID injection
    - In-memory rate limiting
    - Health check aggregation
    - Timeout / connection error handling
    """
    print("\n" + "=" * 60)
    print("DEMO 1: API Gateway Patterns")
    print("=" * 60)

    # ── JWT helpers ────────────────────────────────────────────
    try:
        import jwt as pyjwt
        JWT_AVAILABLE = True
    except ImportError:
        JWT_AVAILABLE = False

    SECRET_KEY = "gateway-secret-key-do-not-expose"

    def create_token(user_id: int, role: str = "user") -> str:
        if not JWT_AVAILABLE:
            return f"mock-token-{user_id}"
        payload = {
            "sub":  str(user_id),
            "role": role,
            "exp":  datetime.utcnow() + timedelta(hours=1),
        }
        return pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")

    def verify_token(token: str) -> dict:
        if not JWT_AVAILABLE:
            if token.startswith("mock-token-"):
                return {"sub": token.split("-")[-1], "role": "user"}
            raise ValueError("Invalid mock token")
        try:
            return pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except pyjwt.InvalidTokenError:
            raise ValueError("Invalid token")

    # ── Rate Limiter (in-memory, sliding window) ───────────────
    class RateLimiter:
        def __init__(self, limit: int = 10, window_seconds: int = 60):
            self.limit = limit
            self.window = window_seconds
            self._store: dict = defaultdict(list)

        def is_allowed(self, client_id: str) -> bool:
            now = time.time()
            # Purane entries clean karo
            self._store[client_id] = [
                t for t in self._store[client_id] if now - t < self.window
            ]
            if len(self._store[client_id]) >= self.limit:
                return False
            self._store[client_id].append(now)
            return True

        def remaining(self, client_id: str) -> int:
            now = time.time()
            recent = [t for t in self._store[client_id] if now - t < self.window]
            return max(0, self.limit - len(recent))

    # ── Mock downstream services ───────────────────────────────
    class MockService:
        """Real HTTP call ki jagah — mock downstream response"""

        def __init__(self, name: str, healthy: bool = True, delay_ms: int = 50):
            self.name = name
            self.healthy = healthy
            self.delay_ms = delay_ms

        async def handle(self, path: str, method: str, body: dict = None) -> dict:
            await asyncio.sleep(self.delay_ms / 1000)
            if not self.healthy:
                raise ConnectionError(f"{self.name} is down!")
            return {
                "service":     self.name,
                "path":        path,
                "method":      method,
                "data":        {"mock": True, "timestamp": datetime.now().isoformat()},
                "request_body": body,
            }

    # ── Gateway core ───────────────────────────────────────────
    class APIGateway:
        def __init__(self):
            self.services: dict[str, MockService] = {
                "users":    MockService("user-service",    healthy=True,  delay_ms=30),
                "products": MockService("product-service", healthy=True,  delay_ms=20),
                "orders":   MockService("order-service",   healthy=False, delay_ms=100),  # orders down!
            }
            self.rate_limiter = RateLimiter(limit=5, window_seconds=60)

        async def handle_request(
            self,
            path: str,
            method: str,
            headers: dict,
            body: dict = None,
            client_ip: str = "127.0.0.1",
        ) -> dict:
            """
            Gateway request processing pipeline:
            1. Rate limit check
            2. JWT verify
            3. Service routing
            4. Correlation ID inject
            5. Forward to downstream
            6. Error handling
            """
            # Step 1: Rate limit
            if not self.rate_limiter.is_allowed(client_ip):
                return {
                    "status":  429,
                    "error":   "Too Many Requests",
                    "message": f"Rate limit exceeded. Max {self.rate_limiter.limit} req/min",
                }

            # Step 2: JWT verify
            token = headers.get("Authorization", "")
            try:
                user_payload = verify_token(token)
            except ValueError as e:
                return {"status": 401, "error": "Unauthorized", "message": str(e)}

            # Step 3: Route parsing — /users/123 → service=users, path=123
            parts = path.strip("/").split("/", 1)
            service_name = parts[0] if parts else ""
            service_path = parts[1] if len(parts) > 1 else ""

            if service_name not in self.services:
                return {
                    "status":  404,
                    "error":   "Not Found",
                    "message": f"Service '{service_name}' not registered",
                    "available": list(self.services.keys()),
                }

            # Step 4: Correlation ID
            correlation_id = headers.get("X-Request-ID", str(uuid.uuid4()))
            enriched_headers = {
                **headers,
                "X-Request-ID":  correlation_id,
                "X-User-ID":     user_payload.get("sub", ""),
                "X-User-Role":   user_payload.get("role", "user"),
                "X-Gateway":     "python-gateway-v1",
            }

            # Step 5: Forward to downstream service
            service = self.services[service_name]
            try:
                result = await asyncio.wait_for(
                    service.handle(f"/{service_path}", method, body),
                    timeout=10.0
                )
                return {
                    "status":         200,
                    "correlation_id": correlation_id,
                    "data":           result,
                    "rate_limit_remaining": self.rate_limiter.remaining(client_ip),
                }
            except asyncio.TimeoutError:
                return {
                    "status":         504,
                    "error":          "Gateway Timeout",
                    "correlation_id": correlation_id,
                    "message":        f"{service_name} service did not respond in time",
                }
            except ConnectionError as e:
                return {
                    "status":         502,
                    "error":          "Bad Gateway",
                    "correlation_id": correlation_id,
                    "message":        str(e),
                }

        async def health_check(self) -> dict:
            """Sab services ka health check karo"""
            results = {}
            for name, svc in self.services.items():
                try:
                    await asyncio.wait_for(svc.handle("/health", "GET"), timeout=3.0)
                    results[name] = "up"
                except Exception:
                    results[name] = "down"
            overall = "healthy" if all(v == "up" for v in results.values()) else "degraded"
            return {"overall": overall, "services": results}

    # ── Run gateway demo ───────────────────────────────────────
    async def run_gateway_demo():
        gateway = APIGateway()
        token = create_token(user_id=42, role="admin")

        print("\n[1] Valid request — GET /users/profile")
        resp = await gateway.handle_request(
            path="/users/profile",
            method="GET",
            headers={"Authorization": token},
            client_ip="10.0.0.1",
        )
        print(f"    Status: {resp['status']} | Correlation ID: {resp.get('correlation_id','')[:8]}...")
        print(f"    Service: {resp.get('data', {}).get('service', 'N/A')}")

        print("\n[2] Request without auth token")
        resp = await gateway.handle_request(
            path="/products/123",
            method="GET",
            headers={},
            client_ip="10.0.0.2",
        )
        print(f"    Status: {resp['status']} | Error: {resp.get('message')}")

        print("\n[3] Down service — POST /orders/create")
        resp = await gateway.handle_request(
            path="/orders/create",
            method="POST",
            headers={"Authorization": token},
            body={"product_id": 5, "quantity": 2},
            client_ip="10.0.0.1",
        )
        print(f"    Status: {resp['status']} | Error: {resp.get('message')}")

        print("\n[4] Unknown service")
        resp = await gateway.handle_request(
            path="/payments/charge",
            method="POST",
            headers={"Authorization": token},
            client_ip="10.0.0.1",
        )
        print(f"    Status: {resp['status']} | Available: {resp.get('available')}")

        print("\n[5] Rate limit demo — 6 rapid requests (limit=5)")
        for i in range(6):
            resp = await gateway.handle_request(
                path="/products/list",
                method="GET",
                headers={"Authorization": token},
                client_ip="10.0.0.99",
            )
            status = resp["status"]
            remaining = resp.get("rate_limit_remaining", "N/A")
            label = "BLOCKED" if status == 429 else f"OK (remaining: {remaining})"
            print(f"    Request {i+1}: {status} → {label}")

        print("\n[6] Health check — sab services ka status")
        health = await gateway.health_check()
        print(f"    Overall: {health['overall'].upper()}")
        for svc, status in health["services"].items():
            icon = "✓" if status == "up" else "✗"
            print(f"    {icon} {svc}: {status}")

    asyncio.run(run_gateway_demo())


# ──────────────────────────────────────────────────────────────
# SECTION 2 — INTERNAL SERVICE CLIENT (Circuit Breaker + Retry)
# ──────────────────────────────────────────────────────────────

def demo_service_client():
    """
    InternalServiceClient demo:
    - Retry with exponential backoff
    - Circuit breaker (closed/open/half-open)
    - Service token auth headers
    - Correlation ID propagation
    """
    print("\n" + "=" * 60)
    print("DEMO 2: Service Client — Circuit Breaker + Retry")
    print("=" * 60)

    class CircuitBreakerError(Exception):
        pass

    class InternalServiceClient:
        """
        Service-to-service HTTP client.
        Production mein httpx use hoga — yahan asyncio mock hai.
        """

        def __init__(self, service_name: str, base_url: str):
            self.service_name   = service_name
            self.base_url       = base_url
            self._failure_count = 0
            self._last_failure_time: Optional[float] = None
            self._state         = "closed"   # closed | open | half-open
            self._half_open_calls = 0

            # Service-to-service JWT (real code mein create_service_token() se aata)
            self._service_token = f"service-token-{service_name}"

        def _get_headers(self, correlation_id: str = "") -> dict:
            return {
                "Authorization":  f"Bearer {self._service_token}",
                "X-Service-Name": self.service_name,
                "X-Request-ID":   correlation_id or str(uuid.uuid4()),
                "Content-Type":   "application/json",
            }

        def _check_circuit(self):
            """Circuit state check karo"""
            if self._state == "open":
                elapsed = time.time() - (self._last_failure_time or 0)
                if elapsed > 10:  # demo: 10s (production: 30-60s)
                    self._state = "half-open"
                    self._half_open_calls = 0
                    print(f"    [CB] {self.service_name}: OPEN → HALF-OPEN (testing...)")
                else:
                    raise CircuitBreakerError(
                        f"Circuit OPEN for {self.service_name} "
                        f"— retry after {10 - elapsed:.1f}s"
                    )

        def _record_success(self):
            if self._state == "half-open":
                self._half_open_calls += 1
                if self._half_open_calls >= 2:
                    self._state = "closed"
                    self._failure_count = 0
                    print(f"    [CB] {self.service_name}: HALF-OPEN → CLOSED (recovered!)")
            else:
                self._failure_count = 0

        def _record_failure(self):
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= 3:  # demo: 3 (production: 5)
                self._state = "open"
                print(f"    [CB] {self.service_name}: threshold hit → OPEN (fast-fail mode)")

        async def get(self, path: str, retries: int = 3) -> dict:
            """GET with retry + circuit breaker"""
            self._check_circuit()

            correlation_id = str(uuid.uuid4())

            for attempt in range(retries):
                try:
                    # Simulate HTTP call — real code mein httpx.AsyncClient
                    result = await self._mock_http_get(path)
                    self._record_success()
                    return result

                except CircuitBreakerError:
                    raise  # circuit open hai — reraise immediately, no retry

                except Exception as e:
                    if attempt == retries - 1:
                        # Last attempt failed
                        self._record_failure()
                        raise

                    wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                    print(f"    Attempt {attempt+1} failed → retrying in {wait}s...")
                    await asyncio.sleep(wait)

        async def _mock_http_get(self, path: str) -> dict:
            """Mock downstream call — real code mein httpx"""
            await asyncio.sleep(0.01)
            # Simulate intermittent failure for demo
            if hasattr(self, "_force_fail") and self._force_fail:
                raise ConnectionError(f"Cannot connect to {self.service_name}")
            return {"service": self.service_name, "path": path, "data": {"id": 1}}

    # ── Demo scenarios ─────────────────────────────────────────
    async def run_service_client_demo():
        print("\n[1] Normal service calls — inventory service")
        inventory = InternalServiceClient("inventory-service", "http://inventory-service:8002")

        for i in range(3):
            result = await inventory.get(f"/api/stock/{i+1}")
            print(f"    GET /api/stock/{i+1} → {result['data']}")

        print("\n[2] Circuit breaker demo — simulate failures")
        payment = InternalServiceClient("payment-service", "http://payment-service:8004")
        payment._force_fail = True  # Force failures

        for i in range(5):
            try:
                await payment.get("/api/charge", retries=1)  # quick fail
            except CircuitBreakerError as e:
                print(f"    Call {i+1}: CIRCUIT OPEN — {e}")
            except Exception as e:
                print(f"    Call {i+1}: Error ({type(e).__name__}) — failure count: {payment._failure_count}")

        print(f"\n    Circuit state: {payment._state.upper()}")
        print(f"    Failure count: {payment._failure_count}")

        print("\n[3] Multiple services concurrently")
        user_client    = InternalServiceClient("user-service",    "http://user-service:8001")
        product_client = InternalServiceClient("product-service", "http://product-service:8002")

        # Parallel calls — await asyncio.gather
        user_task    = user_client.get("/api/users/42")
        product_task = product_client.get("/api/products/100")

        user_resp, product_resp = await asyncio.gather(user_task, product_task)
        print(f"    User Service:    {user_resp['service']} → path: {user_resp['path']}")
        print(f"    Product Service: {product_resp['service']} → path: {product_resp['path']}")

    asyncio.run(run_service_client_demo())


# ──────────────────────────────────────────────────────────────
# SECTION 3 — ASYNC EVENT-DRIVEN COMMUNICATION
# ──────────────────────────────────────────────────────────────

def demo_event_publishing():
    """
    Event-driven service communication demo.
    In-memory asyncio.Queue = RabbitMQ ka mock.

    Services:
      Order Service    → publishes  "order.placed"
      Inventory Service → subscribes "order.placed"  → stock decrement
      Email Service    → subscribes "order.placed"  → confirmation email
      Analytics Service → subscribes "order.*"       → all order events
    """
    print("\n" + "=" * 60)
    print("DEMO 3: Async Event-Driven Communication")
    print("=" * 60)

    # Shared event bus (RabbitMQ / Kafka ka mock)
    event_bus: asyncio.Queue = asyncio.Queue()
    processed_events: list = []

    async def publish_event(event_type: str, payload: dict, source: str):
        """Event publish karo — caller wait nahi karta"""
        event = {
            "event_id":   str(uuid.uuid4())[:8],
            "event_type": event_type,
            "payload":    payload,
            "timestamp":  datetime.now().isoformat(),
            "source":     source,
        }
        await event_bus.put(event)
        print(f"  [PUBLISH]  {source} → '{event_type}' (id: {event['event_id']})")

    # ── Order Service ──────────────────────────────────────────
    async def order_service_place_order(order_data: dict) -> dict:
        order = {
            **order_data,
            "id":         random.randint(1000, 9999),
            "status":     "placed",
            "created_at": datetime.now().isoformat(),
        }
        print(f"\n  [ORDER SVC]  Creating order {order['id']} "
              f"(user={order_data['user_id']}, product={order_data['product_id']})")

        # Publish event — no direct HTTP call to inventory or email
        await publish_event(
            event_type="order.placed",
            payload=order,
            source="order-service",
        )
        return order

    async def order_service_cancel_order(order_id: int) -> dict:
        print(f"\n  [ORDER SVC]  Cancelling order {order_id}")
        await publish_event(
            event_type="order.cancelled",
            payload={"order_id": order_id, "reason": "user_requested"},
            source="order-service",
        )
        return {"order_id": order_id, "status": "cancelled"}

    # ── Inventory Service (subscriber) ────────────────────────
    async def inventory_service_listener():
        """order.placed events sunti hai — stock ghatao"""
        while True:
            event = await event_bus.get()
            # Routing key match — only order.placed
            if event["event_type"] == "order.placed":
                order = event["payload"]
                print(f"  [INVENTORY] Stock -2 for product {order['product_id']} "
                      f"(order {order['id']}) ✓")
                processed_events.append(("inventory", event["event_id"]))
            elif event["event_type"] == "order.cancelled":
                print(f"  [INVENTORY] Stock +2 restored "
                      f"(order {event['payload']['order_id']}) ✓")
                processed_events.append(("inventory-restore", event["event_id"]))
            else:
                # Unknown event — requeue for other listeners
                await event_bus.put(event)
            event_bus.task_done()

    # ── Email Service (subscriber) ────────────────────────────
    async def email_service_listener():
        """order.placed events sunti hai — confirmation email bhejo"""
        await asyncio.sleep(0.05)  # small offset to avoid competing with inventory
        while True:
            try:
                event = await asyncio.wait_for(event_bus.get(), timeout=2.0)
                if event["event_type"] == "order.placed":
                    order = event["payload"]
                    print(f"  [EMAIL SVC] Confirmation sent to user {order['user_id']} "
                          f"(order {order['id']}) ✉")
                    processed_events.append(("email", event["event_id"]))
                else:
                    await event_bus.put(event)
                event_bus.task_done()
            except asyncio.TimeoutError:
                break  # No more events

    # ── Analytics Service (subscriber) ────────────────────────
    async def analytics_service_listener():
        """order.* events sab sunti hai — metrics record karo"""
        await asyncio.sleep(0.1)  # offset
        while True:
            try:
                event = await asyncio.wait_for(event_bus.get(), timeout=2.0)
                if event["event_type"].startswith("order."):
                    print(f"  [ANALYTICS] Event '{event['event_type']}' recorded "
                          f"(id: {event['event_id']}) 📊")
                    processed_events.append(("analytics", event["event_id"]))
                else:
                    await event_bus.put(event)
                event_bus.task_done()
            except asyncio.TimeoutError:
                break

    # ── Run event flow simulation ──────────────────────────────
    async def simulate_event_flow():
        print("\n  Starting services (listeners)...")

        # Ek separate event bus per subscriber hona chahiye (production mein)
        # Yahan demo ke liye — sequential processing
        print("  Note: Demo uses sequential event queues for clarity\n")

        # Place orders one by one aur listeners ko separately run karo
        orders = []
        for i in range(3):
            order = await order_service_place_order({
                "product_id": i + 1,
                "user_id":    100 + i,
                "quantity":   2,
                "amount":     (i + 1) * 1500,
            })
            orders.append(order)
            await asyncio.sleep(0.1)

        print("\n  Processing events through subscribers...")

        # Drain the queue through each subscriber
        # (In real system: each subscriber has its own queue binding)
        temp_events = []
        while not event_bus.empty():
            temp_events.append(await event_bus.get())
            event_bus.task_done()

        # Inventory processes all
        for event in temp_events:
            if event["event_type"] == "order.placed":
                order = event["payload"]
                print(f"  [INVENTORY] Stock -2 for product {order['product_id']} "
                      f"(order {order['id']}) ✓")
                processed_events.append(("inventory", event["event_id"]))

        # Email processes all
        for event in temp_events:
            if event["event_type"] == "order.placed":
                order = event["payload"]
                print(f"  [EMAIL SVC] Confirmation sent to user {order['user_id']} "
                      f"(order {order['id']}) ✉")
                processed_events.append(("email", event["event_id"]))

        # Analytics processes all
        for event in temp_events:
            if event["event_type"].startswith("order."):
                print(f"  [ANALYTICS] Event '{event['event_type']}' recorded "
                      f"(id: {event['event_id']}) 📊")
                processed_events.append(("analytics", event["event_id"]))

        # Cancel one order
        await order_service_cancel_order(orders[0]["id"])
        cancel_events = []
        while not event_bus.empty():
            cancel_events.append(await event_bus.get())
            event_bus.task_done()
        for event in cancel_events:
            if event["event_type"] == "order.cancelled":
                print(f"  [INVENTORY] Stock +2 restored "
                      f"(order {event['payload']['order_id']}) ✓")
                print(f"  [ANALYTICS] Cancellation recorded 📊")

        print(f"\n  Total events processed: {len(processed_events)}")
        print("  Loose coupling achieved — services never called each other directly!")

    asyncio.run(simulate_event_flow())


# ──────────────────────────────────────────────────────────────
# SECTION 4 — DOCKER COMPOSE CONFIG GENERATOR
# ──────────────────────────────────────────────────────────────

def demo_docker_compose_config():
    """
    Complete docker-compose.yml for microservices setup:
    - api-gateway
    - user-service, product-service, order-service, payment-service
    - Per-service PostgreSQL databases
    - Shared Redis
    - RabbitMQ for async events
    """
    print("\n" + "=" * 60)
    print("DEMO 4: Docker Compose — Multi-Service Configuration")
    print("=" * 60)

    compose_config = """
version: '3.8'

# ============================================================
# Network: sab services ek private network pe hain
# Service names = DNS hostnames (Docker automatic resolution)
# ============================================================

networks:
  microservices-net:
    driver: bridge

# ============================================================
# Volumes: persistent data
# ============================================================

volumes:
  users_db_data:
  products_db_data:
  orders_db_data:
  payments_db_data:
  redis_data:
  rabbitmq_data:

services:

  # ──────────────────────────────────────────────────────────
  # API GATEWAY — single entry point for all clients
  # ──────────────────────────────────────────────────────────
  api-gateway:
    build:
      context: ./gateway
      dockerfile: Dockerfile
    image: myapp/api-gateway:latest
    ports:
      - "8000:8000"   # only this port is exposed to outside
    environment:
      - APP_ENV=production
      # Service discovery — Docker DNS handles resolution
      - USER_SERVICE_URL=http://user-service:8001
      - PRODUCT_SERVICE_URL=http://product-service:8002
      - ORDER_SERVICE_URL=http://order-service:8003
      - PAYMENT_SERVICE_URL=http://payment-service:8004
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=change-this-in-production
      - RATE_LIMIT_PER_MINUTE=100
    depends_on:
      - user-service
      - product-service
      - order-service
      - redis
    networks:
      - microservices-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ──────────────────────────────────────────────────────────
  # USER SERVICE — registration, login, profiles
  # ──────────────────────────────────────────────────────────
  user-service:
    build: ./user-service
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:userpass@users-db:5432/users_db
      - REDIS_URL=redis://redis:6379/1
      - JWT_SECRET=change-this-in-production
      - SERVICE_NAME=user-service
      - SERVICE_TOKEN=user-service-internal-token
    depends_on:
      users-db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - microservices-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  # ──────────────────────────────────────────────────────────
  # PRODUCT SERVICE — catalog, inventory, search
  # ──────────────────────────────────────────────────────────
  product-service:
    build: ./product-service
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://user:productpass@products-db:5432/products_db
      - REDIS_URL=redis://redis:6379/2    # separate DB index
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
      - SERVICE_NAME=product-service
      - SERVICE_TOKEN=product-service-internal-token
    depends_on:
      products-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - microservices-net
    restart: unless-stopped

  # ──────────────────────────────────────────────────────────
  # ORDER SERVICE — order lifecycle management
  # ──────────────────────────────────────────────────────────
  order-service:
    build: ./order-service
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql://user:orderpass@orders-db:5432/orders_db
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
      # Internal service calls (service discovery via Docker DNS)
      - PRODUCT_SERVICE_URL=http://product-service:8002
      - PAYMENT_SERVICE_URL=http://payment-service:8004
      - SERVICE_NAME=order-service
      - SERVICE_TOKEN=order-service-internal-token
    depends_on:
      orders-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - microservices-net
    restart: unless-stopped

  # ──────────────────────────────────────────────────────────
  # PAYMENT SERVICE — payment processing
  # ──────────────────────────────────────────────────────────
  payment-service:
    build: ./payment-service
    ports:
      - "8004:8004"
    environment:
      - DATABASE_URL=postgresql://user:paymentpass@payments-db:5432/payments_db
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
      - STRIPE_KEY=sk_test_xxxx   # real key: docker secret / vault
      - SERVICE_NAME=payment-service
      - SERVICE_TOKEN=payment-service-internal-token
    depends_on:
      payments-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - microservices-net
    restart: unless-stopped

  # ──────────────────────────────────────────────────────────
  # DATABASES — per-service (no shared DB!)
  # ──────────────────────────────────────────────────────────
  users-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB:       users_db
      POSTGRES_USER:     user
      POSTGRES_PASSWORD: userpass
    volumes:
      - users_db_data:/var/lib/postgresql/data
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d users_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  products-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB:       products_db
      POSTGRES_USER:     user
      POSTGRES_PASSWORD: productpass
    volumes:
      - products_db_data:/var/lib/postgresql/data
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d products_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  orders-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB:       orders_db
      POSTGRES_USER:     user
      POSTGRES_PASSWORD: orderpass
    volumes:
      - orders_db_data:/var/lib/postgresql/data
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d orders_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  payments-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB:       payments_db
      POSTGRES_USER:     user
      POSTGRES_PASSWORD: paymentpass
    volumes:
      - payments_db_data:/var/lib/postgresql/data
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d payments_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ──────────────────────────────────────────────────────────
  # REDIS — caching, sessions, rate limiting
  # Shared across services — alag DB indices use karo
  # ──────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    networks:
      - microservices-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # ──────────────────────────────────────────────────────────
  # RABBITMQ — async event bus
  # Services publish/subscribe to events here
  # Management UI: http://localhost:15672 (guest/guest)
  # ──────────────────────────────────────────────────────────
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"     # AMQP protocol
      - "15672:15672"   # Management Web UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
      RABBITMQ_DEFAULT_VHOST: /
    networks:
      - microservices-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
      interval: 30s
      timeout: 10s
      retries: 5
"""

    print(compose_config)

    print("\n" + "-" * 60)
    print("Service Discovery Explanation:")
    print("-" * 60)

    discovery_notes = {
        "order-service calling product-service": "http://product-service:8002/api/products/123",
        "gateway calling user-service":          "http://user-service:8001/api/users/me",
        "order-service calling rabbitmq":         "amqp://guest:guest@rabbitmq:5672/",
        "any service calling redis":              "redis://redis:6379/0",
    }

    for caller, url in discovery_notes.items():
        print(f"  {caller}:")
        print(f"    → {url}")
        print(f"    (Docker DNS resolves service name → container IP automatically)")
        print()

    print("Start commands:")
    print("  docker-compose up --build          # sab services start")
    print("  docker-compose up user-service     # sirf ek service")
    print("  docker-compose logs -f order-service  # logs tail karo")
    print("  docker-compose ps                  # running services")
    print("  docker-compose down -v             # sab band + volumes delete")


# ──────────────────────────────────────────────────────────────
# MAIN — sys.argv dispatcher
# ──────────────────────────────────────────────────────────────

def main():
    demos = {
        "gateway":        demo_api_gateway,
        "service_client": demo_service_client,
        "events":         demo_event_publishing,
        "docker_compose": demo_docker_compose_config,
    }

    usage = (
        "\nUsage:\n"
        "  python 02_api_gateway_service_comm.py gateway\n"
        "  python 02_api_gateway_service_comm.py service_client\n"
        "  python 02_api_gateway_service_comm.py events\n"
        "  python 02_api_gateway_service_comm.py docker_compose\n"
        "  python 02_api_gateway_service_comm.py all\n"
    )

    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "all":
        for name, fn in demos.items():
            fn()
    elif arg in demos:
        demos[arg]()
    else:
        print(f"Unknown demo: '{arg}'{usage}")
        sys.exit(1)


if __name__ == "__main__":
    main()
