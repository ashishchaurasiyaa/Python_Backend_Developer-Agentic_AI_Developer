# Lecture 3 — Practical Hands-On: Reactive Principles

> **Theory file:** [03_Reactive_Principles.md](03_Reactive_Principles.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Reactive system implementations:

1. ✅ **Async/non-blocking** FastAPI service
2. ✅ **Reactive streams** with backpressure
3. ✅ **Supervision tree** with auto-restart
4. ✅ **Circuit breaker** + bulkhead
5. ✅ **Elastic auto-scaling** with K8s HPA
6. ✅ **Back pressure** demo
7. ✅ **Actor model** in Python
8. ✅ **Graceful degradation** patterns
9. ✅ **Reactive observability**
10. ✅ **Real-time dashboard** end-to-end

By end: aap **production reactive system** bana sakte ho.

---

## 1. Project Structure

```
reactive_demo/
├── docker-compose.yml
├── README.md
│
├── responsiveness/
│   ├── async_api.py
│   ├── timeout_fallback.py
│   └── graceful_degradation.py
│
├── resilience/
│   ├── supervision_tree.py
│   ├── actor_model.py
│   ├── circuit_breaker.py
│   └── bulkhead.py
│
├── elasticity/
│   ├── stateless_service.py
│   ├── kubernetes/
│   │   └── hpa.yaml
│   └── load_test.py
│
├── message_driven/
│   ├── back_pressure.py
│   ├── reactive_streams.py
│   └── pub_sub.py
│
├── observability/
│   └── reactive_metrics.py
│
└── end_to_end/
    └── real_time_dashboard.py
```

---

## 2. Setup

```bash
pip install fastapi uvicorn
pip install asyncio
pip install pyakka                  # Actor model
pip install rx                       # Reactive extensions
pip install httpx
pip install aiokafka
pip install prometheus-client
```

---

## 3. ⚡ Responsiveness Pattern

### `responsiveness/async_api.py`

```python
"""
Non-blocking async API with FastAPI.
Each request handled on event loop, not threads.
"""
from fastapi import FastAPI, HTTPException
import asyncio
import httpx
import time

app = FastAPI()

# ─────────────────────────────────────────────────────────────
# ASYNC ENDPOINT - thousands of concurrent connections!
# ─────────────────────────────────────────────────────────────
@app.get("/profile/{user_id}")
async def get_profile(user_id: int):
    """
    Fully async:
    - Doesn't block thread while waiting
    - Can handle 10,000+ concurrent requests
    - On single CPU core!
    """
    async with httpx.AsyncClient(timeout=2.0) as client:
        # Parallel async calls
        user_task = client.get(f"http://user-svc/users/{user_id}")
        orders_task = client.get(f"http://order-svc/users/{user_id}/orders")
        prefs_task = client.get(f"http://prefs-svc/users/{user_id}")
        
        # await all simultaneously
        user, orders, prefs = await asyncio.gather(
            user_task, orders_task, prefs_task,
            return_exceptions=True,
        )
    
    return {
        "user": user.json() if not isinstance(user, Exception) else None,
        "orders": orders.json() if not isinstance(orders, Exception) else [],
        "prefs": prefs.json() if not isinstance(prefs, Exception) else {},
    }
```

### `responsiveness/timeout_fallback.py`

```python
"""
Always respond - timeout + fallback pattern.
"""
import asyncio
import httpx
from typing import Optional

async def call_with_timeout_fallback(
    primary_url: str,
    fallback_data: dict,
    timeout: float = 1.0,
) -> dict:
    """
    Try primary, fall back to cached/default on timeout.
    NEVER hang the user.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(primary_url)
            response.raise_for_status()
            return response.json()
    except (httpx.TimeoutException, httpx.HTTPError):
        # Quick fallback (responsive!)
        print(f"[FALLBACK] Using cached data for {primary_url}")
        return fallback_data

# Real usage
async def get_recommendations(user_id: int):
    return await call_with_timeout_fallback(
        primary_url=f"http://ml-service/recommend/{user_id}",
        fallback_data={"recommendations": ["popular-item-1", "popular-item-2"]},
        timeout=0.5,  # 500ms max
    )
```

### `responsiveness/graceful_degradation.py`

```python
"""
Graceful degradation: better partial UI than nothing.
"""
from fastapi import FastAPI

app = FastAPI()

@app.get("/dashboard")
async def dashboard(user_id: int):
    """Fetch all components in parallel, fail gracefully"""
    async def safe_call(coro, fallback):
        try:
            return await coro
        except Exception as e:
            print(f"Component failed: {e}")
            return fallback
    
    user, orders, recs, notifs, analytics = await asyncio.gather(
        safe_call(fetch_user(user_id), fallback={"name": "User", "avatar": None}),
        safe_call(fetch_orders(user_id), fallback=[]),
        safe_call(fetch_recommendations(user_id), fallback=[]),  # ML can fail, OK
        safe_call(fetch_notifications(user_id), fallback=[]),
        safe_call(fetch_analytics(user_id), fallback=None),       # Non-critical
    )
    
    # Always returns a usable dashboard, even if parts failed
    return {
        "user": user,
        "orders": orders,
        "recommendations": recs,
        "notifications": notifs,
        "analytics": analytics,  # Frontend hides section if None
        "_degraded": any(x in [None, []] for x in [recs, analytics]),
    }
```

---

## 4. 🛡 Resilience Patterns

### `resilience/supervision_tree.py`

```python
"""
Supervision tree - actors that monitor and restart on failure.
Inspired by Erlang/Akka.
"""
import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

class SupervisionStrategy(Enum):
    RESTART = "restart"       # Restart failed child
    STOP = "stop"             # Stop failed child
    ESCALATE = "escalate"     # Escalate to parent

class Worker:
    """Worker that supervisor watches"""
    
    def __init__(self, name: str, task: Callable[[], Awaitable[None]]):
        self.name = name
        self.task = task
        self.is_running = False
        self.restart_count = 0
        self._task: Optional[asyncio.Task] = None
    
    async def start(self, supervisor):
        self.is_running = True
        while self.is_running:
            try:
                await self.task()
                # Task completed normally
                if self.is_running:
                    logger.info(f"[{self.name}] Completed naturally, restarting")
                    self.restart_count += 1
                    await asyncio.sleep(0.5)  # Backoff
            
            except Exception as e:
                logger.error(f"[{self.name}] Failed: {e}")
                # Ask supervisor what to do
                strategy = supervisor.handle_failure(self, e)
                
                if strategy == SupervisionStrategy.RESTART:
                    self.restart_count += 1
                    logger.info(f"[{self.name}] Restarting (attempt #{self.restart_count})")
                    await asyncio.sleep(min(2 ** self.restart_count, 30))
                    continue
                
                elif strategy == SupervisionStrategy.STOP:
                    self.is_running = False
                    break
                
                elif strategy == SupervisionStrategy.ESCALATE:
                    raise
    
    def stop(self):
        self.is_running = False

class Supervisor:
    """Supervisor managing workers"""
    
    def __init__(self, name: str, max_restarts: int = 5):
        self.name = name
        self.max_restarts = max_restarts
        self.workers: list[Worker] = []
    
    def supervise(self, worker: Worker):
        self.workers.append(worker)
    
    def handle_failure(self, worker: Worker, error: Exception) -> SupervisionStrategy:
        """Decide what to do when child fails"""
        if worker.restart_count >= self.max_restarts:
            logger.warning(f"[{self.name}] {worker.name} exceeded max restarts → STOP")
            return SupervisionStrategy.STOP
        
        if isinstance(error, ValueError):
            # Bad data - won't recover
            return SupervisionStrategy.STOP
        
        # Transient failure - retry
        return SupervisionStrategy.RESTART
    
    async def run(self):
        """Start all workers"""
        await asyncio.gather(*[w.start(self) for w in self.workers])

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
import random

async def flaky_worker_task():
    """Simulates a worker that sometimes fails"""
    print("Working...")
    await asyncio.sleep(1)
    
    if random.random() < 0.3:
        raise ConnectionError("Network blip")
    
    print("Work done!")

async def main():
    supervisor = Supervisor("main", max_restarts=5)
    
    # Multiple workers under supervision
    for i in range(3):
        supervisor.supervise(Worker(f"worker-{i}", flaky_worker_task))
    
    await supervisor.run()

asyncio.run(main())
```

### `resilience/actor_model.py`

```python
"""
Simple actor model implementation.
Each actor:
- Has private state
- Processes messages one at a time (no concurrent state access)
- Communicates only via messages
"""
import asyncio
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class Message:
    sender: Any
    content: dict

class Actor:
    """Base actor class"""
    
    def __init__(self, name: str):
        self.name = name
        self.mailbox: asyncio.Queue = asyncio.Queue()
        self.state = {}  # Private!
        self._task: asyncio.Task = None
        self.running = False
    
    async def start(self):
        self.running = True
        self._task = asyncio.create_task(self._process_messages())
    
    async def send(self, message: dict, sender=None):
        """Send message to this actor (non-blocking)"""
        await self.mailbox.put(Message(sender=sender, content=message))
    
    async def _process_messages(self):
        """Process one message at a time"""
        while self.running:
            msg = await self.mailbox.get()
            try:
                await self.receive(msg)
            except Exception as e:
                print(f"[{self.name}] Failed processing message: {e}")
                # Supervisor would handle this
    
    async def receive(self, message: Message):
        """Override in subclasses"""
        pass
    
    def stop(self):
        self.running = False

# ─────────────────────────────────────────────────────────────
# EXAMPLE: Counter actor
# ─────────────────────────────────────────────────────────────
class CounterActor(Actor):
    """Actor that maintains a counter"""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.state["count"] = 0
    
    async def receive(self, message: Message):
        action = message.content.get("action")
        
        if action == "increment":
            self.state["count"] += message.content.get("by", 1)
            print(f"[{self.name}] count = {self.state['count']}")
        
        elif action == "get":
            if message.sender:
                await message.sender.send({"count": self.state["count"]})

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
async def main():
    counter = CounterActor("counter-1")
    await counter.start()
    
    # Send messages (async, non-blocking)
    for _ in range(100):
        await counter.send({"action": "increment", "by": 1})
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Counter is automatically thread-safe!
    # No locks needed because messages processed one at a time
    print(f"Final count: {counter.state['count']}")  # 100

asyncio.run(main())
```

---

## 5. 🚢 Bulkhead Pattern

### `resilience/bulkhead.py`

```python
"""
Bulkhead - isolate resources per dependency.
"""
import asyncio
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")

class Bulkhead:
    """Limit concurrent calls per dependency"""
    
    def __init__(self, name: str, max_concurrent: int):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active = 0
        self.rejected = 0
    
    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        # Try to acquire (with timeout)
        try:
            async with asyncio.timeout(0):  # Non-blocking attempt
                await self.semaphore.acquire()
        except asyncio.TimeoutError:
            self.rejected += 1
            raise BulkheadFullError(f"Bulkhead '{self.name}' full")
        
        try:
            self.active += 1
            result = await func(*args, **kwargs)
            return result
        finally:
            self.active -= 1
            self.semaphore.release()

class BulkheadFullError(Exception):
    pass

# ─────────────────────────────────────────────────────────────
# USAGE: separate bulkheads per dependency
# ─────────────────────────────────────────────────────────────
payment_bulkhead = Bulkhead("payment", max_concurrent=50)
recommendations_bulkhead = Bulkhead("recommendations", max_concurrent=20)
inventory_bulkhead = Bulkhead("inventory", max_concurrent=100)

async def call_payment(amount):
    async def _call():
        # Actual call
        return await httpx.post(...)
    return await payment_bulkhead.call(_call)

# If payment is slow:
#    → Only 50 threads stuck
#    → 100 threads still free for inventory
#    → 20 threads still free for recommendations
#    → User can browse, just can't checkout
```

---

## 6. 📈 Elasticity — Stateless Service

### `elasticity/stateless_service.py`

```python
"""
Stateless service - easy to scale horizontally.
ALL state in external stores.
"""
from fastapi import FastAPI, Header
import redis.asyncio as redis
import asyncpg

app = FastAPI()

# External state (NOT in process)
redis_client: redis.Redis = None
db_pool: asyncpg.Pool = None

@app.on_event("startup")
async def startup():
    global redis_client, db_pool
    redis_client = redis.from_url("redis://redis:6379")
    db_pool = await asyncpg.create_pool("postgresql://app:app@postgres/app")

@app.get("/user/{user_id}/profile")
async def get_profile(user_id: int):
    # Session state from Redis (any instance can read)
    session = await redis_client.get(f"session:{user_id}")
    
    # User data from DB
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    
    return {"user": dict(user), "session": session}

# Any instance can serve any request → easy to scale
```

### Kubernetes Auto-Scaling

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 2
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  # Custom metrics
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 1000
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
```

### Load Test

```python
"""Generate load to test elasticity"""
import asyncio
import httpx
from time import time

async def make_request(client, url):
    try:
        await client.get(url, timeout=10)
    except Exception:
        pass

async def load_test(concurrent: int, duration: int):
    async with httpx.AsyncClient() as client:
        end_time = time() + duration
        request_count = 0
        
        while time() < end_time:
            tasks = [
                make_request(client, "http://localhost:8000/user/1/profile")
                for _ in range(concurrent)
            ]
            await asyncio.gather(*tasks)
            request_count += concurrent
        
        print(f"Total requests: {request_count}")
        print(f"RPS: {request_count / duration:.0f}")

# Watch K8s auto-scale:
# $ kubectl get hpa api-service -w
asyncio.run(load_test(concurrent=100, duration=300))
```

---

## 7. 📬 Back Pressure

### `message_driven/back_pressure.py`

```python
"""
Back pressure - prevent producer from overwhelming consumer.
"""
import asyncio
from asyncio import Queue

class BackpressuredQueue:
    """Bounded queue - producer blocks if full"""
    
    def __init__(self, max_size: int = 1000):
        self.queue = Queue(maxsize=max_size)
        self.dropped = 0
    
    async def produce(self, item):
        """Producer blocks if queue full"""
        try:
            # Wait if queue full (back pressure!)
            await asyncio.wait_for(self.queue.put(item), timeout=5.0)
        except asyncio.TimeoutError:
            # Optionally: drop on overflow
            self.dropped += 1
            print(f"Dropped (queue full): {item}")
    
    async def consume(self):
        return await self.queue.get()

# ─────────────────────────────────────────────────────────────
# DEMO: Slow consumer slows down fast producer
# ─────────────────────────────────────────────────────────────
queue = BackpressuredQueue(max_size=10)

async def fast_producer():
    """Tries to produce 1000/sec"""
    for i in range(10000):
        await queue.produce(f"item-{i}")
        # No sleep - tries max speed
        # But blocks when queue is full!

async def slow_consumer():
    """Only processes 10/sec"""
    while True:
        item = await queue.consume()
        await asyncio.sleep(0.1)  # Slow processing
        print(f"Processed: {item}")

async def main():
    await asyncio.gather(
        fast_producer(),
        slow_consumer(),
    )

asyncio.run(main())
# Producer naturally slows down to match consumer speed
# No queue explosion, no memory crash
```

### Reactive Streams with RxPY

```python
"""
Proper reactive streams with backpressure (Python).
"""
import asyncio
import rx
from rx import operators as ops
from rx.scheduler.eventloop import AsyncIOScheduler

async def reactive_pipeline():
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(loop=loop)
    
    # Create reactive stream
    source = rx.from_iterable(range(1000)).pipe(
        ops.map(lambda x: x * 2),
        ops.filter(lambda x: x > 100),
        ops.observe_on(scheduler),
        # Backpressure: buffer with cap
        ops.buffer_with_count(10),
    )
    
    # Subscribe
    source.subscribe(
        on_next=lambda batch: print(f"Got batch: {batch}"),
        on_error=lambda e: print(f"Error: {e}"),
        on_completed=lambda: print("Done!"),
    )
    
    # Let it run
    await asyncio.sleep(2)

asyncio.run(reactive_pipeline())
```

---

## 8. 🔄 Pub/Sub with NATS

### Lightweight, fast pub/sub

```python
"""
NATS - simple, fast, reactive messaging.
"""
import asyncio
import nats
import json

async def publisher():
    nc = await nats.connect("nats://localhost:4222")
    
    for i in range(100):
        event = {"id": i, "msg": f"hello-{i}"}
        await nc.publish("events.user.signup", json.dumps(event).encode())
        await asyncio.sleep(0.1)
    
    await nc.drain()

async def subscriber():
    nc = await nats.connect("nats://localhost:4222")
    
    async def handler(msg):
        data = json.loads(msg.data.decode())
        print(f"[Subscriber] {data}")
    
    # Subscribe with subject wildcards
    await nc.subscribe("events.user.>", cb=handler)
    
    # Run for 30 sec
    await asyncio.sleep(30)
    await nc.drain()

# Run both
async def main():
    await asyncio.gather(subscriber(), publisher())

asyncio.run(main())
```

---

## 9. 🛡 Combined Resilience: Real Service

```python
"""
Production-grade resilient API endpoint.
Combines: timeout, retry, circuit breaker, bulkhead, fallback.
"""
from fastapi import FastAPI, HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
from circuitbreaker import circuit
import httpx
import asyncio

app = FastAPI()

# Bulkheads
payment_bulkhead = asyncio.Semaphore(50)
inventory_bulkhead = asyncio.Semaphore(100)

# Circuit breaker on payment service
@circuit(failure_threshold=5, recovery_timeout=30)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=5),
)
async def call_payment(amount):
    async with httpx.AsyncClient(timeout=2.0) as client:
        async with payment_bulkhead:
            response = await client.post(
                "http://payment-service/charge",
                json={"amount": amount}
            )
            response.raise_for_status()
            return response.json()

