"""
Kafka Lab 03 — Keys, Partitioning & Ordering
=============================================
OBJECTIVE: prove karo ki ordering guarantee PER-PARTITION hai, topic-wide nahi —
aur key hi decide karti hai kaunsa event kis partition me jaayega.

TASK:
  1. TODO 1: bina key ke bhejo → dekho ek order ke events bikhar jaate hain
  2. TODO 2: order_id ko key banao → sab ek partition me, order me
  3. Run: python 03_ordering_keys.py

Prereq: docker compose up -d   |   pip install aiokafka
"""

import asyncio
import json
from collections import defaultdict
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

BOOTSTRAP = "localhost:9092"
TOPIC = "lab-ordering"
PARTITIONS = 3

# Ek order ka lifecycle — inka order badalna business bug hai
EVENTS = ["created", "paid", "packed", "shipped", "delivered"]
ORDERS = ["order-A", "order-B"]


async def setup_topic() -> None:
    admin = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP)
    await admin.start()
    try:
        await admin.create_topics(
            [NewTopic(TOPIC, num_partitions=PARTITIONS, replication_factor=1)])
    except Exception:
        pass
    finally:
        await admin.close()


async def produce(with_key: bool) -> None:
    p = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP,
                         value_serializer=lambda v: json.dumps(v).encode())
    await p.start()
    try:
        for order_id in ORDERS:
            for seq, event in enumerate(EVENTS):
                payload = {"order_id": order_id, "seq": seq, "event": event}

                if with_key:
                    # ─────────────────────────────────────────────
                    # TODO 2: order_id ko KEY banao (bytes chahiye).
                    #   Kafka: partition = hash(key) % num_partitions
                    #   → same key = same partition = ORDER GUARANTEED
                    # await p.send_and_wait(TOPIC, payload, key=...)
                    await p.send_and_wait(TOPIC, payload)      # ← isse badlo
                    # ─────────────────────────────────────────────
                else:
                    # TODO 1: kuch mat badlo — bina key = round-robin
                    await p.send_and_wait(TOPIC, payload)
    finally:
        await p.stop()


async def consume(group: str) -> dict:
    c = AIOKafkaConsumer(
        TOPIC, bootstrap_servers=BOOTSTRAP, group_id=group,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
    )
    await c.start()
    per_order = defaultdict(list)          # order_id -> [(partition, seq)]
    try:
        batches = await c.getmany(timeout_ms=5000)
        for _tp, msgs in batches.items():
            for m in msgs:
                v = m.value
                per_order[v["order_id"]].append((m.partition, v["seq"]))
    finally:
        await c.stop()
    return per_order


def report(per_order: dict, label: str) -> bool:
    print(f"\n  {label}")
    all_ok = True
    for order_id, items in sorted(per_order.items()):
        partitions = {p for p, _ in items}
        seqs = [s for _, s in items]
        in_order = seqs == sorted(seqs)
        single_partition = len(partitions) == 1
        ok = in_order and single_partition
        all_ok &= ok
        print(f"    {order_id}: partitions={sorted(partitions)} "
              f"seq={seqs} {'✅' if ok else '❌ bikhra hua / out of order'}")
    return all_ok


async def main() -> None:
    await setup_topic()

    print("\n[A] BINA key — round-robin partitioning")
    await produce(with_key=False)
    ok_nokey = report(await consume("lab03-nokey"), "Result:")

    print("\n[B] KEY ke saath — hash(order_id) % partitions")
    await produce(with_key=True)
    ok_key = report(await consume("lab03-key"), "Result:")

    print("\n" + "─" * 55)
    if ok_key and not ok_nokey:
        print("✅ PASS — key ne ordering fix kar di (aur bina key bikhra tha)")
    elif ok_key and ok_nokey:
        print("⚠️  Dono pass dikhe — TODO 2 bhara? Bina key wala bhi single "
              "partition me gaya ho sakta hai (chance). Dobara chalao.")
    else:
        print("❌ FAIL — TODO 2 me key=order_id.encode() set karo")

    print("""
SOCH (bolke jawab do):
  1. Kafka ordering kis level pe guarantee karta hai — topic, partition,
     ya consumer group?
  2. Key chunne ka trade-off: order_id key = perfect ordering, par ek
     hot customer/order sab traffic ek partition pe daal de to? (hot partition)
  3. Partition count BADHANE pe purani keys ka mapping badal jaata hai —
     yeh production me kya todta hai?
  4. Agar strict global ordering chahiye to kya karoge? (Hint: 1 partition
     — aur uska throughput cost kya hai?)
""")


if __name__ == "__main__":
    asyncio.run(main())
