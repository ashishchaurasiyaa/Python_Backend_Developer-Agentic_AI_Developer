"""
Event Loop Internals — asyncio ka dil

Event loop ek infinite loop hai jo:
  1. I/O events check karta hai (socket readable? file ready?)
  2. Scheduled callbacks run karta hai
  3. Ready tasks execute karta hai
  4. Repeat

Architecture:
  asyncio.run(main()) → creates loop → runs main coroutine → closes loop
  Ek thread = ek event loop (default)
  Blocking call in async code = entire loop freezes!
"""

import asyncio
import time

# ─── Event loop basics ────────────────────────────────────────────────────

async def demo_loop_basics():
    print("=== Event Loop Basics ===")

    # Get reference to running loop
    loop = asyncio.get_running_loop()
    print(f"  Loop type: {type(loop).__name__}")
    print(f"  Loop running: {loop.is_running()}")
    print(f"  Loop closed: {loop.is_closed()}")

    # Schedule a callback (non-coroutine) after N seconds
    def on_timer():
        print("  [callback] Timer fired!")

    loop.call_later(0.05, on_timer)
    await asyncio.sleep(0.1)   # give loop time to fire the callback

asyncio.run(demo_loop_basics())

# ─── Blocking code freezes the loop — THE classic mistake ─────────────────

async def bad_blocking_example():
    print("\n=== WRONG: time.sleep() in async code ===")
    print("  Starting 3 concurrent tasks...")
    start = time.time()

    async def bad_task(name: str):
        print(f"  {name}: about to block...")
        time.sleep(1)   # BLOCKS the entire event loop!
        print(f"  {name}: done")

    # Even though we use gather, time.sleep blocks — sequential not concurrent!
    await asyncio.gather(bad_task("A"), bad_task("B"), bad_task("C"))
    print(f"  Total: {time.time() - start:.1f}s (should be ~3s, not ~1s)")

asyncio.run(bad_blocking_example())

async def good_nonblocking_example():
    print("\n=== CORRECT: asyncio.sleep() in async code ===")
    start = time.time()

    async def good_task(name: str):
        print(f"  {name}: starting...")
        await asyncio.sleep(1)   # yields control to event loop
        print(f"  {name}: done")

    await asyncio.gather(good_task("A"), good_task("B"), good_task("C"))
    print(f"  Total: {time.time() - start:.1f}s (should be ~1s — truly concurrent!)")

asyncio.run(good_nonblocking_example())

# ─── run_in_executor — blocking code ko thread mein bhejo ────────────────

import concurrent.futures

def blocking_cpu_work(n: int) -> int:
    """Pure CPU work — can't use await here."""
    return sum(i * i for i in range(n))

async def demo_run_in_executor():
    print("\n=== run_in_executor — blocking code to thread ===")
    loop = asyncio.get_running_loop()

    with concurrent.futures.ThreadPoolExecutor() as pool:
        # Offload blocking call to thread — loop stays responsive
        result = await loop.run_in_executor(pool, blocking_cpu_work, 100_000)
        print(f"  CPU result: {result:,}")
        print("  Loop remained responsive during CPU work (in thread)")

asyncio.run(demo_run_in_executor())

# ─── asyncio.Event — one coroutine signals another ────────────────────────

async def demo_event():
    print("\n=== asyncio.Event — coroutine signaling ===")
    ready = asyncio.Event()

    async def producer():
        print("  Producer: working...")
        await asyncio.sleep(0.3)
        print("  Producer: data ready! signaling...")
        ready.set()

    async def consumer():
        print("  Consumer: waiting for data...")
        await ready.wait()   # blocks until ready.set() is called
        print("  Consumer: got signal, processing!")

    await asyncio.gather(producer(), consumer())

asyncio.run(demo_event())

# SOCH:
# Q1: Event loop ek thread pe chalta hai. Ek coroutine CPU pe busy ho jaye toh kya?
#     (Loop freeze — baaki coroutines wait karte hain. Fix: run_in_executor)
# Q2: FastAPI ek async framework hai. Request handler mein time.sleep() likhne pe?
#     (Entire server hang — no other requests processed during that sleep)
# Q3: asyncio.Event vs threading.Event — kab kaunsa?
#     asyncio.Event: async code ke liye; threading.Event: threads ke liye
