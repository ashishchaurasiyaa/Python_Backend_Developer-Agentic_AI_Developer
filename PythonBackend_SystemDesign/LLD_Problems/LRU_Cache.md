# LRU Cache — LLD
> **Difficulty:** Medium-Hard | **Frequency:** ★★★★★ | **Type:** Data Structure + OOP

---

## What is LRU?

```
LRU = Least Recently Used

Cache full ho gayi → kise nikalna hai?
→ Jisko sabse pehle use kiya tha (least recently used)

Example — capacity=3:
  get(1) → miss → cache: [1]
  get(2) → miss → cache: [1, 2]
  get(3) → miss → cache: [1, 2, 3]    ← full
  get(1) → HIT  → cache: [2, 3, 1]    ← 1 recently used, moves to end
  get(4) → miss → cache: [3, 1, 4]    ← 2 evicted (LRU)

Rule:
  - Most recently used  → right end (tail)
  - Least recently used → left end (head) → evicted first
```

---

## Requirements

```
1. get(key)        → O(1) — return value or -1 if not found
2. put(key, value) → O(1) — insert/update; evict LRU if over capacity
3. Fixed capacity
4. Thread-safe (bonus)
5. TTL support (bonus — Niroskos Redis cache pattern)
6. Stats: hit_rate, miss_rate, evictions (bonus)
```

---

## Two Approaches

```
Approach 1: OrderedDict                ← Python built-in, interview mein quick
  Pros:  3 lines of code, clean
  Cons:  Abstraction hide karta hai — interviewer "internals explain karo" puch sakta hai

Approach 2: Doubly LinkedList + HashMap ← From scratch, shows real understanding
  Pros:  Internals clearly visible — O(1) proof dena easy
  Cons:  More code

Interview tip:
  Pehle OrderedDict se shuru karo (fast) →
  "Under the hood yeh kaise kaam karta hai?" puchne pe Doubly LL dikhao
```

---

## WHY Doubly LinkedList + HashMap?

```
HashMap  alone → O(1) get/put, but can't track order (who's LRU?)
LinkedList alone → order track hoti hai, but O(n) search
Together  →
  HashMap: key → node (O(1) access)
  DLL:     node order = usage order (O(1) move to front/back)

Why DOUBLY (not singly) linked list?
  Node delete karne ke liye prev pointer chahiye
  Singly LL mein: node pata hai but prev node pata nahi → O(n) traversal
  Doubly LL mein: node.prev direct access → O(1) delete
```

---

## Visual

```
HashMap:
  { 1: Node(1,10), 2: Node(2,20), 3: Node(3,30) }

Doubly Linked List (LRU → MRU):
  HEAD ↔ Node(2) ↔ Node(3) ↔ Node(1) ↔ TAIL
   (dummy)   LRU         →         MRU   (dummy)

  HEAD and TAIL are sentinel/dummy nodes — edge case handling easy hoti hai

get(3):
  HashMap → Node(3) milta hai
  Node(3) DLL se remove karo → TAIL se pehle insert karo (MRU)
  HEAD ↔ Node(2) ↔ Node(1) ↔ Node(3) ↔ TAIL

put(4) — capacity=3, evict LRU:
  Node(2) = HEAD.next = LRU → remove karo
  HashMap se bhi delete karo
  Node(4) TAIL se pehle insert karo
  HEAD ↔ Node(1) ↔ Node(3) ↔ Node(4) ↔ TAIL
```

---

## Implementation