@app.post("/checkout")
async def checkout(amount: float):
    """
    Resilient checkout:
    1. Async (non-blocking)
    2. Timeout (2s max)
    3. Retry with backoff
    4. Circuit breaker (fail fast if dead)
    5. Bulkhead (limit concurrent)
    6. Fallback (queue for later if all else fails)
    """
    try:
        result = await call_payment(amount)
        return {"status": "success", "transaction": result}
    
    except Exception as e:
        # Last resort fallback
        print(f"Payment failed: {e}, queuing for async retry")
        await queue_for_async_processing(amount)
        
        # Still respond quickly to user
        return {
            "status": "queued",
            "message": "Processing your payment...",
        }
```

---

## 10. 📊 Reactive Observability

### Metrics for Reactive Systems

```python
"""
Reactive-specific metrics with Prometheus.
"""
from prometheus_client import Counter, Histogram, Gauge

# Queue depth (back pressure indicator)
queue_depth = Gauge(
    "queue_depth",
    "Current queue depth",
    ["queue_name"]
)

# Backpressure events
backpressure_events = Counter(
    "backpressure_events_total",
    "Number of backpressure activations",
)

# Circuit breaker state
circuit_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state",
    ["service"]
)

# Bulkhead saturation
bulkhead_active = Gauge(
    "bulkhead_active_calls",
    "Active calls in bulkhead",
    ["bulkhead"]
)

