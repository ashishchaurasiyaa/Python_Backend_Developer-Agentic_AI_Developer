# Distributed Locks & Redlock

## Why It Matters

Multiple processes/servers competing for the same resource (cron job, inventory decrement, payment processing) — need mutual exclusion **across machines**, not just across threads. `08_lua_scripting.md` already covers the single-instance lock (`SET NX PX` + token-compare Lua unlock). That's fine when one Redis instance is your source of truth. But:
- **Sentinel failover** → lock state can vanish (async replication)
- **Single point of failure** → that one Redis node down = no locking at all

Redlock = Antirez's proposed algorithm to get locking that survives a single node dying, using N independent Redis masters instead of one.

Senior interview: "Why not just use one Redis instance for locking?" → failover + replication lag = correctness bug. "Is Redlock safe?" → this is a **known controversy** (Kleppmann vs Antirez, 2016) — interviewers use it to test if you understand distributed-systems tradeoffs, not just API syntax. Answering "yes it's totally safe" or "no it's totally useless" both signal shallow understanding. The right answer is "it depends what you're protecting."

---

## Core Concepts

### 1. Single-Instance Lock Recap (foundation)

Already covered in `08_lua_scripting.md` → Atomic Patterns → Distributed Lock. Quick recap because everything below builds on it:

```lua
-- Acquire (atomic — SET handles NX + TTL in one command)
SET lock:resource unique_token NX PX 30000
```

```lua
-- Release — MUST be Lua, MUST compare token first
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
```

**Why compare-then-delete, not bare `DEL`:** if the critical section takes longer than the TTL, the lock auto-expires and a second client can acquire it. If the first (slow) client then does a bare `DEL` when it finally finishes, it deletes the **second client's** lock — not its own. Two clients now believe they hold zero and one lock respectively, but there's no lock at all protecting the resource anymore, and a third client can walk right in. The token (unique per acquirer, e.g. `secrets.token_hex(16)`) is what lets release code tell "is this still mine?" — GET+compare+DEL must be atomic (Lua) because a bare GET-then-DEL from application code has the same race in miniature (another client could acquire between your GET and your DEL).

This single-instance pattern is the **building block** — Redlock is "do this same acquire/release dance against N independent masters and require a majority."

### 2. Why Single-Instance Isn't Enough

Scenario with Redis Sentinel (or any master-replica setup with auto-failover):

```
1. Client A: SET lock:x token_A NX PX 10000  → master (succeeds)
2. Master crashes BEFORE replicating this key to the replica
   (Redis replication is async — SET returns to client before replica ack)
3. Sentinel promotes replica → new master (doesn't have lock:x!)
4. Client B: SET lock:x token_B NX PX 10000  → new master (succeeds — key doesn't exist there)
5. Now A and B both believe they hold the lock. Mutual exclusion broken.
```

This isn't a bug you can config your way out of — it's inherent to async replication + failover. Sync replication (`WAIT`) narrows the window but adds latency and still isn't bulletproof (WAIT can time out and the failover proceeds anyway depending on config). This is the motivating problem Redlock tries to solve: don't depend on ONE instance's fate (crash, failover, network partition) determining lock correctness.

### 3. The Redlock Algorithm

