"""
Celery Lab 07 — Task Chunking & Parallel Processing
=====================================================
OBJECTIVE: 5000 records ko efficiently process karo — ek-ek nahi, parallel batches mein.

SCENARIO:
  Monthly report generate karna hai — 5000 user records process karne hain.
  Sequential ek-ek → ~250 seconds.
  Parallel batches (group + chord) → ~5 seconds.

TASK:
  1. TODO 1: records ko 100-size batches mein toddo (chunking)
  2. TODO 2: group() se parallel batch processing
  3. TODO 3: chord() se parallel processing + automatic aggregation

  Terminal 1: celery -A tasks worker --loglevel=info --concurrency=10
  Terminal 2: python 07_chunking_parallel.py

Prereq: docker compose up -d   |   pip install "celery[redis]" redis
"""

import time
from celery import group, chord
from tasks import process_batch, aggregate_results

TOTAL_RECORDS   = 5000
BATCH_SIZE      = 100
ALL_RECORDS     = list(range(1, TOTAL_RECORDS + 1))    # record IDs 1..5000


# ─────────────────────────────────────────────────────────────
# HELPER — records ko N-size batches mein split karo
# ─────────────────────────────────────────────────────────────
def make_batches(records: list, batch_size: int) -> list:
    """
    [1,2,...,5000] → [[1..100], [101..200], ..., [4901..5000]]

    TODO 1: isse implement karo.
    Hint: range(0, len(records), batch_size) aur list slicing use karo.
    """
    # ── TODO 1 ────────────────────────────────────────────────────────────
    return []   # ← isse badlo
    # ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# APPROACH 1 — Sequential (baseline, slow)
# ─────────────────────────────────────────────────────────────
def approach_sequential(batches: list) -> dict:
    """
    Har batch ek ke baad ek. Worker pe koi parallelism nahi.
    Sirf comparison ke liye — isko actually run mat karo full data pe.
    """
    print(f"\n[1] Sequential — {len(batches)} batches, ek ke baad ek")
    t0 = time.perf_counter()

    results = []
    for i, batch in enumerate(batches[:5]):    # sirf 5 batches for demo
        r = process_batch.delay(batch)
        results.append(r.get(timeout=30))
        print(f"  batch {i+1}/5 done: {results[-1]['count']} records")

    elapsed = time.perf_counter() - t0
    print(f"  5 batches sequential: {elapsed:.1f}s  (full 50 batches ≈ {elapsed*10:.0f}s)")
    return results[0] if results else {}


# ─────────────────────────────────────────────────────────────
# APPROACH 2 — group() (parallel, no aggregation)
# ─────────────────────────────────────────────────────────────
def approach_group(batches: list) -> list:
    """
    group() = saare batches simultaneously dispatch karo.
    GroupResult.get() → list of results (order preserved).

    TODO 2: group() se saare batches dispatch karo.
    """
    print(f"\n[2] group() — {len(batches)} batches parallel")

    # ── TODO 2 ────────────────────────────────────────────────────────────
    # job = group(process_batch.s(batch) for batch in batches)
    # t0 = time.perf_counter()
    # group_result = job.apply_async()
    # results = group_result.get(timeout=120)
    # elapsed = time.perf_counter() - t0
    # print(f"  {len(results)} batches done in {elapsed:.1f}s")
    # return results
    print("  ❌ TODO 2 abhi bharna hai")
    return []
    # ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# APPROACH 3 — chord() (parallel + automatic aggregation)
# ─────────────────────────────────────────────────────────────
def approach_chord(batches: list) -> dict:
    """
    chord() = group() + callback.
    Saare batches parallel chalte hain, sab complete hone par
    aggregate_results() automatically call hota hai.

    TODO 3: chord() implement karo.
    """
    print(f"\n[3] chord() — {len(batches)} batches parallel + auto aggregation")

    # ── TODO 3 ────────────────────────────────────────────────────────────
    # header  = group(process_batch.s(batch) for batch in batches)
    # callback = aggregate_results.s()
    # job = chord(header)(callback)
    # t0 = time.perf_counter()
    # final = job.get(timeout=120)
    # elapsed = time.perf_counter() - t0
    # print(f"  Aggregated: {final}")
    # print(f"  Total time: {elapsed:.1f}s")
    # return final
    print("  ❌ TODO 3 abhi bharna hai")
    return {}
    # ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# APPROACH 4 — Memory-efficient chunking (generator pattern)
# ─────────────────────────────────────────────────────────────
def approach_memory_efficient():
    """
    Large dataset: records ko memory mein load mat karo.
    Generator se chunks stream karo.
    Production mein: db.execute("SELECT id FROM records").fetchmany(100)
    """
    print("\n[4] Memory-efficient chunking (generator pattern)")

    def record_chunks(total: int, size: int):
        """Yields batches without loading all records into memory."""
        for start in range(0, total, size):
            yield list(range(start + 1, min(start + size, total) + 1))

    # First 3 chunks only (demo)
    chunks_demo = list(record_chunks(300, 100))
    header   = group(process_batch.s(chunk) for chunk in chunks_demo)
    callback = aggregate_results.s()
    result   = chord(header)(callback).get(timeout=60)

    print(f"  300 records, 3 chunks: {result}")
    print("  ✅ Generator pattern — koi bhi N pe kaam karta hai, RAM constant")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    batches = make_batches(ALL_RECORDS, BATCH_SIZE)
    print(f"Total records: {TOTAL_RECORDS} → {len(batches)} batches × {BATCH_SIZE}")

    if not batches:
        print("❌ TODO 1 bharo: make_batches() khali list return kar raha hai")
        print("   Hint: [records[i:i+batch_size] for i in range(0, len(records), batch_size)]")
        return

    print(f"  Sample: batch[0]={batches[0][:3]}... batch[-1]={batches[-1][:3]}...")

    # Baseline: 5 batches sequential
    approach_sequential(batches)

    # Parallel with group
    group_results = approach_group(batches)
    if group_results:
        total_via_group = sum(r["batch_sum"] for r in group_results)
        print(f"  group() total_sum={total_via_group} (expected: {sum(ALL_RECORDS)})")

    # Parallel + aggregate with chord
    chord_result = approach_chord(batches)
    if chord_result:
        print(f"  chord() grand_sum={chord_result.get('grand_sum')} "
              f"(expected: {sum(ALL_RECORDS)})")
        if chord_result.get("grand_sum") == sum(ALL_RECORDS):
            print("  ✅ PASS — chord() correctly processed all records")
        else:
            print("  ❌ Sum mismatch — check process_batch aur aggregate_results tasks")

    # Memory-efficient chunking
    approach_memory_efficient()

    print("\n" + "─" * 55)
    print("SOCH QUESTIONS:")
    print("  1. group() aur chord() mein kya fark hai?")
    print("  2. Agar ek batch fail ho jaaye chord() mein kya hota hai?")
    print("  3. 1 crore records ke liye kya approach use karoge? (DB pagination)")
    print("  4. Worker count > batch count hone se kya fayda?")
    print("  5. celery.chunks() aur group() mein kya difference hai?")


if __name__ == "__main__":
    main()
