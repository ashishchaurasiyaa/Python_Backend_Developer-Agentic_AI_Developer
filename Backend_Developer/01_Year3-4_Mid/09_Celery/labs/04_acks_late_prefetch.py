"""
Celery Lab 04 — acks_late & Prefetch (worker crash ka behaviour)
=================================================================
OBJECTIVE: samjho ki worker crash pe task khota hai ya dobara chalta hai —
aur prefetch kaise ek slow worker ke peeche kaam phansa deta hai.

Yeh lab CODE se zyada CONFIG samajhne ka hai. Do experiments karo:

  EXPERIMENT 1 — acks_late=False (default)
    Terminal 1: celery -A tasks worker --loglevel=info --concurrency=1
    Terminal 2: python 04_acks_late_prefetch.py
    Jab "kill worker NOW" dikhe → Terminal 1 me Ctrl+C DO BAAR (hard kill)
    Terminal 1 dobara start karo. Task WAPAS aaya? → NAHI (message ack ho
    chuka tha jab task shuru hua) = at-most-once = kaam KHO GAYA.

  EXPERIMENT 2 — acks_late=True
    tasks.py me TODO bharo: app.conf.task_acks_late = True
    Wahi steps dohrao. Ab task WAPAS aata hai = at-least-once.

TASK:
  1. Experiment 1 chalao, observe karo
  2. tasks.py me task_acks_late=True karo, worker restart
  3. Experiment 2 chalao, farq note karo

Prereq: docker compose up -d
"""

import time
from tasks import app, slow_task, bulk_task


def show_config() -> None:
    print("\n[config] abhi ke settings:")
    print(f"  task_acks_late            = {app.conf.task_acks_late}")
    print(f"  worker_prefetch_multiplier= {app.conf.worker_prefetch_multiplier}")
    print("""
  acks_late=False → task SHURU hote hi broker ko ack (message delete)
                    crash = kaam gaya (at-most-once)
  acks_late=True  → task KHATAM hone pe ack
                    crash = message wapas queue me (at-least-once)
                    → task idempotent hona CHAHIYE
""")


def crash_experiment() -> None:
    print("[experiment] 20s ka task bhej rahe hain...")
    handle = slow_task.delay(20)
    print(f"  task_id: {handle.id}")
    time.sleep(3)
    print("\n  ⚠️  ABHI worker ko KILL karo (Terminal 1 me Ctrl+C twice)")
    print("     Phir worker dobara start karo aur dekho:")
    print(f"       - acks_late=False → task {handle.id[:8]}… kabhi complete nahi hoga")
    print("       - acks_late=True  → naya worker usse dobara uthayega")
    print("\n  60s wait kar rahe hain (worker restart karne ka time)...")

    try:
        result = handle.get(timeout=60)
        print(f"\n  ✅ Task COMPLETE hua: {result}")
        print("     → Matlab acks_late=True hai (crash ke baad redeliver hua),")
        print("       YA tumne worker kill nahi kiya 🙂")
    except Exception as exc:
        print(f"\n  ❌ Task complete nahi hua ({type(exc).__name__})")
        print("     → acks_late=False ka classic behaviour: kaam kho gaya")


def prefetch_demo() -> None:
    print("\n[prefetch] ek worker (concurrency=1) ko 8 slow tasks dete hain")
    print("  prefetch_multiplier=4 → worker 4 tasks RESERVE kar leta hai,")
    print("  chahe wo abhi ek hi chala sakta ho. Doosra worker aaye to bhi")
    print("  wo reserved tasks usse nahi milte → 'idle worker, backed-up queue'")
    handles = [bulk_task.delay(i) for i in range(8)]
    t0 = time.perf_counter()
    done = 0
    for h in handles:
        try:
            h.get(timeout=60)
            done += 1
        except Exception:
            break
    print(f"  {done}/8 tasks {time.perf_counter() - t0:.1f}s me")
    print("""
  Production fix (long tasks ke liye):
      worker_prefetch_multiplier = 1
      task_acks_late = True
  Chhote-tez tasks ke liye default prefetch theek hai (throughput accha).
""")


def main() -> None:
    show_config()
    mode = input("Kya chalana hai? [1] crash experiment  [2] prefetch demo : ").strip()
    if mode == "1":
        crash_experiment()
    else:
        prefetch_demo()

    print("""
SOCH (bolke jawab do):
  1. acks_late=True default kyun nahi hai? (kyunki tab HAR task ko
     idempotent hona padega — Celery wo assume nahi kar sakta)
  2. Tumhare "send invoice email" task ke liye kaunsa mode? Aur
     "charge customer card" ke liye? Dono ka reasoning alag hoga.
  3. Long task + acks_late=True + visibility timeout (Redis/SQS) —
     agar task visibility timeout se lamba chale to kya hota hai?
     (Message dobara deliver — DO worker same task chalayenge!)
  4. Prefetch 1 karne ka cost kya hai? (har task ke liye broker round-trip
     = throughput kam, latency zyada — isliye chhote tasks pe mat karo)
""")


if __name__ == "__main__":
    main()
