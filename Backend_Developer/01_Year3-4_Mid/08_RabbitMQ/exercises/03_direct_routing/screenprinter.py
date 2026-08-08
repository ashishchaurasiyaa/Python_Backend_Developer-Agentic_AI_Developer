"""
RabbitMQ Exercise 03 — Direct Exchange Subscriber: screenprinter
====================================================================
TASK: TODO 1 — is queue ko Error, Warning, aur Info teeno chahiye
      (screen pe sab kuch dikhana hai) — sirf "Other" nahi.

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "logs_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: Error + Warning + Info chahiye, "Other" nahi.
#   Hint: ["Error", "Warning", "Info"]
BOUND_KEYS = None
# ─────────────────────────────────────────────────────────

if BOUND_KEYS is None:
    print("❌ TODO 1 abhi bharna hai — BOUND_KEYS set karo")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange=EXCHANGE, exchange_type='direct')

result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

for key in BOUND_KEYS:
    channel.queue_bind(exchange=EXCHANGE, queue=queue_name, routing_key=key)

print('[*] waiting for the messages')


def callback(ch, method, properties, body):
    print('[x] Alarm:::: %r' % body)


channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

if __name__ == "__main__":
    channel.start_consuming()
