# Azure Cosmos DB — for the MongoDB-Experienced Candidate

> **Interview angle:** JD me "Cosmos DB" likha hai, tumne kabhi use nahi kiya —
> yeh lesson tumhe fake experience nahi deta, **honest pivot** deta hai:
> "MongoDB production me chalaya hai, Cosmos ke concepts 1:1 map hote hain,
> yeh raha mapping." Interviewer ko yehi chahiye hota hai.

## Why It Matters

Azure Cosmos DB = Microsoft ka globally-distributed, multi-model NoSQL
database. Azure-heavy JDs (GenAI/backend roles) me almost hamesha appear
hota hai kyunki Azure OpenAI + Cosmos DB ek standard pairing hai (chat
history, agent state, vector search in vCore).

Tumhare liye critical baat: **Cosmos DB me ek MongoDB wire-protocol API
hai** — tumhara pymongo/Motor code, connection string change karke, Cosmos
ke against chal jaata hai. Iska matlab tumhara saara MongoDB knowledge
(is directory ke lessons 01-09) directly transfer hota hai. Interview me
yeh transfer explicitly dikhana hi strategy hai.

| MongoDB concept (tumhe aata hai) | Cosmos DB equivalent | Lesson cross-ref |
|---|---|---|
| Shard key | Partition key | `04_sharding_aggregation_advanced.md` |
| mongos + shards + chunks | Logical/physical partitions (fully managed) | `04_...` |
| Read/write concerns, read preference | 5 consistency levels (account-level) | `06_replication_read_preferences.md` |
| Change streams (oplog tail) | Change feed (persisted log) | `07_change_streams.md`, `../practical/07_change_streams.py` |
| WiredTiger + you manage ops | ARS engine + fully managed, SLA-backed | — |
| Query planner + explain() | RU charge per operation | this lesson |

Honest-gap context: yeh topic repo me isliye hai kyunki live Azure JD isko
naam se maangti hai —
`Agentic_AI/Interview_Prep/05_genai_developer_azure_role_prep.md` isko
"true gap — don't claim it" flag karta hai. Claim mat karo; map karo.

---

## 1. Positioning — Multi-Model, One Engine, Five APIs

Cosmos DB internally ek hi storage engine use karta hai (**ARS —
atom-record-sequence**). Uske upar alag-alag **wire-protocol APIs** exposed
hain — API tum account create karte time choose karte ho, baad me change
nahi hota:

| API | What it speaks | When you'd pick it |
|---|---|---|
| **NoSQL (Core / SQL)** | Cosmos-native, SQL-like query over JSON | New apps, first-class features land here first |
| **MongoDB** | MongoDB wire protocol (pymongo/Motor/mongoose work) | Migrating a MongoDB app, reuse Mongo skills/tooling |
| **Cassandra** | CQL wire protocol | Migrating Cassandra workloads |
| **Gremlin** | Graph traversal (TinkerPop) | Graph use cases |
| **Table** | Azure Table Storage API | Upgrading old Table Storage apps |

(Ek aur offering hai — *Cosmos DB for PostgreSQL* — but woh Citus-based
distributed Postgres hai, alag beast, is engine family ka part nahi.)

**Key positioning claims (SLA-backed, interview me quote-able):**
- Single-digit-millisecond p99 latency for point reads/writes in-region
- 99.999% read/write availability with multi-region writes
- Turnkey global distribution — portal me region add karo, done
- Elastic, per-operation-metered throughput (RU model, next section)

**MongoDB API ke andar bhi 2 flavors hain — interview me confuse mat hona:**

| | **RU-based** (classic) | **vCore** (newer, 2023+) |
|---|---|---|
| Billing | Request Units (RU/s) | Provisioned vCores/RAM (like Atlas tiers) |
| Compatibility | Partial — extension of Cosmos engine | Much closer to real MongoDB |
| Wire versions | Up to 4.2 | 5.0/6.0/7.0+ |
| Vector search | No | Yes (Azure GenAI pairing ka reason) |
| Best for | Spiky, partition-friendly workloads | Lift-and-shift MongoDB apps, AI workloads |

> **Senior Tip:** Agar interviewer bole "we use Cosmos DB Mongo API" —
> pehla clarifying question poochho: **"RU-based ya vCore?"** Yeh ek
> question hi signal de deta hai ki tum landscape samajhte ho, bina
> hands-on claim kiye.

---