bulkhead_rejected = Counter(
    "bulkhead_rejections_total",
    "Calls rejected by bulkhead",
    ["bulkhead"]
)

# Fallback usage
fallback_used = Counter(
    "fallback_used_total",
    "Times fallback was used",
    ["service"]
)

# Async task health
async_tasks_active = Gauge(
    "async_tasks_active",
    "Active async tasks"
)

# Latency under load
request_duration = Histogram(
    "request_duration_seconds",
    "Request duration",
    ["endpoint", "status"]
)
```

### Distributed Tracing

```python
"""
Trace across async boundaries.
"""
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

@app.get("/api/data")
async def get_data():
    with tracer.start_as_current_span("api.get_data") as span:
        # Span follows async calls!
        result = await call_downstream()
        span.set_attribute("result.size", len(result))
        return result

async def call_downstream():
    with tracer.start_as_current_span("downstream_call"):
        # Nested span in async context
        async with httpx.AsyncClient() as client:
            return await client.get("...")
```

---

## 11. 🎯 End-to-End: Real-Time Dashboard

### Combining All Reactive Patterns

```python
"""
Real-time dashboard - all 4 reactive pillars in action.
"""
from fastapi import FastAPI, WebSocket
import asyncio
import aiokafka
import json

app = FastAPI()

