# Lecture 1 — Practical Hands-On: Sync vs Async Communication

> **Theory file:** [01_Sync_vs_Async_Communication.md](01_Sync_vs_Async_Communication.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Working examples of:

1. ✅ **REST sync** with FastAPI + httpx client
2. ✅ **gRPC sync** with Python (high performance)
3. ✅ **GraphQL sync** with Strawberry
4. ✅ **RabbitMQ async** queues with aio-pika
5. ✅ **Kafka async** event streams
6. ✅ **Webhooks async** (Stripe-style)
7. ✅ **Hybrid architecture** demo (sync API + async workers)
8. ✅ **Timeout + retry + jitter** patterns
9. ✅ **Cascading failure simulation** + protection
10. ✅ **Distributed tracing** across sync + async

By end: aap **production-grade communication patterns** ko implement kar sakte ho.

---

## 1. Project Structure

```
communication_demo/
├── docker-compose.yml
├── README.md
│
├── sync_examples/
│   ├── rest/
│   │   ├── server.py             # FastAPI REST server
│   │   └── client.py             # httpx client
│   │
│   ├── grpc/
│   │   ├── user.proto            # IDL
│   │   ├── server.py
│   │   └── client.py
│   │
│   └── graphql/
│       ├── server.py
│       └── client.py
│
├── async_examples/
│   ├── rabbitmq/
│   │   ├── producer.py
│   │   └── consumer.py
│   │
│   ├── kafka/
│   │   ├── producer.py
│   │   └── consumer.py
│   │
│   └── webhooks/
│       └── webhook_handler.py
│
├── hybrid/
│   ├── api.py                    # Sync API
│   ├── worker.py                 # Async worker
│   └── notifier.py
│
└── resilience/
    ├── timeout_retry.py
    ├── cascading_demo.py
    └── circuit_breaker_demo.py
```

---

## 2. Setup & Dependencies

```bash
pip install fastapi uvicorn httpx
pip install grpcio grpcio-tools
pip install strawberry-graphql
pip install aio-pika aiokafka
pip install tenacity backoff
```

---

## 3. ☎️ Sync Example 1: REST with FastAPI

### Server (`sync_examples/rest/server.py`)

```python
"""
REST sync server - the classic pattern.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

app = FastAPI(title="Sync REST Service")

class User(BaseModel):
    id: int
    name: str
    email: str

# Mock DB
USERS = {
    1: User(id=1, name="Ashish Chaurasiya", email="ashish@example.com"),
    2: User(id=2, name="Rahul Singh", email="rahul@example.com"),
}

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    """Synchronous endpoint - client waits for response"""
    # Simulate DB call
    await asyncio.sleep(0.05)  # 50ms processing
    
    if user_id not in USERS:
        raise HTTPException(404, "User not found")
    return USERS[user_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Client (`sync_examples/rest/client.py`)

```python
"""
Sync client - blocks waiting for response
"""
import httpx
import time

def get_user_sync(user_id: int):
    """Blocking call - waits for response"""
    print(f"[{time.strftime('%H:%M:%S')}] Sending request...")
    
    with httpx.Client(timeout=5.0) as client:
        response = client.get(f"http://localhost:8000/users/{user_id}")
    
    print(f"[{time.strftime('%H:%M:%S')}] Got response: {response.status_code}")
    return response.json()

if __name__ == "__main__":
    user = get_user_sync(1)
    print(f"User: {user}")
    
    # ── DEMONSTRATE BLOCKING BEHAVIOR ──
    print("\nMaking 5 sequential calls (blocks each time):")
    start = time.time()
    for i in range(1, 3):
        get_user_sync(i % 2 + 1)
    print(f"Total time: {time.time() - start:.2f}s")
```

### Async Sync Client (better!)

```python
"""
Even with sync semantics, we can call concurrently using asyncio
"""
import httpx
import asyncio
import time

async def get_user_concurrent(client, user_id: int):
    response = await client.get(f"http://localhost:8000/users/{user_id}")
    return response.json()

async def main():
    print("Making 5 concurrent calls:")
    start = time.time()
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # All 5 calls happen IN PARALLEL
        tasks = [get_user_concurrent(client, i % 2 + 1) for i in range(5)]
        results = await asyncio.gather(*tasks)
    
    print(f"Total time: {time.time() - start:.2f}s")  # Much faster!
    for r in results:
        print(r)

asyncio.run(main())
```

---

## 4. 🚀 Sync Example 2: gRPC (High Performance)

### Define IDL (`sync_examples/grpc/user.proto`)

```protobuf
syntax = "proto3";

package user;

service UserService {
    rpc GetUser(GetUserRequest) returns (User);
    rpc StreamUsers(StreamRequest) returns (stream User);
}

message GetUserRequest {
    int32 id = 1;
}

message User {
    int32 id = 1;
    string name = 2;
    string email = 3;
}

message StreamRequest {
    int32 limit = 1;
}
```

### Generate Python Code

```bash
$ python -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    --proto_path=. \
    user.proto

# Generates: user_pb2.py, user_pb2_grpc.py
```

### Server (`sync_examples/grpc/server.py`)

```python
"""gRPC sync server"""
import grpc
from concurrent import futures
import user_pb2
import user_pb2_grpc

USERS = {
    1: {"id": 1, "name": "Ashish Chaurasiya", "email": "ashish@example.com"},
    2: {"id": 2, "name": "Rahul Singh", "email": "rahul@example.com"},
}

class UserService(user_pb2_grpc.UserServiceServicer):
    
    def GetUser(self, request, context):
        if request.id not in USERS:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"User {request.id} not found")
            return user_pb2.User()
        
        user = USERS[request.id]
        return user_pb2.User(
            id=user["id"],
            name=user["name"],
            email=user["email"]
        )
    
    def StreamUsers(self, request, context):
        """Server-side streaming - returns multiple responses"""
        for user_id, user in list(USERS.items())[:request.limit]:
            yield user_pb2.User(
                id=user["id"],
                name=user["name"],
                email=user["email"]
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("gRPC server on :50051")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
```

### Client (`sync_examples/grpc/client.py`)

```python
"""gRPC sync client"""
import grpc
import user_pb2
import user_pb2_grpc

with grpc.insecure_channel('localhost:50051') as channel:
    stub = user_pb2_grpc.UserServiceStub(channel)
    
    # Unary call (single request → single response)
    response = stub.GetUser(user_pb2.GetUserRequest(id=1))
    print(f"User: {response.name}, {response.email}")
    
    # Streaming call (single request → multiple responses)
    for user in stub.StreamUsers(user_pb2.StreamRequest(limit=5)):
        print(f"Streamed: {user.name}")
```

### gRPC vs REST Benchmark

```python
import time
import httpx
import grpc

# Benchmark 1000 calls
REQUESTS = 1000

# REST
start = time.time()
with httpx.Client() as client:
    for _ in range(REQUESTS):
        client.get("http://localhost:8000/users/1")
rest_time = time.time() - start

# gRPC
start = time.time()
with grpc.insecure_channel('localhost:50051') as channel:
    stub = user_pb2_grpc.UserServiceStub(channel)
    for _ in range(REQUESTS):
        stub.GetUser(user_pb2.GetUserRequest(id=1))
grpc_time = time.time() - start

print(f"REST: {rest_time:.2f}s for {REQUESTS} requests")
print(f"gRPC: {grpc_time:.2f}s for {REQUESTS} requests")
print(f"gRPC is {rest_time/grpc_time:.1f}x faster")
# Typically gRPC is 2-5x faster
```

---

## 5. 📨 Async Example 1: RabbitMQ Queue

### Producer (`async_examples/rabbitmq/producer.py`)

```python
"""
RabbitMQ producer - fire and forget
"""
import asyncio
import aio_pika
import json

async def send_email_job(to: str, subject: str, body: str):
    """Send job to queue - returns immediately"""
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        
        # Declare durable queue (persists if broker restarts)
        queue = await channel.declare_queue("email_jobs", durable=True)
        
        # Publish message
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"to": to, "subject": subject, "body": body}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # Survive broker restart
            ),
            routing_key="email_jobs",
        )
        
        print(f"[PRODUCER] Queued email to {to}")

