"""
Celery Lab 01 — Task States & Result Backend
=============================================
OBJECTIVE: samjho ki .delay() turant return karta hai, aur result kahan se aata hai.

TASK:
  1. TODO 1: task ko async queue me bhejo
  2. TODO 2: result ka wait karo (timeout ke saath)
  3. Terminal 1: celery -A tasks worker --loglevel=info
     Terminal 2: python 01_basics_states.py

Prereq: docker compose up -d   |   pip install "celery[redis]"
"""

import time
from celery.result import AsyncResult
from tasks import app, add, slow_task


def main() -> None:
    print("\n[1] Task queue me bhejo (non-blocking)")
    t0 = time.perf_counter()

    # ─────────────────────────────────────────────────────
    # TODO 1: add(4, 6) ko WORKER pe chalao, yahan nahi.
    #   add(4, 6)        → seedha function call, worker involve hi nahi
    #   add.delay(4, 6)  → queue me jaata hai, AsyncResult milta hai
    #   add.apply_async(args=[4, 6], countdown=5) → 5s baad chalega
    result = None      # ← isse badlo
    # ─────────────────────────────────────────────────────

    if result is None:
        print("❌ TODO 1 abhi bharna hai")
        return

    submit_ms = (time.perf_counter() - t0) * 1000
    print(f"  .delay() {submit_ms:.1f}ms me return hua (task abhi chal raha hai)")
    print(f"  task_id: {result.id}")
    print(f"  state:   {result.state}")            # PENDING

    print("\n[2] Result ka wait karo")
    # ─────────────────────────────────────────────────────
    # TODO 2: result ka value nikalo, max 10s wait.
    #   Hint: result.get(timeout=10)
    #   NOTE: web request ke andar .get() KABHI mat karo — wo async
    #         ka poora point khatam kar deta hai (blocking ho jaata hai)
    value = None       # ← isse badlo
    # ─────────────────────────────────────────────────────

    print(f"  value: {value}   state: {result.state}")

    print("\n[3] Task ID se result wapas fetch karo (naya process bhi kar sakta hai)")
    fetched = AsyncResult(result.id, app=app)
    print(f"  same task_id se: {fetched.result} (state={fetched.state})")

    print("\n[4] Multiple tasks parallel me")
    t0 = time.perf_counter()
    handles = [slow_task.delay(1) for _ in range(4)]
    values = [h.get(timeout=20) for h in handles]
    elapsed = time.perf_counter() - t0
    print(f"  4 tasks × 1s = {elapsed:.1f}s (concurrency se kam hua)")

    print("\n" + "─" * 55)
    if value == 10 and len(values) == 4:
        print("✅ PASS — task queue hua, result mila, ID se fetch bhi hua")
        if elapsed < 3:
            print(f"   Bonus: {elapsed:.1f}s me 4 tasks — worker parallel chala")
    else:
        print("❌ FAIL — TODO 1/2 check karo (worker chal raha hai?)")

    print("""
SOCH (bolke jawab do):
  1. .delay() vs .apply_async() — dusra kab chahiye? (countdown, eta,
     queue, priority, retry policy)
  2. State PENDING ka matlab "queue me hai" NAHI hai — Celery me PENDING
     = "mujhe is id ka kuch pata nahi". Yeh galat-fehmi kaise bug banti hai?
  3. Result backend na ho to kya khota hai? Kya har task ko result
     backend chahiye? (fire-and-forget tasks ke liye ignore_result=True)
  4. Web request ke andar .get() kyun mana hai?
""")


if __name__ == "__main__":
    main()