## 2. RU/s Pricing Model — Cosmos ka Sabse Alag Concept

MongoDB me tum instance size/IOPS provision karte ho. Cosmos me tum
**Request Units per second (RU/s)** provision karte ho — ek normalized
currency jo CPU + memory + IOPS ko abstract karti hai.

### Baseline costs (yaad rakhne layak)

```
1 RU     = point read of a 1KB item by id + partition key
~5 RU    = write of a 1KB item
Queries  = variable — depends on index usage, result size, cross-partition fan-out
```

Har operation ka exact RU charge response me milta hai (Mongo API me
`getLastRequestStatistics` command se). RU charge = Cosmos ka `explain()`
equivalent — high RU charge means bad index/partition usage.

### Teen capacity modes

| Mode | How it works | When |
|---|---|---|
| **Provisioned (manual)** | Fixed RU/s, billed hourly whether used or not | Steady, predictable traffic |
| **Autoscale** | Set max RU/s; instantly scales in 10%–100% band of max; billed at ~1.5x unit rate on the hour's peak | Spiky but frequent traffic |
| **Serverless** | Pay per million RUs consumed, zero idle cost, lower per-container ceilings | Dev/test, infrequent traffic |

- Throughput assign hota hai **container (collection) level** pe ya
  **database level** pe (shared across collections — noisy neighbour risk).
- Minimum provisioned: 400 RU/s.

### Throttling — 429 / error 16500

RU budget cross kiya → request reject with **HTTP 429 (TooManyRequests)** +
`retry-after` hint. **MongoDB API me yeh error code `16500` ke roop me
aata hai** — yeh Cosmos-Mongo ka sabse famous production error hai.
SDKs kuch retries khud karte hain; sustained overload me app-level
backoff chahiye (`../practical/09_cosmos_db_emulator.py` me retry decorator
hai).

> **Senior Tip:** RU model ka real-world sting: **provisioned RU/s
> physical partitions me evenly split hota hai.** 10,000 RU/s + 10
> physical partitions = har partition ko sirf 1,000 RU/s. Ek hot
> partition 1,000 pe hi throttle karega jabki baaki 9 idle hain — bill
> 10k ka, capacity effectively 1k. Yehi hot-shard problem hai jo tum
> MongoDB me jaante ho, bas billing ke saath fused.

---

## 3. Partition Keys — Tumhara Shard-Key Knowledge, Renamed

`04_sharding_aggregation_advanced.md` ka shard-key section dobara padh lo —
Cosmos partition key design **wahi problem** hai. Mapping:

```
MongoDB                          Cosmos DB
───────                          ─────────
shard key                    →   partition key (path, e.g. /userId)
chunk                        →   logical partition (all items sharing one PK value)
shard (replica set)          →   physical partition (managed, invisible)
balancer moves chunks        →   Cosmos splits/moves partitions automatically
targeted vs scatter-gather   →   in-partition vs cross-partition query
```

### Hard limits (numbers interviewer expect karta hai)

- **Logical partition: max 20GB** — ek PK value ke saare items 20GB tak.
  (MongoDB me jumbo chunk warning hoti; yahan hard write failure.)
- **Physical partition: max ~50GB storage, max 10,000 RU/s** — Cosmos
  automatically splits, tumhara control nahi.
- **Partition key is immutable** — container banne ke baad change nahi
  hota. Galat PK = naya container + data migration (change feed se copy).
  MongoDB me bhi shard key resharding painful hai (5.0+ me
  `reshardCollection` aaya), Cosmos me container-copy hi raasta hai.

### Good PK = same 3 rules as good shard key

1. **High cardinality** — thousand+ distinct values
2. **Even distribution of requests AND storage** — no hot key
3. **Appears in your hottest query filters** — warna har query
   cross-partition fan-out (RU charge multiplied by partition count)

### Hot-partition pitfalls — same anti-patterns, new billing pain

| Anti-pattern | MongoDB symptom (lesson 04) | Cosmos symptom |
|---|---|---|
| Monotonic key (`created_at`, ObjectId) | Hot last shard | Ek physical partition 429 karta hai, baaki idle — paying for idle RU |
| Low cardinality (`country`, `status`) | Uneven chunks | Logical partition 20GB hit → **writes fail permanently** for that key |
| Key not in queries | Scatter-gather | Cross-partition query — RU charge × partition count |
| Celebrity/tenant hot key | Hot chunk | That tenant throttles; others unaffected but you overpay |

