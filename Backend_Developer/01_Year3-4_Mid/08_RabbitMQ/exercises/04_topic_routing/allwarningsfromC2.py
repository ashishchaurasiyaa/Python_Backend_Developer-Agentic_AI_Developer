"""
RabbitMQ Exercise 04 — Topic Subscriber: allwarningsfromC2
===============================================================
TASK: TODO 1 — sirf Warning severity ke messages chahiye jo component
      C2 se hain (beech ka priority/action kuch bhi ho sakta hai).

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "system_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: Warning severity (position 0 = "W") AUR component C2
#   (position 3 = "C2") chahiye — beech ka priority.action kuch bhi
#   ho sakta hai (`#` = zero+ words beech me).
#   Hint: "W.#.C2"
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
