# 42 — Bloom Filters

---

## What & Why

**Bloom filter** = a space-efficient probabilistic data structure that tells you:
- "Definitely NOT in set" — with 100% certainty.
- "Probably in set" — with a tunable false-positive rate.

**Never false negatives.** Sometimes false positives.

**Trade-off:** Trade exactness for massive space savings (~10 bits per element instead of full key storage).

### Where it shines
- Quickly check "is this URL malicious?" before expensive blocklist lookup.
- Check "have we seen this username?" before DB query.
- Cassandra uses bloom filters per SSTable to skip disk reads.
- BigTable, HBase, RocksDB do the same.
- CDN: "is this URL in cache?" pre-check.
- Crypto: lighting network channel announcements.

---

## How It Works

```
Initialization:
  bitarray of size m, all zeros
  k different hash functions

Insert(x):
  for each hash h_i in {h_1...h_k}:
    bitarray[h_i(x) % m] = 1

Lookup(x):
  for each hash h_i:
    if bitarray[h_i(x) % m] == 0:
      return "DEFINITELY NOT IN SET"
  return "PROBABLY IN SET"   ← may be false positive
```

### Visual
```
m = 16 bits
k = 3 hash functions

Insert "apple":
  h1("apple") = 2
  h2("apple") = 7
  h3("apple") = 13
  bits = 0010000100001000

Insert "banana":
  h1("banana") = 5
  h2("banana") = 9
  h3("banana") = 13
  bits = 0010010100101000

Lookup "cherry":
  h1("cherry") = 4 → bit 4 is 0 → DEFINITELY NOT IN SET ✓

Lookup "ghost":
  h1("ghost") = 2 → bit set
  h2("ghost") = 7 → bit set
  h3("ghost") = 13 → bit set
  → "probably in set" — but we never inserted "ghost"!
  → FALSE POSITIVE
```

---

## Math

For n inserted elements in m-bit array with k hashes:

**Probability a bit is still 0:**
$$P(\text{bit } = 0) = \left(1 - \frac{1}{m}\right)^{kn} \approx e^{-kn/m}$$

**False positive rate:**
$$P(\text{FP}) = \left(1 - e^{-kn/m}\right)^k$$

**Optimal k** (for given m, n):
$$k_{opt} = \frac{m}{n} \ln 2 \approx 0.693 \frac{m}{n}$$

**Optimal m** (for given n, desired FP rate p):
$$m = -\frac{n \ln p}{(\ln 2)^2}$$

### Quick reference

| FP rate | bits per element |
|---|---|
| 10% | 4.8 |
| 1% | 9.6 |
| 0.1% | 14.4 |
| 0.01% | 19.2 |

So 100M elements × 0.1% FP rate = ~180 MB. Compare to storing actual keys (varies but often 100x more).

---

## Implementation in Python

```python
import math
import mmh3   # murmurhash3 — fast, well-distributed
from bitarray import bitarray

class BloomFilter:
    def __init__(self, expected_items: int, fp_rate: float = 0.01):
        self.m = self._optimal_size(expected_items, fp_rate)
        self.k = self._optimal_hashes(self.m, expected_items)
        self.bits = bitarray(self.m)
        self.bits.setall(False)
        self.n = 0

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return int(-n * math.log(p) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_hashes(m: int, n: int) -> int:
        return max(1, int((m / n) * math.log(2)))

    def add(self, item: str) -> None:
        for seed in range(self.k):
            idx = mmh3.hash(item, seed) % self.m
            self.bits[idx] = True
        self.n += 1

    def __contains__(self, item: str) -> bool:
        for seed in range(self.k):
            idx = mmh3.hash(item, seed) % self.m
            if not self.bits[idx]:
                return False
        return True

    def current_fp_rate(self) -> float:
        # Estimate based on current load
        return (1 - math.exp(-self.k * self.n / self.m)) ** self.k

# Usage
bf = BloomFilter(expected_items=1_000_000, fp_rate=0.001)
bf.add("user123")
bf.add("user456")
print("user123" in bf)   # True
print("user789" in bf)   # False (probably)
```

---

## Why mmh3 over hashlib.md5?

- **mmh3** (MurmurHash3): non-cryptographic, very fast (~10ns/key), good distribution.
- **md5/sha**: cryptographic — overkill, ~100ns/key.
- For bloom filter, distribution > security; mmh3 is industry-standard choice.

### Trick: two hashes, derive k

Instead of k independent hash functions, use:
$$h_i(x) = h_1(x) + i \cdot h_2(x)$$

Same statistical guarantees, only 2 hash computations needed.

---

## Variants