### Cosmos-specific fixes

```
Synthetic key:        pk = f"{tenant_id}_{bucket}"  (bucket = hash(id) % 10)
                      → spreads a hot tenant over 10 logical partitions
                      → read side: query all 10 buckets (fan-out tradeoff)

Hierarchical PK:      up to 3 levels, e.g. /tenantId /userId /sessionId
(subpartitioning)     → per-tenant data can exceed 20GB; prefix queries
                        still route efficiently (compound shard key vibes)
```

MongoDB API note: `shardCollection` command hi partition key set karta
hai — `sh.shardCollection("db.coll", {user_id: 1})` Cosmos me
`/user_id` partition key ban jaata hai. Tumhara mental model unchanged.

---

## 4. Consistency Levels — 5 Levels vs MongoDB Concerns

MongoDB me consistency tum **per-operation** tune karte ho (readConcern /
writeConcern / readPreference — lesson 06). Cosmos me ek **account-level
default** hota hai, 5 well-defined levels ka spectrum, jo per-request
sirf **weaken** kar sakte ho (strengthen nahi):

```
Strong ──── Bounded Staleness ──── Session ──── Consistent Prefix ──── Eventual
◄── stronger consistency, higher latency/RU        weaker, faster, cheaper ──►
```

| Level | Guarantee | MongoDB nearest-equivalent |
|---|---|---|
| **Strong** | Linearizable — read always latest committed write | `writeConcern: majority` + `readConcern: linearizable` |
| **Bounded Staleness** | Lag bounded by K versions **or** T seconds — whichever hits first | No direct equivalent (secondary read with bounded lag monitoring) |
| **Session** (default) | Read-your-own-writes within a session token | Causal consistency sessions (Mongo 3.6+), majority w + primary read |
| **Consistent Prefix** | Reads never see writes out of order | Reading from a secondary (oplog order preserved) |
| **Eventual** | No ordering guarantee, converges | `readPreference: secondary` + `readConcern: local`, lagging secondary |

**Interview-grade nuances:**
- **Session is the default and the right answer 90% of the time** — user
  apna hi likha data turant dekh leta hai, cross-user me thodi staleness
  acceptable. Exactly the property most apps actually need.
- **Strong + multi-region = latency tax** — writes majority-commit across
  regions. Historically strong was single-region-write only; the point to
  make in interview: "global strong consistency physics se ladti hai."
- Consistency level **RU cost bhi affect karta hai** — e.g. strong/bounded
  reads cost roughly 2x eventual-tier reads (quorum reads).
- MongoDB API me client jo readConcern bhejta hai woh account default pe
  map hota hai — Mongo driver settings se Cosmos ke guarantees override
  **nahi** hote. Gotcha section me dobara aayega.

> **Interview Angle:** "MongoDB me tumne consistency kaise handle ki?"
> ka jawab lesson 06 se do (w:majority + readPreference tradeoffs), phir
> khud bridge karo: "Cosmos isko 5 named levels me formalize karta hai —
> mera default choice Session hota, kyunki woh causal-consistency
> sessions jaisa hai jo maine MongoDB me use kiya."

---

## 5. Global Distribution & Multi-Region Writes

MongoDB me global distribution = tum khud replica set members ko regions
me place karte ho, ya Atlas Global Clusters use karte ho. Cosmos me yeh
**turnkey** hai:

- Portal/CLI me region add karo → Cosmos data replicate + route karta hai
- **Single-region write** (default): ek write region, N read regions.
  Reads nearest region se (read preference `nearest` jaisa feel).
- **Multi-region write** (multi-master): har region write accept karta
  hai → 99.999% write availability, low write latency everywhere,
  **lekin ab conflicts possible hain.**

### Conflict resolution (multi-region writes)

| Policy | How |
|---|---|
| **Last-Writer-Wins** (default) | Highest `_ts` (ya custom numeric path) jeetta hai — silent data loss possible for concurrent writes |
| **Custom (merge procedure)** | Stored procedure decides (NoSQL API only) |
| **Conflict feed** | Unresolved conflicts ek feed me land karte hain, app manually resolve karti hai |

MongoDB comparison: replica set me conflicts **ho hi nahi sakte** — single
primary hi likhta hai; failover pe rollback files banti hain. Cosmos
multi-master deliberately availability chooses karta hai aur conflict
resolution ko explicit policy banata hai. (CAP terms: Cosmos multi-region
write = AP-leaning with tunable consistency; MongoDB replica set = CP-leaning.)

