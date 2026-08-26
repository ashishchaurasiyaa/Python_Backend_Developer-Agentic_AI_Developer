"""
RabbitMQ Exercise 08 — Idempotent Consumer (Publisher)
=======================================================
OBJECTIVE: at-least-once delivery simulate karo — same message THRICE deliver karo
           (payment broker crash simulate) aur consumer ko sirf ONCE process karna hai.

SCENARIO:
  1. Payment task queue mein jaata hai
  2. Consumer payment process karta hai
  3. Consumer CRASHES before ACK
  4. RabbitMQ redelivers message
  5. Consumer dobara process karta hai → DOUBLE CHARGE ❌

FIX: Idempotent consumer — message_id check karo, already processed? Skip karo.

MECHANISM (andar kya hota hai — WHY yeh consumer ki responsibility hai,
  broker ki nahi): at-least-once delivery koi bug nahi hai, RabbitMQ ka
  DELIBERATE design hai. Jab consumer process karke ACK bhejne se
  PEHLE crash ho jaaye, broker ke paas yeh janne ka koi tareeka nahi ki
  "processing complete hui thi ya nahi" — sirf itna pata hai ACK nahi
  aaya. Ambiguity resolve karne ke do options the: silently drop karo
  (agar processing ho chuki thi to fine, nahi hui thi to message KHO
  gaya — data loss) ya REDELIVER karo (agar processing ho chuki thi to
  duplicate — par kam se kam LOSS nahi hota). RabbitMQ hamesha DOOSRA
  choose karta hai — matlab dedup hamesha CONSUMER ka kaam hai. Dedup
  key STABLE hona chahiye across redeliveries (publisher-set message_id,
  ya ek natural business key) — is exercise ka in-memory set sirf ek
  process-lifetime tak surviv karta hai; production me yeh ek DB unique
  constraint (ya Redis SETNX) hota hai jo process-restart ke baad bhi
  yaad rakhe.

TASK:
  Kuch nahi bharna yahan. Subscriber.py ke TODOs bharo.
  publisher.py same message_id se 3 baar "deliver" karta hai.

Run: python publisher.py  (phir subscriber.py, phir verify.py)
Prereq: docker compose up -d   |   pip install pika
"""

import pika

QUEUE = "payment_queue_demo"

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel    = connection.channel()

channel.queue_declare(queue=QUEUE, durable=True)

# Simulate at-least-once: same payment sent 3 times (worker crash + redelivery)
PAYMENT_ID = "pay_order_42_user_99"
AMOUNT     = 1999.0

if __name__ == "__main__":
    for i in range(1, 4):
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=f'{{"payment_id": "{PAYMENT_ID}", "amount": {AMOUNT}, "delivery_attempt": {i}}}',
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=PAYMENT_ID,    # unique ID — subscriber uses this for dedup
            ),
        )
        print(f"[→] Delivery {i}/3: payment_id={PAYMENT_ID}, amount={AMOUNT}")

    print(f"\n[✓] 3 deliveries of same payment in {QUEUE}")
    print("    Run: python subscriber.py")
    connection.close()
