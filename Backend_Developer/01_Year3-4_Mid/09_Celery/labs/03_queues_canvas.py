"""
Celery Lab 03 — Queue Routing & Canvas Workflows
=================================================
OBJECTIVE: (a) urgent kaam ko bulk backlog ke peeche mat phansne do,
           (b) chain/group/chord se multi-step workflows banao.

TASK:
  1. TODO 1: urgent task ko explicitly "high" queue pe bhejo
  2. TODO 2: chain banao — fetch_price → apply_tax
  3. TODO 3: chord banao — parallel fetches → summarize

  Terminal 1: celery -A tasks worker -Q high,default --loglevel=info
  Terminal 2: python 03_queues_canvas.py

Prereq: docker compose up -d
"""

import time
from celery import chain, group, chord
from tasks import urgent_task, bulk_task, fetch_price, apply_tax, summarize


def part_a_routing() -> bool:
    print("\n[A] Queue routing — bulk backlog ke saath urgent task")

    # 10 slow bulk tasks queue me daalo (har ek 1s)
    for i in range(10):
        bulk_task.delay(i)
    print("  10 bulk tasks (1s each) queue kiye")

    t0 = time.perf_counter()

    # ─────────────────────────────────────────────────────
    # TODO 1: urgent task ko "high" queue pe bhejo.
    #   tasks.py ke task_routes me already mapping hai, par yahan
    #   explicitly bhi kar sakte ho:
    #     urgent_task.apply_async(args=["ORD-1"], queue="high")
    handle = urgent_task.delay("ORD-1")        # ← queue= add karo
    # ─────────────────────────────────────────────────────

    out = handle.get(timeout=30)
    elapsed = time.perf_counter() - t0
    print(f"  {out} — {elapsed:.1f}s me")

    if elapsed < 3:
        print("  ✅ urgent task bulk backlog se aage nikal gaya")
        return True
    print("  ⚠️  urgent task ko intezaar karna pada — worker 'high' queue "
          "consume kar raha hai? (-Q high,default)")
    return False


def part_b_canvas() -> bool:
    print("\n[B] Canvas — chain (sequential pipeline)")

    # ─────────────────────────────────────────────────────
    # TODO 2: fetch_price("laptop") ka result apply_tax me jaana chahiye.
    #   chain me pehle task ka return AGLE task ka pehla arg ban jaata hai.
    #   Hint: chain(fetch_price.s("laptop"), apply_tax.s())()
    #   NOTE: .s() = signature (task + args, abhi chalega nahi)
    chain_result = None      # ← isse badlo
    # ─────────────────────────────────────────────────────

    if chain_result is None:
        print("  ❌ TODO 2 baaki hai")
        return False
    final = chain_result.get(timeout=30)
    print(f"  price → tax lagne ke baad: {final}")

    print("\n[C] Canvas — group (parallel) + chord (parallel → callback)")
    items = ["laptop", "mouse", "keyboard", "monitor"]

    t0 = time.perf_counter()
    g = group(fetch_price.s(i) for i in items)()
    prices = g.get(timeout=30)
    print(f"  group: {len(prices)} prices parallel me "
          f"({time.perf_counter() - t0:.1f}s)")

    # ─────────────────────────────────────────────────────
    # TODO 3: same parallel fetches, par sab khatam hone pe
    #   summarize automatically chale.
    #   Hint: chord(group(...))(summarize.s())
    chord_result = None      # ← isse badlo
    # ─────────────────────────────────────────────────────

    if chord_result is None:
        print("  ❌ TODO 3 baaki hai")
        return False
    summary = chord_result.get(timeout=30)
    print(f"  chord callback ka result: {summary}")
    return True


def main() -> None:
    ok_a = part_a_routing()
    ok_b = part_b_canvas()

    print("\n" + "─" * 55)
    if ok_a and ok_b:
        print("✅ PASS — routing + chain/group/chord sab kaam kar rahe hain")
    else:
        print("❌ Kuch TODO baaki hain (upar dekho)")

    print("""
SOCH (bolke jawab do):
  1. Alag queues kyun? Ek queue + priority field se kaam kyun nahi chalta?
     (Redis me priority weak hai; alag worker pools = resource isolation)
  2. chain me beech ka task fail ho gaya — baaki chain ka kya hota hai?
     Partial work rollback kaise karoge? (Saga pattern)
  3. chord ka callback KAB chalta hai, aur uska hidden cost kya hai?
     (Result backend polling — bade groups pe mehnga)
  4. Ek hi worker -Q high,default consume kar raha hai — kya high truly
     priority paayi? Better setup kya hoga? (dedicated worker per queue)
""")


if __name__ == "__main__":
    main()