> **Senior Tip:** Multi-region writes tabhi lo jab genuinely har region se
> low-latency **writes** chahiye. Sirf global **reads** chahiye to
> single-write-region + read regions sasta aur conflict-free hai. Yeh
> exactly wahi discipline hai jo "shard too early mat karo" wali hai
> (lesson 04, section 1).

---

## 6. Change Feed vs MongoDB Change Streams

Tumne change streams deeply cover kiye hain (`07_change_streams.md` +
`../practical/07_change_streams.py` — resume tokens, at-least-once,
ES-sync pattern). Cosmos ka equivalent **change feed** hai — same job
(react to data changes), different mechanics:

| | MongoDB Change Streams | Cosmos DB Change Feed |
|---|---|---|
| **Source** | Oplog tail (live) | Persisted, ordered log per partition |
| **History** | Sirf oplog window tak (token expire ho sakta hai — lesson 07 pitfall 6) | **Full history — beginning se replay kar sakte ho** |
| **Deletes** | ✅ `delete` events milte hain | ❌ Classic mode me sirf inserts + updates ("latest version" mode); delete ke liye soft-delete + TTL pattern. (Newer "all versions and deletes" mode NoSQL API me aaya hai — Mongo API pe assume mat karo) |
| **Ordering** | Cluster-wide timestamp order | Per-partition-key ordering only |
| **Checkpointing** | Resume token (tum persist karte ho) | Lease container (processor library manage karta hai) ya continuation token |
| **Consumption** | Driver `watch()` — push-style cursor | Pull model (SDK), **Azure Functions Cosmos trigger** (serverless push), change feed processor |
| **Fan-out** | Har consumer apna stream + token | Processor library consumers ko partitions distribute karti hai (Kafka consumer group jaisa) |

**The killer difference to say in interviews:** change feed **replayable
log** hai (Kafka-topic jaisa semantics), change streams **live tail**
hain. Isliye Cosmos me "naya downstream consumer add karo aur history se
rebuild karo" trivially possible hai; MongoDB me uske liye tum
initial-sync + stream stitch karte ho (ya Kafka Connect laate ho —
lesson 07 Q4).

**Mongo API pe:** `watch()` chalega (change streams supported), lekin
constrained — deletes emit nahi hote, pipeline stages limited
(`$match`/`$project` subset), pre-images nahi. Delete tracking chahiye to
soft-delete flag + TTL — yeh pattern practical file me dikhaya hai.

Azure GenAI context (JD-relevant): Azure Functions + Cosmos change feed
trigger = standard pattern for "document upsert hua → embedding
regenerate karo → vector index update karo."

---

## 7. Cosmos-for-MongoDB API — Compatibility Gotchas

"Wire-compatible" ≠ "MongoDB". Yeh section hi tumhe un logon se alag
karta hai jo sirf marketing page padh ke aaye hain. RU-based flavor ke
classic gotchas:

### 7.1 `retryWrites` connection-string gotcha
Modern drivers (pymongo 4+, mongoose 6+) default `retryWrites=true`
bhejte hain — classic RU-based Cosmos isko support nahi karta tha →
connect/write errors. Fix: connection string me `retrywrites=false`.
Sabse common "day 1 migration" failure.

### 7.2 Throttling surfaces as error 16500
RU exceed → Mongo error code **16500** (mapped from HTTP 429). Real
MongoDB me yeh error exist hi nahi karta, isliye generic Mongo retry
logic isko handle nahi karta. App-level backoff + `retry-after` respect
karna padta hai.

### 7.3 Sort requires an index — hard fail
Real MongoDB: non-indexed sort = in-memory sort (100MB tak, phir
`allowDiskUse`). Cosmos Mongo RU: non-indexed field pe sort →
**query fails outright**. Migration ke baad "worked locally, fails in
Cosmos" bugs ka classic source. By default sirf `_id` indexed hota hai —
baaki sab explicitly banao (ya wildcard index enable karo).

### 7.4 Unique indexes only on empty collections
Unique index **collection create hone ke turant baad, data insert hone se
pehle** banana padta hai. Populated collection pe unique index add karna
supported nahi (real MongoDB me hota hai). Schema migrations plan
accordingly.

