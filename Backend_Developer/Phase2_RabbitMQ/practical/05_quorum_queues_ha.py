"""
Quorum Queues + HA — Production Patterns
"""

import pika
import aio_pika
import asyncio


# ==========================================================================
# 1. DECLARE QUORUM QUEUE
# ==========================================================================

def declare_quorum_queue():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='rabbit-1',
            port=5672,
            credentials=pika.PlainCredentials('admin', 'admin'),
        ),
    )
    channel = connection.channel()

    channel.queue_declare(
        queue='orders',
        durable=True,
        arguments={
            'x-queue-type': 'quorum',
            'x-quorum-initial-group-size': 3,
            'x-delivery-limit': 10,                  # max redeliveries before dead-letter
            'x-max-length': 1_000_000,                # cap message count
            'x-overflow': 'reject-publish-dlx',       # what to do when full
            'x-dead-letter-exchange': 'dlx',
        },
    )
    connection.close()


# ==========================================================================
# 2. STREAM QUEUE
# ==========================================================================

def declare_stream_queue():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbit-1'))
    channel = connection.channel()

    channel.queue_declare(
        queue='events-stream',
        durable=True,
        arguments={
            'x-queue-type': 'stream',
            'x-max-length-bytes': 50 * 1024 ** 3,    # 50 GB cap
            'x-stream-max-segment-size-bytes': 500 * 1024 ** 2,
            'x-max-age': '24h',                       # delete segments > 24h
        },
    )
    connection.close()


# ==========================================================================
# 3. CONSUMER FROM STREAM (offset support)
# ==========================================================================

def consume_stream_from_offset(offset='last'):
    """offset = 'first', 'last', 'next', timestamp, or specific offset."""
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbit-1'))
    channel = connection.channel()

    channel.basic_qos(prefetch_count=10)

    def callback(ch, method, props, body):
        print(f"[stream offset={method.delivery_tag}] {body}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(
        queue='events-stream',
        on_message_callback=callback,
        arguments={
            'x-stream-offset': offset,
        },
    )
    channel.start_consuming()


# ==========================================================================
# 4. LAZY QUEUE (huge backlogs)
# ==========================================================================

def declare_lazy_queue():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbit-1'))
    channel = connection.channel()

    channel.queue_declare(
        queue='marketing-emails',
        durable=True,
        arguments={
            'x-queue-mode': 'lazy',         # messages to disk ASAP
            'x-max-length': 100_000_000,    # 100M emails
        },
    )
    connection.close()


# ==========================================================================
# 5. PUBLISHER WITH HA + RETRY
# ==========================================================================

class HAPublisher:
    def __init__(self, hosts: list[str], creds, exchange='orders.x'):
        self.hosts = hosts
        self.creds = creds
        self.exchange = exchange
        self.connection = None
        self.channel = None

    def _connect(self):
        params = [
            pika.ConnectionParameters(host=h, credentials=self.creds)
            for h in self.hosts
        ]
        self.connection = pika.BlockingConnection(params)   # tries each in order
        self.channel = self.connection.channel()
        self.channel.confirm_delivery()
        self.channel.exchange_declare(self.exchange, exchange_type='topic', durable=True)

    def publish(self, routing_key: str, body: bytes, persistent: bool = True):
        if self.connection is None or self.connection.is_closed:
            self._connect()

        properties = pika.BasicProperties(
            delivery_mode=2 if persistent else 1,
            content_type='application/json',
        )

        try:
            self.channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
                mandatory=True,
            )
        except pika.exceptions.UnroutableError:
            # Mandatory + no binding → message returned
            raise
        except pika.exceptions.NackError:
            # Publisher confirms = nacked
            raise


# ==========================================================================
# 6. CONSUMER WITH AUTO-RECONNECT
# ==========================================================================

import time
import logging


log = logging.getLogger(__name__)


