# Redis Core Data Structures Deep Dive (Lists, Hashes, Sets, Sorted Sets)

## Why It Matters

Redis interview ka sabse common opening: "Redis sirf key-value store hai?" — Answer: nahi, 5 core data structures hain aur **sahi structure choose karna hi senior-level skill hai**. Galat structure choose karoge → O(n) operations, memory bloat, ya race conditions.

Senior interview framing: "Design a leaderboard" / "Design a rate limiter" / "Design a social graph (mutual friends)" — in sab ka answer ek specific data structure + command combo hai, generic "use a database" nahi chalega.

Is doc mein: Lists, Hashes, Sets, Sorted Sets — internal encoding already `01_basics_installation_cli.md` (Q5) mein cover hui hai, yahan hum **use-case framing + interview angles + pitfalls** pe focus karenge, command syntax repeat nahi karenge (wo `practical/01_basics_cli_keys.py` mein already exercised hai).

---

## Core Concepts

### 1. Lists — Ordered Collection (Linked List Semantics)

Lists = insertion-order-preserving sequences, duplicates allowed. Push/pop dono ends se O(1).

**Commands already exercised:** `LPUSH/RPUSH`, `LPOP/RPOP`, `LRANGE`, `LTRIM`, `LINSERT`, `LREM`, `LSET`, `LMOVE`, `BLPOP` — dekho `practical/01_basics_cli_keys.py::demo_lists`.

**Queue pattern (simple, lightweight):**
```bash
LPUSH queue:jobs job1        # producer pushes
BRPOP queue:jobs 5           # consumer blocks up to 5s, pops FIFO
```
Ye kaam karta hai chhote/simple queues ke liye — koi extra broker install nahi karna.

**Kyun Streams usually better hain real queue ke liye** (see `theory/05_streams_consumer_groups.md`):
- List queue mein message consume hote hi **gayab ho jaata hai** — consumer crash ho gaya beech mein → message lost (no ACK mechanism).
- Multiple consumers List se BRPOP karein to ek hi consumer ko message milega (competing consumers, fine for simple load balancing) — lekin **replay / consumer groups / pending-entries-list nahi hai**.
- Streams: at-least-once delivery, XACK, XPENDING, XCLAIM for stuck messages, multiple independent consumer groups reading same data.
- **Rule of thumb:** disposable/simple background jobs → List + BRPOP theek hai. Durable/auditable/must-not-lose queue → Streams.

**LMOVE — atomic reliable queue pattern:**
```bash
# Old unreliable pattern (message lost if consumer crashes after LPOP, before processing):
job = RPOP queue:jobs
process(job)

# Reliable pattern: atomically move to a "processing" list before working on it
job = RPOPLPUSH queue:jobs queue:processing   # deprecated alias, use LMOVE
job = LMOVE queue:jobs queue:processing RIGHT LEFT
process(job)
LREM queue:processing 1 job                    # remove only after success
```
Agar consumer crash ho jaaye processing ke beech mein, job `queue:processing` list mein reh jaata hai — ek watchdog process use wapas `queue:jobs` mein move kar sakta hai (timeout check karke). Yehi **reliable queue pattern** hai jo interview mein poocha jaata hai.

**O(n) danger:**
- `LINDEX`, `LSET`, `LINSERT` — ye O(n) hain kyunki List ek linked-list-like structure hai (quicklist = linked list of listpacks), random access ke liye poori list traverse karni padti hai worst case.
- Sirf `LPUSH/RPUSH/LPOP/RPOP` (dono ends) O(1) hain.
- **Bade lists pe `LINDEX` loop mein mat chalao** — agar random access chahiye, List galat structure hai, Hash ya sorted structure socho.

### 2. Hashes — Field-Value Map (Object Representation)

Hash = ek key ke andar multiple field-value pairs — **object/record ko represent karne ka natural way**.

**Commands already exercised:** `HSET/HGET/HGETALL/HMGET/HINCRBY/HSETNX/HDEL/HEXISTS/HSCAN` — dekho `demo_hashes`.

