"""
Kafka Lab 04 — Manual Commit & At-Least-Once Redelivery
========================================================
OBJECTIVE: crash-before-commit simulate karke dekho ki message DOBARA aata hai —
aur samjho ki isliye consumer IDEMPOTENT hona chahiye.

TASK:
  1. TODO 1: auto-commit band karo (manual control chahiye)
  2. TODO 2: process ke BAAD commit karo
  3. Run: python 04_manual_commit_redelivery.py

Prereq: docker compose up -d   |   pip install aiokafka
"""

import asyncio
import json
import uuid
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

BOOTSTRAP = "localhost:9092"
TOPIC = f"lab-commit-{uuid.uuid4().hex[:6]}"     # har run pe fresh topic
GROUP = "lab04-worker"
MESSAGES = 5
CRASH_AT = 3          # 3rd message process karte time "crash"


async def produce() -> None:
    p = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP,
                         value_serializer=lambda v: json.dumps(v).encode())
    await p.start()
    try:
        for i in range(MESSAGES):
            await p.send_and_wait(TOPIC, {"task_id": i})
    finally:
        await p.stop()
    print(f"  {MESSAGES} messages produce kiye")


def make_consumer() -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",

        # ─────────────────────────────────────────────────────
        # TODO 1: auto-commit BAND karo.
        #   Auto-commit har 5s me offset commit kar deta hai — chahe
        #   tumne message process kiya ho ya nahi. Yeh at-MOST-once ka
        #   raasta hai (crash = message gaya).
        # enable_auto_commit=...,
        # ─────────────────────────────────────────────────────
    )


async def run_pass(label: str, crash: bool) -> list:
    """Ek consumer run — crash=True to CRASH_AT pe exception."""
    c = make_consumer()
    await c.start()
    processed = []
    try:
        batches = await c.getmany(timeout_ms=4000)
        for _tp, msgs in batches.items():
            for m in msgs:
                task_id = m.value["task_id"]

                if crash and task_id == CRASH_AT:
                    print(f"    💥 {label}: task {task_id} process karte time CRASH "
                          "(commit nahi hua)")
                    return processed

                # ── process the message (yahan tumhara business logic) ──
                processed.append(task_id)
                print(f"    {label}: processed task {task_id}")

                # ─────────────────────────────────────────────
                # TODO 2: process ho gaya — ab offset commit karo.
                #   Order matters: process → commit = at-least-once
                #                   commit → process = at-most-once
                #   Hint: await c.commit()
                # ─────────────────────────────────────────────
    finally:
        await c.stop()
    return processed


async def main() -> None:
    print(f"\n[setup] topic={TOPIC}")
    await produce()

    print("\n[run 1] processing... (task 3 pe crash hoga)")
    first = await run_pass("run1", crash=True)

    print("\n[run 2] restart — kahan se shuru hoga?")
    second = await run_pass("run2", crash=False)

    print("\n" + "─" * 55)
    print(f"  Run 1 processed: {first}")
    print(f"  Run 2 processed: {second}")

    redelivered = set(first) & set(second)
    if second and min(second) == CRASH_AT:
        print(f"✅ PASS — run 2 task {CRASH_AT} se shuru hua (uncommitted "
              "message redeliver hua) = AT-LEAST-ONCE")
    elif redelivered:
        print(f"⚠️  Redelivery hui par extra bhi: {sorted(redelivered)} dobara aaye.")
        print("   Matlab commit nahi ho raha (TODO 2 bharo) — har restart pe sab dobara.")
    elif not second:
        print("❌ FAIL — run 2 me kuch nahi aaya. Auto-commit ON hai? TODO 1 check karo.")
    else:
        print(f"❌ FAIL — run 2 {min(second)} se shuru hua, {CRASH_AT} se hona chahiye tha.")

    print(f"""
SOCH (bolke jawab do):
  1. Task {CRASH_AT} dobara aaya — agar wo "charge the customer" hota to?
     Consumer ko IDEMPOTENT kaise banaoge? (dedup key, DB unique constraint)
  2. commit-then-process karte to task {CRASH_AT} ka kya hota? Kaunsi
     delivery semantic milti?
  3. Har message pe commit() = safe par slow. Batch commit = fast par
     crash pe zyada redelivery. Tum kya chunoge aur kis basis pe?
  4. Exactly-once Kafka me kaise milta hai? (Hint: idempotent producer +
     transactional offset commit — ../05_exactly_once_transactions.md)
""")


if __name__ == "__main__":
    asyncio.run(main())
