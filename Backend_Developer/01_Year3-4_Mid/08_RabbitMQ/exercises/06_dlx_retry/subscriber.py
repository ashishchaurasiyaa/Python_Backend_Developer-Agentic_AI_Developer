"""
RabbitMQ Exercise 06 — DLX Retry (Subscriber)
===============================================
OBJECTIVE: consumer NACKs failed messages. DLX + TTL retry loop chalta hai.
           Max retries ke baad message dead_letter_queue mein jaata hai.

TASK:
  4. TODO 3: x-death count check karo — max retries exceed hue?
  5. TODO 4: NACK karo WITHOUT requeue — DLX trigger karo
  6. Run: python subscriber.py   (publisher.py ke baad)

Prereq: docker compose up -d   |   publisher.py already run ho chuka ho
"""

import pika
import time

MAX_RETRIES = 3

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel    = connection.channel()

channel.basic_qos(prefetch_count=1)


def get_retry_count(properties) -> int:
    """
    RabbitMQ x-death header se total retry count nikalo.
    Har baar message dead-letter hota hai, broker ek entry add karta hai.
    count field = kitni baar is queue se dead-letter hua.
    """
    x_death = (properties.headers or {}).get("x-death", [])
    return sum(int(d.get("count", 0)) for d in x_death)


def on_message(ch, method, properties, body):
    task_id, payload = body.decode().split(":", 1)
    retry_count = get_retry_count(properties)

    print(f"[←] Received: {task_id} | retry #{retry_count} | payload={payload}")

    # Simulate: task-001 always fails, task-002 succeeds on first try
    task_fails = (task_id == "task-001")

    if not task_fails:
        # ── Success path ───────────────────────────────────────────────
        print(f"  [✓] {task_id} processed successfully")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # ── Failure path ───────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # TODO 3: retry_count check karo.
    #   Agar retry_count >= MAX_RETRIES:
    #     → message "dead" routing_key pe manually republish karo DLQ mein
    #       (ya simply ACK karo — x-overflow se already DLQ mein ja sakta hai
    #       depending on config — yahan manual approach dikhate hain)
    #     → basic_ack karo (remove from main_queue)
    #   Hint:
    #     if retry_count >= MAX_RETRIES:
    #         print(f"  [✗] {task_id} — max retries ({MAX_RETRIES}) exhausted → DLQ")
    #         ch.basic_ack(delivery_tag=method.delivery_tag)
    #         return
    pass   # ← TODO 3: isse badlo
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # TODO 4: NACK karo WITHOUT requeue.
    #   requeue=False → message dead-letters to dlx_exchange
    #   retry_queue pe jaata hai → TTL=3s expire → main_queue pe wapas
    #   DO NOT use requeue=True here — that would send it back instantly
    #   (no delay) and creates a spin loop
    #   Hint:
    #     print(f"  [↩] {task_id} failed (retry {retry_count+1}/{MAX_RETRIES}) → DLX")
    #     ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    print(f"  [✗] {task_id} NACK placeholder — TODO 4 bharo")
    ch.basic_ack(delivery_tag=method.delivery_tag)   # ← isse badlo
    # ──────────────────────────────────────────────────────────────────


channel.basic_consume(queue="main_queue", on_message_callback=on_message)

if __name__ == "__main__":
    print(f"[*] Waiting for tasks (MAX_RETRIES={MAX_RETRIES})... Ctrl+C to stop")
    print(f"    task-001: will fail {MAX_RETRIES}x then go to DLQ")
    print(f"    task-002: will succeed on first try")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[*] Stopped")
        connection.close()
