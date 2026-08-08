"""
RabbitMQ Exercise 04 — Topic Subscriber: errorhandlingsub
==============================================================
TASK: TODO 1 — Error severity ke SAARE messages chahiye, chahe
      priority/action/component kuch bhi ho.

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "system_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: sirf severity "E" (Error) chahiye — baaki teeno position
#   (priority.action.component) kuch bhi ho sakta hai.
#   Hint: "E.#"
BINDING_PATTERN = None
# ─────────────────────────────────────────────────────────

if BINDING_PATTERN is None:
    print("❌ TODO 1 abhi bharna hai — BINDING_PATTERN set karo")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)

result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange=EXCHANGE, queue=queue_name, routing_key=BINDING_PATTERN)

print('[*] waiting for the messages')


def callback(ch, method, properties, body):
    print('[x] :::: %r' % body)


channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

if __name__ == "__main__":
    channel.start_consuming()
