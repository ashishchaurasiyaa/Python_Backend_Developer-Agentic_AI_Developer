"""
============================================================
ITERATOR PATTERN — Practical Implementation
============================================================
Run:  python iterator.py
"""
import asyncio
import itertools
from collections.abc import Iterator, Iterable, AsyncIterator
from typing import Any


# ============================================================
# 1. CLASSIC ITERATOR (custom class with __iter__ + __next__)
# ============================================================
class CountDown:
    """Counts from start down to 1."""
    def __init__(self, start: int):
        self.start = start

    def __iter__(self) -> Iterator[int]:
        # Return a NEW iterator each time (Iterable behavior)
        return CountDownIterator(self.start)


class CountDownIterator:
    def __init__(self, start):
        self.current = start

    def __iter__(self):
        return self          # iterator returns self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        val = self.current
        self.current -= 1
        return val


def demo_classic():
    print("=" * 60)
    print("DEMO 1: Classic iterator class")
    print("=" * 60)
    countdown = CountDown(5)
    print(f"  Pass 1: {list(countdown)}")
    print(f"  Pass 2: {list(countdown)}  ← works because Iterable creates new iterator")


# ============================================================
# 2. GENERATOR FUNCTION (preferred Pythonic way)
# ============================================================
def countdown_gen(start):
    while start > 0:
        yield start
        start -= 1


def demo_generator():
    print("\n" + "=" * 60)
    print("DEMO 2: Generator function")
    print("=" * 60)
    gen = countdown_gen(5)
    print(f"  Pass 1: {list(gen)}")
    print(f"  Pass 2: {list(gen)}  ← empty, generator is exhausted")


# ============================================================
# 3. INFINITE ITERATOR — Fibonacci
# ============================================================
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def demo_infinite():
    print("\n" + "=" * 60)
    print("DEMO 3: Infinite generator + islice")
    print("=" * 60)
    first_10 = list(itertools.islice(fibonacci(), 10))
    print(f"  First 10 Fib: {first_10}")


# ============================================================
# 4. TREE ITERATOR (in-order traversal)
# ============================================================
class TreeNode:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right


def in_order(node):
    if node:
        yield from in_order(node.left)
        yield node.value
        yield from in_order(node.right)


def level_order(root):
    """BFS using generator + queue."""
    if not root:
        return
    from collections import deque
    queue = deque([root])
    while queue:
        node = queue.popleft()
        yield node.value
        if node.left: queue.append(node.left)
        if node.right: queue.append(node.right)


def demo_tree():
    print("\n" + "=" * 60)
    print("DEMO 4: Tree traversal generators")
    print("=" * 60)
    #       5
    #      / \
    #     3   8
    #    / \   \
    #   1   4   9
    root = TreeNode(5,
                    TreeNode(3, TreeNode(1), TreeNode(4)),
                    TreeNode(8, None, TreeNode(9)))
    print(f"  In-order:    {list(in_order(root))}")
    print(f"  Level-order: {list(level_order(root))}")


# ============================================================
# 5. PAGINATED API ITERATOR
# ============================================================
class PaginatedAPI:
    """Iterator that pages through API results."""
    def __init__(self, total_pages=3, page_size=2):
        self.total_pages = total_pages
        self.page_size = page_size
        self.current_page = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.current_page >= self.total_pages:
            raise StopIteration
        # Simulate API call
        start = self.current_page * self.page_size
        page_data = [f"item_{i}" for i in range(start, start + self.page_size)]
        self.current_page += 1
        return page_data


def demo_paginated_api():
    print("\n" + "=" * 60)
    print("DEMO 5: Paginated API iterator")
    print("=" * 60)
    api = PaginatedAPI(total_pages=3, page_size=2)
    for batch in api:
        print(f"  Batch: {batch}")


# ============================================================
# 6. LAZY FILE READER (streaming)
# ============================================================
def read_log_entries(filepath):
    """Generator: yields parsed log entries one by one."""
    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            yield {"line": line_no, "content": line}


def demo_file_streaming():
    print("\n" + "=" * 60)
    print("DEMO 6: Streaming file reader")
    print("=" * 60)
    # Create a temp file
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".log") as f:
        f.write("INFO: started\nERROR: failed\nINFO: retry\n")
        tmpfile = f.name

    for entry in read_log_entries(tmpfile):
        print(f"  Line {entry['line']}: {entry['content']}")
    os.unlink(tmpfile)


