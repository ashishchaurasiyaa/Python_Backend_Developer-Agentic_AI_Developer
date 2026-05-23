# Coding Patterns — Python Interview Problems

## Key Patterns for Backend/AI Interviews
```
Most common patterns:
1. Two Pointers / Sliding Window
2. Hash Map (frequency, lookup)
3. Stack / Queue
4. Binary Search
5. Dynamic Programming (memoization)
6. Tree/Graph traversal
7. Async patterns (Python-specific)
```

---

## Pattern 1: Sliding Window + Two Pointers

```python
# ===== LRU CACHE (Very common in interviews!) =====
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)  # Mark as recently used
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # Remove LRU (first item)

# Test
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))   # 1
cache.put(3, 3)       # Evicts key 2
print(cache.get(2))   # -1 (evicted)

# ===== SLIDING WINDOW MAXIMUM =====
from collections import deque

def max_sliding_window(nums: list[int], k: int) -> list[int]:
    """O(n) — monotonic deque"""
    dq: deque[int] = deque()  # stores indices
    result = []
    
    for i, num in enumerate(nums):
        # Remove elements outside window
        while dq and dq[0] < i - k + 1:
            dq.popleft()
        
        # Remove smaller elements (they'll never be max)
        while dq and nums[dq[-1]] < num:
            dq.pop()
        
        dq.append(i)
        
        if i >= k - 1:
            result.append(nums[dq[0]])
    
    return result

print(max_sliding_window([1, 3, -1, -3, 5, 3, 6, 7], 3))
# [3, 3, 5, 5, 6, 7]

# ===== LONGEST SUBSTRING WITHOUT REPEAT =====
def length_of_longest_substring(s: str) -> int:
    char_index: dict[str, int] = {}
    max_len = left = 0
    
    for right, char in enumerate(s):
        if char in char_index and char_index[char] >= left:
            left = char_index[char] + 1
        char_index[char] = right
        max_len = max(max_len, right - left + 1)
    
    return max_len

print(length_of_longest_substring("abcabcbb"))  # 3 "abc"
```

---

## Pattern 2: HashMap + Frequency

```python
# ===== GROUP ANAGRAMS =====
from collections import defaultdict

def group_anagrams(strs: list[str]) -> list[list[str]]:
    groups: dict[tuple, list[str]] = defaultdict(list)
    
    for word in strs:
        key = tuple(sorted(word))  # "eat" → ('a','e','t')
        groups[key].append(word)
    
    return list(groups.values())

print(group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"]))
# [["eat","tea","ate"], ["tan","nat"], ["bat"]]

# ===== TOP K FREQUENT ELEMENTS =====
import heapq
from collections import Counter

def top_k_frequent(nums: list[int], k: int) -> list[int]:
    count = Counter(nums)
    # heap of (-count, num) — negative for max-heap
    return heapq.nlargest(k, count.keys(), key=count.get)

print(top_k_frequent([1, 1, 1, 2, 2, 3], 2))  # [1, 2]

# ===== TWO SUM =====
def two_sum(nums: list[int], target: int) -> list[int]:
    seen: dict[int, int] = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# ===== WORD FREQUENCY COUNTER (Practical) =====
from collections import Counter
import re

def analyze_text(text: str) -> dict:
    words = re.findall(r'\b[a-z]+\b', text.lower())
    freq = Counter(words)
    
    return {
        "total_words": len(words),
        "unique_words": len(freq),
        "top_10": freq.most_common(10),
        "hapax": [w for w, c in freq.items() if c == 1],  # appear once
    }
```

---

## Pattern 3: Stack & Queue

```python
# ===== VALID PARENTHESES =====
def is_valid(s: str) -> bool:
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}
    
    for char in s:
        if char in '({[':
            stack.append(char)
        elif char in pairs:
            if not stack or stack[-1] != pairs[char]:
                return False
            stack.pop()
    
    return len(stack) == 0

# ===== DAILY TEMPERATURES (Monotonic Stack) =====
def daily_temperatures(temperatures: list[int]) -> list[int]:
    """For each day, how many days until warmer temperature?"""
    result = [0] * len(temperatures)
    stack: list[int] = []  # stores indices
    
    for i, temp in enumerate(temperatures):
        while stack and temperatures[stack[-1]] < temp:
            prev_idx = stack.pop()
            result[prev_idx] = i - prev_idx
        stack.append(i)
    
    return result

print(daily_temperatures([73, 74, 75, 71, 69, 72, 76, 73]))
# [1, 1, 4, 2, 1, 1, 0, 0]

# ===== IMPLEMENT QUEUE USING TWO STACKS =====
class MyQueue:
    def __init__(self):
        self.input_stack: list = []
        self.output_stack: list = []
    
    def push(self, x: int) -> None:
        self.input_stack.append(x)
    
    def pop(self) -> int:
        self._transfer()
        return self.output_stack.pop()
    
    def peek(self) -> int:
        self._transfer()
        return self.output_stack[-1]
    
    def empty(self) -> bool:
        return not self.input_stack and not self.output_stack
    
    def _transfer(self):
        if not self.output_stack:
            while self.input_stack:
                self.output_stack.append(self.input_stack.pop())
```

