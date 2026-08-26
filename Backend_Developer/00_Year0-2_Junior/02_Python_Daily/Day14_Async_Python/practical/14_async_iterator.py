"""
Async Iterators — async for

Sync iterator: __iter__ / __next__
Async iterator: __aiter__ / __anext__  (await kar sakte hain next item ke liye)

Use case: DB cursor (paginated rows), SSE stream, WebSocket messages,
          large file reading in chunks, API pagination.
"""

import asyncio

# ─── Manual async iterator ────────────────────────────────────────────────

class AsyncDBCursor:
    """Simulates paginated DB rows fetched asynchronously."""

    def __init__(self, table: str, total_rows: int, page_size: int = 3):
        self.table = table
        self.total_rows = total_rows
        self.page_size = page_size
        self._offset = 0

    def __aiter__(self):
        return self   # self is the iterator

    async def __anext__(self):
        if self._offset >= self.total_rows:
            raise StopAsyncIteration  # tells 'async for' to stop

        # Simulate async DB fetch for this page
        await asyncio.sleep(0.05)  # DB round-trip
        batch = [
            {"id": i, "name": f"Row {i}"}
            for i in range(self._offset, min(self._offset + self.page_size, self.total_rows))
        ]
        self._offset += self.page_size
        return batch

async def demo_async_iterator():
    print("=== Async Iterator — DB rows paginated ===")
    cursor = AsyncDBCursor(table="users", total_rows=8, page_size=3)
    async for batch in cursor:
        print(f"  Fetched batch: {[r['name'] for r in batch]}")
    print("  All rows consumed")

asyncio.run(demo_async_iterator())

# ─── Async generator (simpler than __aiter__/__anext__) ──────────────────

async def paginate_api(endpoint: str, total: int, per_page: int = 2):
    """Async generator — yields pages from a paginated API."""
    page = 1
    fetched = 0
    while fetched < total:
        await asyncio.sleep(0.05)  # API call
        items = [f"{endpoint}/item/{i}" for i in range(fetched, min(fetched + per_page, total))]
        yield items
        fetched += per_page
        page += 1

async def demo_async_generator():
    print("\n=== Async Generator — API pagination ===")
    async for page_items in paginate_api("/api/posts", total=7, per_page=2):
        print(f"  Page: {page_items}")

asyncio.run(demo_async_generator())

# ─── async for with break ─────────────────────────────────────────────────

async def demo_early_stop():
    print("\n=== async for with break — stop after finding target ===")
    async for page in paginate_api("/api/users", total=20, per_page=3):
        for item in page:
            if "item/5" in item:
                print(f"  Found target: {item} — stopping")
                return  # or break out of both loops
        print(f"  Page done, continuing...")
    print("  Not found")

asyncio.run(demo_early_stop())

# SOCH:
# Q1: Sync 'for' aur 'async for' kab kaunsa?
#     Sync: next item lena blocking nahi (list, generator)
#     Async: next item ke liye await karna padta hai (DB cursor, WebSocket)
# Q2: Async generator (yield wala) vs __aiter__/__anext__ class — kaunsa prefer?
#     Generator simpler hai for simple cases. Class use karo jab state complex ho.
