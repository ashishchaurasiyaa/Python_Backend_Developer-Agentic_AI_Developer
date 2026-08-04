"""
Kafka Lab 02 — Consumer Groups & Partition Assignment
======================================================
OBJECTIVE: dekho ki parallelism partitions se bandha hai, consumers se nahi.

TASK:
  1. `make_consumer()` me TODO bharo — sab same group me hone chahiye
  2. Run: python 02_consumer_groups.py
  3. Output me dekho: 3 partitions, 3 consumers → 1-1 partition;
     phir 4th consumer add hone pe wo IDLE baithta hai (koi partition nahi)

Prereq: docker compose up -d   |   pip install aiokafka
"""

import asyncio
import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

BOOTSTRAP = "localhost:9092"
TOPIC = "lab-groups"
PARTITIONS = 3
GROUP = "lab02-workers"


async def setup_topic() -> None:
    admin = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP)
    await admin.start()
    try:
        await admin.create_topics(
            [NewTopic(TOPIC, num_partitions=PARTITIONS, replication_factor=1)]
        )
        print(f"  topic '{TOPIC}' banaya ({PARTITIONS} partitions)")
    except Exception:
        print(f"  topic '{TOPIC}' pehle se hai")
    finally:
        await admin.close()


async def produce(n: int = 30) -> None:
    p = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP,
                         value_serializer=lambda v: json.dumps(v).encode())
    await p.start()
    try:
        for i in range(n):
            await p.send_and_wait(TOPIC, {"job": i})
    finally:
        await p.stop()
    print(f"  {n} messages produce kiye")


def make_consumer(name: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",

        # ─────────────────────────────────────────────────────
        # TODO: saare consumers ko EK hi group me daalo (GROUP use karo).
        #       Soch: agar har consumer ka group_id ALAG hota, to
        #       kya hota? (har ek ko SAARE messages milte — pub/sub
        #       behaviour, work-sharing nahi)
        # group_id=...,
        # ─────────────────────────────────────────────────────
    )


async def run_consumer(name: str, seconds: int = 6) -> tuple:
    c = make_consumer(name)
    await c.start()
    count = 0
    try:
        await asyncio.sleep(1)                     # rebalance settle hone do
        assigned = sorted(tp.partition for tp in c.assignment())
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            batches = await c.getmany(timeout_ms=500)
            for _tp, msgs in batches.items():
                count += len(msgs)
        return name, assigned, count
    finally:
        await c.stop()


async def main() -> None:
    print("\n[setup]")
    await setup_topic()
    await produce()

    print(f"\n[round 1] 3 consumers, {PARTITIONS} partitions")
    results = await asyncio.gather(*[run_consumer(f"C{i}") for i in range(1, 4)])
    for name, parts, count in results:
        print(f"  {name}: partitions={parts}  messages={count}")

    total = sum(r[2] for r in results)
    all_parts = sorted(p for r in results for p in r[1])
    ok1 = all_parts == list(range(PARTITIONS))

    print(f"\n[round 2] 4 consumers, sirf {PARTITIONS} partitions")
    await produce(15)
    results2 = await asyncio.gather(*[run_consumer(f"D{i}") for i in range(1, 5)])
    idle = [name for name, parts, _ in results2 if not parts]
    for name, parts, count in results2:
        tag = "  ← IDLE (koi partition nahi mila)" if not parts else ""
        print(f"  {name}: partitions={parts}  messages={count}{tag}")

    print("\n" + "─" * 55)
    if ok1 and len(idle) == 1:
        print("✅ PASS — har partition exactly ek consumer ko, extra consumer idle")
    elif not all_parts:
        print("❌ FAIL — kisi consumer ko partition nahi mila. TODO (group_id) bharo.")
    else:
        print(f"⚠️  Partitions={all_parts}, idle={idle} — dobara chalao "
              "(rebalance timing se kabhi-kabhi alag baant hoti hai)")

    print(f"""
SOCH (bolke jawab do):
  1. Topic me {PARTITIONS} partitions hain. 10 consumers add karo to kitne
     kaam karenge? Throughput badhane ke liye asli lever kya hai?
  2. Ek consumer mar gaya — baaki ko uski partitions kab milti hain?
     (Hint: session.timeout.ms, heartbeat, rebalance)
  3. Rebalance ke dauraan processing rukti hai — "stop-the-world" kam
     karne ke liye kaunsi strategy? (Hint: cooperative sticky)
  4. Do ALAG group_id wale consumers same topic pe — kya hota hai?
""")


if __name__ == "__main__":
    asyncio.run(main())