**Hash vs multiple String keys — memory aur round-trip dono:**
```bash
# BAD: 5 separate String keys for one user object
SET user:1:name "Alice"
SET user:1:email "alice@test.com"
SET user:1:age "30"
SET user:1:city "Delhi"
SET user:1:balance "5000"
# → 5 keys, 5x key-overhead (~56 bytes/key metadata), 5 round-trips to fetch all fields

# GOOD: 1 Hash key
HSET user:1 name "Alice" email "alice@test.com" age 30 city "Delhi" balance 5000
HGETALL user:1     # single round-trip gets everything
```
- **Memory:** listpack encoding (jab fields ≤ `hash-max-listpack-entries`, default 128, aur values ≤ `hash-max-listpack-value`, default 64 bytes) — compact contiguous memory block, no per-field pointer overhead. Compare to 5 separate top-level keys jahan har key apna dictionary entry + expiry slot + refcount leta hai.
- **Round-trip:** `HGETALL` = 1 network call. 5 `GET`s (without pipelining) = 5 round-trips = 5x latency.
- **Trade-off:** Hash fields ki apni TTL nahi hoti (Redis < 7.4) — poori Hash ek hi TTL leti hai key-level pe.

**Field-level TTL — HEXPIRE (Redis 7.4+):**
```bash
HEXPIRE user:1 3600 FIELDS 1 otp_code     # sirf 'otp_code' field expire, baaki Hash rehta hai
HTTL user:1 FIELDS 1 otp_code             # remaining TTL for that field
HPERSIST user:1 FIELDS 1 otp_code         # remove field TTL
```
Use case: ek Hash mein user ka permanent profile + ek temporary OTP field — pehle alag key chahiye hota tha, ab same Hash mein field-level expiry.

### 3. Sets — Unordered Unique Collection

Set = unique members, no order, no duplicates. **Set algebra** iska superpower hai.

**Commands already exercised:** `SADD/SREM/SISMEMBER/SMISMEMBER/SMEMBERS/SCARD/SPOP/SRANDMEMBER/SMOVE/SINTER/SUNION/SDIFF/SINTERSTORE` — dekho `demo_sets`.

**Real-world set algebra use cases:**
```bash
# 1. Tag intersection — "posts tagged both 'redis' AND 'python'"
SADD tag:redis post:1 post:2 post:5
SADD tag:python post:2 post:5 post:9
SINTER tag:redis tag:python              # → post:2, post:5

# 2. Mutual friends — classic interview question
SADD friends:alice bob carol dave
SADD friends:bob alice carol eve
SINTER friends:alice friends:bob         # → carol (mutual friend)

# 3. Unique visitor tracking (daily unique users, no duplicates)
SADD visitors:2026-08-06 user:100 user:101 user:100   # user:100 counted once
SCARD visitors:2026-08-06                              # → 2 (unique count)

# 4. Store result for reuse (avoid recomputation)
SINTERSTORE mutual:alice:bob friends:alice friends:bob
```
**Caveat:** `SCARD` for unique-visitor counting works but Set memory grows linearly with unique members — for very high cardinality (millions), consider **HyperLogLog** (`PFADD`/`PFCOUNT`, see `theory/03_geo_hyperloglog_json.md`) which trades exact count for ~12KB fixed memory.

**Encoding:**
- All-integer Set, small size (≤ `set-max-intset-entries`, default 512) → **intset** (sorted integer array, most compact).
- Small Set with strings, or mixed (≤ `set-max-listpack-entries`) → **listpack** (Redis 7.2+).
- Large Set → **hashtable** (O(1) membership check, more memory per member).
- Interview trap: agar ek intset mein ek bhi non-integer add karo, poora Set silently **hashtable** mein convert ho jaata hai — memory profile change ho jaata hai bina warning ke.

### 4. Sorted Sets (ZSets) — Scored, Ranked Collection

ZSet = unique members with a floating-point **score**, always kept sorted by score. Ye Redis ka sabse powerful structure hai ranking/range queries ke liye.

**Commands already exercised:** `ZADD/ZRANGE/ZREVRANGE/ZRANGEBYSCORE/ZRANK/ZREVRANK/ZSCORE/ZINCRBY/ZCARD/ZCOUNT/ZREM/ZPOPMIN/ZPOPMAX/ZRANGEBYLEX/ZUNIONSTORE` — dekho `demo_sorted_sets`.

**Leaderboard pattern (the canonical ZSet interview answer):**
```bash
ZINCRBY leaderboard:game 10 "player:42"    # score update — atomic increment on a match win
ZREVRANGE leaderboard:game 0 9 WITHSCORES  # top-10 (highest score first)
ZRANK leaderboard:game "player:42"         # 0-indexed rank, ascending
ZREVRANK leaderboard:game "player:42"      # 0-indexed rank, descending → "user's rank" for UI
```
Sabhi operations O(log n) — even a 10-million-player leaderboard ke top-10 aur kisi bhi player ka rank milliseconds mein.

