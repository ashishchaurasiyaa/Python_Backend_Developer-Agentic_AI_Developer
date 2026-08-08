"""
RabbitMQ Exercise 03 — Direct Exchange (Publisher)
======================================================
OBJECTIVE: samjho ki DIRECT exchange sirf EXACT routing_key match
           wali queues ko message deta hai — baaki sab ko nahi. Yeh
           01_fanout se farak hai (fanout sabko deta hai, key ignore
           karke).

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