# Connected WebSocket clients (elastic - any number)
active_connections: set[WebSocket] = set()

# ─────────────────────────────────────────────────────────────
# MESSAGE-DRIVEN: Kafka consumer
# ─────────────────────────────────────────────────────────────
async def kafka_consumer_task():
    """
    Consumes events from Kafka, broadcasts to all WebSocket clients.
    Reactive: async, non-blocking, backpressure built-in.
    """
    consumer = aiokafka.AIOKafkaConsumer(
        "user_events",
        bootstrap_servers="kafka:9092",
        group_id="dashboard",
        max_poll_records=100,
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode())
            
            # Broadcast to all WebSocket clients
            disconnected = set()
            for ws in active_connections:
                try:
                    # Non-blocking send (back pressure!)
                    await asyncio.wait_for(ws.send_json(event), timeout=1.0)
                except (asyncio.TimeoutError, Exception):
                    # Slow/disconnected client - drop
                    disconnected.add(ws)
            
            # Cleanup
            active_connections.difference_update(disconnected)
    
    finally:
        await consumer.stop()

# ─────────────────────────────────────────────────────────────
# RESPONSIVE: WebSocket endpoint
# ─────────────────────────────────────────────────────────────
@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(30)
    except Exception:
        pass
    finally:
        active_connections.discard(websocket)

