# Cache Eviction Techniques — LRU, LFU, MRU, LIFO, FIFO, Random Replacement

## Quick Reference Card
```
LRU  → Least Recently Used — recently use nahi kiya → evict (most common)
LFU  → Least Frequently Used — least access count → evict
MRU  → Most Recently Used — most recently used → evict (streaming use case)
FIFO → First In First Out — purana data pehle bahar
LIFO → Last In First Out → naya data pehle bahar (rarely used)
RR   → Random Replacement — random koi bhi evict karo
Interview hook → "Redis default = allkeys-lru | LRU = browser cache, CDN cache"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Cache Eviction Kya Hai?

**Analogy: Fridge mein jagah khatam**

Teri fridge mein jagah khatam ho gayi. Tujhe kuch naya rakhna hai. To kuch purana item nikalna padega. Kaunsa nikalega?

- **LRU** (Least Recently Used): Jo item sabse zyada time pehle khaya tha, usse nikalo — probably useful nahi hai ab
- **LFU** (Least Frequently Used): Jo item sabse kam baar khaya gaya, usse nikalo — demand nahi hai
- **FIFO**: Jo item pehle aaya, usse pehle nikalo — queue ki tarah
- **Random**: Koi bhi ek item random nikalo — simple but unpredictable

```
Cache size limit hit → Need to evict → Which key to remove?
  
  [Key A: "package:1" → 2min ago]
  [Key B: "package:2" → 10min ago] ← LRU victim (oldest access)
  [Key C: "user:5"   → 1min ago ]
  [Key D: "booking:3"→ 5min ago ]
  
  New key needed → Evict Key B (least recently used)
```

---

### 1.2 LRU — Least Recently Used

```
CONCEPT: Agar kisi data ko kaafi time se use nahi kiya, 
         toh future mein bhi use hone ki probability kam hai.

IMPLEMENTATION: Doubly Linked List + HashMap

  HashMap: O(1) key lookup
  DLL: O(1) move to front (most recent) and remove from back (least recent)

  Most Recent ←────────────────────────────────────────→ Least Recent
  [pkg:1] ↔ [user:5] ↔ [booking:3] ↔ [pkg:2] ↔ [user:1] ↔ [pkg:7]
  HEAD                                                         TAIL

  When key accessed: move to HEAD (most recent)
  When eviction needed: remove from TAIL (least recent)
  When new key added: add at HEAD, if capacity exceeded → evict TAIL

OPERATIONS:
  get(key): O(1) — hashmap lookup + move node to HEAD
  put(key, val): O(1) — insert at HEAD, evict TAIL if full

EXAMPLE TRACE (capacity=3):
  Cache: []
  
  put(A):  [A]
  put(B):  [B, A]
  put(C):  [C, B, A]
  get(A):  [A, C, B]  ← A moved to front (recently used)
  put(D):  [D, A, C]  ← B evicted (LRU — at tail)
  get(B):  MISS (B was evicted)
  get(C):  [C, D, A]  ← C moved to front

USE CASES:
  Web page cache (browser history)
  Database query result cache
  CDN edge cache
  OS page cache
  
  Redis policy: allkeys-lru, volatile-lru
  Python: functools.lru_cache(maxsize=128)
```

**LRU Python Implementation:**
```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()  # Ordered = insertion order maintained
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        
        self.cache[key] = value
        
        if len(self.cache) > self.capacity:
            # Remove from beginning (least recently used)
            self.cache.popitem(last=False)

# Usage:
cache = LRUCache(3)
cache.put(1, 1)
cache.put(2, 2)
cache.put(3, 3)
cache.get(1)      # Returns 1, moves 1 to most recent
cache.put(4, 4)   # Evicts 2 (LRU), cache: {3:3, 1:1, 4:4}
print(cache.get(2))  # -1 (evicted)
```

---

### 1.3 LFU — Least Frequently Used

```
CONCEPT: Jo data least times access hua hai, wo probably less useful hai.
         Popularity-based eviction.