async def main():
    # Send multiple jobs quickly - no waiting for actual email send
    await send_email_job("user1@ex.com", "Welcome!", "Hi user1")
    await send_email_job("user2@ex.com", "Welcome!", "Hi user2")
    await send_email_job("user3@ex.com", "Welcome!", "Hi user3")
    
    print("\n✓ All 3 jobs queued, producer done immediately!")

if __name__ == "__main__":
    asyncio.run(main())
```

### Consumer (`async_examples/rabbitmq/consumer.py`)

```python
"""
RabbitMQ consumer - processes jobs from queue
"""
import asyncio
import aio_pika
import json

async def process_email(message: aio_pika.IncomingMessage):
    """Process email - acknowledge only on success"""
    async with message.process():  # Auto-ack on success, requeue on error
        data = json.loads(message.body.decode())
        print(f"[CONSUMER] Sending email to {data['to']}...")
        
        # Simulate sending email
        await asyncio.sleep(2)
        
        print(f"[CONSUMER] ✓ Sent to {data['to']}")

async def main():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)  # One message at a time
        
        queue = await channel.declare_queue("email_jobs", durable=True)
        
        await queue.consume(process_email)
        
        print("[CONSUMER] Waiting for messages... (Ctrl+C to stop)")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
```

### Run It

```bash
# Terminal 1: Start RabbitMQ
$ docker run -p 5672:5672 -p 15672:15672 rabbitmq:management

