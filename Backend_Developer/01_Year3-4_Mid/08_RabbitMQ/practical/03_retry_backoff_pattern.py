"""
RabbitMQ — Retry with Exponential Backoff + DLQ Pattern
═══════════════════════════════════════════════════════════════
Run: python 03_retry_backoff_pattern.py

pip install aio-pika

Pattern:
  Message fail hota hai →
    attempt 1: 2 sec wait → retry
    attempt 2: 4 sec wait → retry
    attempt 3: 8 sec wait → retry
    attempt 4: Permanent DLQ → alert

Queues:
  main_queue         → actual work
  retry_2s_queue     → 2 sec TTL → wapas main
  retry_4s_queue     → 4 sec TTL → wapas main
  retry_8s_queue     → 8 sec TTL → wapas main
  permanent_dlq      → give up — alert here
"""

import asyncio
import aio_pika
import json
import logging
import random

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")
logger = logging.getLogger("RetryDemo")

RABBITMQ_URL = "amqp://guest:guest@localhost/"
MAX_RETRIES = 3

# Retry delays in milliseconds
RETRY_DELAYS = {
    1: 2000,   # 1st retry: 2 sec
    2: 4000,   # 2nd retry: 4 sec
    3: 8000,   # 3rd retry: 8 sec
}


# ═══════════════════════════════════════════════════════════
# SECTION 1: Setup — All queues with retry routing
# ═══════════════════════════════════════════════════════════

async def setup_retry_queues(channel: aio_pika.Channel):
    """Retry architecture setup karo"""

    # Main work exchange
    work_exchange = await channel.declare_exchange(
        "work_exchange", aio_pika.ExchangeType.DIRECT, durable=True
    )

    # Retry exchange — retry queues se wapas main queue
    retry_exchange = await channel.declare_exchange(
        "retry_exchange", aio_pika.ExchangeType.DIRECT, durable=True
    )

    # Permanent DLQ exchange
    dlq_exchange = await channel.declare_exchange(
        "dlq_exchange", aio_pika.ExchangeType.DIRECT, durable=True
    )

    # ── Permanent DLQ ──
    permanent_dlq = await channel.declare_queue("permanent_dlq", durable=True)
    await permanent_dlq.bind(dlq_exchange, routing_key="permanent_fail")

    # ── Main work queue ──
    main_queue = await channel.declare_queue(
        "email_send_queue",
        durable=True,
        arguments={
            "x-dead-letter-exchange":    "dlq_exchange",
            "x-dead-letter-routing-key": "permanent_fail",
        }
    )
    await main_queue.bind(work_exchange, routing_key="send_email")

    # ── Retry queues (each with TTL → bounce back to main) ──
    for attempt, delay_ms in RETRY_DELAYS.items():
        retry_q = await channel.declare_queue(
            f"retry_{delay_ms}ms_queue",
            durable=True,
            arguments={
                "x-message-ttl":             delay_ms,
                "x-dead-letter-exchange":    "work_exchange",   # TTL expire → main queue
                "x-dead-letter-routing-key": "send_email",
            }
        )
        await retry_q.bind(retry_exchange, routing_key=f"retry_{attempt}")

    logger.info("✅ Retry queues setup complete!")
    return work_exchange, retry_exchange, dlq_exchange


# ═══════════════════════════════════════════════════════════
# SECTION 2: Producer
# ═══════════════════════════════════════════════════════════

