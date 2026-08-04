"""
Kafka Lab 01 — Produce & Consume
=================================
OBJECTIVE: pehla message end-to-end bhejo aur padho.

TASK:
  1. `produce()` me TODO bharo — 5 messages bhejo topic "lab-orders" pe
  2. `consume()` me TODO bharo — shuru se saare messages padho
  3. Run: python 01_produce_consume.py

Prereq: docker compose up -d   |   pip install aiokafka
"""

import asyncio
import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

BOOTSTRAP = "localhost:9092"
TOPIC = "lab-orders"
EXPECTED = 5


async def produce() -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await producer.start()
    try:
        for i in range(EXPECTED):
            payload = {"order_id": i, "amount": 100 * (i + 1)}

            # ─────────────────────────────────────────────────────
            # TODO 1: `payload` ko TOPIC pe bhejo aur delivery ka
            #         wait karo (metadata return hota hai).
            #         Hint: await producer.send_and_wait(...)
            #         Fire-and-forget chahiye to send() — par yahan
            #         hume confirm chahiye, isliye send_and_wait.
            metadata = None
            # ─────────────────────────────────────────────────────

            if metadata is None:
                print("❌ TODO 1 abhi bharna hai")
                return
            print(f"  → sent order_id={i} to partition {metadata.partition} "
                  f"offset {metadata.offset}")
    finally:
        await producer.stop()


async def consume() -> list:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id="lab01-reader",
        value_deserializer=lambda v: json.loads(v.decode()),

        # ─────────────────────────────────────────────────────
        # TODO 2: naye consumer group ko SHURU se padhna hai.
        #         Kaunsa parameter? ("latest" default hai — usse
        #         purane messages miss ho jaate hain)
        # auto_offset_reset=...,
        # ─────────────────────────────────────────────────────
    )
    await consumer.start()
    received = []
    try:
        # 5 second me jitna mile — getmany timeout-based hai
        batches = await consumer.getmany(timeout_ms=5000)
        for _tp, messages in batches.items():
            for msg in messages:
                received.append(msg.value)
                print(f"  ← got {msg.value} (partition {msg.partition}, "
                      f"offset {msg.offset})")
    finally:
        await consumer.stop()
    return received


async def main() -> None:
    print("\n[1] Producing...")
    await produce()

    print("\n[2] Consuming...")
    received = await consume()

    print("\n" + "─" * 55)
    if len(received) >= EXPECTED:
        print(f"✅ PASS — {len(received)} messages mile")
    else:
        print(f"❌ FAIL — sirf {len(received)}/{EXPECTED} mile.")
        print("   Agar 0 mile: TODO 2 (auto_offset_reset) check karo.")
        print("   Agar produce fail hua: docker compose ps se broker dekho.")

    print("""
SOCH (bolke jawab do):
  1. `send()` vs `send_and_wait()` — kab kaunsa, aur acks se kya rishta?
  2. auto_offset_reset="earliest" vs "latest" — production me naya
     consumer group deploy karte time kaunsa chahoge, aur kyun?
  3. Offset kahan store hota hai? (Hint: __consumer_offsets topic)
""")


if __name__ == "__main__":
    asyncio.run(main())