# Terminal 2: Start consumer
$ python consumer.py
[CONSUMER] Waiting for messages...

# Terminal 3: Produce jobs (instant!)
$ python producer.py
[PRODUCER] Queued email to user1@ex.com
[PRODUCER] Queued email to user2@ex.com
[PRODUCER] Queued email to user3@ex.com
✓ All 3 jobs queued, producer done immediately!

# Back in Terminal 2: Watch consumer process
[CONSUMER] Sending email to user1@ex.com...
[CONSUMER] ✓ Sent to user1@ex.com
[CONSUMER] Sending email to user2@ex.com...
...
```

---

## 6. 🌊 Async Example 2: Kafka Event Streams

### Producer

```python
"""
Kafka producer - publishes events that MULTIPLE consumers can read
"""
import asyncio
from aiokafka import AIOKafkaProducer
import json

async def publish_order_event(order_id: str, user_id: int, amount: float):
    producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode(),
        key_serializer=lambda v: str(v).encode(),
    )
    await producer.start()
    
    try:
        event = {
            "event_type": "order.placed",
            "order_id": order_id,
            "user_id": user_id,
            "amount": amount,
            "timestamp": "2026-05-26T10:00:00Z",
        }
        
        # Key ensures same user's events go to same partition (ordering)
        await producer.send_and_wait(
            "orders",
            value=event,
            key=str(user_id)  # Partition by user_id
        )
        
        print(f"[PRODUCER] Published event for order {order_id}")
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(publish_order_event("ORD-001", 123, 999.99))
```

### Consumer 1: Inventory Service

```python
"""Inventory consumer - one of MANY consumers of same event"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json

async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="inventory-service",  # Each service has its own group
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            print(f"[INVENTORY] Reserving stock for order {event['order_id']}")
            # Reserve inventory...
            await asyncio.sleep(0.5)
    finally:
        await consumer.stop()

asyncio.run(consume())
```

### Consumer 2: Email Service

```python
"""Email consumer - INDEPENDENTLY reads same event"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json

async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="email-service",  # DIFFERENT group from inventory!
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            print(f"[EMAIL] Sending confirmation for order {event['order_id']}")
            await asyncio.sleep(0.3)
    finally:
        await consumer.stop()

asyncio.run(consume())
```

### Key Insight

```
With Kafka, ONE event reaches BOTH consumers!
   
   Producer publishes once → orders topic
   Inventory service reads it     (its own offset)
   Email service ALSO reads it    (its own offset)
   Analytics service ALSO reads it (its own offset)
   
   Add NEW consumers without changing the producer!
```

---

## 7. 🪝 Async Example 3: Webhooks

### Webhook Sender (e.g., a Stripe-like service)

```python
"""
We send webhooks to customer URLs when events happen
"""
import httpx
import asyncio
import hmac
import hashlib
import json
import time

async def send_webhook(url: str, secret: str, event: dict):
    """Send webhook with HMAC signature for verification"""
    body = json.dumps(event)
    timestamp = str(int(time.time()))
    
    # Sign payload (allows receiver to verify)
    signature = hmac.new(
        secret.encode(),
        f"{timestamp}.{body}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": signature,
    }
    
    # Best practice: retry with backoff
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, content=body, headers=headers)
                if response.status_code < 300:
                    return  # Success
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    print(f"Failed to send webhook to {url} after 3 attempts")
```

### Webhook Receiver

```python
"""Customer's webhook endpoint"""
from fastapi import FastAPI, Request, HTTPException, Header
import hmac
import hashlib

app = FastAPI()

WEBHOOK_SECRET = "whsec_test_xyz123"

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_webhook_timestamp: str = Header(...),
    x_webhook_signature: str = Header(...),
):
    body = await request.body()
    
    # Verify signature
    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        f"{x_webhook_timestamp}.{body.decode()}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_sig, x_webhook_signature):
        raise HTTPException(401, "Invalid signature")
    
    # Process event (idempotently!)
    event = await request.json()
    print(f"Received webhook: {event['type']}")
    
    return {"received": True}