IMPLEMENTATION: 
  key → value mapping (O(1) lookup)
  key → frequency mapping (O(1) frequency update)
  frequency → [list of keys with that frequency] (for O(1) eviction)
  min_frequency tracker

EXAMPLE TRACE (capacity=3):
  Cache: []
  
  put(A): [A(freq=1)]
  put(B): [A(1), B(1)]
  put(C): [A(1), B(1), C(1)]
  get(A): [A(2), B(1), C(1)]  ← A freq becomes 2
  get(A): [A(3), B(1), C(1)]  ← A freq becomes 3
  get(B): [A(3), B(2), C(1)]  ← B freq becomes 2
  put(D): Evict C (freq=1, LFU)
          [A(3), B(2), D(1)]

TIE-BREAKING: When two keys have same frequency?
  Use LRU as tiebreaker — among equal frequency, evict least recently used

USE CASES:
  When some content is permanently popular (vs temporarily viral)
  Cache for infrequently changing reference data
  Browser caching (frequently visited pages stay)
  
  Redis: allkeys-lfu, volatile-lfu (Redis 4.0+)
  Not as common as LRU — more complex, more memory overhead
```

**LFU Python Implementation:**
```python
from collections import defaultdict, OrderedDict

class LFUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.key_to_val = {}             # key → value
        self.key_to_freq = {}            # key → frequency
        self.freq_to_keys = defaultdict(OrderedDict)  # freq → {key: None} ordered
        self.min_freq = 0
    
    def _increment_freq(self, key):
        freq = self.key_to_freq[key]
        self.key_to_freq[key] = freq + 1
        
        # Remove from old frequency bucket
        del self.freq_to_keys[freq][key]
        if not self.freq_to_keys[freq]:
            del self.freq_to_keys[freq]
            if self.min_freq == freq:
                self.min_freq += 1
        
        # Add to new frequency bucket (OrderedDict preserves insertion order = LRU tiebreak)
        self.freq_to_keys[freq + 1][key] = None
    
    def get(self, key: int) -> int:
        if key not in self.key_to_val:
            return -1
        self._increment_freq(key)
        return self.key_to_val[key]
    
    def put(self, key: int, value: int) -> None:
        if self.capacity <= 0:
            return
        
        if key in self.key_to_val:
            self.key_to_val[key] = value
            self._increment_freq(key)
            return
        
        # Evict if at capacity
        if len(self.key_to_val) >= self.capacity:
            # Evict LFU (and LRU among ties)
            evict_key, _ = self.freq_to_keys[self.min_freq].popitem(last=False)
            del self.key_to_val[evict_key]
            del self.key_to_freq[evict_key]
        
        # Insert new key
        self.key_to_val[key] = value
        self.key_to_freq[key] = 1
        self.freq_to_keys[1][key] = None
        self.min_freq = 1
```

---

### 1.4 MRU — Most Recently Used

```
CONCEPT: Most recently used item evict karo
         Counterintuitive! When is this useful?

USE CASE: Scanning / sequential access patterns
  Example: Reading a huge file sequentially
  - Read Page 1 → cache it
  - Read Page 2 → cache it
  - Read Page 3 → cache it (evict Page 2 — most recent)
  
  If reading sequentially, you'll NEVER re-read a page
  So the most recent one is the LEAST likely to be needed again
  
  Betadistribution tail detection, anti-scan protection
  
OTHER USE CASE: Cache cycling / loop detection
  Loop accessing same 10 pages with cache size 9
  LRU would evict what was accessed 9 steps ago → but loop = you need it!
  MRU would evict what was just accessed → you won't need it immediately

  Rarely used in practice. More of an academic concept.
  MySQL buffer pool has MRU for sequential scan protection.
```

---

### 1.5 FIFO — First In, First Out

```
CONCEPT: Queue ki tarah — jo pehle aaya, pehle bahar

  Time →
  [Old data] → [Newer] → [Newest]
      ↑
  Evict first (FIFO)