```python
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, Generic, Optional, TypeVar

K = TypeVar('K')
V = TypeVar('V')


# ═══════════════════════════════════════════════════════════════
# APPROACH 1: OrderedDict — Quick & Clean
# ═══════════════════════════════════════════════════════════════

class LRUCacheOrderedDict:
    """
    Python ka OrderedDict internally DLL + HashMap hi hai.
    move_to_end(key) → O(1)
    popitem(last=False) → LRU evict → O(1)

    Interview mein: "Pehle yeh dikhata hoon, phir internals explain karta hoon"
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity  = capacity
        self._cache    = OrderedDict()   # key → value, insertion order maintained
        self._lock     = Lock()
        # Stats
        self._hits     = 0
        self._misses   = 0
        self._evictions = 0

    def get(self, key) -> int:
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return -1

            # Move to end → mark as most recently used
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]

    def put(self, key, value) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)   # Update → move to MRU end
                self._cache[key] = value
            else:
                if len(self._cache) >= self.capacity:
                    # popitem(last=False) → removes from front = LRU
                    evicted_key, _ = self._cache.popitem(last=False)
                    self._evictions += 1
                    print(f"[LRU] Evicted key: {evicted_key}")
                self._cache[key] = value

    def __len__(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return round(self._hits / total, 3) if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            "capacity":   self.capacity,
            "size":       len(self._cache),
            "hits":       self._hits,
            "misses":     self._misses,
            "evictions":  self._evictions,
            "hit_rate":   f"{self.hit_rate * 100:.1f}%"
        }

    def __repr__(self):
        return f"LRUCache(capacity={self.capacity}, size={len(self._cache)})"


# ═══════════════════════════════════════════════════════════════
# APPROACH 2: Doubly LinkedList + HashMap — From Scratch
# ═══════════════════════════════════════════════════════════════

class DLLNode:
    """
    Doubly Linked List node.
    HashMap value = pointer to this node → O(1) access.
    """
    __slots__ = ('key', 'value', 'prev', 'next')  # Memory efficient

    def __init__(self, key=None, value=None):
        self.key   = key
        self.value = value
        self.prev: Optional[DLLNode] = None
        self.next: Optional[DLLNode] = None


class LRUCache:
    """
    Doubly LinkedList + HashMap implementation.
    O(1) get, O(1) put — provably.

    DLL maintains usage order:
      HEAD (dummy) ↔ ... LRU ... MRU ... ↔ TAIL (dummy)
      HEAD.next = LRU (evict this first)
      TAIL.prev = MRU (most recently used)

    HashMap: key → DLLNode (O(1) access without traversal)
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity   = capacity
        self._map: Dict[Any, DLLNode] = {}   # key → node

        # Sentinel nodes — no edge cases for empty list
        self._head = DLLNode()   # dummy head (before LRU)
        self._tail = DLLNode()   # dummy tail (after MRU)
        self._head.next = self._tail
        self._tail.prev = self._head

        self._lock = Lock()
        self._hits = self._misses = self._evictions = 0

    # ─── Public Interface ─────────────────────────────────────

    def get(self, key) -> int:
        with self._lock:
            node = self._map.get(key)
            if node is None:
                self._misses += 1
                return -1

            # Move to MRU position (just before TAIL)
            self._move_to_tail(node)
            self._hits += 1
            return node.value

    def put(self, key, value) -> None:
        with self._lock:
            if key in self._map:
                # Update existing — move to MRU
                node = self._map[key]
                node.value = value
                self._move_to_tail(node)
            else:
                # New node
                if len(self._map) >= self.capacity:
                    self._evict_lru()

                new_node = DLLNode(key, value)
                self._map[key] = new_node
                self._insert_before_tail(new_node)

    def peek(self, key) -> int:
        """Get without updating recency — useful for testing"""
        with self._lock:
            node = self._map.get(key)
            return node.value if node else -1

    def delete(self, key) -> bool:
        """Explicit delete — not standard LRU but useful in practice"""
        with self._lock:
            node = self._map.pop(key, None)
            if node is None:
                return False
            self._remove_node(node)
            return True

    def __len__(self) -> int:
        return len(self._map)

    def __contains__(self, key) -> bool:
        return key in self._map

    # ─── DLL Operations (Private) — O(1) each ─────────────────

    def _remove_node(self, node: DLLNode) -> None:
        """
        Unlink node from DLL.
        prev ↔ node ↔ next  →  prev ↔ next
        O(1) because we have prev pointer (that's why DOUBLY linked)
        """
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None    # Help GC
        node.next = None

    def _insert_before_tail(self, node: DLLNode) -> None:
        """
        Insert at MRU position (just before TAIL sentinel).
        ... ↔ TAIL.prev ↔ TAIL
        becomes:
        ... ↔ TAIL.prev ↔ node ↔ TAIL
        """
        prev_node       = self._tail.prev
        prev_node.next  = node
        node.prev       = prev_node
        node.next       = self._tail
        self._tail.prev = node

    def _move_to_tail(self, node: DLLNode) -> None:
        """Remove from current position → insert at MRU end"""
        self._remove_node(node)
        self._insert_before_tail(node)

    def _evict_lru(self) -> None:
        """
        Remove LRU node — HEAD.next is always the LRU.
        Also remove from HashMap.
        """
        lru_node = self._head.next
        if lru_node == self._tail:
            return  # Empty cache — shouldn't happen

        self._remove_node(lru_node)
        del self._map[lru_node.key]
        self._evictions += 1
        print(f"[LRU] Evicted: key={lru_node.key}, value={lru_node.value}")

    # ─── Debug & Stats ────────────────────────────────────────

    def display(self) -> str:
        """LRU → MRU order"""
        nodes = []
        curr  = self._head.next
        while curr != self._tail:
            nodes.append(f"({curr.key}:{curr.value})")
            curr = curr.next
        return "HEAD ↔ " + " ↔ ".join(nodes) + " ↔ TAIL"

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return round(self._hits / total, 3) if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            "capacity":  self.capacity,
            "size":      len(self._map),
            "hits":      self._hits,
            "misses":    self._misses,
            "evictions": self._evictions,
            "hit_rate":  f"{self.hit_rate * 100:.1f}%"
        }


# ═══════════════════════════════════════════════════════════════
# BONUS: TTL-aware LRU Cache (Niroskos Redis pattern)
# ═══════════════════════════════════════════════════════════════

@dataclass
class TTLEntry:
    value:      Any
    expires_at: Optional[datetime]

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class TTLLRUCache(LRUCache):
    """
    LRU + TTL — expired entries treated as cache miss.
    Niroskos pattern:
      SAPTokenCache: token valid for 5 minutes → TTL=300
      BookingCache:  refresh after payment → TTL=3600 but invalidated on write

    Lazy expiry: check on get() — no background thread needed.
    """

    def __init__(self, capacity: int, default_ttl: Optional[int] = None):
        super().__init__(capacity)
        self.default_ttl = default_ttl   # seconds; None = no expiry
        # Override map to store TTLEntry instead of plain value
        self._ttl_map: Dict[Any, TTLEntry] = {}

    def get(self, key) -> Any:
        with self._lock:
            node = self._map.get(key)
            if node is None:
                self._misses += 1
                return -1

            # TTL check — lazy expiry
            ttl_entry = self._ttl_map.get(key)
            if ttl_entry and ttl_entry.is_expired():
                # Treat as miss — evict stale entry
                self._remove_node(node)
                del self._map[key]
                del self._ttl_map[key]
                self._misses += 1
                print(f"[TTL] Expired: key={key}")
                return -1

            self._move_to_tail(node)
            self._hits += 1
            return node.value

    def put(self, key, value, ttl: Optional[int] = None) -> None:
        """
        ttl: seconds until expiry (None = use default_ttl, 0 = no expiry)
        """
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = (
            datetime.now() + timedelta(seconds=effective_ttl)
            if effective_ttl else None
        )
        self._ttl_map[key] = TTLEntry(value=value, expires_at=expires_at)
        super().put(key, value)

    def delete(self, key) -> bool:
        self._ttl_map.pop(key, None)
        return super().delete(key)


# ═══════════════════════════════════════════════════════════════
# BONUS: Generic Typed LRU Cache
# ═══════════════════════════════════════════════════════════════

class TypedLRUCache(Generic[K, V]):
    """
    Type-safe wrapper — int keys, str values, etc.
    Usage: TypedLRUCache[str, dict](capacity=100)
    """

    def __init__(self, capacity: int):
        self._cache = LRUCache(capacity)

    def get(self, key: K) -> Optional[V]:
        result = self._cache.get(key)
        return None if result == -1 else result

    def put(self, key: K, value: V) -> None:
        self._cache.put(key, value)

    def __len__(self) -> int:
        return len(self._cache)
```