### 7.5 Aggregation pipeline — subset support
`$match`, `$group`, `$sort`, `$project`, `$limit`, `$unwind` etc. work;
lekin `$graphLookup`, `$facet` variants, map-reduce, ilaake ke hisaab se
`$lookup` limitations (esp. across shards) — sab wire version + flavor
dependent. **Rule: migration se pehle har aggregation Cosmos ke against
test karo, docs ke feature matrix pe blind trust mat karo.**

### 7.6 Transactions — narrower scope
RU-based: multi-document transactions sirf **unsharded (single logical
partition)** scope me. Tumhare lesson 05 wale cross-shard transaction
patterns yahan port nahi honge. vCore closer to real Mongo here.

### 7.7 Consistency settings silently remapped
Driver ka `readConcern`/`writeConcern` Cosmos ke **account-level
consistency** pe map hota hai — tumhare per-op Mongo settings actual
guarantees change nahi karte (section 4). Silent behavioral difference,
error nahi aata.

### 7.8 Misc quick hits
- **Capped collections**: not supported
- **TTL**: TTL index supported but semantics/fields flavor-dependent (RU
  classic historically `_ts`-based); test it
- **Change streams**: limited (section 6)
- **Per-op RU visibility**: `db.command({"getLastRequestStatistics": 1})`
  — Cosmos-only extension, yeh tumhara naya `explain()` hai
- **Extension commands**: `customAction: CreateCollection` with
  `shardKey` + `offerThroughput` — collection-level RU set karne ka
  Mongo-API tarika (practical me hai)
- **Port 10255 + TLS mandatory** — connection string format hi alag
  dikhta hai

> **Senior Tip:** In gotchas ka meta-lesson interview me bolo: "Cosmos
> Mongo API ko main 'MongoDB' nahi, 'MongoDB-shaped interface over a
> different engine' treat karunga — migration plan me compatibility test
> suite pehla step hoga, especially aggregations, index creation order,
> aur error-16500 retry handling." Yeh ek sentence hands-on jitna hi
> credible lagta hai.

---

## Common Pitfalls (Recap Table)

| # | Pitfall | Fix |
|---|---|---|
| 1 | Hot partition key → 429s while paying for idle RU | High-cardinality/synthetic/hierarchical PK (section 3) |
| 2 | 20GB logical partition hard limit hit | PK redesign — container copy via change feed |
| 3 | `retryWrites` default breaks connection | `retrywrites=false` in connection string |
| 4 | Treating 16500 as a bug, not backpressure | Exponential backoff + honor retry-after |
| 5 | Non-indexed sort fails post-migration | Create indexes explicitly; test all queries |
| 6 | Unique index on populated collection | Create unique indexes at collection creation |
| 7 | Expecting deletes in change feed | Soft-delete flag + TTL |
| 8 | Multi-region writes "for safety" | Only for multi-region write latency needs; LWW can silently drop conflicting writes |
| 9 | Autoscale assumed cheap | Billed at ~1.5x unit rate on hourly peak — steady load pe manual sasta |
| 10 | Shared database throughput noisy neighbour | Dedicated container throughput for hot collections |

---

## Interview Q&A — the Honest-Pivot Script

Yeh section is lesson ka asli deliverable hai. Goal: kabhi bhi "yes I've
used it" mat bolo; har baar MongoDB depth → Cosmos concept bridge banao.

**Q1: "Have you worked with Cosmos DB?"**
**A (the pivot, practice this):** "Hands-on production experience MongoDB
ki hai, Cosmos DB ki nahi — main woh claim nahi karunga. Lekin Cosmos ka
MongoDB API wire-compatible hai, to mera pymongo/Motor experience directly
apply hota hai, aur core concepts 1:1 map hote hain: shard key ↔ partition
key, read/write concerns ↔ the 5 consistency levels, change streams ↔
change feed. Jo genuinely naya hai woh RU-based throughput model hai — us
pe maine specifically padha hai, including hot-partition throttling aur
RU-split-across-partitions gotcha. Ramp-up days ka hoga, weeks ka nahi."
*(Honest + specific + confident. Interviewer ko exactly yeh chahiye.)*

**Q2: "Cosmos DB me partition key kaise choose karoge?"**
**A:** Same discipline as MongoDB shard key: high cardinality, request +
storage dono ki even distribution, aur hottest queries ke filter me
presence — warna cross-partition fan-out RU multiply karta hai. Cosmos
specifics jo main add karunga: 20GB logical partition hard limit (Mongo
ke jumbo chunks se zyada brutal — writes fail), PK immutability (galat
choice = container copy), aur hot tenant ke liye synthetic bucketed keys
ya hierarchical PK (3 levels).

