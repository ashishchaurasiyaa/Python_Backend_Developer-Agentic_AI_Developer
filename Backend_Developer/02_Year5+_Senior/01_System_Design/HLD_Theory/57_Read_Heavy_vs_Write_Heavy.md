# Read-Heavy vs Write-Heavy Systems — Workload pehchaano, architecture chuno

## WHAT

Kisi bhi system ko design karne se pehle ek number nikaalo: **read:write ratio**. Yeh ratio hi decide karta hai ki kahan optimize karna hai.

- **Read-heavy** = reads >> writes (e.g. 100:1). Log padhte zyada hain, likhte kam. (news site, product catalog, social feed)
- **Write-heavy** = writes heavy/lagataar (e.g. 1:1 ya write-dominant). Data constantly aa raha hai. (logging, IoT sensors, analytics ingestion, chat)

| | Read-Heavy | Write-Heavy |
|---|---|---|
| Bottleneck | Read throughput / latency | Write throughput / disk I/O |
| Best friend | **Caching, replicas** | **Sharding, async, batching** |
| DB choice | RDBMS + read replicas, cache | LSM-tree stores (Cassandra), TSDB |
| Scaling trick | Add read replicas / CDN | Partition writes across shards |
| Examples | News, catalog, blog, feed | Logs, metrics, IoT, chat, clickstream |

---

## READ-HEAVY — Strategies

Goal: read ko **DB tak pahunchne hi mat do**, ya cheap bana do.

```
1. CACHING          → Redis/Memcache. 90%+ reads cache se. (sabse bada lever)
2. READ REPLICAS    → writes primary pe, reads N replicas pe distribute
3. CDN              → static/media edge pe cache (DB tak request aati hi nahi)
4. DENORMALIZATION  → joins mehnge; data pehle se "ready" rakho (HLD_Theory/19)
5. MATERIALIZED VIEW→ precomputed query results
```
**Trade-off:** caching/replicas = **stale data** (eventual consistency) ka risk. Read-heavy me yeh aksar acceptable hota hai (±100 views matter nahi karte).

---

## WRITE-HEAVY — Strategies

Goal: writes ko **fast accept karo**, heavy work baad me/parallel me karo.

```
1. SHARDING         → writes ko kai DB nodes pe baant do (HLD_Theory/38)
2. ASYNC + QUEUE    → write ko Kafka/queue me daal do, turant ack;
                      consumer baad me DB me likhe (write buffering)
3. BATCHING         → 1000 writes ek saath flush karo (per-write overhead kam)
4. LSM-TREE STORES  → Cassandra/RocksDB writes ko sequential append karte hain
                      (random disk writes se bahut fast)
5. WAL              → pehle log me append (sequential), DB update baad me
```
**Trade-off:** async/batching = data thodi der **durable na dikhe**, aur read-your-own-write tricky ho jaata hai.

### Kyun LSM-tree write-heavy ke liye accha?
B-tree (RDBMS) har write pe random disk location update karta hai (slow). LSM-tree writes ko memory me jamaa karke **sequential bulk** me disk pe likhta hai — disk ke liye yeh bahut tez. Isliye Cassandra/ScyllaDB write-heavy ingestion me rule karte hain.

---

## REAL LIFE ANALOGY

**Read-heavy = public library.** Hazaaron log ek hi popular book padhna chahte hain. Solution: us book ki **kai copies** rakho (replicas) aur ek **photocopy summary** counter pe rakho (cache). Likhna (nayi book aana) kabhi-kabhi hota hai.

**Write-heavy = post office sorting center.** Lagataar dher saari chitthiyan aa rahi hain. Tum ek-ek karke process nahi karte — **batch** me sort karte ho, aur kai counters (shards) pe baant dete ho.

---

## WHEN TO USE WHAT

| System | Type | Primary tactic |
|---|---|---|
| News / Blog / Wikipedia | Read-heavy | CDN + cache + replicas |
| E-commerce catalog | Read-heavy | Cache + denormalized read model |
| Social feed | Read-heavy | Fan-out + cache (precompute feed) |
| Application logging | Write-heavy | Async queue + batch + TSDB |
| IoT / sensor data | Write-heavy | Sharding + LSM/time-series DB |
| Chat / messaging | Write-heavy | Sharded by conversation + queue |
| Analytics clickstream | Write-heavy | Kafka ingest + batch to warehouse |

**Mixed?** Bahut systems dono hote hain → **CQRS** (Command Query Responsibility Segregation): write-path aur read-path ko alag-alag optimize karo (write→normalized store, read→denormalized cache/view). Dekho LLD_Theory/Event_Sourcing_CQRS.

---

## Illustrative Code (concept)

```python
# READ-HEAVY: cache-aside — DB ko bachao
def get_product(pid):
    p = redis.get(f"prod:{pid}")
    if p:                      # 90%+ reads yahin se
        return p
    p = db.query(pid)          # cache miss → DB
    redis.setex(f"prod:{pid}", 300, p)   # 5 min cache
    return p

# WRITE-HEAVY: async buffer — turant ack, DB likhna defer
def ingest_event(evt):
    queue.push(evt)            # O(1), turant return
    # alag consumer process batch me DB/warehouse me likhega

def consumer_loop():
    batch = queue.pop_many(1000)   # 1000 ek saath
    db.bulk_insert(batch)          # ek round-trip
```

---

## Connection to Other Topics

- **Caching** (HLD_Theory/13) — read-heavy ka #1 hathiyaar.
- **Database Sharding** (HLD_Theory/38) — write-heavy scaling ka core.
- **Replication** (HLD_Theory/11) — read replicas se read scale.
- **CQRS / Event Sourcing** (LLD_Theory) — read aur write path alag karna.
- **Message Queues** (SD_Theory/05) — write buffering/async ingestion.

---

## Interview Q&A

**Q: System read-heavy hai ya write-heavy — pehle kaise decide karoge?**
A: Read:write ratio estimate karo (back-of-envelope). Feed/catalog/news = read-heavy (cache+replicas). Logs/IoT/metrics/chat = write-heavy (shard+async+batch). Yeh ratio architecture choices drive karta hai.

**Q: Read replicas add karne se kaunsi problem aati hai?**
A: **Replication lag** → replica thoda stale ho sakta hai. "Read-your-own-write" tootta hai (user ne likha, replica se padha, purana dikha). Solution: critical reads primary se, ya session ko primary pe pin karo.

**Q: Write-heavy me RDBMS kab fail karta hai, kya use karein?**
A: Single primary ka write throughput cap ho jaata hai (B-tree random I/O). Tab sharding, ya LSM-tree based stores (Cassandra/ScyllaDB), time-series DB (InfluxDB), ya Kafka-buffered ingestion use karte hain.

**Q: CQRS read/write-heavy me kaise madad karta hai?**
A: Write model aur read model alag — write side normalized + consistent, read side denormalized + cached. Dono ko independently scale aur optimize kar sakte ho.