# ─────────────────────────────────────────────────────────────
# RESILIENT: Auto-restart on failure
# ─────────────────────────────────────────────────────────────
async def resilient_consumer():
    """Restart Kafka consumer on failure"""
    while True:
        try:
            await kafka_consumer_task()
        except Exception as e:
            print(f"Consumer crashed: {e}, restarting in 5s")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup():
    # Start consumer task in background
    asyncio.create_task(resilient_consumer())

# ─────────────────────────────────────────────────────────────
# ELASTIC: Run multiple instances, K8s auto-scales
# ─────────────────────────────────────────────────────────────
# Each instance: serves WebSockets + consumes Kafka
# K8s HPA scales based on connection count
```

### Frontend (Connect from browser)

```html
<!DOCTYPE html>
<html>
<head><title>Reactive Dashboard</title></head>
<body>
  <h1>Real-Time Events</h1>
  <div id="events"></div>
  
  <script>
    const ws = new WebSocket('ws://localhost:8000/ws/dashboard');
    
    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data);
      const div = document.createElement('div');
      div.textContent = JSON.stringify(event);
      document.getElementById('events').prepend(div);
    };
    
    // Auto-reconnect on failure (responsive!)
    ws.onclose = () => {
      setTimeout(() => location.reload(), 1000);
    };
  </script>
