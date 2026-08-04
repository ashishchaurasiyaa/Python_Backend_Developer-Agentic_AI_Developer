"""
Celery Lab 02 — Retries, Backoff & Jitter
==========================================
OBJECTIVE: flaky upstream ko survive karna — manual retry aur declarative
autoretry dono, aur backoff/jitter kyun zaroori hai.

TASK:
  1. tasks.py me `flaky_api_call` ka TODO bharo (manual self.retry)
  2. Yahan run karke dono forms compare karo
  3. Terminal 1: celery -A tasks worker --loglevel=info
     Terminal 2: python 02_retries_backoff.py

Prereq: docker compose up -d
"""

import time
from tasks import flaky_api_call, auto_retry_task


def main() -> None:
    print("\n[1] MANUAL retry — tasks.py me self.retry() se")
    print("    (worker terminal me 'attempt N → failing' lines dikhengi)")
    t0 = time.perf_counter()
    r1 = flaky_api_call.delay(fail_times=2)
    try:
        out1 = r1.get(timeout=30)
        elapsed1 = time.perf_counter() - t0
        print(f"  ✅ {out1}  ({elapsed1:.1f}s)")
        manual_ok = True
    except Exception as exc:
        elapsed1 = time.perf_counter() - t0
        print(f"  ❌ task fail hua: {type(exc).__name__}: {exc}")
        print("     tasks.py me flaky_api_call ka TODO bharo:")
        print("       raise self.retry(exc=ConnectionError('upstream 503'))")
        print("     (abhi wo seedha raise kar raha hai — retry trigger hi nahi hota)")
        manual_ok = False

    print("\n[2] DECLARATIVE autoretry — decorator me config")
    print("    autoretry_for + retry_backoff + retry_jitter")
    t0 = time.perf_counter()
    r2 = auto_retry_task.delay(fail_times=2)
    out2 = r2.get(timeout=60)
    elapsed2 = time.perf_counter() - t0
    print(f"  ✅ {out2}  ({elapsed2:.1f}s — backoff ki wajah se time laga)")

    print("\n[3] Retries khatam ho gaye to?")
    r3 = auto_retry_task.delay(fail_times=99)      # kabhi succeed nahi hoga
    try:
        r3.get(timeout=90)
        print("  ⚠️  succeed ho gaya? fail_times check karo")
    except Exception as exc:
        print(f"  Task FAILURE state me gaya: {type(exc).__name__}")
        print(f"  state={r3.state} — yahan se DLQ/alert/manual-review flow chalta hai")

    print("\n" + "─" * 55)
    if manual_ok:
        print("✅ PASS — dono retry forms kaam kar rahe hain")
    else:
        print("⚠️  Declarative form chala, manual form ka TODO baaki hai")

    print("""
SOCH (bolke jawab do):
  1. retry_backoff ke bina 1000 tasks ek saath fail ho jaayein to upstream
     ka kya hoga? (thundering herd) Jitter usme kya add karta hai?
  2. max_retries khatam — task FAILURE me chala gaya. Ab wo message kahan
     jaana chahiye taaki data loss na ho? (DLQ / dead-letter table)
  3. Kaunsi errors pe retry NAHI karna chahiye? (400 bad request,
     validation error — retry se bhi wahi result aayega)
  4. Retry idempotency: task ne DB me row insert kar di phir crash hua,
     retry pe duplicate ban jaayegi. Kaise rokoge?
     (idempotency key / get_or_create / unique constraint)
""")


if __name__ == "__main__":
    main()
