# RabbitMQ — aio-pika (Async), FastAPI Integration & RPC Pattern
**Advanced Level | Theory + Interview Q&A**

---

## Quick Concepts
- **aio-pika** = pika ka async version — FastAPI ke saath use karo
- **asyncio** compatible — await karo blocking nahi hoga
- **RPC over RabbitMQ** = Request-Reply pattern — response chahiye toh
- **Connection Pool** = Multiple connections manage karo efficiently
- **Lifespan** = FastAPI startup pe connect, shutdown pe close
- **reply_to** = RPC mein consumer kahan response bhejega
- **correlation_id** = Request aur Response match karne ke liye unique ID

---

## Interview Questions & Answers

---

### Q1: aio-pika vs pika — kya fark hai? FastAPI mein kaunsa use karo?

**Answer:**
```
pika (blocking):
  channel.start_consuming()  ← ye line BLOCK karti hai
  FastAPI event loop block ho jaata hai
  Concurrency khatam ❌

aio-pika (async):
  await queue.consume(callback)  ← non-blocking
  FastAPI event loop free rehta hai
  1000 concurrent requests handle kar sakta hai ✅

Rule: FastAPI = async = aio-pika ALWAYS
```

```python
# pip install aio-pika

import asyncio
import aio_pika
import json

async def basic_aiopika_example():
    # Connect karo
    connection = await aio_pika.connect_robust(
        "amqp://guest:guest@localhost/",
        heartbeat=60
    )

    async with connection:
        channel = await connection.channel()

        # Queue declare karo
        queue = await channel.declare_queue(
            "hello_async",
            durable=True
        )

        # Message publish karo
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"msg": "Hello from async!"}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="hello_async"
        )
        print("Message published!")

        # Message consume karo
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():   # auto ack on success
                    data = json.loads(message.body)
                    print(f"Received: {data}")
                    break   # ek message ke baad stop

asyncio.run(basic_aiopika_example())
```

---

### Q2: aio-pika ke saath Exchanges kaise use karte hain?

**Answer:**
```python
import asyncio
import aio_pika
import json

async def exchanges_with_aiopika():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")

    async with connection:
        channel = await connection.channel()

        # ─── Direct Exchange ───
        direct_exchange = await channel.declare_exchange(
            "orders_direct",
            aio_pika.ExchangeType.DIRECT,
            durable=True
        )
        payment_queue = await channel.declare_queue("payments", durable=True)
        await payment_queue.bind(direct_exchange, routing_key="payment")

        await direct_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"order_id": 1, "amount": 500}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="payment"
        )
        print("Direct exchange message sent!")

        # ─── Fanout Exchange ───
        fanout_exchange = await channel.declare_exchange(
            "notifications_fanout",
            aio_pika.ExchangeType.FANOUT,
            durable=True
        )
        email_q = await channel.declare_queue("email_notify", durable=True)
        sms_q   = await channel.declare_queue("sms_notify",   durable=True)
        await email_q.bind(fanout_exchange)
        await sms_q.bind(fanout_exchange)

        await fanout_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"user_id": 42, "event": "signup"}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=""   # fanout mein ignored
        )
        print("Fanout message sent to email + sms!")

        # ─── Topic Exchange ───
        topic_exchange = await channel.declare_exchange(
            "app_events_topic",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        order_q = await channel.declare_queue("all_orders", durable=True)
        await order_q.bind(topic_exchange, routing_key="order.#")

        await topic_exchange.publish(
            aio_pika.Message(
                body=b"Order placed in India",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="order.placed.india"
        )
        print("Topic exchange message sent!")

asyncio.run(exchanges_with_aiopika())
```

---

### Q3: FastAPI + RabbitMQ — Production Integration kaise karo?