</body>
</html>
```

---

## 12. Key Learnings Summary

```
✅ FastAPI + asyncio = native async/reactive
✅ Supervision trees + actor model for resilience
✅ Bulkheads isolate failures
✅ Circuit breakers prevent cascading failures
✅ Bounded queues = automatic backpressure
✅ Stateless services = trivial scaling
✅ K8s HPA for elasticity
✅ Reactive observability (queue depth, lag)
✅ WebSocket + Kafka = real-time
✅ Combine ALL patterns for maximum reactivity

🎯 Production reactive stack:
   ✓ Async-first frameworks (FastAPI, Node.js)
   ✓ Message broker (Kafka, NATS)
   ✓ Stateless services
   ✓ K8s with HPA
   ✓ Circuit breakers + bulkheads
   ✓ Distributed tracing
   ✓ Backpressure throughout
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll cover **Distributed Consistency** with Saga + Outbox patterns.

> **Next lecture:** [04_Saga_Outbox_Patterns.md](04_Saga_Outbox_Patterns.md)

---

## 📚 Try It Yourself

1. Build **WebSocket-based chat** with backpressure
2. Implement **supervision tree** for worker pool
3. Add **circuit breakers** to all external calls
4. Set up **K8s HPA** based on queue depth
5. Build **reactive dashboard** with live Kafka events
