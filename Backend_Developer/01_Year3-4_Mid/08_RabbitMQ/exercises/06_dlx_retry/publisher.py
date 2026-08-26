"""
RabbitMQ Exercise 06 — Dead Letter Exchange + TTL Retry (Publisher / Setup)
============================================================================
OBJECTIVE: samjho ki failed messages kaise automatically retry hote hain
           DLX + TTL-based delay queue pattern ke through.

FLOW:
  publisher → main_exchange → main_queue
                                  ↓ (consumer NACKs)
                             dlx_exchange → retry_queue (TTL=3s)
                                                ↓ (TTL expires)
                             main_exchange → main_queue (retry)
                                  ↓ (after MAX_RETRIES NACKs)
                             dlx_exchange → dead_letter_queue (final DLQ)

TASK:
  1. TODO 1: main_queue declare karo — DLX arguments ke saath
  2. TODO 2: retry_queue declare karo — TTL + DLX back to main_exchange
  3. Subscriber.py chalao, phir verify.py se proof dekho

Prereq: docker compose up -d   |   pip install pika
"""

import pika

# ── Constants ──────────────────────────────────────────────────────────────
MAIN_EXCHANGE     = "main_exchange"
DLX_EXCHANGE      = "dlx_exchange"
MAIN_QUEUE        = "main_queue"
RETRY_QUEUE       = "retry_queue"
DLQ               = "dead_letter_queue"
RETRY_TTL_MS      = 3000     # 3 seconds between retries

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel    = connection.channel()

# ── Infrastructure setup ───────────────────────────────────────────────────

# 1. Exchanges
channel.exchange_declare(exchange=MAIN_EXCHANGE, exchange_type="direct", durable=True)
channel.exchange_declare(exchange=DLX_EXCHANGE,  exchange_type="direct", durable=True)

# 2. Dead Letter Queue (final destination after all retries exhausted)
channel.queue_declare(queue=DLQ, durable=True)
channel.queue_bind(queue=DLQ, exchange=DLX_EXCHANGE, routing_key="dead")

# ─────────────────────────────────────────────────────────────────────────
# TODO 1: main_queue declare karo WITH DLX arguments.
#   Failed messages (NACKed with requeue=False) automatically
#   dead-letter hote hain dlx_exchange pe, routing_key="retry" se.
#   Arguments:
#     "x-dead-letter-exchange":    DLX_EXCHANGE
#     "x-dead-letter-routing-key": "retry"
#   Hint:
#     channel.queue_declare(
#         queue=MAIN_QUEUE,
#         durable=True,
#         arguments={
#             "x-dead-letter-exchange":    DLX_EXCHANGE,
#             "x-dead-letter-routing-key": "retry",
#         },
#     )
channel.queue_declare(queue=MAIN_QUEUE, durable=True)   # ← isse badlo
channel.queue_bind(queue=MAIN_QUEUE, exchange=MAIN_EXCHANGE, routing_key="task")
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
# TODO 2: retry_queue declare karo WITH:
#   - TTL (x-message-ttl): messages 3s baad expire hoti hain
#   - DLX back to main_exchange (x-dead-letter-exchange)
#   - routing_key back to "task" (x-dead-letter-routing-key)
#   After TTL expires, message main_exchange → main_queue pe wapas jaata hai
#   (automatic retry without any consumer on retry_queue!)
#   Arguments:
#     "x-message-ttl":             RETRY_TTL_MS,
#     "x-dead-letter-exchange":    MAIN_EXCHANGE,
#     "x-dead-letter-routing-key": "task",
channel.queue_declare(queue=RETRY_QUEUE, durable=True)  # ← isse badlo
channel.queue_bind(queue=RETRY_QUEUE, exchange=DLX_EXCHANGE, routing_key="retry")
# ─────────────────────────────────────────────────────────────────────────


def publish_task(task_id: str, payload: str):
    channel.basic_publish(
        exchange=MAIN_EXCHANGE,
        routing_key="task",
        body=f"{task_id}:{payload}",
        properties=pika.BasicProperties(
            delivery_mode=2,              # persistent
            message_id=task_id,
        ),
    )
    print(f"[→] Published task: {task_id}")


if __name__ == "__main__":
    publish_task("task-001", "process_payment_order_42")
    publish_task("task-002", "send_report_to_cfo")
    print("[✓] 2 tasks published to main_queue")
    print("    Now run: python subscriber.py  (in another terminal)")
    connection.close()