### Counting Bloom Filter
- Each "bit" is a small counter (2-4 bits).
- Supports DELETE by decrementing counters.
- ~4x memory overhead.
- Used when you need deletion.

### Scalable Bloom Filter
- Grows dynamically when capacity reached.
- New layer added with tighter FP rate.
- Query checks all layers.

### Compressed Bloom Filter
- Optimize for transmission over network.
- Higher in-memory FP rate but smaller wire size.

### Cuckoo Filter
- Modern alternative.
- Supports deletion.
- Better space efficiency for low FP rates.
- Used in Redis 4.0+ via RedisBloom module.

### Quotient Filter / XOR Filter
- Better cache locality than Bloom.
- Used in modern databases (RocksDB optionally).

---

## Real-World Use Cases

### Cassandra
- Per SSTable bloom filter for keys.
- Before disk read, check filter: if "not in" → skip disk.
- Massive read speedup for queries on absent keys.

### BigTable / HBase
- Same pattern.

### Chrome's Safe Browsing
- Bloom filter of malicious URLs.
- Bandwidth-efficient distribution to clients.
- False positive → fall back to server check.

### Medium / Quora — feed personalization
- "Has user seen this article?" → bloom filter per user.
- Avoid re-showing already-seen items.

### Email service (Spamhaus)
- "Is this IP in blocklist?" → bloom filter.
- Quick reject before full lookup.

### URL shortener
- "Is this short code taken?" → bloom filter.
- Skip DB hit for guaranteed-unused codes.

### Tinder swiped check (example we covered)
- "Has user swiped this candidate?" → bloom filter per user.
- ~125 KB per user supports 100K swipes.

---

## When NOT to Use Bloom Filter

- **Need exact answers.** Use a hash set if memory allows.
- **Frequent deletions.** Use Counting Bloom or Cuckoo Filter.
- **Need to iterate elements.** Bloom can't enumerate inserts.
- **Small sets** (< 1000 elements). Overhead not worth it.

---

## Production Tips

### 1. Tune for actual load
Default `fp_rate=0.01` is usually fine. For high-stakes (security), use 0.001 or lower. Memory grows logarithmically with FP rate.

### 2. Pre-size correctly
Re-sizing is expensive (or impossible without rebuild). Estimate max n at start and size for that.

### 3. Combine with cache
```python
def is_in_db(key):
    if key not in bloom: return False  # cheap reject
    return cache.get(key) or db.get(key)
```

Bloom rejects ~99% of misses cheaply; cache + DB handles the rest.

### 4. Persistence
Bloom is in-memory. To survive restart, persist:
- Pickle the bitarray to disk.
- Or rebuild from source on startup (slower cold start).

### 5. Distributed Bloom
- Each node has same bloom (replicated).
- Updates via Kafka/pubsub.
- Or sharded bloom: hash key → which node holds bloom for that key.

### 6. Monitor saturation
As inserts approach capacity, FP rate climbs. Alert on bit density > 80%.

```python
def density(bf):
    return bf.bits.count(True) / bf.m
```

---

## Interview Story

**Common question:** "How does Cassandra avoid reading from disk for missing keys?"

**Answer arc:**
1. Cassandra stores data in SSTables (immutable on-disk files).
2. Each SSTable has a bloom filter of its keys.
3. Read query → check bloom for each SSTable → only read disks where bloom says "maybe".
4. Result: 99%+ of "key not exists" queries skip disk entirely.
5. Trade-off: false positives mean some unnecessary disk reads (small cost).

---

## Comparison Table

| Structure | Insert | Lookup | Delete | Space | False Positive |
|---|---|---|---|---|---|
| Hash Set | O(1) | O(1) | O(1) | High | None |
| Bloom Filter | O(k) | O(k) | ✗ | Very Low | Yes |
| Counting Bloom | O(k) | O(k) | O(k) | Low | Yes |
| Cuckoo Filter | O(k) | O(1) | O(1) | Lower | Yes |

---

## Key Formulas to Memorize for Interviews

```
# bits per element for FP rate p
bits_per_element = -log(p) / (ln(2))^2 ≈ -1.44 * log2(p)

# Quick estimates:
1% FP → ~10 bits/element
0.1% FP → ~15 bits/element

# Optimal hash count
k = bits_per_element × ln(2) ≈ 0.7 × bits_per_element
```

These let you eyeball memory budgets in interviews.

---

## TL;DR

Bloom filter = "I might lie about presence, never about absence."

Use when:
- Set is huge.
- "Probably no" or "definitely no" answers are useful.
- Some false positives acceptable.
- Memory matters.

Skip when:
- Need exact membership.
- Need delete + accurate counting.
- Small data set.

**Spend the 20 minutes to truly understand this — it shows up in 30% of senior system design rounds.**