IMPLEMENTATION: Simple queue (deque)
  put: append to right
  evict: popleft (oldest)

EXAMPLE:
  Cache: []
  put(A): [A]
  put(B): [A, B]
  put(C): [A, B, C]
  put(D): [B, C, D]  ← A evicted (first in, first out)
  put(E): [C, D, E]  ← B evicted

PROBLEM:
  Old data ko hata deta hai even if frequently accessed!
  
  Example: User frequently uses A every 5 seconds
  But FIFO removes A when queue fills up regardless
  
  A re-fetched from DB → back in queue → eventually evicted again → infinite cycle!
  Called: FIFO thrashing

USE CASE:
  When access pattern truly is time-based (old = less relevant)
  Content delivery for news feeds (old news less relevant)
  Log rotation (old logs archived first)
  Simple when implementation complexity matters more than efficiency

Python implementation:
from collections import deque

class FIFOCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}
        self.queue = deque()
    
    def get(self, key):
        return self.cache.get(key, -1)
    
    def put(self, key, value):
        if key in self.cache:
            self.cache[key] = value  # Update (but don't change queue position)
            return
        
        if len(self.cache) >= self.capacity:
            evict = self.queue.popleft()  # Remove oldest
            del self.cache[evict]
        
        self.cache[key] = value
        self.queue.append(key)
```

---

### 1.6 Random Replacement (RR)

```
CONCEPT: Evict karo koi bhi random key

IMPLEMENTATION: O(1) — just pick random index from cache

PROS:
  Extremely simple
  No overhead of tracking access patterns
  Surprisingly competitive in practice!
  (Research shows random is often only 5-10% worse than LRU)
  
CONS:
  No intelligence — might evict frequently used data
  Unpredictable behavior

USE CASE:
  Embedded systems (very limited memory for metadata)
  CPU TLB (Translation Lookaside Buffer) — hardware constraint
  When O(1) metadata overhead of LRU is too expensive

Python:
import random

class RandomCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}
    
    def get(self, key):
        return self.cache.get(key, -1)
    
    def put(self, key, value):
        if key not in self.cache and len(self.cache) >= self.capacity:
            # Random eviction
            evict_key = random.choice(list(self.cache.keys()))
            del self.cache[evict_key]
        self.cache[key] = value
```

---

### 1.7 LIFO — Last In, First Out

```
CONCEPT: Stack ki tarah — jo last aaya, pehle bahar
         Most recently added item evicted first (not used = recently added)

USAGE: Very rare in caching
  When newest data is least likely to be needed
  (Opposite of typical "hot new content" assumption)
  
  Some use case: Recursive call stack caching
  Undo buffer (recent action undone first)
  
  Generally NOT used for web caching
```

---

### 1.8 Algorithm Comparison

```
Access Pattern Analysis:

Temporal Locality:
  "Recently accessed data likely to be accessed again"
  → Use LRU or LFU
  → Most web apps have this pattern

Frequency Locality:
  "Some data accessed much more than others (Pareto principle)"
  → Use LFU
  → Good for: Popular pages vs long-tail content