**Time-range queries using timestamp as score:**
```bash
# Events log — score = unix timestamp
ZADD events:user:1 1735689600 "login"
ZADD events:user:1 1735693200 "purchase"
ZRANGEBYSCORE events:user:1 1735689600 1735692000   # events between two timestamps
```
Ye pattern time-series-lite queries ke liye kaafi common hai jab full TSDB overkill ho.

**ZRANGEBYLEX — edge case:**
```bash
ZADD words 0 apple 0 banana 0 cherry     # ⚠️ ALL scores must be equal (0 here)
ZRANGEBYLEX words "[a" "[c\xff"          # lexicographic range — only valid when scores tied
```
Agar scores different hain, `ZRANGEBYLEX` ka result **undefined/meaningless** hota hai — ye sirf tab use karo jab tumhe ek Set ko sorted-order mein rakhna ho with autocomplete-style prefix matching, aur score sirf ek dummy tie-breaker ho (usually 0).

**Internal structure — skiplist:**
Bade ZSets (> `zset-max-listpack-entries`, default 128) internally **skiplist + hashtable** combo use karte hain:
- Hashtable: O(1) member → score lookup (`ZSCORE`).
- Skiplist: multi-level linked list jahan har level pichhle level se "faster lane" hai — insert/delete/range O(log n) mein, bina poora balanced tree maintain kiye (jaise B-tree/AVL). Skiplist probabilistically balanced hoti hai (coin-flip se level decide hota hai), simpler to implement/maintain than tree rebalancing.

### 5. SORT — Generic Sorting Over Collections

`SORT` List/Set/ZSet ke elements ko sort kar sakta hai, aur external keys se related data bhi fetch kar sakta hai (`BY`/`GET` pattern).

```bash
# Numeric sort of a List
RPUSH mylist 3 1 2
SORT mylist                              # → 1, 2, 3

# BY pattern — sort a Set of IDs by an external weight
SADD myset 1 2 3
SET weight_1 30
SET weight_2 10
SET weight_3 20
SORT myset BY weight_*                    # → 2, 3, 1 (sorted by external weight keys)

# GET pattern — sort by weight, but return related data instead of the ID itself
SET data_1 "Item One"
SET data_2 "Item Two"
SET data_3 "Item Three"
SORT myset BY weight_* GET data_*         # → "Item Two", "Item Three", "Item One"

# GET # — return the sorted element itself alongside GET data
SORT myset BY weight_* GET # GET data_*
```
**Use case:** product IDs Set mein hain, price/rating alag String keys mein hai — `SORT ... BY price_* GET name_*` se ek hi command mein "sorted-by-price product names" mil jaate hain, without pulling everything into app code and sorting there. **Caveat:** `SORT` by default O(N log N) aur `BY`/`GET` ke saath extra key lookups — bade collections pe expensive ho sakta hai, aur Cluster mode mein `BY`/`GET` external keys same hash slot mein hone chahiye (practically Cluster mein avoid karo).

### 6. Comparison Table — Which Structure For Which Use Case

| Use Case | Structure | Why |
|---|---|---|
| Simple key → value cache | **String** | O(1) GET/SET, simplest |
| Object/record with multiple fields | **Hash** | Single round-trip, memory-efficient vs many Strings |
| Ordered queue (simple, disposable) | **List** | LPUSH+BRPOP, O(1) push/pop |
| Durable/replayable queue | **Stream** (not in this doc) | ACK, consumer groups, replay |
| Unique membership (tags, dedup) | **Set** | O(1) SADD/SISMEMBER, no duplicates |
| Relationship queries (mutual friends, intersection) | **Set** | SINTER/SUNION/SDIFF are native set algebra |
| Leaderboard / ranking | **Sorted Set** | O(log n) insert + range, ZREVRANGE for top-N |
| Time-range / time-series-lite | **Sorted Set** | score = timestamp, ZRANGEBYSCORE |
| Rate limiting (sliding window) | **Sorted Set** or **String+INCR** | ZSet: precise sliding window via ZREMRANGEBYSCORE + ZCARD; String: simple fixed window counter |
| Unique count at massive scale | **HyperLogLog** (not in this doc) | ~12KB regardless of cardinality, approximate |
| Recent-N items (capped list) | **List + LTRIM** | keep bounded size, O(1) trim |

Yeh table hi actual interview answer hai jab poocha jaaye "how would you design X in Redis" — structure choice + ek-line justification.

---

