"""
asyncio.gather() vs create_task() — dono concurrent chalate hain lekin fark hai.

gather()      → coroutines/tasks ko ek saath chalao, sab ke results list mein wait karo
create_task() → task schedule karo aur baaki kaam karte raho (fire and continue)
"""

import asyncio

# ─── gather() — sabka wait karo ──────────────────────────────────────────

async def fetch_user(user_id: int) -> dict:
    print(f"  Fetching user {user_id}...")
    await asyncio.sleep(1)  # DB/API call simulate
    return {"id": user_id, "name": f"User {user_id}"}

async def demo_gather():
    print("=== asyncio.gather() — 3 users ek saath fetch ===")
    # Teeno concurrently chalte hain — total ~1 sec (not 3 sec)
    results = await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3),
    )
    for user in results:
        print(f"  Got: {user}")

asyncio.run(demo_gather())

# ─── create_task() — schedule and continue ───────────────────────────────

async def send_email(to: str) -> str:
    print(f"  Sending email to {to}...")
    await asyncio.sleep(2)
    return f"Email sent to {to}"

async def demo_create_task():
    print("\n=== create_task() — schedule karo, wait baad mein ===")
    # Task start hota hai immediately, but main kaam karta rehta hai
    task1 = asyncio.create_task(send_email("alice@example.com"), name="email-alice")
    task2 = asyncio.create_task(send_email("bob@example.com"),   name="email-bob")

    print("  Tasks scheduled. Main thread aur kaam kar sakta hai...")
    await asyncio.sleep(0)  # yield so tasks can start

    # Baad mein results lao
    result1 = await task1
    result2 = await task2
    print(f"  {result1}")
    print(f"  {result2}")

asyncio.run(demo_create_task())

# ─── gather() with return_exceptions=True ────────────────────────────────

async def risky_call(n: int) -> int:
    await asyncio.sleep(0.1)
    if n == 2:
        raise ValueError(f"Call {n} failed!")
    return n * 10

async def demo_gather_exceptions():
    print("\n=== gather(return_exceptions=True) — error ek ko rok nahi pata ===")
    results = await asyncio.gather(
        risky_call(1),
        risky_call(2),   # ye fail hoga
        risky_call(3),
        return_exceptions=True,  # exception catch karo, raise mat karo
    )
    for r in results:
        if isinstance(r, Exception):
            print(f"  ERROR: {r}")
        else:
            print(f"  OK: {r}")

asyncio.run(demo_gather_exceptions())

# SOCH: gather() vs create_task() kab use karein?
# gather()      → sab results chahiye tab result ek list mein
# create_task() → fire-and-maybe-forget, ya tasks pe control chahiye (cancel etc.)