# ============================================================
# 7. GENERATOR send() — two-way communication
# ============================================================
def averager():
    total = 0
    count = 0
    avg = 0
    while True:
        value = yield avg
        if value is None:
            break
        total += value
        count += 1
        avg = total / count


def demo_generator_send():
    print("\n" + "=" * 60)
    print("DEMO 7: Generator with send() — coroutine pattern")
    print("=" * 60)
    g = averager()
    next(g)                 # prime
    print(f"  Send 10: avg = {g.send(10)}")
    print(f"  Send 20: avg = {g.send(20)}")
    print(f"  Send 30: avg = {g.send(30)}")


# ============================================================
# 8. itertools — composable iterator utilities
# ============================================================
def demo_itertools():
    print("\n" + "=" * 60)
    print("DEMO 8: itertools power tools")
    print("=" * 60)

    # chain
    print(f"  chain([1,2], [3,4])     = {list(itertools.chain([1,2], [3,4]))}")

    # combinations
    print(f"  combinations('abc', 2)  = {list(itertools.combinations('abc', 2))}")

    # groupby (sort first!)
    data = [("py", "fast"), ("py", "easy"), ("rust", "fast")]
    print("  groupby by lang:")
    for k, group in itertools.groupby(data, key=lambda x: x[0]):
        print(f"    {k}: {list(group)}")

    # takewhile / dropwhile
    nums = [1, 2, 3, 5, 1, 2]
    print(f"  takewhile(<5) = {list(itertools.takewhile(lambda x: x < 5, nums))}")
    print(f"  dropwhile(<5) = {list(itertools.dropwhile(lambda x: x < 5, nums))}")

    # accumulate
    print(f"  accumulate([1,2,3,4]) = {list(itertools.accumulate([1,2,3,4]))}")

    # cycle (limited)
    cycled = itertools.cycle(["A", "B", "C"])
    print(f"  cycle ['A','B','C'] x6 = {[next(cycled) for _ in range(6)]}")


# ============================================================
# 9. ASYNC ITERATOR
# ============================================================
class AsyncFetcher:
    """Simulates async paginated fetcher."""
    def __init__(self, n_pages):
        self.n_pages = n_pages
        self.i = 0
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self.i >= self.n_pages:
            raise StopAsyncIteration
        await asyncio.sleep(0.05)
        page = f"page_{self.i}"
        self.i += 1
        return page


async def async_data_stream(n=3):
    """Async generator."""
    for i in range(n):
        await asyncio.sleep(0.05)
        yield {"event": "data", "id": i}


async def demo_async_iter():
    print("\n" + "=" * 60)
    print("DEMO 9: Async iterators")
    print("=" * 60)
    print("  AsyncFetcher (class-based):")
    async for page in AsyncFetcher(3):
        print(f"    Got {page}")
    print("  async generator:")
    async for item in async_data_stream(3):
        print(f"    {item}")


# ============================================================
# 10. CUSTOM RANGE-LIKE ITERATOR
# ============================================================
class FloatRange:
    """range() for floats."""
    def __init__(self, start, stop, step=0.1):
        self.start, self.stop, self.step = start, stop, step

    def __iter__(self):
        x = self.start
        while x < self.stop:
            yield round(x, 10)
            x += self.step


def demo_float_range():
    print("\n" + "=" * 60)
    print("DEMO 10: Float range generator")
    print("=" * 60)
    fr = FloatRange(0, 1, 0.2)
    print(f"  FloatRange(0, 1, 0.2): {list(fr)}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_classic()
    demo_generator()
    demo_infinite()
    demo_tree()
    demo_paginated_api()
    demo_file_streaming()
    demo_generator_send()
    demo_itertools()
    asyncio.run(demo_async_iter())
    demo_float_range()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Prefer generators (yield) over manual __iter__/__next__
2. Iterable = multi-pass (returns new iterator); Iterator = single-use
3. Use yield from for delegation
4. itertools = composable iterator pipeline
5. Async iterators for streaming I/O
6. Generators give O(1) memory regardless of data size
""")