**Answer:**
```python
# main.py — Complete FastAPI + aio-pika production setup
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import aio_pika
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Global connection (lifespan mein manage karo) ───
rabbitmq_connection: Optional[aio_pika.RobustConnection] = None
rabbitmq_channel: Optional[aio_pika.Channel] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup → connect RabbitMQ, shutdown → close"""
    global rabbitmq_connection, rabbitmq_channel

    # STARTUP
    logger.info("Connecting to RabbitMQ...")
    rabbitmq_connection = await aio_pika.connect_robust(
        "amqp://guest:guest@localhost/",
        heartbeat=60,
        reconnect_interval=5   # auto reconnect on failure
    )
    rabbitmq_channel = await rabbitmq_connection.channel()
    await rabbitmq_channel.set_qos(prefetch_count=10)

    # Queues declare karo startup pe
    await rabbitmq_channel.declare_queue("order_queue", durable=True)
    await rabbitmq_channel.declare_queue("email_queue", durable=True)

    logger.info("RabbitMQ connected!")

    yield  # App run karo

    # SHUTDOWN
    logger.info("Closing RabbitMQ connection...")
    if rabbitmq_channel and not rabbitmq_channel.is_closed:
        await rabbitmq_channel.close()
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        await rabbitmq_connection.close()
    logger.info("RabbitMQ disconnected!")

app = FastAPI(lifespan=lifespan)

# ─── Pydantic Models ───
class OrderRequest(BaseModel):
    user_id: int
    item: str
    quantity: int
    price: float

class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str

# ─── API Endpoints ───
@app.post("/orders", response_model=OrderResponse)
async def create_order(order: OrderRequest):
    """Order create karo — RabbitMQ mein queue karo"""
    import uuid
    order_id = str(uuid.uuid4())

    order_data = {
        "order_id": order_id,
        **order.model_dump()
    }

    # RabbitMQ mein publish karo
    await rabbitmq_channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(order_data).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=order_id,
        ),
        routing_key="order_queue"
    )

    logger.info(f"Order {order_id} queued for processing")
    return OrderResponse(
        order_id=order_id,
        status="queued",
        message="Order received and queued for processing"
    )

@app.post("/notifications/broadcast")
async def broadcast_notification(message: str, user_id: int):
    """Fanout — sab notification services ko bhejo"""
    # Fanout exchange se sab queues ko
    fanout_exchange = await rabbitmq_channel.declare_exchange(
        "notifications", aio_pika.ExchangeType.FANOUT, durable=True
    )
    await fanout_exchange.publish(
        aio_pika.Message(
            body=json.dumps({"user_id": user_id, "message": message}).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        ),
        routing_key=""
    )
    return {"status": "broadcasted", "message": message}

@app.get("/health")
async def health():
    """RabbitMQ connection check karo"""
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        return {"status": "healthy", "rabbitmq": "connected"}
    raise HTTPException(status_code=503, detail="RabbitMQ disconnected")
```

**Worker (Consumer) — separate process:**
```python
# worker.py — Background worker
import asyncio
import aio_pika
import json
import logging

logger = logging.getLogger(__name__)

async def process_order(message: aio_pika.IncomingMessage):
    """Order process karo"""
    async with message.process():   # exception aaye → nack automatically
        data = json.loads(message.body)
        logger.info(f"Processing order: {data['order_id']}")

        try:
            # Business logic
            # 1. Inventory check karo
            # 2. Payment process karo
            # 3. Confirmation bhejo
            print(f"Order {data['order_id']} processed: {data['item']} x{data['quantity']}")

        except Exception as e:
            logger.error(f"Order failed: {e}")
            raise   # message.process() nack karega

async def main():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=5)   # 5 concurrent messages

        queue = await channel.declare_queue("order_queue", durable=True)

        logger.info("Worker started — waiting for orders...")
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await process_order(message)

asyncio.run(main())
```

---

### Q4: RPC over RabbitMQ kya hai? Kaise implement karo?

**Answer:**
Request bhejo aur **Response wapas chahiye** — two queues use hota hai.

```
Client               RabbitMQ              Server
  │                     │                    │
  │─── request ────────►│─── rpc_queue ─────►│
  │  reply_to=callback  │                    │ process karo
  │  correlation_id=xyz │                    │
  │                     │◄─── callback ──────│
  │◄── response ────────│  correlation_id=xyz│
  │  match karo         │                    │
```

