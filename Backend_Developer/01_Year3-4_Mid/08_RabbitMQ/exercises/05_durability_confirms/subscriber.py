"""
RabbitMQ Exercise 05 — Durability & Confirms Subscriber (Work Queue)
=========================================================================
TASK: TODO 3 — queue ko DURABLE banao, taaki broker restart ke baad
      bhi queue (aur uske persistent messages) survive karein.
      Persistent messages (delivery_mode=2, publisher.py TODO 2) ka
      koi fayda nahi agar queue khud hi restart pe gayab ho jaaye —
      dono chahiye ek saath.

Prereq: docker compose up -d   |   pip install pika
"""

import pika
import random
import time

subId = random.randint(1, 100)
print("Subscriber Id = ", subId)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='logs_exchange', exchange_type='direct', durable=True)

queue_name = "task_queue"

# ─────────────────────────────────────────────────────────
# TODO 3: queue ko durable banao.
#   Hint: True
QUEUE_DURABLE = None
# ─────────────────────────────────────────────────────────

if QUEUE_DURABLE is None:
    print("❌ TODO 3 abhi bharna hai — QUEUE_DURABLE set karo (Hint: True)")
    raise SystemExit(1)

channel.queue_declare(queue=queue_name, durable=QUEUE_DURABLE)

severity = ["Error", "Warning", "Info", "Other"]
for s in severity:
    channel.queue_bind(exchange='logs_exchange', queue=queue_name, routing_key=s)

print('[*] waiting for the messages')


def callback(ch, method, properties, body):
    print('[x] Received message:::: %r' % body)
    work = 2
    print("Working for ", work, "seconds")
    while work > 0:
        print(".", end="")
        time.sleep(1)
        work -= 1
    print("!")
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=queue_name, on_message_callback=callback)

if __name__ == "__main__":
    channel.start_consuming()
