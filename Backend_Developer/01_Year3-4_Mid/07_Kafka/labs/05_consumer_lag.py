"""
Kafka Lab 05 — Consumer Lag
============================
OBJECTIVE: lag ko apni aankhon se badhte dekho, aur usse measure karna seekho —
production me Kafka ka sabse important alert yahi hai.

TASK:
  1. TODO: lag calculate karo (end_offset - committed_offset)
  2. Run: python 05_consumer_lag.py

Prereq: docker compose up -d   |   pip install aiokafka
UI me bhi dekh sakte ho: http://localhost:8080 → Consumers
"""

import asyncio
import json
import uuid
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.structs import TopicPartition

BOOTSTRAP = "localhost:9092"
TOPIC = f"lab-lag-{uuid.uuid4().hex[:6]}"
GROUP = "lab05-slow-worker"

FAST_PRODUCE = 200        # messages
SLOW_PROCESS_MS = 15      # har message pe itna "kaam"


async def produce_burst(n: int) -> None:
    p = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP,
                         value_serializer=lambda v: json.dumps(v).encode())
    await p.start()
    try:
        for i in range(n):
            await p.send_and_wait(TOPIC, {"i": i})
    finally:
        await p.stop()


async def measure_lag(consumer: AIOKafkaConsumer) -> int:
    """Lag = kitne messages produce ho chuke par consume nahi hue."""
    total_lag = 0
    for tp in consumer.assignment():
        end_offsets = await consumer.end_offsets([tp])
        end = end_offsets[tp]                       # next offset to be written
        position = await consumer.position(tp)      # consumer kahan hai

        # ─────────────────────────────────────────────────────
        # TODO: lag nikalo.
        #   end     = latest offset broker pe (log end offset)
        #   position = consumer ka current offset
        #   lag = ?
        lag = 0        # ← isse badlo
        # ─────────────────────────────────────────────────────

        total_lag += lag
    return total_lag


async def slow_consumer() -> None:
    c = AIOKafkaConsumer(
        TOPIC, bootstrap_servers=BOOTSTRAP, group_id=GROUP,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest", enable_auto_commit=False,
        max_poll_records=10,
    )
    await c.start()
    processed = 0
    samples = []
    try:
        await asyncio.sleep(0.5)
        for tick in range(6):
            batches = await c.getmany(timeout_ms=500, max_records=10)
            for _tp, msgs in batches.items():
                for _m in msgs:
                    await asyncio.sleep(SLOW_PROCESS_MS / 1000)   # slow work
                    processed += 1
            await c.commit()
            lag = await measure_lag(c)
            samples.append(lag)
            print(f"    t={tick}  processed={processed:>3}  lag={lag}")
        return samples, processed
    finally:
        await c.stop()


async def main() -> None:
    print(f"\n[setup] topic={TOPIC}")
    print(f"  Fast producer: {FAST_PRODUCE} messages ek saath")
    print(f"  Slow consumer: {SLOW_PROCESS_MS}ms per message\n")

    await produce_burst(FAST_PRODUCE)
    result = await slow_consumer()
    samples, processed = result

    print("\n" + "─" * 55)
    if all(s == 0 for s in samples):
        print("❌ FAIL — lag hamesha 0 dikha. TODO bhara? (lag = end - position)")
    elif samples[0] > samples[-1]:
        print(f"✅ PASS — lag {samples[0]} se {samples[-1]} tak ghata "
              "(consumer catch up kar raha hai)")
    else:
        print(f"✅ PASS — lag measure ho raha hai (samples: {samples})")
        print("   Lag ghata nahi kyunki consumer producer se dheema hai — "
              "yahi production ka asli scenario hai.")

    print(f"""
SOCH (bolke jawab do):
  1. Lag badh raha hai — teen possible causes batao (consumer slow?
     partitions kam? downstream DB slow?) aur har ek ka fix.
  2. Consumers badha ke lag kam karoge — limit kya hai? (partition count)
     Partitions badhane ka side-effect? (key→partition mapping badalti hai)
  3. Lag alert kis pe lagaoge: absolute messages ya time-lag (records/sec
     se divide karke)? Kaunsa business ko zyada meaningful lagta hai?
  4. Retention se pehle consumer catch up na kare to kya hota hai?
     (Messages delete — permanent data loss. Yeh monitor karna zaroori hai.)
""")


if __name__ == "__main__":
    asyncio.run(main())
