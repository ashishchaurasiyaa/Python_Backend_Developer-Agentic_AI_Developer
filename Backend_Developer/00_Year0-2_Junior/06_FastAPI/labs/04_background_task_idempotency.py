"""
FastAPI Lab 04 — Background Task Idempotency
================================================
OBJECTIVE: make a background side-effect (e.g. "charge the customer", "send
the email") safe against duplicate requests using an `Idempotency-Key` header.

TASK:
  1. TODO 1: before scheduling the background task, check whether this
     idempotency key has already been SEEN. If yes, skip scheduling.
  2. TODO 2: implement the side effect itself — it must record the key as
     seen and increment the effect counter, exactly once per key.
  3. Run: python 04_background_task_idempotency.py

Prereq: pip install fastapi httpx   (no Docker needed — everything is in-process)
"""

from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient

app = FastAPI(title="Lab 04 — Background Task Idempotency")

# In-memory stand-ins for "already processed this key" storage (Redis in prod)
seen_keys: set[str] = set()
side_effect_count = 0


def charge_customer(idempotency_key: str) -> None:
    """The actual side effect — pretend this charges a card or sends an email.
    Must be safe to call at most once per idempotency key."""
    global side_effect_count

    # ─────────────────────────────────────────────────────
    # TODO 2: record `idempotency_key` as seen AND bump the counter.
    #   This function runs inside the background task, so it's the last
    #   line of defense — but the real dedup check belongs in TODO 1
    #   (before scheduling), otherwise you'd schedule two background tasks
    #   for the same key and just make the SECOND one a no-op, which still
    #   wastes a worker slot. Do both: skip scheduling AND guard here.
    #   Hint:
    #       seen_keys.add(idempotency_key)
    #       side_effect_count += 1
    pass  # WRONG: does nothing — counter never increments
    # ─────────────────────────────────────────────────────


@app.post("/charge")
async def charge(
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    # ─────────────────────────────────────────────────────
    # TODO 1: if `idempotency_key` is already in `seen_keys`, do NOT schedule
    #         the background task again — return immediately with a flag
    #         showing this was a duplicate.
    #   Hint:
    #       if idempotency_key in seen_keys:
    #           return {"scheduled": False, "duplicate": True}
    #       background_tasks.add_task(charge_customer, idempotency_key)
    #       return {"scheduled": True, "duplicate": False}
    background_tasks.add_task(charge_customer, idempotency_key)  # WRONG: always schedules
    return {"scheduled": True, "duplicate": False}
    # ─────────────────────────────────────────────────────


async def main() -> None:
    global side_effect_count, seen_keys
    side_effect_count = 0
    seen_keys = set()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        print("\n[1] First request, key=abc-123")
        r1 = await client.post("/charge", headers={"Idempotency-Key": "abc-123"})
        print(f"  status={r1.status_code} body={r1.json()}")

        print("\n[2] Duplicate request, SAME key=abc-123")
        r2 = await client.post("/charge", headers={"Idempotency-Key": "abc-123"})
        print(f"  status={r2.status_code} body={r2.json()}")

        print("\n[3] Different key=xyz-789")
        r3 = await client.post("/charge", headers={"Idempotency-Key": "xyz-789"})
        print(f"  status={r3.status_code} body={r3.json()}")

        # BackgroundTasks scheduled via ASGITransport run after the response
        # is sent but before the client call returns control here in this
        # single-process test setup — give the event loop one tick to be safe.
        await asyncio.sleep(0.05)

    print("\n" + "─" * 55)
    print(f"  side_effect_count = {side_effect_count} (expected 2: one per unique key)")
    print(f"  seen_keys = {seen_keys}")

    dup_flagged = r2.json().get("duplicate") is True
    count_ok = side_effect_count == 2

    if dup_flagged and count_ok:
        print("✅ PASS — duplicate key did not re-trigger the side effect, "
              "new key did")
    else:
        print("❌ FAIL")
        if not dup_flagged:
            print("   Duplicate request wasn't flagged — check TODO 1 (seen_keys lookup"
                  " before scheduling).")
        if not count_ok:
            print(f"   side_effect_count={side_effect_count}, expected 2 — check TODO 2"
                  " (charge_customer must actually increment the counter).")
            print("   If it's 0: TODO 2 body is still a no-op `pass`.")
            print("   If it's 3+: TODO 1 isn't blocking duplicate scheduling.")

    print("""
THINK (answer out loud):
  1. Why check `seen_keys` BEFORE scheduling the background task, instead of
     only inside `charge_customer` itself? What's the cost of only guarding
     in one place vs both?
  2. This lab uses an in-memory `set()`. What breaks when you run this app
     with 3 worker processes behind a load balancer? What would you swap
     `seen_keys` for?
  3. There's a race: two requests with the same key arrive in the SAME
     millisecond, both check `seen_keys` before either has added to it. How
     would you close that window (hint: atomic check-and-set, e.g. Redis
     `SETNX` or a DB unique constraint on the key)?
  4. How long should an idempotency key stay in `seen_keys`? What decides
     the TTL?
""")


if __name__ == "__main__":
    asyncio.run(main())