---

## Demo

```python
# ─── Basic LRU (DLL + HashMap) ────────────────────────────────
print("=" * 50)
print("BASIC LRU CACHE — DLL + HashMap")
print("=" * 50)

cache = LRUCache(capacity=3)

cache.put(1, 10)
cache.put(2, 20)
cache.put(3, 30)
print(cache.display())           # HEAD ↔ (1:10) ↔ (2:20) ↔ (3:30) ↔ TAIL

print(cache.get(1))              # 10 — 1 becomes MRU
print(cache.display())           # HEAD ↔ (2:20) ↔ (3:30) ↔ (1:10) ↔ TAIL

cache.put(4, 40)                 # Evicts 2 (LRU)
print(cache.display())           # HEAD ↔ (3:30) ↔ (1:10) ↔ (4:40) ↔ TAIL

print(cache.get(2))              # -1 — evicted
print(cache.get(3))              # 30 — hit
print(cache.display())           # HEAD ↔ (1:10) ↔ (4:40) ↔ (3:30) ↔ TAIL

cache.put(3, 300)                # Update existing — moves to MRU
print(cache.display())           # HEAD ↔ (1:10) ↔ (4:40) ↔ (3:300) ↔ TAIL

print(cache.stats)


# ─── OrderedDict version ──────────────────────────────────────
print("\n" + "=" * 50)
print("ORDERED DICT VERSION")
print("=" * 50)

od_cache = LRUCacheOrderedDict(capacity=3)
od_cache.put(1, 10)
od_cache.put(2, 20)
od_cache.put(3, 30)
print(od_cache.get(1))   # 10
od_cache.put(4, 40)      # Evicts 2
print(od_cache.get(2))   # -1
print(od_cache.stats)


# ─── TTL Cache ────────────────────────────────────────────────
print("\n" + "=" * 50)
print("TTL LRU CACHE")
print("=" * 50)
import time

ttl_cache = TTLLRUCache(capacity=3, default_ttl=2)  # 2 second TTL
ttl_cache.put("token", "Bearer xyz123")
ttl_cache.put("user:1", {"name": "Rahul"})

print(ttl_cache.get("token"))    # Bearer xyz123

time.sleep(3)  # Wait for TTL to expire

print(ttl_cache.get("token"))    # -1 — expired
print(ttl_cache.get("user:1"))   # -1 — expired

# Put with custom TTL
ttl_cache.put("perm_key", "no expiry", ttl=0)   # 0 = no expiry
time.sleep(1)
print(ttl_cache.get("perm_key"))  # Still there


# ─── Thread Safety Test ───────────────────────────────────────
print("\n" + "=" * 50)
print("CONCURRENT ACCESS TEST")
print("=" * 50)
import threading

concurrent_cache = LRUCache(capacity=5)
errors = []

def writer(thread_id: int):
    for i in range(20):
        try:
            concurrent_cache.put(f"key_{i % 5}", f"val_{thread_id}_{i}")
        except Exception as e:
            errors.append(str(e))

def reader(thread_id: int):
    for i in range(20):
        try:
            concurrent_cache.get(f"key_{i % 5}")
        except Exception as e:
            errors.append(str(e))

threads = (
    [threading.Thread(target=writer, args=(i,)) for i in range(3)] +
    [threading.Thread(target=reader, args=(i,)) for i in range(3)]
)
for t in threads: t.start()
for t in threads: t.join()

print(f"Errors: {len(errors)}")   # 0
print(f"Cache size: {len(concurrent_cache)}")
print(concurrent_cache.stats)
```