```

---

## 8. 🎼 Hybrid Architecture Demo

### `hybrid/api.py` (Sync front door)

```python
"""
Hybrid: Sync API for immediate response + async background work
"""
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uuid
import aio_pika
import json
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.broker = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    yield
    await app.state.broker.close()

app = FastAPI(lifespan=lifespan)

class VideoUpload(BaseModel):
    url: str
    user_id: int

@app.post("/videos/upload", status_code=202)
async def upload_video(video: VideoUpload, background: BackgroundTasks):
    """
    HYBRID PATTERN:
    1. Sync: validate + save metadata (fast)
    2. Async: queue heavy processing for workers
    3. Return immediately to user
    """
    video_id = f"vid-{uuid.uuid4().hex[:8]}"
    
    # 1. SYNC: Save metadata immediately
    # ... save to DB ...
    print(f"[API] Saved metadata for {video_id}")
    
    # 2. ASYNC: Enqueue heavy work
    async def enqueue():
        channel = await app.state.broker.channel()
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps({
                    "video_id": video_id,
                    "url": video.url,
                    "user_id": video.user_id,
                }).encode()
            ),
            routing_key="video_processing"
        )
    
    background.add_task(enqueue)
    
    # 3. Return immediately
    return {
        "video_id": video_id,
        "status": "PROCESSING",
        "message": "We'll notify you when ready"
    }
```

### `hybrid/worker.py` (Async heavy lifting)

```python
"""Background worker - does the heavy lifting"""
import asyncio
import aio_pika
import json

async def process_video(message: aio_pika.IncomingMessage):
    async with message.process():
        data = json.loads(message.body.decode())
        video_id = data["video_id"]
        
        print(f"[WORKER] Starting processing {video_id}")
        
        # Heavy work
        await asyncio.sleep(2)  # Transcode
        print(f"[WORKER] Transcoded {video_id}")
        
        await asyncio.sleep(1)  # Thumbnail
        print(f"[WORKER] Thumbnail {video_id}")
        
        await asyncio.sleep(0.5)  # Upload to CDN
        print(f"[WORKER] Uploaded {video_id}")
        
        # Notify user
        # ...
        print(f"[WORKER] ✓ Done with {video_id}")

async def main():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=3)  # Process 3 in parallel
    
    queue = await channel.declare_queue("video_processing", durable=True)
    await queue.consume(process_video)
    
    print("[WORKER] Ready to process videos")
    await asyncio.Future()

asyncio.run(main())
```

### Demo: Hybrid in Action

```bash
# Terminal 1: API
$ uvicorn api:app --port 8000

# Terminal 2: Worker
$ python worker.py
[WORKER] Ready to process videos

# Terminal 3: Make request
$ curl -X POST http://localhost:8000/videos/upload \
    -H "Content-Type: application/json" \
    -d '{"url": "https://example.com/video.mp4", "user_id": 123}'

Response (instant!): 
{
    "video_id": "vid-abc12345",
    "status": "PROCESSING",
    "message": "We'll notify you when ready"
}

# Back in worker terminal: heavy work happens
[WORKER] Starting processing vid-abc12345
[WORKER] Transcoded vid-abc12345
[WORKER] Thumbnail vid-abc12345
[WORKER] Uploaded vid-abc12345
[WORKER] ✓ Done with vid-abc12345
```

---

## 9. 🛡 Timeout, Retry, and Jitter

### `resilience/timeout_retry.py`

```python
"""
Production-grade resilience for sync calls
"""
import httpx
import asyncio
import random
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type
)

# ─────────────────────────────────────────────────────────────
# PATTERN 1: Timeout (always set one!)
# ─────────────────────────────────────────────────────────────
async def call_with_timeout(url):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            return response.json()
    except httpx.TimeoutException:
        print("Timeout! Don't wait forever")
        raise

# ─────────────────────────────────────────────────────────────
# PATTERN 2: Retry with exponential backoff + jitter
# ─────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    before_sleep=lambda r: print(f"Retry attempt {r.attempt_number}, waiting..."),
)
async def call_with_retry(url):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

