"""
RabbitMQ Exercise 05 — Durability & Publisher Confirms (Publisher)
========================================================================
OBJECTIVE: samjho durability ke teen pillars —
  1. publisher confirms — broker ne message ACTUALLY accept kiya, sirf
     "fire and forget" nahi
  2. persistent message (delivery_mode=2) — disk pe likha jaaye
  3. durable queue (subscriber.py me) — broker restart survive kare

MECHANISM (andar kya hota hai — teeno ALAG cheezein hain, aksar confuse
  hoti hain):
  - `durable=True` (queue/exchange): sirf DEFINITION broker ki apni
    persistent metadata-store (Mnesia/Khepri) me save hoti hai — taaki
    restart ke baad queue/exchange dobara ban jaaye. Yeh QUEUE ke ANDAR
    KE MESSAGES ko persist NAHI karta — khaali durable queue restart ke
    baad khaali hi milegi agar messages persistent nahi the.
  - `delivery_mode=2` (per-message property): yeh MESSAGE ko disk pe
    fsync karta hai. Durable queue + non-persistent message = restart
    pe message GAYAB; non-durable queue + persistent message = queue
    khud hi restart pe gayab (message bhi saath).  → dono zaroori hain.
  - Publisher confirms: broker ek ASYNC confirm frame bhejta hai, jo
    per-channel ek internal delivery-tag counter se correlate hota hai.
    Persistent message + durable queue ke liye, confirm TABHI aata hai
    jab write disk (ya cluster replica) tak pahunch chuki ho — isiliye
    confirm ek genuine durability guarantee hai, "TCP se broker tak
    pahunch gaya" jaisa weak signal nahi.

TASK:
  1. TODO 1: publisher confirms ON karo
  2. TODO 2: message ko persistent banao (delivery_mode)
  3. subscriber.py me TODO 3 (durable queue) bhi bharo
  4. Run: python publisher.py
  5. Ya seedha: python verify.py (broker ki REAL state check karta hai
     management HTTP API se — sirf "chal gaya" nahi, "sach me persist
     hua" prove karta hai)

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "logs_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: publisher confirms ON karo. Iske BINA basic_publish()
#   "fire and forget" hai — broker ne message accept kiya ya nahi,
#   tumhe pata hi nahi chalega. ON karne ke baad, agar message
#   route/accept NAHI ho paata (aur mandatory=True ho), pika exception
#   raise karta hai — silent data loss nahi hoti.
#   Hint: True
CONFIRMS_ENABLED = None
# ─────────────────────────────────────────────────────────

if CONFIRMS_ENABLED is None:
    print("❌ TODO 1 abhi bharna hai — CONFIRMS_ENABLED = True/False set karo")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

if CONFIRMS_ENABLED:
    channel.confirm_delivery()

channel.exchange_declare(exchange=EXCHANGE, exchange_type='direct', durable=True)


def publish_message(routing_key, body, mandatory=False):
    """Ek message publish karta hai.

    `mandatory=True` verify.py istemal karta hai yeh prove karne ke
    liye ki confirms SACH ME ON hain — unroutable message pe exception
    aani chahiye, silently gayab nahi honi chahiye.
    """
    # ─────────────────────────────────────────────────────
    # TODO 2: message ko PERSISTENT banao — broker crash/restart ke
    #   baad bhi disk se recover ho sake (agar queue bhi durable hai —
    #   subscriber.py ka TODO 3).
    #   delivery_mode: 1 = transient (RAM only, restart pe gayab),
    #                  2 = persistent (disk pe likha jaata hai)
    #   Hint: 2
    DELIVERY_MODE = None
    # ─────────────────────────────────────────────────────

    if DELIVERY_MODE is None:
        print("❌ TODO 2 abhi bharna hai — DELIVERY_MODE set karo (Hint: 2)")
        raise SystemExit(1)

    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=routing_key,
        body=body,
        mandatory=mandatory,
        properties=pika.BasicProperties(delivery_mode=DELIVERY_MODE),
    )


if __name__ == "__main__":
    severity = ["Error", "Warning", "Info", "Other"]
    messages = ["EMsg", "WMsg", "IMsg", "OMsg"]

    for rk, message in zip(severity, messages):
        try:
            publish_message(rk, message)
            print("[x] sent %r (persistent, confirmed)" % message)
        except pika.exceptions.UnroutableError:
            print("[!] broker ne NACK kiya — message accept nahi hua")

    connection.close()
