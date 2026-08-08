"""
RabbitMQ Exercise 04 — Topic Subscriber: A3actiontaker
==========================================================
TASK: TODO 1 — "A3" action wale SAARE messages chahiye, chahe
      severity/priority/component kuch bhi ho.

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "system_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: A3 action wale SAARE messages chahiye — position 1
#   (severity.priority) aur position 3 (component) kuch bhi ho sakta
#   hai. `#` zero ya zyada words match karta hai, `*` exactly ek word.
#   Hint: "#.A3.#"
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
