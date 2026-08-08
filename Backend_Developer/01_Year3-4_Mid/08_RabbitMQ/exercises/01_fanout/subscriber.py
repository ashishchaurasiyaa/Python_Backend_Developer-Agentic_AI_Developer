"""
RabbitMQ Exercise 01 — Fanout Exchange (Subscriber)
=====================================================
TASK:
  1. TODO 1: EXCHANGE_TYPE bharo (publisher.py se match hona chahiye,
     warna "inequivalent arg" error milega)
  2. TODO 2: BINDING_KEY socho — fanout me routing_key ki zaroorat hai?
  3. Isse do alag terminals me chalao (2 subscribers), phir teesre
     terminal me publisher.py chalao — DONO ko SAME message milega.

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "br_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: exchange type — publisher.py jaisa hi hona chahiye.
#   Hint: "fanout"
EXCHANGE_TYPE = None
# ─────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────
# TODO 2: fanout exchange ROUTING KEY dekhta hi nahi — har bound
#   queue ko message milta hai chahe routing_key kuch bhi ho. Isliye
#   yahan empty string chalta hai (direct/topic exchanges me yeh
#   REQUIRED hoga — wahan bhool gaye to message hi nahi milega).
#   Hint: ""
BINDING_KEY = None
# ─────────────────────────────────────────────────────────

if EXCHANGE_TYPE is None or BINDING_KEY is None:
    print("❌ TODO abhi bharna hai — EXCHANGE_TYPE aur BINDING_KEY set karo")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange=EXCHANGE, exchange_type=EXCHANGE_TYPE)

result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue
print("Subscriber queue_name =", queue_name)

channel.queue_bind(exchange=EXCHANGE, queue=queue_name, routing_key=BINDING_KEY)

print('[*] waiting for the messages')


def callback(ch, method, properties, body):
    print('[x] %r' % body)


channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

if __name__ == "__main__":
    channel.start_consuming()