## How It Works Internally

### Quicklist (List)
List ki internal encoding **quicklist** hai — ek doubly-linked list of **listpacks** (small compact nodes). Har node mein multiple elements listpack format mein packed hote hain (no per-element pointer overhead within a node), aur nodes ek doubly-linked list se connected hain. Ye hybrid design deta hai: memory efficiency of listpack (within node) + O(1) push/pop at both ends (linked list property). `list-max-listpack-size` controls kitne elements/bytes ek node mein fit ho sakte hain before splitting.

### Skiplist + Hashtable (ZSet)
Bada ZSet do structures maintain karta hai simultaneously:
1. **Hashtable** — member string → score, O(1) `ZSCORE` lookup.
2. **Skiplist** — score-ordered structure with multiple "express lane" levels, O(log n) average for insert/delete/range queries (`ZRANGE`, `ZRANGEBYSCORE`).

Dono structures same data point karte hain — insert/delete dono jagah update hote hain, memory thoda zyada leta hai (double bookkeeping) lekin dono access patterns (by member, by score-range) fast rehte hain.

### Intset / Listpack / Hashtable (Set)
Set encoding data pattern pe depend karta hai:
- Sab integers, chhota → **intset** (sorted C array of integers, binary search O(log n), most compact).
- Chhota, strings ya mixed → **listpack** (Redis 7.2+, sequential compact encoding).
- Bada, ya ek bhi non-integer intset mein aa jaaye → **hashtable** (O(1) avg lookup, more memory per entry due to hash buckets + pointers).

### Listpack (Hash, chhoti List/ZSet bhi)
Listpack = single contiguous memory block jisme entries sequentially packed hain (length-prefixed), koi per-entry pointer nahi (ziplist ka successor, safer against cascading update bug). Chhoti collections ke liye CPU cache-friendly bhi hai (sequential memory access) — isliye chhoti Hash pe `HGETALL` bhi fast hoti hai despite O(n) complexity, kyunki n chhota hai aur memory locality achhi hai.

---

## Common Pitfalls

### 1. Full Scans on Large Collections (KEYS-Pattern Anti-Pattern, But for Collections)

```bash
SMEMBERS huge:set          # ❌ 10M member Set — blocks server, returns everything at once
HGETALL huge:hash          # ❌ same problem for large Hash
LRANGE huge:list 0 -1      # ❌ same problem for large List
```
Jaise `KEYS *` production mein bad hai, waise hi **`SMEMBERS`/`HGETALL`/`LRANGE 0 -1`** bade collections pe bad hain — poora structure ek single-threaded blocking call mein serialize hota hai. Use `SSCAN`/`HSCAN`/`ZSCAN` (cursor-based, non-blocking) for Sets/Hashes/ZSets, aur Lists ke liye chunked `LRANGE` (e.g., 0-99, 100-199...) with `LLEN` check pehle.

### 2. LPUSH/LPOP Busy-Polling Instead of BRPOP

```python
# ❌ BAD — busy polling, wastes CPU + Redis round-trips
while True:
    job = r.lpop("queue:jobs")
    if job:
        process(job)
    else:
        time.sleep(0.1)   # polling delay

# ✅ GOOD — blocking pop, no wasted round-trips
job = r.blpop("queue:jobs", timeout=5)   # blocks server-side until item or timeout
```
Busy-polling har 100ms Redis ko hit karta hai chahe queue empty ho — thousands of idle consumers = wasted connections + CPU. `BLPOP`/`BRPOP` Redis server-side block karte hain aur item aate hi turant return karte hain — zero-latency, zero-waste.

### 3. Hash Field Count Silently Crossing `hash-max-listpack-entries`

```bash
CONFIG GET hash-max-listpack-entries    # default 128
HSET bigobj f1 v1 f2 v2 ... f200 v200   # 200 fields
OBJECT ENCODING bigobj                   # → "hashtable" (silently converted!)
```
Koi error/warning nahi aata — Hash chup-chaap listpack se hashtable mein convert ho jaati hai. Memory profile change hota hai (hashtable = more overhead per field due to hash bucket pointers). Agar tumhare objects consistently 128+ fields rakhte hain, ya to threshold tune karo (`CONFIG SET hash-max-listpack-entries 256`) soch-samajh ke, ya schema design revisit karo (kya wo fields alag Hash mein split ho sakte hain).

### 4. Unbounded ZRANGEBYSCORE on Huge Sorted Sets