async def send_emails(work_exchange: aio_pika.Exchange):
    """Email tasks queue mein daalo"""
    emails = [
        {"id": 1, "to": "alice@test.com",   "subject": "Welcome!",       "will_fail": False},
        {"id": 2, "to": "bob@test.com",     "subject": "Order confirm",  "will_fail": True},  # → DLQ
        {"id": 3, "to": "charlie@test.com", "subject": "Reset password", "will_fail": False},
        {"id": 4, "to": "dave@test.com",    "subject": "Invoice ready",  "will_fail": True},  # → DLQ
    ]

    for email in emails:
        await work_exchange.publish(
            aio_pika.Message(
                body=json.dumps({**email, "retry_count": 0}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key="send_email"
        )
        logger.info(f"📤 Queued email {email['id']} → {email['to']}")


# ═══════════════════════════════════════════════════════════
# SECTION 3: Consumer with Retry Logic
# ═══════════════════════════════════════════════════════════

async def email_worker(channel: aio_pika.Channel, retry_exchange: aio_pika.Exchange):
    """Email worker — retry karo on failure"""
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue("email_send_queue", durable=True)
    logger.info("Email worker started — waiting for tasks...")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process(ignore_processed=True):
                data = json.loads(message.body)
                retry_count = data.get("retry_count", 0)
                email_id = data.get("id")

                logger.info(f"📥 Processing email {email_id} (attempt {retry_count + 1}/{MAX_RETRIES + 1})")

                try:
                    # Simulate email sending — failure scenario
                    if data.get("will_fail", False):
                        raise ConnectionError(f"SMTP server timeout for email {email_id}")

                    # Success
                    logger.info(f"✅ Email {email_id} sent to {data['to']}")
                    await message.ack()

                except Exception as e:
                    logger.warning(f"❌ Email {email_id} failed: {e}")

                    if retry_count >= MAX_RETRIES:
                        # Max retries reach — permanent DLQ
                        logger.error(f"💀 Email {email_id} → PERMANENT DLQ (gave up after {MAX_RETRIES} retries)")
                        await message.nack(requeue=False)   # → permanent DLQ via x-dead-letter

                    else:
                        # Retry karo — delay ke baad
                        next_retry = retry_count + 1
                        delay = RETRY_DELAYS[next_retry]
                        logger.info(f"🔄 Email {email_id} → retry {next_retry}/{MAX_RETRIES} in {delay/1000}s")

                        # Updated retry_count ke saath message
                        data["retry_count"] = next_retry
                        await retry_exchange.publish(
                            aio_pika.Message(
                                body=json.dumps(data).encode(),
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                content_type="application/json",
                            ),
                            routing_key=f"retry_{next_retry}"
                        )
                        await message.ack()  # original ack karo


# ═══════════════════════════════════════════════════════════
# SECTION 4: DLQ Monitor
# ═══════════════════════════════════════════════════════════

async def dlq_monitor():
    """Permanent DLQ — failed messages alert karo"""
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()

    queue = await channel.declare_queue("permanent_dlq", durable=True)
    logger.info("DLQ Monitor started!")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                data = json.loads(message.body)
                logger.error(
                    f"⚠️  PERMANENT FAILURE ALERT:\n"
                    f"     Email ID: {data.get('id')}\n"
                    f"     To:       {data.get('to')}\n"
                    f"     Subject:  {data.get('subject')}\n"
                    f"     Retried:  {data.get('retry_count')} times\n"
                    f"     Action:   Manual review required!"
                )
                # Yahan: Slack alert, PagerDuty, DB log, email to admin


# ═══════════════════════════════════════════════════════════
# SECTION 5: Main Runner
# ═══════════════════════════════════════════════════════════

async def main():
    logger.info("=== Retry + Exponential Backoff Demo ===\n")

    # Connection
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    async with connection:
        channel = await connection.channel()

        # Setup
        work_exchange, retry_exchange, dlq_exchange = await setup_retry_queues(channel)

        # DLQ monitor background mein
        asyncio.create_task(dlq_monitor())

        # Worker start karo
        worker_task = asyncio.create_task(
            email_worker(channel, retry_exchange)
        )

        # Thoda wait karo worker ready hone ke liye
        await asyncio.sleep(0.5)

        # Emails bhejo
        await send_emails(work_exchange)

        logger.info("\n⏳ Waiting for all retries to complete (max 15 seconds)...")
        await asyncio.sleep(15)

        worker_task.cancel()
        logger.info("\n=== Demo complete ===")

        # Expected output:
        # Email 1 → sent immediately ✅
        # Email 2 → attempt 1 fail → 2s wait → attempt 2 fail → 4s wait → attempt 3 fail → 8s wait → attempt 4 fail → DLQ
        # Email 3 → sent immediately ✅
        # Email 4 → same as email 2 → DLQ

if __name__ == "__main__":
    asyncio.run(main())
