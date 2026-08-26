"""
RabbitMQ Exercise 07 — Manual ACK / NACK / REJECT (Publisher)
===============================================================
OBJECTIVE: samjho ki consumer message acknowledgement modes ka kya effect
           padta hai queue state pe.

Three messages bhejenge:
  "success"       → consumer ACK karega → queue se permanently remove
  "requeue"       → consumer NACK + requeue=True → message wapas queue mein
  "drop"          → consumer NACK + requeue=False → DLX ya discard

MECHANISM (andar kya hota hai): jab broker ek message consumer ko
  DELIVER karta hai, woh use QUEUE se turant nahi hataata — sirf
  "delivered but unconfirmed" mark kar deta hai (us consumer connection
  ke liye). Jab tak ACK na aaye, broker use woh SAME message dobara
  usi consumer ko nahi bhejega — par agar consumer ka TCP connection
  BEECH mein hi drop ho jaaye (crash), broker automatically un saare
  unacked messages ko queue me WAPAS daal deta hai (kisi doosre consumer
  ko milega) — yehi wajah hai "crash mid-processing" message loss nahi
  banti agar ACK time pe sahi jagah lagाया ho. `basic_qos(prefetch_count=N)`
  yeh control karta hai ki broker EK SAATH kitne unacked messages ek
  consumer ko push kar sakta hai before rukna — yeh asli BACKPRESSURE
  knob hai: prefetch high = fast par ek slow-consumer crash pe zyada
  in-flight messages redeliver hote; prefetch low = safer par throughput
  kam.

TASK:
  Yahan kuch nahi bharna — bas subscriber.py ke TODOs bharo.
  Verify karo ki queue behavior correct hai.

Run: python publisher.py  (phir subscriber.py, phir verify.py)
Prereq: docker compose up -d   |   pip install pika
"""

import pika

QUEUE = "ack_demo_queue"
DLQ   = "ack_demo_dlq"
DLX   = "ack_demo_dlx"

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel    = connection.channel()

# DLX for dropped messages
channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
channel.queue_declare(queue=DLQ, durable=True)
channel.queue_bind(queue=DLQ, exchange=DLX, routing_key="dropped")

# Main queue with DLX for dropped messages
channel.queue_declare(
    queue=QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange":    DLX,
        "x-dead-letter-routing-key": "dropped",
    },
)

if __name__ == "__main__":
    messages = [
        ("success", "Process this normally"),
        ("requeue", "I will fail but should come back"),
        ("drop",    "I will fail and be discarded to DLQ"),
    ]
    for msg_type, body in messages:
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=f"{msg_type}:{body}",
            properties=pika.BasicProperties(delivery_mode=2, message_id=msg_type),
        )
        print(f"[→] Sent '{msg_type}'")

    print(f"\n[✓] 3 messages in {QUEUE}")
    print("    Run: python subscriber.py  (stops after processing 3 messages)")
    connection.close()
