"""
RabbitMQ Exercise 01 — Fanout Exchange (Publisher)
=====================================================
OBJECTIVE: ek message bhejo jo SAARE subscribers ko mile — koi routing
           key filtering nahi, sirf broadcast.

TASK:
  1. TODO 1: EXCHANGE_TYPE bharo (fanout ka matlab kya hai?)
  2. Run: python publisher.py   (subscriber.py pehle 1-2 alag terminals
     me chalao taaki unhe message mile)
  3. Ya seedha: python verify.py   (dono roles khud chalata hai aur
     proof deta hai ki SAARE subscribers ko message mila)

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "br_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: Fanout exchange ka type kya hota hai?
#   Fanout = routing_key ko IGNORE karta hai, bound SAARI queues ko
#   message deta hai. (Compare: 'direct' sirf EXACT matching
#   routing_key wali queue ko deta hai — 03_direct_routing me dekhoge.)
#   Hint: "fanout"
EXCHANGE_TYPE = None
# ─────────────────────────────────────────────────────────

if EXCHANGE_TYPE is None:
    print("❌ TODO 1 abhi bharna hai — EXCHANGE_TYPE set karo (Hint: \"fanout\")")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.exchange_declare(exchange=EXCHANGE, exchange_type=EXCHANGE_TYPE)

if __name__ == "__main__":
    for i in range(4):
        message = "Hello" + str(i)
        channel.basic_publish(exchange=EXCHANGE, routing_key='', body=message)
        print("[x] sent %r" % message)

    channel.exchange_delete(exchange=EXCHANGE, if_unused=False)
    connection.close()
