"""
Async Context Managers — async with

Sync: __enter__ / __exit__
Async: __aenter__ / __aexit__  (await kar sakte hain andar)

Use case: DB connection open/close, file lock, HTTP session — jo async operations hain.
"""

import asyncio

# ─── Manual __aenter__ / __aexit__ ───────────────────────────────────────

class AsyncDBConnection:
    """Simulates an async DB connection pool."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None

    async def __aenter__(self):
        print(f"  [DB] Connecting to {self.db_url}...")
        await asyncio.sleep(0.1)  # simulate connection setup
        self.conn = {"url": self.db_url, "id": id(self)}
        print(f"  [DB] Connected. conn_id={self.conn['id']}")
        return self.conn   # ye 'as conn' ko milta hai

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print(f"  [DB] Closing connection {self.conn['id']}...")
        await asyncio.sleep(0.05)  # simulate cleanup
        self.conn = None
        if exc_type:
            print(f"  [DB] Exception during use: {exc_val} — still closing cleanly")
        return False  # exception ko suppress mat karo

async def demo_async_context_manager():
    print("=== Async Context Manager (__aenter__/__aexit__) ===")
    async with AsyncDBConnection("postgresql://localhost/mydb") as conn:
        print(f"  Using connection: {conn['url']}")
        await asyncio.sleep(0.1)  # DB query
        print(f"  Query done")
    print("  Connection automatically closed")

asyncio.run(demo_async_context_manager())

# ─── @asynccontextmanager — simpler way ──────────────────────────────────

from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_http_session(base_url: str):
    print(f"\n  [HTTP] Opening session to {base_url}")
    session = {"base_url": base_url, "requests": 0}
    try:
        yield session              # 'as session' yahan milta hai
    finally:
        print(f"  [HTTP] Closing session. {session['requests']} requests made.")

async def demo_asynccontextmanager():
    print("\n=== @asynccontextmanager ===")
    async with managed_http_session("https://api.example.com") as session:
        session["requests"] += 1
        await asyncio.sleep(0.1)   # API call
        print(f"  Made request to {session['base_url']}/users")
        session["requests"] += 1
        await asyncio.sleep(0.05)  # Another API call

asyncio.run(demo_asynccontextmanager())

# ─── Nested async context managers ───────────────────────────────────────

async def demo_nested():
    print("\n=== Nested Async Context Managers ===")
    async with AsyncDBConnection("db://primary") as db1, \
               AsyncDBConnection("db://replica") as db2:
        print(f"  Both connections open: {db1['id']}, {db2['id']}")

asyncio.run(demo_nested())

# SOCH:
# Q1: Sync 'with' aur 'async with' mein kab kaunsa?
#     Sync: setup/teardown synchronous hai (file open, lock acquire)
#     Async: setup/teardown mein await chahiye (DB conn, HTTP session, socket)
# Q2: __aexit__ mein return False vs return True ka fark?
#     False: exception propagate karo; True: exception suppress karo (rare)
