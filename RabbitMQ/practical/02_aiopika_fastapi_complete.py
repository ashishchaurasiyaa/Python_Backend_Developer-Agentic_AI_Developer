"""
RabbitMQ — aio-pika + FastAPI Complete Production Pattern
═══════════════════════════════════════════════════════════════
Run:
  pip install aio-pika fastapi uvicorn pydantic
  docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
  uvicorn 02_aiopika_fastapi_complete:app --reload

Test endpoints:
  POST /orders             → Create order (queued)
  POST /notifications/send → Broadcast notification
  GET  /health             → RabbitMQ health check
  POST /rpc/calculate      → RPC example

Topics Covered:
  1. aio-pika async connection
  2. FastAPI lifespan — connect/disconnect
  3. Exchange types with aio-pika
  4. DLX setup async
  5. Background worker
  6. RPC pattern
  7. Publisher Confirms
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional, MutableMapping

import aio_pika
import aio_pika.abc
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# SECTION 1: RabbitMQ Manager — Connection + Channels
# ═══════════════════════════════════════════════════════════

class RabbitMQManager:
    """RabbitMQ connection aur channels manage karo"""

    def __init__(self, url: str = "amqp://guest:guest@localhost/"):
        self.url = url
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None

        # Exchanges
        self.order_exchange: Optional[aio_pika.Exchange] = None
        self.notification_exchange: Optional[aio_pika.Exchange] = None

    async def connect(self):
        """Connect karo + all exchanges aur queues setup karo"""
        logger.info("Connecting to RabbitMQ...")

        self.connection = await aio_pika.connect_robust(
            self.url,
            heartbeat=60,
            reconnect_interval=5
        )

        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)

        await self._setup_exchanges_and_queues()
        logger.info("RabbitMQ connected + exchanges setup done!")

    async def _setup_exchanges_and_queues(self):
        """Sab exchanges aur queues ek jagah setup karo"""
        ch = self.channel

        # ── DLX Setup (pehle karo) ──
        dlx = await ch.declare_exchange("dlx", aio_pika.ExchangeType.DIRECT, durable=True)
        dlq = await ch.declare_queue("dead_letter_queue", durable=True)
        await dlq.bind(dlx, routing_key="dead")

        # ── Direct Exchange (Orders) ──
        self.order_exchange = await ch.declare_exchange(
            "orders", aio_pika.ExchangeType.DIRECT, durable=True
        )
        order_queue = await ch.declare_queue(
            "order_processing",
            durable=True,
            arguments={
                "x-dead-letter-exchange":    "dlx",
                "x-dead-letter-routing-key": "dead",
                "x-message-ttl":             300000,  # 5 min TTL
            }
        )
        await order_queue.bind(self.order_exchange, routing_key="process")

        # ── Fanout Exchange (Notifications) ──
        self.notification_exchange = await ch.declare_exchange(
            "notifications", aio_pika.ExchangeType.FANOUT, durable=True
        )
        email_q = await ch.declare_queue("email_notifications", durable=True)
        sms_q   = await ch.declare_queue("sms_notifications",   durable=True)
        push_q  = await ch.declare_queue("push_notifications",  durable=True)
        await email_q.bind(self.notification_exchange)
        await sms_q.bind(self.notification_exchange)
        await push_q.bind(self.notification_exchange)

        logger.info("All exchanges + queues ready!")

    async def publish_order(self, order_data: dict) -> str:
        """Order queue mein publish karo"""
        message_id = str(uuid.uuid4())

        await self.order_exchange.publish(
            aio_pika.Message(
                body=json.dumps(order_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=message_id,
            ),
            routing_key="process"
        )
        return message_id

    async def broadcast_notification(self, notification: dict):
        """Sabhi notification services ko broadcast karo"""
        await self.notification_exchange.publish(
            aio_pika.Message(
                body=json.dumps(notification).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=""  # fanout mein ignored
        )

    async def close(self):
        """Gracefully close karo"""
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        logger.info("RabbitMQ connection closed")

    @property
    def is_connected(self) -> bool:
        return (
            self.connection is not None
            and not self.connection.is_closed
        )


# ═══════════════════════════════════════════════════════════
# SECTION 2: RPC Client
# ═══════════════════════════════════════════════════════════

class RPCClient:
    """RPC pattern — request bhejo response wait karo"""

    def __init__(self):
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.callback_queue: Optional[aio_pika.Queue] = None
        self.channel: Optional[aio_pika.Channel] = None

    async def setup(self, channel: aio_pika.Channel):
        self.channel = channel
        # Exclusive callback queue — sirf is client ke liye
        self.callback_queue = await channel.declare_queue(exclusive=True, auto_delete=True)
        await self.callback_queue.consume(self._on_response, no_ack=True)

    async def _on_response(self, message: aio_pika.IncomingMessage):
        """Server ka response handle karo"""
        correlation_id = message.correlation_id
        if correlation_id and correlation_id in self.futures:
            future = self.futures.pop(correlation_id)
            if not future.done():
                result = json.loads(message.body)
                future.set_result(result)

    async def call(self, request: dict, timeout: float = 10.0) -> dict:
        """RPC call karo — timeout ke saath"""
        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(request).encode(),
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
                expiration=str(int(timeout * 1000))  # ms
            ),
            routing_key="rpc_math_queue"
        )

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.futures.pop(correlation_id, None)
            raise HTTPException(status_code=504, detail="RPC timeout")


# ═══════════════════════════════════════════════════════════
# SECTION 3: FastAPI App + Lifespan
# ═══════════════════════════════════════════════════════════

rabbitmq = RabbitMQManager()
rpc_client = RPCClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: RabbitMQ connect | Shutdown: disconnect"""
    await rabbitmq.connect()
    await rpc_client.setup(rabbitmq.channel)

    # Background workers start karo
    asyncio.create_task(order_worker())
    asyncio.create_task(notification_worker("email_notifications", "EmailService"))
    asyncio.create_task(notification_worker("sms_notifications", "SMSService"))
    asyncio.create_task(rpc_server_worker())

    logger.info("App startup complete!")
    yield

    await rabbitmq.close()
    logger.info("App shutdown complete!")