Setup: **N independent Redis masters** (Antirez's paper uses N=5), deployed on separate machines/failure domains, **no replication between them** — they're not a cluster, not sentinel-managed, just N unrelated standalone Redis processes. This independence is the whole point: they shouldn't fail together.

To acquire lock `resource` with TTL `T`:

```
1. Record start time (t1)
2. Try SET resource unique_token NX PX T on ALL N instances,
   one after another, using a small connection/response timeout
   per instance (much smaller than T — e.g. T/10) so a down
   instance doesn't block the whole acquire attempt
3. Record end time (t2). elapsed = t2 - t1
4. Lock is considered ACQUIRED only if:
   a) Client got a "yes" from >= N/2 + 1 instances (majority quorum), AND
   b) elapsed < T (with a safety margin — Antirez suggests
      subtracting elapsed AND a clock-drift factor from the
      effective remaining validity time)
5. If acquired: effective lock validity = T - elapsed - drift_margin
6. If NOT acquired (failed quorum, or took too long): immediately
   send release (DEL, via the token-compare script) to ALL N
   instances — even ones that said no (idempotent, harmless) —
   so you don't leave partial locks lying around, then retry
   after random backoff.
```

**Why majority (N/2+1), not all N:** tolerates up to `floor(N/2)` instances being down/unreachable and still makes progress — same quorum reasoning as Raft/Paxos. Two clients cannot both get a majority of the *same* N instances simultaneously (pigeonhole — two disjoint majorities can't both exist among N nodes).

**Why the time budget check matters:** if acquiring the majority took so long that you're already close to TTL, the lock might expire on the instances you got first before you even finish — effective safety margin evaporates. Redlock explicitly re-derives "how much time do I actually have left" as `T - elapsed`, not just `T`.

**Clock-drift assumption:** Redlock's safety argument assumes each Redis instance's local clock advances at roughly the same rate as real time — no instance's clock jumps forward or backward by more than some small `drift` amount. This is a *timing* assumption (bounded clock drift, bounded network delay), not a pure asynchronous-network assumption. That distinction is exactly what the Kleppmann critique (below) attacks.

### 4. The Kleppmann Critique (2016)

Martin Kleppmann ("How to do distributed locking", Feb 2016) argued Redlock is **neither fish nor fowl** — too weak for a real correctness guarantee, more complex than needed if you only want an efficiency lock. Two separate arguments:

**a) The timing/GC-pause argument (attacks the algorithm's own safety proof):**
Redlock's safety relies on bounded clock drift and bounded delays. But a client can experience an arbitrary pause AFTER acquiring the lock and BEFORE using the resource — e.g. a stop-the-world GC pause, a VM live-migration freeze, OS scheduling starvation, or even just slow disk I/O. During that pause the lock's TTL can expire on the Redis side (the Redis instances are fine, up, ticking correctly — only the *client* was paused), a second client acquires the lock, does its work, and then the FIRST client wakes up from its pause still believing it holds the lock and proceeds to touch the shared resource too. Both think they have exclusive access. This isn't a Redlock-specific bug — it affects any lease-based lock with a TTL — but Redlock's added complexity (5 instances, clock-drift math) doesn't fix it, so Kleppmann's point is you're paying algorithmic complexity for a guarantee you don't actually get.

**b) The fencing-token argument (the more fundamental one):**
Even without any pause, "correctly acquired lock" alone doesn't prevent the interleaving above, because Redis's lock doesn't hand out a **monotonically increasing fencing token** that the *protected resource itself* can validate. The correct pattern (used by ZooKeeper, etcd, Chubby-style systems):
```
1. Lock service hands out lock + a token that strictly increases
   each time the lock is granted (33, 34, 35, ...)
2. Client sends token along with every write to the storage/resource
3. Storage service rejects any write whose token is <= the highest
   token it has already seen
```
This way, even if client A pauses and wakes up late, its write carries an old token (e.g. 33) which gets rejected because the storage already saw token 34 from client B. **The safety guarantee lives in the resource, not the lock.** Redis (plain SET NX or Redlock) has no way to atomically hand out such a fencing token that's meaningful to an external, unrelated resource — it's just a mutex, not a fencing-token authority. Kleppmann's conclusion: if you need this level of correctness, use a system explicitly designed for it (ZooKeeper/etcd with proper lease + fencing APIs), not Redis.

### 5. Antirez's Response

Antirez (Redis's creator) [replied in detail](http://antirez.com/news/101), broadly arguing:
- Kleppmann's GC-pause argument applies to **any** lock service with time-bound leases, not uniquely to Redlock — even ZooKeeper sessions can be invalidated by a client pause, and you'd still need fencing tokens on top of ZooKeeper too for full protection.
- For most real use cases, the lock is an **efficiency mechanism** ("try not to do the same expensive work twice"), not the sole correctness guarantee for an irreplaceable resource — in that context Redlock's guarantees (much stronger than a single Redis instance, much cheaper than standing up ZooKeeper) are a reasonable engineering tradeoff.
- If you truly need airtight correctness, add fencing tokens on top regardless of which lock service you use.

**Frame this as "context matters," not a winner.** Kleppmann is correct that Redlock alone does not give you the formal safety property he's evaluating it against (linearizable mutual exclusion under arbitrary pauses). Antirez is correct that for the majority of practical "avoid duplicate work" use cases, that formal property was never the requirement. Both are right about different things — a senior answer acknowledges both sides rather than picking a side.

### 6. When Redlock / Redis Locks Are Appropriate vs Not

| Use case | Appropriate? | Why |
|---|---|---|
| "Only one worker should run this cron job" | Yes | Duplicate run = wasted work, not corruption. Worst case: ran twice, idempotent job = no harm. |
| Cache stampede prevention (only one request rebuilds a hot cache key) | Yes | Worst case: rebuilt twice, no correctness issue. |
| Rate limiting coordination across instances | Yes (efficiency-oriented) | |
| Inventory reservation UX during checkout (soft-hold before payment) | Yes, **with a DB-level check backing it up** | Lock avoids showing "in stock" to two buyers simultaneously, but... |
| Preventing double-spend on a financial ledger | **No — not as the sole mechanism** | Needs fencing token validated by the ledger itself, or DB unique-constraint/optimistic-concurrency, or a real consensus system. |
| Distributed transaction coordination for money movement | **No** | Use proper consensus (etcd/ZooKeeper with lease + fencing) or DB-level ACID guarantees (unique constraints, `SELECT ... FOR UPDATE`, compare-and-swap on a version column). |

Rule of thumb: **Redlock protects against wasted duplicate work, not against corruption of an irreplaceable resource.** If a bug in the locking bought you "acquired the lock twice," ask "what's the actual damage?" — if the answer is "some wasted CPU," Redlock is fine; if the answer is "double-charged a customer," it isn't.

### 7. Library Landscape

`redlock-py`, `redlock-rb`, `pottery` (Python), and redis-py itself expose `Redis.lock()` (single-instance, with `blocking_timeout` and token-based release built in) — none of this changes the tradeoffs above. **In interviews, understanding the quorum/timing/fencing-token reasoning matters far more than reciting a library's method signature** — a candidate who can explain *why* Redlock needs a majority and *where* it still falls short is worth more than one who's memorized `redlock.Redlock([...]).lock(...)`.

---

## How It Works Internally

### Quorum Math

With N=5 instances, majority = 3. Two clients can never both get 3-out-of-5 for the same key at the same time: if client A holds 3, at most 2 remain for client B — client B cannot reach 3. This is the same "any two majorities overlap" argument used in Paxos/Raft — Redlock borrows the quorum idea but does NOT get the same formal consistency proof as those systems, because Redis instances don't run a consensus protocol among themselves — each SET NX is an independent, uncoordinated decision, and the "majority" is only assembled client-side, after the fact, from possibly-stale information (no instance knows what any other instance decided).

### Timing Budget

```
lock_validity_ms = TTL_ms - (t2 - t1) - clock_drift_margin_ms
```
If `lock_validity_ms <= 0`, treat the acquisition as failed (release everything, retry) even if you technically got quorum — you have zero time margin, next scheduling hiccup and you're over TTL.

### Why "No Replication Between Instances"

If the 5 instances replicated to each other, a single underlying failure (e.g. shared network partition, shared power event, misconfigured replication cluster) could take out correctness for all of them simultaneously — defeating the purpose of having 5. Independence across failure domains (ideally: different physical hosts, ideally different racks/AZs) is what makes the majority-of-5 more robust than one instance with a replica.

---

## Common Pitfalls

### 1. Bare `DEL` on Unlock

```python
# WRONG
r.delete(f"lock:{resource}")
```
If your TTL already expired and someone else acquired the lock, this deletes **their** lock, not yours. Silent double-critical-section bug — no error, no exception, just two workers both "safely" inside the section. Always compare-then-delete via Lua (see `08_lua_scripting.md`), never a bare `DEL`.

### 2. No TTL At All

```python
# WRONG — SET NX with no PX/EX
r.set(f"lock:{resource}", token, nx=True)
```
If the holder crashes before releasing, the lock is held forever — every future acquirer blocks permanently. Deadlock with no self-healing. TTL is not optional for a lock meant to survive process crashes.

### 3. TTL Too Short for the Critical Section

```python
lock.acquire()  # ttl=2s
do_expensive_work()  # takes 5s
lock.release()
```
Lock expires at 2s while work is still running. A second client acquires at 2s and enters the "protected" section while the first client is still inside it — the exact race the lock was supposed to prevent, self-inflicted by an undersized TTL. Either size TTL generously above the worst-case critical-section duration, or use a **watchdog/auto-extend** pattern (background thread periodically calls the EXTEND script from `08_lua_scripting.md` while work is ongoing) — but note auto-extend doesn't fix the Kleppmann GC-pause problem, since a paused client can't extend anything either.

### 4. Assuming Redlock Gives Correctness Guarantees It Doesn't

Treating "I hold the Redlock" as equivalent to "no other process can possibly touch this resource right now" — it isn't, per the fencing-token gap (Core Concepts #4). If a paused/slow client can resume after expiry and still perform the write, the lock alone never prevented that. For anything where a stale write causes real damage (money, inventory that can go negative and cause a bad ship, safety-critical state), pair the lock with a **fencing token the resource itself checks**, or use a system built for that guarantee.

### 5. Treating 5 Instances on the Same Host/VM/AZ as "Redlock"

Running 5 Redis processes on one box (or one VM, one AZ) gives you almost none of Redlock's fault-tolerance benefit — one host crash takes out all 5 at once, quorum math becomes theater. The independence-of-failure-domains assumption is load-bearing, not decorative.

---

## Interview Q&A

**Q1: Single Redis lock kaafi kyun nahi hai — Redlock kyun chahiye?**
A: Single instance ka lock state Sentinel failover survive nahi karta — replication async hai, so agar master crash ho jaaye lock key replicate hone se pehle, naya master us key ko jaanta hi nahi, aur doosra client wahi lock le sakta hai. Redlock is problem ko address karta hai N independent masters pe majority-based acquire se — ek instance down/failover ho bhi jaaye, majority phir bhi doosre instances se mil sakta hai.

**Q2: Redlock algorithm ka core logic samjhao.**
A: N (typically 5) independent Redis masters — koi replication nahi beech mein. Client same key+token pe SET NX PX try karta hai sabhi N pe, ek chhote per-instance timeout ke saath. Agar majority (N/2+1) se "yes" mila AND total time liya elapsed < TTL (safety margin ke saath), tab lock acquired maana jaata hai — effective validity = TTL - elapsed - clock_drift. Fail hone pe jo bhi acquire hua tha wo turant release karke retry karo random backoff ke saath.

**Q3: Redlock "unsafe" hai — ye controversy kya hai?**
A: Martin Kleppmann (2016) ne do arguments diye: (1) Redlock client-side pause (GC pause, VM freeze) se safe nahi hai — lock TTL expire ho sakta hai jab tak client paused tha, aur wake hone ke baad wo purana client abhi bhi lock hold karne ka galat vishwas karke resource touch kar sakta hai. (2) Zyada fundamental — Redlock fencing token nahi deta jo resource khud validate kar sake, is liye "correctly acquired lock" bhi ek paused-then-resumed client ko galat write karne se nahi rok sakta. Antirez ne jawab diya ki ye issue kisi bhi lease-based lock (ZooKeeper included) mein hota hai, aur zyadatar use cases mein lock sirf efficiency optimization hai, correctness guarantee nahi — dono points apni jagah sahi hain, context pe depend karta hai.

**Q4: Fencing token kya hai aur ye gap kaise fix karta hai?**
A: Fencing token ek monotonically increasing number hai jo lock service har naye acquire pe deta hai (33, 34, 35...). Client har write ke saath ye token resource/storage service ko bhejta hai, aur resource khud purane (chhote) token wale writes reject kar deta hai. Isse agar ek paused client purane token (33) ke saath late write bhejta hai jabki resource already 34 dekh chuka hai, wo write reject ho jaata hai — safety guarantee lock mein nahi, resource mein hoti hai. Redis (Redlock included) ye capability nately provide nahi karta.

**Q5: Kab Redlock use karna theek hai, kab nahi?**
A: Efficiency locks ke liye theek hai — jaise ek hi scheduler instance job run kare (duplicate = wasted work, harm nahi), cache stampede rokna, rate-limit coordination. Sole safety mechanism ke roop mein NAHI use karna chahiye jahan corruption ka risk ho — jaise financial ledger double-spend prevention. Uske liye fencing token (resource-validated), ya proper consensus system (etcd/ZooKeeper with lease + fencing API), ya DB-level constraints (unique constraint, optimistic concurrency) use karo.

**Q6: Unlock ke liye bare DEL kyun galat hai?**
A: Agar tumhara TTL expire ho gaya kaam khatam hone se pehle, koi aur client wahi lock acquire kar sakta hai. Jab tumhara original client finally finish karke bare DEL karega, wo apna lock nahi — doosre client ka valid lock delete kar dega. Correct approach: Lua script jo pehle GET karke token compare kare, tabhi DEL kare (`08_lua_scripting.md` ka release script). Ye atomic hona zaroori hai warna GET-then-DEL ke beech mein bhi wahi race ho sakta hai.

---

## Real-World Use Cases

### 1. Distributed Cron / Scheduler

Fleet of N app servers, each running the same cron schedule internally, but only ONE should actually execute a given job at its scheduled time (e.g. "send daily digest emails" — running it 3x would spam users 3x). Each instance tries `SET lock:cron:daily_digest token NX PX <job_duration_estimate>` (or full Redlock across 5 instances if a single Redis node is an unacceptable SPOF for this). Whoever wins runs the job; TTL sized above expected job duration; losers just skip this run. Duplicate-run risk if TTL is undersized is low-consequence here (idempotent job, or at worst a duplicate email) — a textbook efficiency-lock use case.

### 2. Inventory Reservation Lock During Checkout

`SET lock:inventory:sku_123 token NX PX 5000` while checking "is this SKU still in stock" and creating a soft-hold, so two concurrent checkouts don't both see "1 in stock" and both proceed. This is fine as a UX-smoothing mechanism (avoid an obvious race in the common case) — but the **actual stock decrement must be backed by a DB-level atomic check** (e.g. `UPDATE inventory SET qty = qty - 1 WHERE sku = ? AND qty > 0`, checking rows-affected) or a fencing token validated at the DB layer, because the lock alone cannot guarantee a paused checkout process won't still commit a stale decrement after its lock expired. Money-adjacent logic never trusts the lock as the final word.

### 3. Leader Election for a Singleton Worker

A pool of worker processes where exactly one should be "active" at a time (e.g. driving a state machine, polling an upstream API with a rate limit that can't be split across workers) — the active worker holds the lock and renews it periodically (extend script); if it crashes, TTL expiry lets another worker take over within one TTL window. Same efficiency-lock reasoning as cron: worst case of a brief double-active window is wasted API calls, not data corruption.

---

## References

- [Distributed Locks with Redis (official Redlock spec)](https://redis.io/docs/manual/patterns/distributed-locks/)
- Martin Kleppmann — ["How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) (2016)
- Antirez — ["Is Redlock safe?"](http://antirez.com/news/101) — response to Kleppmann
- `theory/08_lua_scripting.md` — single-instance lock (`SET NX PX` + token-compare release script), the building block Redlock extends
- `theory/07_sentinel_ha.md` — failover mechanics that motivate Redlock (async replication + promotion window)