Sequential Scan:
  "Data accessed in order, rarely revisited"
  → Use MRU or Random
  → Bad for: LRU (will keep evicting exactly the pages you're about to need)

Time-based:
  "Old data less relevant"
  → Use FIFO or TTL-based
  → News, social feeds, sensor data
```

---

### 1.9 Redis Eviction Policies

```
Redis maxmemory-policy options:

noeviction:      Return error when memory limit reached (default)
                 Good for: Session storage (never silently lose sessions)

allkeys-lru:     Evict any key using LRU
                 Good for: General cache (most common choice)

volatile-lru:    Evict only keys WITH TTL set, using LRU
                 Good for: Mixed cache (some permanent, some temporary)

allkeys-lfu:     Evict any key using LFU (Redis 4.0+)
                 Good for: Skewed access (20% keys = 80% traffic)

volatile-lfu:    Evict only keys with TTL, using LFU

allkeys-random:  Evict any key randomly
                 Good for: When all keys equally likely to be needed

volatile-random: Evict keys with TTL randomly

volatile-ttl:    Evict keys with TTL, prioritizing keys with shortest TTL
                 Good for: Time-based content (evict expiring-soon first)

Configuration:
  # redis.conf
  maxmemory 256mb
  maxmemory-policy allkeys-lru
  maxmemory-samples 10  # LRU approximation sample size (higher = more accurate, slower)

Youngman Redis config:
  maxmemory 512mb
  maxmemory-policy allkeys-lru
  # SAP tokens, session data, package cache — all LRU is fine
```

---

### 1.10 Ashish ke projects mein

```
Redis (ElastiCache) Configuration:
  Policy: allkeys-lru
  Memory: 512MB
  
  What's cached:
  - SAP tokens (5 hour TTL) — infrequently refreshed, high value
  - Package listings (5 min TTL) — read-heavy
  - Django sessions (24 hour TTL) — must not lose
  - Celery task results (1 hour TTL) — temporary
  
  LRU choice: Most of our cached data has temporal locality
  Recently accessed packages/sessions = recently active users
  Old cached data = inactive sessions, can evict safely

Python LRU usage:
  from functools import lru_cache
  
  @lru_cache(maxsize=100)  # In-process LRU cache
  def get_country_list():
      """Countries don't change — cache in process memory"""
      return list(Country.objects.values('code', 'name'))
  
  # lru_cache is process-level (each Gunicorn worker has its own)
  # For shared cache across workers → use Redis
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Cache Eviction Policy**: The algorithm determining which cached item to remove when the cache reaches its capacity limit. The goal is to maximize cache hit rate by retaining the items most likely to be requested again.

> **LRU (Least Recently Used)**: Evicts the item that has not been accessed for the longest time. Based on temporal locality — recently accessed items are more likely to be accessed again. Implemented with doubly linked list + hashmap for O(1) operations.

> **LFU (Least Frequently Used)**: Evicts the item with the fewest accesses. Distinguishes between temporarily popular (burst) and consistently popular items.

---

### 2.2 Policy Comparison Table

| Policy | Evicts | Time Complexity | Space Overhead | Best For |
|--------|--------|-----------------|----------------|----------|
| LRU | Least recently used | O(1) | O(n) — linked list | Most web apps |
| LFU | Least frequently used | O(1) | O(n) — freq maps | Skewed access patterns |
| MRU | Most recently used | O(1) | O(n) | Sequential scans |
| FIFO | Oldest inserted | O(1) | O(n) — queue | Time-based content |
| LIFO | Newest inserted | O(1) | O(n) — stack | Rare, stack-based |
| Random | Random key | O(1) | O(1) — no metadata | Embedded systems, simplicity |

---

### 2.3 LRU Time/Space Complexity Analysis

```
LRU with Doubly Linked List + HashMap:

  get(key): O(1)
    1. HashMap lookup: O(1)
    2. Move node to front of DLL: O(1) (prev/next pointer updates)
  
  put(key, value): O(1)
    1. Check if exists: O(1) hashmap
    2. Insert at front of DLL: O(1)
    3. Evict tail if over capacity: O(1) DLL tail removal

  Space: O(capacity) — stores capacity items

Why not just sort by access time?
  Sorting = O(n log n) per operation
  DLL approach = O(1) — node just moved to front
```

---

### 2.4 Redis Approximate LRU

```
Redis does NOT use a true LRU implementation.
Why? True LRU = per-key linked list → too much memory overhead.

Redis uses APPROXIMATE LRU:
  - Each key stores its last access timestamp (3 bytes extra per key)
  - On eviction: sample maxmemory-samples keys (default=5)
  - Evict the LRU key among those samples
  - Higher samples = more accurate, more CPU

  maxmemory-samples 5:  fast but less accurate
  maxmemory-samples 10: ~98% as accurate as true LRU

This approximation is good enough for production use.
True LRU adds ~8 bytes per key vs Redis's 3 bytes per key.
```

---

### 2.5 Real Project Answer

> "In our Redis (ElastiCache) configuration, we use allkeys-lru policy with a 512MB memory limit. The choice of LRU is based on our access patterns — recently accessed packages, sessions, and tokens are accessed by currently active users, so temporal locality holds. If memory pressure increases, old cached data for inactive users gets evicted naturally. We don't use LFU because our access patterns don't have extreme skew — we don't have a 'celebrity package' that gets 100x the traffic of others. For in-process caching of reference data like country lists that don't change, we use Python's functools.lru_cache with maxsize=100, which is per-worker LRU cache — very fast since it avoids even the Redis network hop."

---

### 2.6 Common Follow-up Q&A

**Q1: How would you implement LRU cache for an interview?**
> "Use OrderedDict in Python — it maintains insertion order and has a `move_to_end()` method. `get(key)`: call `move_to_end(key)` to mark as recently used, return value. `put(key, val)`: if key exists, `move_to_end(key)`. Set value. If over capacity, `popitem(last=False)` removes the least recently used (first item). This gives O(1) for both get and put. The alternative is manually implementing a doubly linked list with a hashmap, which is how you'd explain it in languages without OrderedDict."

**Q2: LRU vs LFU — when do you choose each?**
> "LRU handles recency well — 'I just used it, I'll use it again.' LFU handles frequency well — 'I always use this popular item, even if I haven't used it in the last minute.' The failure mode of LRU is cache pollution: a scan operation reads 10,000 unique items, evicting your entire working set. LFU handles this better since those scanned items have frequency=1. The failure mode of LFU is frequency bias: a viral piece of content from yesterday dominates the cache even when today's trending content is more relevant. In practice, Redis's LFU uses a logarithmic counter with decay, which balances both concerns."

**Q3: What is the cache hit rate and how do you improve it?**
> "Hit rate = cache_hits / (cache_hits + cache_misses). A good rate is 80%+. To improve: (1) Increase cache size — more items fit, fewer evictions. (2) Choose better eviction policy — LFU if access is skewed. (3) Increase TTL — items stay longer. (4) Better key design — don't cache at too granular a level. (5) Cache warming — pre-populate on startup. In Redis, monitor with `INFO stats` → `keyspace_hits` and `keyspace_misses`. Formula: `hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses) * 100`."

---

## Interview Cheat Sheet

```
LRU (Least Recently Used) — MOST COMMON:
  Evicts: Oldest access time
  Implementation: OrderedDict or DLL + HashMap — O(1)
  Redis: allkeys-lru, volatile-lru
  Use: General web cache, browser cache, OS page cache

LFU (Least Frequently Used):
  Evicts: Fewest access count
  Implementation: freq_map + min_freq tracker — O(1)
  Redis: allkeys-lfu, volatile-lfu (Redis 4.0+)
  Use: Skewed access, popular content must stay

MRU (Most Recently Used):
  Evicts: Most recently accessed (counterintuitive!)
  Use: Sequential scans (just read = won't read again)

FIFO:
  Evicts: Oldest insertion time (not access time)
  Use: Time-based content (news, logs)

Random:
  Evicts: Random key
  Use: Embedded systems, simplicity

LRU Implementation (Python):
  from collections import OrderedDict
  cache = OrderedDict()
  cache.move_to_end(key)        # Mark recent
  cache.popitem(last=False)     # Evict LRU

Redis maxmemory-policy:
  allkeys-lru   (most common — cache all)
  volatile-lru  (mixed: some permanent, some temporary)
  noeviction    (never evict — return error when full)

Cache hit rate:
  keyspace_hits / (keyspace_hits + keyspace_misses)
  Target: 80%+
```