---

## Pattern 4: Binary Search

```python
# ===== SEARCH IN ROTATED SORTED ARRAY =====
def search_rotated(nums: list[int], target: int) -> int:
    left, right = 0, len(nums) - 1
    
    while left <= right:
        mid = (left + right) // 2
        
        if nums[mid] == target:
            return mid
        
        # Left half is sorted
        if nums[left] <= nums[mid]:
            if nums[left] <= target < nums[mid]:
                right = mid - 1
            else:
                left = mid + 1
        # Right half is sorted
        else:
            if nums[mid] < target <= nums[right]:
                left = mid + 1
            else:
                right = mid - 1
    
    return -1

# ===== FIND PEAK ELEMENT =====
def find_peak(nums: list[int]) -> int:
    left, right = 0, len(nums) - 1
    
    while left < right:
        mid = (left + right) // 2
        if nums[mid] < nums[mid + 1]:
            left = mid + 1   # Peak is to the right
        else:
            right = mid      # Peak is at mid or left
    
    return left

# ===== PRACTICAL: Rate Limiter with Binary Search =====
import bisect
import time

class SlidingWindowRateLimiter:
    """Token bucket rate limiter using sorted list"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: list[float] = []  # timestamps
    
    def allow(self) -> bool:
        now = time.time()
        cutoff = now - self.window
        
        # Binary search to find requests outside window
        idx = bisect.bisect_left(self.requests, cutoff)
        self.requests = self.requests[idx:]  # Remove old requests
        
        if len(self.requests) < self.max_requests:
            bisect.insort(self.requests, now)
            return True
        return False
```

---

## Pattern 5: Dynamic Programming

```python
# ===== LONGEST COMMON SUBSEQUENCE =====
def lcs(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    return dp[m][n]

# ===== COIN CHANGE =====
def coin_change(coins: list[int], amount: int) -> int:
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    
    for coin in coins:
        for i in range(coin, amount + 1):
            dp[i] = min(dp[i], dp[i - coin] + 1)
    
    return dp[amount] if dp[amount] != float('inf') else -1

print(coin_change([1, 5, 11], 15))  # 3 (5+5+5)

# ===== MEMOIZATION (Top-down DP) =====
from functools import lru_cache

@lru_cache(maxsize=None)
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# ===== PRACTICAL: Token Cost Optimizer =====
def min_cost_chunking(text_length: int, max_context: int, cost_per_token: float) -> int:
    """Find minimum API calls to process text within context window"""
    if text_length <= max_context:
        return 1
    
    chunks = (text_length + max_context - 1) // max_context
    return chunks
```

---

## Pattern 6: Async Patterns (Python-specific)

```python
import asyncio
import aiohttp
from typing import Any

# ===== GATHER — PARALLEL ASYNC =====
async def fetch_all(urls: list[str]) -> list[dict]:
    """Fetch multiple URLs concurrently"""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

async def fetch_one(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url) as resp:
        return {"url": url, "status": resp.status, "data": await resp.json()}

# ===== SEMAPHORE — LIMIT CONCURRENCY =====
async def bounded_fetch(urls: list[str], max_concurrent: int = 10) -> list[Any]:
    sem = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_sem(url: str) -> Any:
        async with sem:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return await resp.json()
    
    return await asyncio.gather(*[fetch_with_sem(url) for url in urls])

# ===== PRODUCER-CONSUMER =====
async def producer_consumer_example():
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    
    async def producer():
        for i in range(1000):
            await queue.put(i)
            await asyncio.sleep(0.01)
        await queue.put(None)  # Sentinel
    
    async def consumer(worker_id: int):
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            # Process item
            await asyncio.sleep(0.05)
            queue.task_done()
    
    await asyncio.gather(
        producer(),
        consumer(1),
        consumer(2),
        consumer(3),
    )

# ===== TIMEOUT + RETRY =====
async def with_timeout_retry(
    coro_factory,
    timeout: float = 30.0,
    max_retries: int = 3,
):
    for attempt in range(max_retries):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout)
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

# ===== ASYNC CONTEXT MANAGER =====
class AsyncDatabasePool:
    async def __aenter__(self):
        self.conn = await asyncpg.connect("postgresql://...")
        return self.conn
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.conn.close()
        return False

async def use_db():
    async with AsyncDatabasePool() as conn:
        result = await conn.fetch("SELECT * FROM users")
```

