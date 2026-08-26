"""
RabbitMQ Exercise 03 — Direct Exchange (Publisher)
======================================================
OBJECTIVE: samjho ki DIRECT exchange sirf EXACT routing_key match
           wali queues ko message deta hai — baaki sab ko nahi. Yeh
           01_fanout se farak hai (fanout sabko deta hai, key ignore
           karke).

MECHANISM (andar kya hota hai): direct exchange internally ek HASH MAP
  rakhta hai — `{routing_key_string: [queue1, queue2, ...]}`. Publish
  hote hi broker is map me EXACT-STRING lookup karta hai — O(1), poori
  binding list scan nahi karta. Yehi wajah hai direct, topic se FASTER
  hota hai jab tumhe exact-match hi chahiye: topic ko `.`-separated
  segments pe pattern-match (trie traversal) karna padta hai, direct ko
  sirf ek dict lookup. Agar routing_key kisi bhi bound queue se match na
  kare, message SILENTLY DISCARD ho jaata hai (jab tak `mandatory=True`
  na ho) — koi error nahi aata, bas kahin nahi pahunchta.

TASK:
  1. TODO 1: EXCHANGE_TYPE bharo
  2. alarmraiser.py / fiewriter.py / screenprinter.py ke apne TODO
     bharo (kaunse routing_keys sunne hain)
  3. Run: python publisher.py   (subscribers pehle alag terminals me
     chalao)
  4. Ya seedha: python verify.py

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "logs_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: direct exchange ka type — routing_key ka EXACT match karta
#   hai bound queues ke against (fanout jaisa broadcast NAHI).
#   Hint: "direct"
EXCHANGE_TYPE = None
# ─────────────────────────────────────────────────────────

if EXCHANGE_TYPE is None:
    print("❌ TODO 1 abhi bharna hai — EXCHANGE_TYPE set karo (Hint: \"direct\")")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.exchange_declare(exchange=EXCHANGE, exchange_type=EXCHANGE_TYPE)

if __name__ == "__main__":
    # Deterministic set — random ki jagah, taaki verify.py exactly
    # prove kar sake kaunsa subscriber kya paata hai.
    severity = ["Error", "Warning", "Info", "Other"]
    messages = ["EMsg", "WMsg", "IMsg", "OMsg"]

    for rk, message in zip(severity, messages):
        channel.basic_publish(exchange=EXCHANGE, routing_key=rk, body=message)
        print("[x] sent %r with routing_key=%r" % (message, rk))

    channel.exchange_delete(exchange=EXCHANGE, if_unused=False)
    connection.close()