---

## Complexity Analysis

```
Operation        Time      Space    Why
─────────────────────────────────────────────────────────────────
get(key)         O(1)      —        HashMap lookup + DLL move (pointer ops)
put(key, value)  O(1)      —        HashMap insert + DLL insert/evict
evict LRU        O(1)      —        HEAD.next always = LRU, remove = pointer ops
Space overall    O(n)      O(n)     n = capacity (HashMap + DLL nodes)

Why O(1) for DLL operations?
  _remove_node:         3 pointer assignments (not n traversals)
  _insert_before_tail:  4 pointer assignments
  _move_to_tail:        remove + insert = 7 pointer assignments
  _evict_lru:           HEAD.next direct — no traversal needed

Why NOT just HashMap?
  HashMap alone cannot track order → can't find LRU

Why NOT just DLL?
  DLL search = O(n) → need HashMap for O(1) node access by key

Combined = O(1) both
```

---

## DLL Operations — Pointer Diagrams

```python
# _remove_node(B) from: A ↔ B ↔ C
#
#   Before: A.next=B, B.prev=A, B.next=C, C.prev=B
#   After:  A.next=C, C.prev=A
#
#   Code:
#     B.prev.next = B.next    →  A.next = C
#     B.next.prev = B.prev    →  C.prev = A
#     B.prev = B.next = None  →  GC cleanup


# _insert_before_tail(X) into: ... ↔ P ↔ TAIL
#
#   Before: P.next=TAIL, TAIL.prev=P
#   After:  P.next=X, X.prev=P, X.next=TAIL, TAIL.prev=X
#
#   Code:
#     prev_node = self._tail.prev    →  prev_node = P
#     prev_node.next = node          →  P.next = X
#     node.prev = prev_node          →  X.prev = P
#     node.next = self._tail         →  X.next = TAIL
#     self._tail.prev = node         →  TAIL.prev = X


# Why sentinel HEAD and TAIL?
#   Without them, insert/delete at boundaries need special cases:
#     if node == head: head = node.next
#     if node == tail: tail = node.prev
#   With sentinels: same code works for ALL positions
#   HEAD.next always = LRU (even for empty: HEAD.next = TAIL)
```

---

## Interview Q&A

