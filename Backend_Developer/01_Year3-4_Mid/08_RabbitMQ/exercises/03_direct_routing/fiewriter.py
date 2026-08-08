"""
RabbitMQ Exercise 03 — Direct Exchange Subscriber: fiewriter (file writer)
==============================================================================
TASK: TODO 1 — is queue ko sirf "Warning" chahiye, Error/Info/Other
      NAHI (yehi direct exchange ki selectivity prove karega — isko
      kabhi "Other" nahi milna chahiye).

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "logs_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: sirf Warning chahiye — is subscriber ko baaki severities ka
#   traffic bilkul nahi dikhna chahiye.
#   Hint: ["Warning"]
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
    print('[x] Writing to File:::: %r' % body)


channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

if __name__ == "__main__":
    channel.start_consuming()