```python
import asyncio
import aio_pika
import uuid
import json
from asyncio import Future
from typing import MutableMapping

class RabbitMQRPCClient:
    """RPC Client — request bhejo, response wait karo"""

    def __init__(self):
        self.futures: MutableMapping[str, Future] = {}
        self.callback_queue = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        self.channel = await self.connection.channel()

        # Callback queue — server response yahan bhejega
        self.callback_queue = await self.channel.declare_queue(exclusive=True)

        # Callback queue pe consume karo
        await self.callback_queue.consume(self.on_response)
        return self

    async def on_response(self, message: aio_pika.IncomingMessage):
        """Server ka response receive karo"""
        async with message.process():
            correlation_id = message.correlation_id
            if correlation_id in self.futures:
                result = json.loads(message.body)
                self.futures[correlation_id].set_result(result)

    async def call(self, request: dict) -> dict:
        """RPC call karo — response wait karo"""
        correlation_id = str(uuid.uuid4())

        # Future create karo — response aane pe resolve hoga
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        # Request bhejo
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(request).encode(),
                content_type="application/json",
                correlation_id=correlation_id,     # match ke liye
                reply_to=self.callback_queue.name,  # response kahan aayega
            ),
            routing_key="rpc_queue"
        )

        # Response wait karo (timeout with asyncio.wait_for)
        try:
            result = await asyncio.wait_for(future, timeout=10.0)
            return result
        except asyncio.TimeoutError:
            del self.futures[correlation_id]
            raise TimeoutError("RPC call timed out after 10 seconds")

# RPC Server
async def rpc_server():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue("rpc_queue", durable=False)

    print("RPC Server ready...")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                request = json.loads(message.body)
                print(f"RPC request received: {request}")

                # Business logic
                result = {"sum": request.get("a", 0) + request.get("b", 0)}

                # Response bhejo — reply_to queue mein
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(result).encode(),
                        correlation_id=message.correlation_id,  # same ID
                    ),
                    routing_key=message.reply_to  # client ka callback queue
                )
                print(f"RPC response sent: {result}")

# Client usage
async def main():
    client = await RabbitMQRPCClient().connect()

    # RPC call karo — response wait karo
    response = await client.call({"a": 10, "b": 32})
    print(f"RPC Result: {response}")   # {"sum": 42}

    # Multiple concurrent RPC calls
    tasks = [
        client.call({"a": i, "b": i * 2})
        for i in range(5)
    ]
    results = await asyncio.gather(*tasks)
    print(f"All RPC results: {results}")

asyncio.run(main())
```

---

### Q5: RabbitMQ vs Redis Streams — Kab kaunsa use karo?

**Answer:**
```
┌─────────────────────────────────────────────────────────────────────┐
│ Feature           │ RabbitMQ                │ Redis Streams         │
├─────────────────────────────────────────────────────────────────────┤
│ Protocol          │ AMQP (dedicated broker) │ Redis ke andar        │
│ Message Routing   │ Exchanges + Bindings    │ Stream name = topic   │
│ Consumer Groups   │ Queue per consumer      │ XGROUP CREATE         │
│ Message Ordering  │ Queue-level FIFO        │ Strict global order   │
│ Persistence       │ Disk (durable queues)   │ RDB/AOF               │
│ DLQ Support       │ Built-in (DLX)          │ Manual implement      │
│ Priority          │ Built-in                │ Manual (sorted set)   │
│ Throughput        │ Medium (50k/sec)        │ High (100k+/sec)      │
│ Complexity        │ More setup              │ Simpler (already Redis)│
├─────────────────────────────────────────────────────────────────────┤
│ Use RabbitMQ when:│ Complex routing needed, │ DLQ/Priority needed,  │
│                   │ Dedicated broker ok,    │ Multi-service fanout   │
│ Use Redis Streams │ Already using Redis,    │ Simple pub/sub,        │
│ when:             │ High throughput needed, │ Lower infra overhead   │
└─────────────────────────────────────────────────────────────────────┘

Interview Answer:
"RabbitMQ for complex message routing (Direct/Fanout/Topic exchanges),
 guaranteed delivery with DLQ, priority queues.
 Redis Streams for high-throughput event streaming when Redis already
 in stack — avoids separate broker overhead."
```

---

### Q6: RabbitMQ connection_robust vs connect — kya fark hai?

**Answer:**
```python
# connect — ek baar connect, fail → exception
connection = await aio_pika.connect("amqp://localhost/")
# Network hiccup → ConnectionError → crash ❌

# connect_robust — auto-reconnect on failure
connection = await aio_pika.connect_robust(
    "amqp://localhost/",
    reconnect_interval=5,    # 5 sec baad retry
    heartbeat=60             # 60 sec heartbeat
)
# Network hiccup → auto-reconnect → messages continue ✅

# Production ALWAYS use connect_robust
```

---

## Complete Production Checklist

```
RabbitMQ Production Setup:
✅ connect_robust (auto-reconnect)
✅ durable=True (queues survive restart)
✅ DeliveryMode.PERSISTENT (messages survive restart)
✅ auto_ack=False + manual ack/nack
✅ basic_qos prefetch_count set karo
✅ DLX + DLQ setup karo (failed messages)
✅ Publisher Confirms (critical messages ke liye)
✅ Lifespan mein connect/disconnect (FastAPI)
✅ Health check endpoint
✅ Retry with exponential backoff
✅ Message TTL set karo
```