```bash
ZRANGEBYSCORE huge:zset -inf +inf        # ❌ returns EVERYTHING — O(log n + m) where m = result size
```
`ZRANGEBYSCORE` complexity `O(log(N) + M)` hai jahan M = returned elements. Agar range unbounded/wide hai aur ZSet mein millions of members hain, M bhi millions ho sakta hai → poora result ek response mein, network + memory spike. Fix: `LIMIT offset count` use karo pagination ke liye:
```bash
ZRANGEBYSCORE huge:zset -inf +inf LIMIT 0 100    # ✅ only first 100
```

### 5. Using Hash for Data That Needs Per-Field Expiry (Pre-7.4)

Redis < 7.4 mein Hash fields ki apni TTL nahi hoti — sirf poori key expire ho sakti hai. Agar tumhe per-field expiry chahiye (e.g., OTP field ek Hash ke andar) purane Redis pe, to ya to alag String key banao TTL ke saath, ya Redis 7.4+ pe upgrade karke `HEXPIRE` use karo.

### 6. LINDEX/LSET in a Loop on Large Lists

```python
# ❌ O(n) per call × n calls = O(n²)
for i in range(r.llen("biglist")):
    val = r.lindex("biglist", i)
```
List random-access O(n) hai (quicklist traversal). Bade List ko fully iterate karna ho to `LRANGE` (chunked) use karo, `LINDEX` loop nahi — ya better, socho ki List sahi structure hai bhi ya nahi (agar random access chahiye, Hash with numeric field keys ya sorted structure better ho sakta hai).

---

## Interview Q&A

**Q1: List ko queue ke liye kab use karoge, Streams kab?**
A: Simple, disposable, low-durability-requirement background jobs → List + `LPUSH`/`BRPOP` (lightweight, no extra concepts). Jab durability chahiye (crash pe message lost nahi hona chahiye), multiple independent consumer groups chahiye, ya replay/audit chahiye → Streams (`XADD`/`XREADGROUP`/`XACK`/`XCLAIM`). List queue mein koi ACK mechanism nahi hai — consumer crash ho gaya processing ke beech mein to message permanently gone. Reliable pattern chahiye ho List ke saath to `LMOVE` se "processing" list mein move karo pehle, phir process karo, phir remove karo.

**Q2: Hash use karne ka memory benefit kya hai vs multiple String keys?**
A: Do cheezein: (1) Round-trips — `HGETALL` ek call mein saara object deta hai vs N `GET` calls for N fields. (2) Memory — chhoti Hash listpack encoding use karti hai (contiguous block, no per-field key metadata), jabki N separate String keys har ek apna dictionary entry + expiry slot overhead leta hai (~56+ bytes per key just for metadata, data ke alawa). Trade-off: pre-7.4 Hash fields ki apni TTL nahi hoti, poori key ek TTL leti hai.

**Q3: Set algebra commands (SINTER/SUNION/SDIFF) ka real use case do.**
A: Mutual friends: `SINTER friends:A friends:B`. Tag-based filtering: "posts tagged both X and Y" via `SINTER tag:X tag:Y`. Unique daily visitors: `SADD` + `SCARD`. Permissions: user ke roles Set mein, required roles Set mein, `SINTER` se check karo overlap. `SINTERSTORE`/`SUNIONSTORE`/`SDIFFSTORE` result ko naye key mein store karte hain reuse/caching ke liye — repeated computation avoid hoti hai.

**Q4: Sorted Set internally kaise kaam karta hai, aur O(log n) kyun milta hai?**
A: Bada ZSet do structures rakhta hai: hashtable (member → score, O(1) lookup) + skiplist (score-ordered, multi-level linked list). Skiplist mein har level "express lane" hai — top levels se jaldi navigate karke target ke paas pahunch jaate ho, phir lower levels mein fine-grained search. Ye probabilistically balanced structure hai (random level assignment on insert), balanced-tree jitna hi average-case performance deta hai bina complex rebalancing logic ke. Isse insert/delete/range O(log n) milta hai.

**Q5: Leaderboard design karo — kaunsi structure, kaunse commands?**
A: Sorted Set. `ZINCRBY leaderboard score player` — score update atomically (score match jeetne pe increment). `ZREVRANGE leaderboard 0 9 WITHSCORES` — top-10. `ZREVRANK leaderboard player` — user ka current rank UI mein dikhane ke liye. Sab O(log n) — millions of players ke saath bhi fast. Agar "top-10 in last 24h" jaisa time-windowed leaderboard chahiye, alag ZSet per time-bucket rakho ya score mein timestamp-weighting combine karo.