class HAConsumer:
    def __init__(self, hosts: list[str], creds, queue: str, handler):
        self.hosts = hosts
        self.creds = creds
        self.queue = queue
        self.handler = handler

    def run(self):
        while True:
            try:
                self._consume()
            except pika.exceptions.AMQPConnectionError as e:
                log.warning(f"Connection lost: {e}. Reconnecting in 5s")
                time.sleep(5)
            except KeyboardInterrupt:
                break

    def _consume(self):
        params = [
            pika.ConnectionParameters(host=h, credentials=self.creds, heartbeat=30)
            for h in self.hosts
        ]
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.basic_qos(prefetch_count=10)

        def callback(ch, method, props, body):
            try:
                self.handler(body, props)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                log.exception(f"Handler error: {e}")
                # Reject + requeue
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        channel.basic_consume(queue=self.queue, on_message_callback=callback)
        channel.start_consuming()


# ==========================================================================
# 7. ASYNC (aio-pika)
# ==========================================================================

async def async_consume_quorum():
    connection = await aio_pika.connect_robust(
        "amqp://admin:admin@rabbit-1:5672/",
    )
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue(
            'orders',
            durable=True,
            arguments={
                'x-queue-type': 'quorum',
                'x-quorum-initial-group-size': 3,
            },
        )

        async with queue.iterator() as it:
            async for message in it:
                async with message.process(requeue=False):
                    try:
                        await process_order(message.body)
                    except Exception:
                        # Auto-nack on exception via context
                        raise


async def process_order(body):
    print(f"Processing: {body}")


# ==========================================================================
# 8. DEAD LETTER EXCHANGE
# ==========================================================================

def setup_dlq():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbit-1'))
    channel = connection.channel()

    # DLX exchange
    channel.exchange_declare(exchange='dlx', exchange_type='direct', durable=True)

    # DLQ queue
    channel.queue_declare(queue='orders.dlq', durable=True)
    channel.queue_bind(queue='orders.dlq', exchange='dlx', routing_key='orders.dlq')

    # Main queue with DLX
    channel.queue_declare(
        queue='orders',
        durable=True,
        arguments={
            'x-queue-type': 'quorum',
            'x-delivery-limit': 5,
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'orders.dlq',
        },
    )


# ==========================================================================
# 9. ADMIN: QUEUE STATUS
# ==========================================================================

# CLI commands
"""
# Quorum queue status
rabbitmq-queues quorum_status orders

# Cluster status
rabbitmqctl cluster_status

# Add/remove queue member
rabbitmq-queues add_member orders rabbit@node-4
rabbitmq-queues delete_member orders rabbit@node-4

# Force shrink (if member offline indefinitely)
rabbitmq-queues shrink rabbit@node-3 orders


# Bulk operations
rabbitmqctl list_queues name type messages messages_ready messages_unacknowledged


# Stream-specific
rabbitmqctl list_queues name type messages_acknowledged_per_consumer
"""


# ==========================================================================
# 10. PROD CONFIG (rabbitmq.conf)
# ==========================================================================

RABBITMQ_CONF = """
# rabbitmq.conf — production

# Logging
log.console = true
log.console.level = info

# Networking
listeners.tcp.default = 5672
listeners.ssl.default = 5671
ssl_options.certfile = /etc/rabbitmq/server.crt
ssl_options.keyfile = /etc/rabbitmq/server.key

# Memory + disk
vm_memory_high_watermark.relative = 0.6
vm_memory_high_watermark_paging_ratio = 0.5
disk_free_limit.absolute = 5GB

# Cluster
cluster_partition_handling = pause_minority
cluster_keepalive_interval = 10000

# Connections
connection_max = 10000
channel_max = 2000
heartbeat = 60

# Default user (change!)
default_user = admin
default_pass = admin

# Quorum defaults
quorum.commands_soft_limit = 32
"""


# ==========================================================================
# 11. K8S DEPLOYMENT
# ==========================================================================

K8S_RABBITMQ_OPERATOR = """
# Use RabbitMQ Operator for k8s
# https://github.com/rabbitmq/cluster-operator

apiVersion: rabbitmq.com/v1beta1
kind: RabbitmqCluster
metadata:
  name: prod-rabbit
spec:
  replicas: 3
  resources:
    requests:
      cpu: 1
      memory: 4Gi
    limits:
      cpu: 4
      memory: 8Gi
  persistence:
    storageClassName: ssd
    storage: 100Gi
  rabbitmq:
    additionalConfig: |
      cluster_partition_handling = pause_minority
      vm_memory_high_watermark.relative = 0.6
      log.console.level = info
"""