# ─────────────────────────────────────────────────────────────
# PATTERN 3: Manual retry with jitter (more control)
# ─────────────────────────────────────────────────────────────
async def call_with_jitter(url, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                return (await client.get(url)).json()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            
            # Exponential backoff: 1, 2, 4 seconds
            base_delay = 2 ** attempt
            
            # Add jitter: random 0-50% extra
            jitter = random.uniform(0, base_delay * 0.5)
            delay = base_delay + jitter
            
            print(f"Attempt {attempt + 1} failed, waiting {delay:.2f}s")
            await asyncio.sleep(delay)
```

---

## 10. 💥 Cascading Failure Demo

### `resilience/cascading_demo.py`

```python
"""
Demonstrates how SYNC chains amplify failures.
"""
import asyncio
import httpx
import time

# Simulate flaky downstream service
async def flaky_downstream(delay: float):
    await asyncio.sleep(delay)
    if random.random() < 0.5:
        raise Exception("Downstream failed!")
    return "OK"

# ─────────────────────────────────────────────────────────────
# BAD: Sync chain (cascades on failure)
# ─────────────────────────────────────────────────────────────
async def sync_chain_bad(client):
    """Each service calls next - failure propagates"""
    result_a = await client.get("http://service-a/data")  # Could fail
    result_b = await client.get(f"http://service-b/data?from={result_a.json()['id']}")
    result_c = await client.get(f"http://service-c/data?from={result_b.json()['id']}")
    return result_c.json()

# ─────────────────────────────────────────────────────────────
# GOOD: Add timeouts + circuit breaker
# ─────────────────────────────────────────────────────────────
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=30)
async def call_service_a(client):
    response = await client.get("http://service-a/data", timeout=3.0)
    response.raise_for_status()
    return response.json()

# With circuit breaker:
# - 5 failures → circuit OPENS
# - 30s later → tries again
# - Prevents cascading
```

---

## 11. 🔍 Distributed Tracing

### Across sync + async with OpenTelemetry

```python
"""Track a request through sync API → async worker"""
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Auto-instrument
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

@app.post("/orders")
async def create_order(order):
    # Create span manually for custom logic
    with tracer.start_as_current_span("create_order_workflow") as span:
        span.set_attribute("order.user_id", order.user_id)
        
        # 1. Sync DB write (auto-traced)
        await db.save(order)
        
        # 2. Async event publish (need to inject context)
        from opentelemetry import propagate
        carrier = {}
        propagate.inject(carrier)
        
        await kafka.publish("order.created", {
            **order.dict(),
            "_trace_context": carrier,  # Pass trace context!
        })

# In consumer
async def on_order_created(message):
    # Extract trace context
    from opentelemetry import propagate
    context = propagate.extract(message.value.get("_trace_context", {}))
    
    with tracer.start_as_current_span("process_order", context=context):
        # This span is linked to the producer's trace!
        ...
```

---

## 12. 🐳 Docker Compose Setup

```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"  # Management UI at http://localhost:15672 (guest/guest)
  
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
  
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "6831:6831/udp"
```

```bash
$ docker-compose up -d
```

---

## 13. Performance Comparison

### Benchmark Setup

```python
"""Compare sync vs async throughput"""
import time
import asyncio
import httpx

URL = "http://localhost:8000/users/1"
N_REQUESTS = 100

# Sync sequential
def sync_sequential():
    start = time.time()
    with httpx.Client() as client:
        for _ in range(N_REQUESTS):
            client.get(URL)
    return time.time() - start

# Async concurrent
async def async_concurrent():
    start = time.time()
    async with httpx.AsyncClient() as client:
        tasks = [client.get(URL) for _ in range(N_REQUESTS)]
        await asyncio.gather(*tasks)
    return time.time() - start

# Results (typical)
sync_time = sync_sequential()
async_time = asyncio.run(async_concurrent())

print(f"Sync sequential: {sync_time:.2f}s")    # ~5.0s
print(f"Async concurrent: {async_time:.2f}s")   # ~0.2s
print(f"Speedup: {sync_time/async_time:.1f}x")  # ~25x
```

---

## 14. Key Learnings Summary

```
✅ Sync REST/gRPC for user-facing operations
✅ Async Kafka/RabbitMQ for background work
✅ HYBRID: sync front door + async workers (most common!)
✅ Always set timeouts on sync calls
✅ Use retry with exponential backoff + jitter
✅ Webhooks need HMAC signatures + idempotency
✅ Distributed tracing across sync + async
✅ gRPC is 2-5x faster than REST internally
✅ Async producer-consumer decouples completely

🎯 Production reality:
   - User clicks button → sync API (200ms)
   - API enqueues work → async worker
   - Worker publishes event → multiple consumers
   - All traced with correlation IDs
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll build **API Gateway and BFF** patterns — the front door of distributed systems.

> **Next lecture:** [02_API_Gateway_BFF.md](02_API_Gateway_BFF.md)

---

## 📚 Try It Yourself

1. Build a **video upload pipeline** with sync API + async workers
2. Add **OpenTelemetry tracing** across sync REST + Kafka consumers
3. Implement **idempotent webhook receiver** with Redis dedup
4. Compare **REST vs gRPC vs GraphQL** for the same endpoint
5. Simulate **cascading failure** then add timeouts + circuit breaker