**Q3: "RU kya hota hai? 429 aane lage to kya karoge?"**
**A:** RU = normalized throughput currency; 1 RU ≈ 1KB point read, write
~5x. 429/16500 = provisioned budget exceeded. Response: (1) SDK/app-level
exponential backoff with retry-after, (2) diagnose — kya ek hot partition
hai? kyunki RU/s physical partitions me evenly split hota hai, overall
utilization low hote hue bhi ek partition throttle kar sakta hai, (3)
query RU charges inspect karo (`getLastRequestStatistics`) — missing
index ya cross-partition query fix karna often RU raise karne se sasta
hai, (4) tab autoscale/raise RU.

**Q4: "Cosmos ke 5 consistency levels batao. Kaunsa default aur kyun?"**
**A:** Strong → Bounded Staleness → Session → Consistent Prefix →
Eventual, strongest-to-weakest. Session default hai — read-your-own-writes
per session token, jo MongoDB ke causal-consistency sessions jaisa hai.
90% apps ke liye sweet spot: user apna likha data turant dekhta hai,
global strong ka latency/RU tax nahi. Strong multi-region me mehenga hai
(cross-region quorum); Eventual sabse sasta/fastest, ordering guarantee
nahi.

**Q5: "MongoDB change streams use kiye hain — Cosmos change feed se kya
different hai?"**
**A:** Change streams = oplog ka live tail; history oplog window tak,
resume token expire ho sakta hai. Change feed = persisted, replayable log
(Kafka-topic semantics) — naya consumer beginning se rebuild kar sakta
hai. Trade-offs: change feed classic mode deletes emit nahi karta
(soft-delete + TTL pattern), ordering sirf per-partition-key hai, aur
checkpointing lease containers se hota hai — usually Azure Functions
trigger ya change feed processor ke through consume karte hain.

**Q6: "Hum MongoDB se Cosmos (Mongo API) pe migrate kar rahe hain — kya
tootega?"**
**A:** Meri checklist: (1) connection string — `retrywrites=false`
classic RU pe, (2) index parity — Cosmos me non-indexed sort fail hota
hai, sirf `_id` default indexed, (3) unique indexes empty collection pe
hi ban sakte hain — migration order matters, (4) aggregation audit —
subset support, har pipeline test karo, (5) error handling — 16500
throttling retry logic add karo, (6) transactions scope — unsharded/
single-partition only on RU-based, (7) change stream consumers — limited
semantics, deletes nahi milenge. Aur pehla architectural question: RU vs
vCore — lift-and-shift ke liye vCore zyada compatible hai.

**Q7: "Multi-region writes enable karna chahiye?"**
**A:** Sirf tab jab multiple regions se **low-latency writes** business
requirement ho. Warna single write region + read regions: conflicts
impossible, sasta. Multi-region writes ke saath conflict policy sochni
padti hai — default LWW concurrent writes silently drop kar sakta hai.
MongoDB background se yeh mujhe unusual lagta hai kyunki replica sets
single-primary hote hain — Cosmos yahan availability ke liye consistency
trade karta hai, aur woh trade explicit hona chahiye.

**Q8: "Serverless vs autoscale vs provisioned kab?"**
**A:** Dev/test ya idle-mostly workloads → serverless (zero idle cost).
Spiky-but-daily traffic → autoscale (peak-hour billing at ~1.5x unit
rate, 10-100% band of max). Flat predictable load → manual provisioned
(cheapest per RU). Red flag jo main dhoondhunga: autoscale on a flat
workload — steady load pe manual se ~1.5x overpay.

---

## References

- Azure Cosmos DB docs — consistency levels, partitioning, RU model
- Cosmos DB for MongoDB — feature support matrix (RU vs vCore) — *read
  this before any migration claim*
- Change feed design patterns (Azure docs)
- `../theory/04_sharding_aggregation_advanced.md` — shard key design (the transferable half)
- `../theory/06_replication_read_preferences.md` — Mongo concerns vs consistency levels
- `../theory/07_change_streams.md` + `../practical/07_change_streams.py` — change streams (feed comparison)
- `../practical/09_cosmos_db_emulator.py` — wire-compat proof with pymongo
- `../../../../Agentic_AI/Interview_Prep/05_genai_developer_azure_role_prep.md` — the JD gap this closes
