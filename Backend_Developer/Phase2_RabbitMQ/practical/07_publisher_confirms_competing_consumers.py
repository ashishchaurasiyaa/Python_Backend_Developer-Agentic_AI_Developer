"""
Publisher Confirms + Competing Consumers — Production Patterns
"""

import asyncio
import signal
import time
import uuid
import logging
from typing import Optional

import pika
import aio_pika


log = logging.getLogger(__name__)


# ==========================================================================
# 1. SYNCHRONOUS CONFIRMS (simple, slow)
# ==========================================================================

def publish_with_sync_confirm(channel, exchange, routing_key, body):
    """Each publish waits for broker ack."""
    try:
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=str(uuid.uuid4()),
                timestamp=int(time.time()),
            ),
            mandatory=True,
        )
        return True
    except pika.exceptions.UnroutableError:
        log.error(f"Unroutable: {routing_key}")
        return False
    except pika.exceptions.NackError as e:
        log.error(f"Nack: {e}")
        return False


def setup_sync_publisher(host='localhost'):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=host, heartbeat=30),
    )
    channel = connection.channel()
    channel.confirm_delivery()    # enable confirms
    return connection, channel


# ==========================================================================
# 2. BATCH CONFIRMS (faster)
# ==========================================================================

def publish_batch(channel, messages: list[tuple[str, str, bytes]], batch_size=100):
    """Publish in batches; wait once per batch."""
    channel.confirm_delivery()

    for i, (exchange, routing_key, body) in enumerate(messages):
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=str(uuid.uuid4()),
            ),
        )

        if (i + 1) % batch_size == 0:
            # Wait for all in batch to confirm
            if not channel.wait_for_confirms():
                log.error(f"Batch ending at {i} had failures")


# ==========================================================================
# 3. ASYNC CONFIRMS (highest throughput, complex)
# ==========================================================================

class AsyncConfirmsPublisher:
    """Track in-flight messages, handle acks/nacks asynchronously."""

    def __init__(self, channel):
        self.channel = channel
        self.next_tag = 1
        self.pending = {}    # delivery_tag -> message details
        self.confirmed = 0
        self.nacked = 0

        channel.confirm_delivery(self._on_confirm)
        channel.add_on_return_callback(self._on_return)

    def publish(self, exchange, routing_key, body):
        tag = self.next_tag
        self.next_tag += 1

        self.pending[tag] = {
            'exchange': exchange,
            'routing_key': routing_key,
            'body': body,
            'attempts': 0,
        }

        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=str(uuid.uuid4()),
            ),
            mandatory=True,
        )
        return tag

    def _on_confirm(self, method_frame):
        tag = method_frame.method.delivery_tag
        multiple = method_frame.method.multiple

        if isinstance(method_frame.method, pika.spec.Basic.Ack):
            self._handle_ack(tag, multiple)
        else:
            self._handle_nack(tag, multiple)

    def _handle_ack(self, tag, multiple):
        if multiple:
            to_remove = [t for t in self.pending if t <= tag]
            for t in to_remove:
                self.pending.pop(t, None)
                self.confirmed += 1
        else:
            self.pending.pop(tag, None)
            self.confirmed += 1

    def _handle_nack(self, tag, multiple):
        log.warning(f"Broker nacked tag={tag} multiple={multiple}")
        # Retry logic — re-publish from pending
        if multiple:
            to_retry = [t for t in self.pending if t <= tag]
        else:
            to_retry = [tag]
        for t in to_retry:
            msg = self.pending.pop(t, None)
            if msg and msg['attempts'] < 3:
                msg['attempts'] += 1
                time.sleep(0.5 * 2 ** msg['attempts'])
                # Re-publish (new tag assigned)
                self.publish(msg['exchange'], msg['routing_key'], msg['body'])
            else:
                self.nacked += 1
                # Send to DLQ or log

    def _on_return(self, channel, method, props, body):
        log.warning(
            f"Unroutable returned: routing_key={method.routing_key} "
            f"reply_code={method.reply_code}"
        )


# ==========================================================================
# 4. COMPETING CONSUMERS WITH PREFETCH
# ==========================================================================

def consumer_with_prefetch(queue_name='orders', prefetch=10, consumer_name='worker-1'):
    """Multiple instances of this = competing consumers."""

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost', heartbeat=60),
    )
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)

    # Fair dispatch
    channel.basic_qos(prefetch_count=prefetch)

    def callback(ch, method, props, body):
        try:
            log.info(f"[{consumer_name}] Processing {method.delivery_tag}")
            process_message(body, props)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except RetriableError as e:
            log.warning(f"Retriable: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as e:
            log.exception(f"Fatal: {e}")
            # Send to DLQ via dead-letter exchange (configured on queue)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(
        queue=queue_name,
        on_message_callback=callback,
        consumer_tag=consumer_name,
    )
    channel.start_consuming()


def process_message(body, props):
    pass


class RetriableError(Exception):
    pass


# ==========================================================================
# 5. IDEMPOTENT CONSUMER (dedupe via Redis)
# ==========================================================================

import redis


r = redis.Redis(host='localhost')


