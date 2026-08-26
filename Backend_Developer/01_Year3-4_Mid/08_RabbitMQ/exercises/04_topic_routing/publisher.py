"""
RabbitMQ Exercise 04 — Topic Exchange (Publisher)
=====================================================
OBJECTIVE: samjho ki topic exchange me `*` (exactly ek word) aur `#`
           (zero ya zyada words) kaise match karte hain routing_key ke
           against.

Routing key shape: "{severity}.{priority}.{action}.{component}"
  e.g. "E.H.A1.C1" = Error, High priority, Action1, Component1

MECHANISM (andar kya hota hai): direct exchange ek simple hash-map
  lookup hai (03_direct_routing dekho), par topic ko EXACT string match
  nahi karna — usse PATTERN match karna hai. Internally RabbitMQ
  bindings ko ek TRIE (segment-by-segment tree) me organize karta hai:
  har `.`-separated segment ek tree level hai, `*` us level pe "koi bhi
  ek segment" match karta hai, `#` "zero ya zyada segments" (isiliye
  `#` beech ke bhi variable-length gaps cover kar sakta hai, `*` sirf
  exactly ek). Publish hote hi broker routing_key ko segments me todta
  hai aur trie traverse karta hai — ek publish MULTIPLE bindings match
  kar sakta hai (jaisa "W.M.A3.C2" neeche do subscribers ko milta hai)
  kyunki trie traversal saare matching paths collect karta hai, sirf
  pehla nahi.

TASK:
  1. TODO 1: EXCHANGE_TYPE bharo
  2. errorhandlingsub.py / A3actiontaker.py / allwarningsfromC2.py ke
     apne TODO bharo (binding pattern — wildcards)
  3. Run: python publisher.py   (subscribers pehle alag terminals me)
  4. Ya seedha: python verify.py

Prereq: docker compose up -d   |   pip install pika
"""

import pika

EXCHANGE = "system_exchange"

# ─────────────────────────────────────────────────────────
# TODO 1: topic exchange ka type — `.`-separated routing_key pe
#   `*` (exactly ek word) aur `#` (zero+ words) wildcard match
#   karta hai. (direct = exact match, fanout = sab kuch, topic =
#   pattern match)
#   Hint: "topic"
EXCHANGE_TYPE = None
# ─────────────────────────────────────────────────────────

if EXCHANGE_TYPE is None:
    print("❌ TODO 1 abhi bharna hai — EXCHANGE_TYPE set karo (Hint: \"topic\")")
    raise SystemExit(1)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.exchange_declare(exchange=EXCHANGE, exchange_type=EXCHANGE_TYPE, durable=True)

if __name__ == "__main__":
    # Deterministic set (random ki jagah) — teen routing keys jo
    # teeno subscribers ki selectivity clearly prove karte hain:
    #   1. sirf ek subscriber ko milega
    #   2. do subscribers ko milega
    #   3. kisi ko nahi milega (negative control)
    test_messages = [
        ("E.H.A1.C1", "sirf E.# (errorhandlingsub) ko milna chahiye"),
        ("W.M.A3.C2", "A3actiontaker (#.A3.#) AUR allwarningsfromC2 (W.#.C2) dono ko milna chahiye"),
        ("I.L.A2.C3", "KISI ko nahi milna chahiye (koi pattern match nahi karta)"),
    ]

    for rk, note in test_messages:
        message = f"{rk} :::: {note}"
        channel.basic_publish(exchange=EXCHANGE, routing_key=rk, body=message)
        print("[x] sent %r" % message)

    connection.close()