**Q6: ZRANGEBYLEX kab use hota hai, aur iska gotcha kya hai?**
A: Jab members ka lexicographic (alphabetical) range chahiye ho — autocomplete, prefix search. Gotcha: **sirf tab meaningful hai jab saare members ka score same ho** (usually sab ko 0 score do). Agar scores different hain, result undefined hai kyunki ZRANGEBYLEX internally assume karta hai ki elements already score-order mein hain and same-score members lexicographically ordered hain — different scores ke saath ye guarantee toot jaati hai.

**Q7: Hash-max-listpack-entries threshold cross karne pe kya hota hai, aur iska practical impact?**
A: Silently, koi warning ke bina, Hash **listpack → hashtable** encoding mein convert ho jaati hai (aur wapas listpack mein convert nahi hoti even after fields delete). Practical impact: memory per field badh jaata hai (hashtable bucket overhead vs contiguous listpack), lekin O(1) field access milta hai (vs listpack ka O(n) scan for large listpacks). Agar consistently large objects Hash mein store kar rahe ho, threshold tuning ya schema redesign consider karo.

**Q8: List, Set, Sorted Set mein se ek "recent N items" (e.g., last 100 activity log entries) ke liye kya use karoge?**
A: List + `LPUSH` + `LTRIM`. Har naya item `LPUSH` se front mein add karo, phir `LTRIM key 0 99` se list ko 100 items tak capped rakho — O(1) amortized, bounded memory automatically. Sorted Set bhi kaam karega (score = timestamp, `ZREMRANGEBYRANK` for capping) agar range queries by time bhi chahiye, lekin simple recent-N ke liye List simpler aur cheaper hai.

---

## Real-World Use Cases

### 1. Reliable Job Queue (List + LMOVE)

```python
# Producer
r.lpush("queue:emails", json.dumps({"to": "user@x.com", "template": "welcome"}))

# Consumer — atomic move to processing list before working on it
job = r.lmove("queue:emails", "queue:emails:processing", "RIGHT", "LEFT")
if job:
    try:
        send_email(json.loads(job))
        r.lrem("queue:emails:processing", 1, job)   # remove only after success
    except Exception:
        pass  # left in processing list — a watchdog can requeue after timeout
```

### 2. User Profile as Hash (Object Storage)

```python
r.hset(f"user:{user_id}", mapping={
    "name": "Alice", "email": "alice@x.com", "plan": "premium", "last_login": ts
})
profile = r.hgetall(f"user:{user_id}")     # single round-trip
r.hincrby(f"user:{user_id}", "login_count", 1)   # atomic field increment
```

### 3. Tag-Based Content Discovery (Sets)

```python
r.sadd("tag:python", "article:1", "article:5", "article:9")
r.sadd("tag:redis", "article:5", "article:9", "article:12")
both = r.sinter("tag:python", "tag:redis")   # articles tagged with both
```

### 4. Real-Time Leaderboard (Sorted Set)

```python
r.zincrby("leaderboard:season1", 25, f"player:{player_id}")
top10 = r.zrevrange("leaderboard:season1", 0, 9, withscores=True)
my_rank = r.zrevrank("leaderboard:season1", f"player:{player_id}")
```

### 5. Sliding-Window Rate Limiter (Sorted Set)

```python
now = time.time()
key = f"ratelimit:{user_id}"
r.zadd(key, {str(now): now})
r.zremrangebyscore(key, 0, now - 60)     # drop entries older than 60s window
count = r.zcard(key)
if count > 100:
    raise RateLimitExceeded()
r.expire(key, 60)
```

---

## References

- [Redis Data Types](https://redis.io/docs/data-types/)
- [Redis Lists](https://redis.io/docs/data-types/lists/)
- [Redis Hashes](https://redis.io/docs/data-types/hashes/)
- [Redis Sets](https://redis.io/docs/data-types/sets/)
- [Redis Sorted Sets](https://redis.io/docs/data-types/sorted-sets/)
- [SORT command](https://redis.io/commands/sort/)
- [Hash Field Expiration (HEXPIRE)](https://redis.io/docs/latest/commands/hexpire/)
- `theory/01_basics_installation_cli.md` — Q5 (internal encoding basics)
- `theory/05_streams_consumer_groups.md` — durable queue alternative to Lists
- `theory/03_geo_hyperloglog_json.md` — HyperLogLog for massive-scale unique counting
- "Redis in Action" — Data structures chapters