def idempotent_callback(ch, method, props, body):
    message_id = props.message_id
    if not message_id:
        log.error("Message has no message_id — cannot dedupe")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # SETNX with TTL — atomic check + set
    dedup_key = f'msg:processed:{message_id}'
    if not r.set(dedup_key, '1', ex=86400 * 7, nx=True):
        # Already processed — just ack
        log.info(f"Duplicate {message_id}, skipping")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        process_message(body, props)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        # Release dedup lock so retry can process
        r.delete(dedup_key)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# ==========================================================================
# 6. ASYNC (aio-pika) — full pattern
# ==========================================================================

async def async_publisher():
    connection = await aio_pika.connect_robust(
        "amqp://admin:admin@localhost/",
        timeout=10,
    )

    async with connection:
        channel = await connection.channel(publisher_confirms=True)

        # Single-message confirm
        message = aio_pika.Message(
            body=b'hello',
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=str(uuid.uuid4()),
        )

        # publish() returns awaitable; awaits for confirm
        await channel.default_exchange.publish(message, routing_key='orders')


async def async_consumer():
    connection = await aio_pika.connect_robust("amqp://admin:admin@localhost/")

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue('orders', durable=True)

        async with queue.iterator() as it:
            async for message in it:
                async with message.process(requeue=True, ignore_processed=True):
                    # Auto-ack on success, auto-nack(requeue=True) on exception
                    await handle_async(message.body, message.properties)


async def handle_async(body, props):
    pass


# ==========================================================================
# 7. GRACEFUL SHUTDOWN
# ==========================================================================

class GracefulConsumer:
    def __init__(self, host, queue):
        self.host = host
        self.queue = queue
        self.shutdown = False
        self.channel = None
        self.connection = None

    def _signal_handler(self, sig, frame):
        log.info("Shutdown signal received")
        self.shutdown = True
        if self.channel and self.channel.is_open:
            self.channel.stop_consuming()

    def run(self):
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host, heartbeat=30),
        )
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=10)

        def callback(ch, method, props, body):
            if self.shutdown:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return
            try:
                process_message(body, props)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        self.channel.basic_consume(queue=self.queue, on_message_callback=callback)

        try:
            self.channel.start_consuming()
        finally:
            if self.connection.is_open:
                self.connection.close()


# ==========================================================================
# 8. CONNECTION POOLING (multiple channels, one connection)
# ==========================================================================

class ChannelPool:
    """Reuse channels across threads (each thread gets own channel)."""

    def __init__(self, connection):
        self.connection = connection
        self._local = __import__('threading').local()

    @property
    def channel(self):
        if not hasattr(self._local, 'channel'):
            self._local.channel = self.connection.channel()
            self._local.channel.confirm_delivery()
        return self._local.channel


# Usage:
# connection = pika.BlockingConnection(...)
# pool = ChannelPool(connection)
#
# def thread_work():
#     ch = pool.channel  # gets per-thread channel
#     ch.basic_publish(...)


# ==========================================================================
# 9. DEAD LETTER QUEUE (DLQ) PATTERN
# ==========================================================================

def setup_with_dlq(channel):
    # DLX
    channel.exchange_declare(exchange='dlx', exchange_type='direct', durable=True)
    channel.queue_declare(queue='orders.dlq', durable=True)
    channel.queue_bind(queue='orders.dlq', exchange='dlx', routing_key='orders.dead')

    # Main queue with DLX
    channel.queue_declare(
        queue='orders',
        durable=True,
        arguments={
            'x-queue-type': 'quorum',
            'x-delivery-limit': 5,           # nack 5x → goes to DLQ
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'orders.dead',
        },
    )


# Periodic DLQ inspection
def replay_dlq_to_main(channel, source_queue='orders.dlq', target_exchange='', target_rk='orders'):
    """Manual replay after fixing root cause."""
    while True:
        method, props, body = channel.basic_get(queue=source_queue, auto_ack=False)
        if not method:
            break
        try:
            channel.basic_publish(target_exchange, target_rk, body, properties=props)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            break


# ==========================================================================
# 10. RETRY WITH EXPONENTIAL BACKOFF (via TTL)
# ==========================================================================

RETRY_WITH_TTL_SETUP = """
# Use TTL queues for delayed retry:

# orders -> on nack -> orders.retry.1m -> orders (after 1 min)
# If still fails: orders.retry.5m -> orders (after 5 min)
# Then DLQ

channel.queue_declare(
    queue='orders.retry.1m',
    durable=True,
    arguments={
        'x-message-ttl': 60000,                  # 1 min
        'x-dead-letter-exchange': '',            # default
        'x-dead-letter-routing-key': 'orders',   # back to main queue
    },
)

# On consumer nack/error, instead of requeue=True, publish to orders.retry.1m
# After TTL, message reappears in orders
"""


# ==========================================================================
# 11. METRICS / OBSERVABILITY
# ==========================================================================

OBSERVABILITY = """
# Track in consumer:
- messages_processed counter
- messages_failed counter
- processing_duration histogram
- queue_depth gauge (poll periodically)

# Use rabbitmq-prometheus plugin for broker metrics:
- rabbitmq_queue_messages
- rabbitmq_queue_messages_ready
- rabbitmq_queue_messages_unacknowledged
- rabbitmq_connections
- rabbitmq_channels
- rabbitmq_consumers

# Alert on:
- Queue depth > X for > 5 min
- Unacked > 10% of total
- Consumer count = 0 for active queue
- Connection count drops
- DLQ depth > 0 (any failure)
"""