**Q: "Why Doubly LinkedList and not Singly?"**
> "For O(1) delete. In a singly linked list, if I have a pointer to node X, I need to find its predecessor to unlink it — that's O(n) traversal. In a doubly linked list, node.prev gives me the predecessor directly — O(1) delete. Since LRU requires frequent deletion from arbitrary positions (when a key is accessed, we remove it and re-insert at MRU end), doubly linked is essential."

**Q: "Why dummy/sentinel HEAD and TAIL nodes?"**
> "Eliminates edge case handling. Without sentinels, every insert and delete needs to check 'is this the head? is this the tail?' — special cases for empty list, single element. With sentinel nodes, the list is never truly empty (always HEAD ↔ TAIL), and the same pointer operations work for all positions. HEAD.next is always the LRU — even with one element, it's HEAD ↔ node ↔ TAIL, so HEAD.next = node = LRU = correct."

**Q: "How does thread safety work here?"**
> "Single lock (`threading.Lock`) on the cache instance. Every get() and put() acquires the lock before touching the HashMap or DLL. This is correct but not maximally concurrent — reads block each other. A production optimization is `threading.RLock` for re-entrant access, or a `ReadWriteLock` (readers don't block each other, writers get exclusive access). For a distributed cache (Redis), the locking moves to the Redis layer — SET NX for optimistic locking."

**Q: "OrderedDict vs custom DLL — when to use which?"**
> "In an interview with tight time, OrderedDict gets you to a correct solution fast — 10 lines. But if the interviewer asks 'can you implement without built-ins?' or 'what's the time complexity of move_to_end?', you need the custom DLL. In production Python, OrderedDict is perfectly valid — it's already a DLL+HashMap under the hood in CPython (implemented in C). The custom DLL approach demonstrates you understand *why* the data structure works, not just that it does."

**Q: "How would you add TTL support?"**
> "Lazy expiry — check timestamp on get(). If expired, treat as miss and remove the entry. No background thread needed. The alternative is eager expiry with a min-heap (priority queue) ordered by expiry time — a background thread polls the heap and evicts expired entries. Lazy is simpler and works well when misses are acceptable. Eager is better when you need strict memory bounds (expired entries consuming capacity is wasteful). In Niroskos, I used lazy TTL for the SAP token cache — 5-minute TTL, checked on every API call."

**Q: "How would you scale this to a distributed system?"**
> "Single-process LRU → Redis. Redis has no built-in LRU data structure, but you can implement it with a sorted set (ZSET): score = unix timestamp, key = cache key. GET: ZADD key current_time (update score) + fetch from a separate hash. EVICT: ZRANGE with LIMIT 0 0 (lowest score = LRU) + ZREM + HDEL. But Redis already has its own LRU eviction policy (maxmemory-policy allkeys-lru) — so for most cases you just set maxmemory and let Redis handle eviction. The custom ZSET approach is for when you need fine-grained control over what gets evicted."

---

## Comparison: LRU vs LFU vs FIFO

| | LRU | LFU | FIFO |
|---|---|---|---|
| **Evict** | Least recently used | Least frequently used | First inserted |
| **Access pattern** | Temporal locality | Frequency skew | Sequential |
| **Complexity** | O(1) both | O(1) both (with min-heap) | O(1) both |
| **Good for** | Web page cache, DB buffer pool | CDN (popular files stay) | Simple queues |
| **Bad for** | Scan pattern (pollutes cache) | New items evicted before popular | Recent items evicted |
| **Python impl** | `OrderedDict` | `Counter` + `OrderedDict` per freq | `deque` |
| **Real use** | Redis default eviction | Memcached, Varnish | DNS cache |

---

## Real Project Connection

```
Niroskos:
  SAPTokenCache (Singleton + TTL):
    LRU not needed (single key — SAP auth token)
    TTL = 5 minutes, lazy expiry on each API call
    Pattern: cache.get('sap_token') → expired? → refresh → store

  BookingCache (Observer + LRU-like):
    refresh_payment_cache() called via Django Signal (post_save on PaymentAllocation)
    Cache key = booking_id, value = {amount_paid, balance_due}
    Invalidation: write-through (on allocation → immediately refresh)

  Redis as system-level LRU:
    maxmemory-policy = allkeys-lru in redis.conf
    Redis handles eviction automatically — no custom LRU needed
    Custom LRU = only when embedding cache inside Python process

Youngman:
  Role-based query results cached in application layer
  TTL = 10 minutes (menu/role data changes infrequently)
  Invalidation: admin saves role → cache cleared
```

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
