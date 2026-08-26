"""
RabbitMQ Exercise 07 — ACK / NACK Subscriber
==============================================
TASK:
  1. TODO 1: "success" message → basic_ack
  2. TODO 2: "requeue" message → basic_nack WITH requeue=True
  3. TODO 3: "drop" message → basic_nack WITHOUT requeue (goes to DLX)

Run: python subscriber.py   (exits after 3 messages processed)
Prereq: publisher.py already run
"""

import pika

QUEUE   = "ack_demo_queue"
MSG_MAX = 3
received = []

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel    = connection.channel()
channel.basic_qos(prefetch_count=1)


def on_message(ch, method, properties, body):
    msg_type, content = body.decode().split(":", 1)
    received.append(msg_type)
    print(f"\n[←] Received '{msg_type}': {content}")

    if msg_type == "success":
        # ──────────────────────────────────────────────────────────────
        # TODO 1: ACK karo — message permanently queue se remove ho jaata hai.
        #   basic_ack(delivery_tag=...) = "maine process kar liya, hata do"
        #   Hint: ch.basic_ack(delivery_tag=method.delivery_tag)
        print("  → TODO 1: success path — basic_ack karo")
        ch.basic_ack(delivery_tag=method.delivery_tag)   # ← placeholder, replace karo
        # ──────────────────────────────────────────────────────────────

    elif msg_type == "requeue":
        # ──────────────────────────────────────────────────────────────
        # TODO 2: NACK WITH requeue=True.
        #   Message WAPAS queue ke front pe jaata hai (not necessarily
        #   front — depends on queue, but generally re-enqueued).
        #   Use case: transient failure — retry karo thodi der baad.
        #   WARNING: requeue=True without retry limit = infinite loop!
        #   Hint: ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        print("  → TODO 2: requeue path — basic_nack(requeue=True) karo")
        ch.basic_ack(delivery_tag=method.delivery_tag)   # ← isse badlo
        # ──────────────────────────────────────────────────────────────

    elif msg_type == "drop":
        # ──────────────────────────────────────────────────────────────
        # TODO 3: NACK WITHOUT requeue — message DLX pe jaata hai.
        #   requeue=False = "yeh message kisi kaam ka nahi, queue se hata do"
        #   Publisher ne DLX configure kiya hai → message DLQ mein jaayega
        #   Use case: malformed data, permanent error, poison message
        #   Hint: ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print("  → TODO 3: drop path — basic_nack(requeue=False) karo")
        ch.basic_ack(delivery_tag=method.delivery_tag)   # ← isse badlo
        # ──────────────────────────────────────────────────────────────

    # Stop after processing all 3 initial messages
    if len(received) >= MSG_MAX:
        ch.stop_consuming()


channel.basic_consume(queue=QUEUE, on_message_callback=on_message)

if __name__ == "__main__":
    print(f"[*] Waiting for {MSG_MAX} messages...")
    channel.start_consuming()
    print(f"\n[*] Done. Processed: {received}")
    connection.close()