---

## Pattern 7: Tree & Graph

```python
from collections import deque
from typing import Optional

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

# ===== LEVEL ORDER TRAVERSAL (BFS) =====
def level_order(root: Optional[TreeNode]) -> list[list[int]]:
    if not root:
        return []
    
    result = []
    queue = deque([root])
    
    while queue:
        level = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.val)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)
    
    return result

# ===== GRAPH: COURSE SCHEDULE (Topological Sort) =====
def can_finish(num_courses: int, prerequisites: list[list[int]]) -> bool:
    """Detect cycle in directed graph (DFS)"""
    graph: dict[int, list[int]] = {i: [] for i in range(num_courses)}
    for course, pre in prerequisites:
        graph[pre].append(course)
    
    # 0: unvisited, 1: visiting, 2: done
    state = [0] * num_courses
    
    def has_cycle(node: int) -> bool:
        if state[node] == 1:
            return True
        if state[node] == 2:
            return False
        
        state[node] = 1  # Mark as visiting
        for neighbor in graph[node]:
            if has_cycle(neighbor):
                return True
        state[node] = 2  # Mark as done
        return False
    
    return not any(has_cycle(i) for i in range(num_courses) if state[i] == 0)

# ===== NUMBER OF ISLANDS (DFS/BFS) =====
def num_islands(grid: list[list[str]]) -> int:
    if not grid:
        return 0
    
    rows, cols = len(grid), len(grid[0])
    count = 0
    
    def dfs(r: int, c: int):
        if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] != '1':
            return
        grid[r][c] = '#'  # Mark visited
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            dfs(r + dr, c + dc)
    
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1':
                dfs(r, c)
                count += 1
    
    return count
```

---

## Python-Specific Tricks Interviewers Love

```python
# ===== ITERTOOLS =====
from itertools import groupby, chain, product, combinations, permutations

# Group consecutive elements
data = [1, 1, 2, 2, 3, 1, 1]
groups = [(k, list(g)) for k, g in groupby(data)]
# [(1, [1,1]), (2, [2,2]), (3, [3]), (1, [1,1])]

# Flatten nested lists
nested = [[1, 2], [3, 4], [5]]
flat = list(chain.from_iterable(nested))  # [1, 2, 3, 4, 5]

# ===== COLLECTIONS =====
from collections import Counter, defaultdict, namedtuple, deque

Point = namedtuple('Point', ['x', 'y'])
p = Point(1, 2)
print(p.x, p.y)

# Counter arithmetic
c1 = Counter("aabbc")
c2 = Counter("abc")
print(c1 - c2)   # Counter({'a': 1, 'b': 1})
print(c1 & c2)   # Counter({'a': 1, 'b': 1, 'c': 1})  # intersection

# ===== USEFUL BUILTINS =====
# zip_longest
from itertools import zip_longest
list(zip_longest([1, 2], [3, 4, 5], fillvalue=0))
# [(1,3), (2,4), (0,5)]

# enumerate with start
for i, item in enumerate(['a', 'b', 'c'], start=1):
    print(i, item)  # 1 a, 2 b, 3 c

# walrus operator (Python 3.8+)
data = [1, 2, 3, 4, 5]
if (n := len(data)) > 3:
    print(f"List too long: {n}")

# ===== SORT TRICKS =====
people = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
sorted_by_age = sorted(people, key=lambda x: x["age"])
sorted_multi = sorted(people, key=lambda x: (-x["age"], x["name"]))  # age desc, name asc

# ===== COMPREHENSIONS =====
# Dict comprehension with condition
squares = {x: x**2 for x in range(10) if x % 2 == 0}

# Nested list comp
matrix_flat = [cell for row in [[1,2],[3,4],[5,6]] for cell in row]

# Generator (memory efficient)
total = sum(x**2 for x in range(1_000_000))  # No list created
```