app = FastAPI(title="RabbitMQ + FastAPI Demo", lifespan=lifespan)


# ═══════════════════════════════════════════════════════════
# SECTION 4: Background Workers (Consumers)
# ═══════════════════════════════════════════════════════════

async def order_worker():
    """Order processing worker"""
    conn = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=5)

    queue = await channel.declare_queue("order_processing", durable=True)
    logger.info("Order worker started!")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    order = json.loads(message.body)
                    logger.info(f"Processing order: {order.get('order_id')}")
                    await asyncio.sleep(0.1)  # simulate processing
                    logger.info(f"Order {order.get('order_id')} done!")
                except Exception as e:
                    logger.error(f"Order failed: {e}")
                    raise  # nack → DLQ


async def notification_worker(queue_name: str, service_name: str):
    """Notification worker — email ya sms"""
    conn = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=10)

    queue = await channel.declare_queue(queue_name, durable=True)
    logger.info(f"{service_name} worker started!")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                data = json.loads(message.body)
                logger.info(f"[{service_name}] Sending to user {data.get('user_id')}: {data.get('message', '')[:50]}")


async def rpc_server_worker():
    """RPC Server — math operations"""
    conn = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue("rpc_math_queue", durable=False)
    logger.info("RPC Server worker started!")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                request = json.loads(message.body)
                operation = request.get("operation", "add")
                a = request.get("a", 0)
                b = request.get("b", 0)

                if operation == "add":
                    result = a + b
                elif operation == "multiply":
                    result = a * b
                else:
                    result = None

                response = {"result": result, "operation": operation, "a": a, "b": b}

                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(response).encode(),
                        correlation_id=message.correlation_id,
                    ),
                    routing_key=message.reply_to
                )


# ═══════════════════════════════════════════════════════════
# SECTION 5: API Endpoints
# ═══════════════════════════════════════════════════════════

class OrderRequest(BaseModel):
    user_id: int
    item: str
    quantity: int
    price: float


class NotificationRequest(BaseModel):
    user_id: int
    message: str
    channel: str = "all"   # all, email, sms


class RPCRequest(BaseModel):
    operation: str = "add"   # add, multiply
    a: float
    b: float


@app.post("/orders")
async def create_order(order: OrderRequest):
    """Order create karo — RabbitMQ queue mein daalo"""
    order_id = str(uuid.uuid4())[:8]
    order_data = {"order_id": order_id, **order.model_dump()}

    message_id = await rabbitmq.publish_order(order_data)

    return {
        "order_id":   order_id,
        "message_id": message_id,
        "status":     "queued",
        "message":    "Order queued for processing"
    }


@app.post("/notifications/send")
async def send_notification(notif: NotificationRequest):
    """Notification broadcast karo — sabhi services ko"""
    await rabbitmq.broadcast_notification({
        "user_id":   notif.user_id,
        "message":   notif.message,
        "timestamp": asyncio.get_event_loop().time()
    })
    return {"status": "broadcasted", "reached_services": ["email", "sms", "push"]}


@app.post("/rpc/calculate")
async def rpc_calculate(request: RPCRequest):
    """RPC call — response wait karo"""
    result = await rpc_client.call({
        "operation": request.operation,
        "a": request.a,
        "b": request.b
    })
    return result


@app.get("/health")
async def health_check():
    """RabbitMQ connection status"""
    if rabbitmq.is_connected:
        return {"status": "healthy", "rabbitmq": "connected"}
    raise HTTPException(status_code=503, detail="RabbitMQ not connected")


@app.get("/")
async def root():
    return {
        "endpoints": {
            "POST /orders":              "Create order (queued)",
            "POST /notifications/send":  "Broadcast notification",
            "POST /rpc/calculate":       "RPC math operation",
            "GET  /health":              "Health check",
        }
    }


# ═══════════════════════════════════════════════════════════
# SECTION 6: Standalone async demo (without FastAPI)
# ═══════════════════════════════════════════════════════════

async def standalone_demo():
    """FastAPI ke bina — pure aio-pika demo"""
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")

    async with connection:
        channel = await connection.channel()

        # Direct Exchange demo
        exchange = await channel.declare_exchange(
            "demo_direct", aio_pika.ExchangeType.DIRECT, durable=True
        )
        queue = await channel.declare_queue("demo_queue", durable=True)
        await queue.bind(exchange, routing_key="demo")

        # Publish
        for i in range(5):
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps({"task": f"Task-{i}", "id": i}).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key="demo"
            )
            print(f"Published task {i}")

        # Consume
        print("\nConsuming messages:")
        async with queue.iterator() as queue_iter:
            count = 0
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body)
                    print(f"  Received: {data}")
                    count += 1
                    if count >= 5:
                        break


if __name__ == "__main__":
    # Standalone demo
    asyncio.run(standalone_demo())

    # FastAPI run karne ke liye:
    # uvicorn 02_aiopika_fastapi_complete:app --reload --port 8000
