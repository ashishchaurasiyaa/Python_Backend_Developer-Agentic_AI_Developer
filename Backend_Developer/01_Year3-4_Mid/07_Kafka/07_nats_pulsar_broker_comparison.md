# 07 — Message Broker Landscape: NATS/JetStream & Apache Pulsar vs Kafka vs RabbitMQ

> Ab tak humne **Kafka** (partitioned append-only log) aur **RabbitMQ** (AMQP smart broker) cover kiya. Yeh lesson do aur major players add karta hai — **NATS/JetStream** aur **Apache Pulsar** — aur ek **decision framework** deta hai: "kab kaunsa broker use karein."

---

## Why This Lesson

Backend interviews aur real system-design mein sirf "Kafka jaanta hoon" kaafi nahi. Senior log poochte hain: *"Tumne Kafka kyun chuna, Pulsar ya NATS kyun nahi?"* — yeh lesson us answer ka backbone hai.

Char broker, char alag philosophy:

| Broker | One-line mental model |
|---|---|
| **Kafka** | Distributed append-only **log**, partition-centric storage. |
| **RabbitMQ** | **Smart broker** (AMQP) — exchanges + complex routing. |
| **Apache Pulsar** | Log + queue **hybrid**, storage compute se decoupled (BookKeeper). |
| **NATS / JetStream** | Ultra-lightweight **messaging fabric**; core = fire-and-forget, JetStream = persistence. |

---

## Recap: Kafka (contrast ke liye)

Kafka ek **distributed commit log** hai. Topic → N **partitions** mein bat-ta hai, har partition ek ordered append-only sequence hai. Storage **partition-centric** hai: har partition ek broker pe physically rehta hai (plus replicas), aur leader hi saare reads/writes handle karta hai. Consumers **consumer groups** mein hote hain — har partition group ke exactly ek consumer ko assign hoti hai, isliye consumer parallelism partition count se **bound** hai. Strength: massive throughput, offset-based **replay**, mature ecosystem (Kafka Streams, Connect). Weakness: ek partition ka data ek broker se tied hai, isliye rebalance/expansion ke time **data movement** hota hai (detail `01_kafka_fundamentals.md` mein).

## Recap: RabbitMQ (contrast ke liye)

RabbitMQ ek **AMQP smart broker** hai. Producer **exchange** ko message bhejta hai, exchange **bindings + routing keys** ke basis pe ek ya zyada **queues** mein route karta hai (direct / topic / fanout / headers). Intelligence broker mein hai — complex routing, per-message TTL, DLX, priority, RPC sab built-in. By default messages consume hone ke baad **delete** ho jate hain (replay nahi, unless Streams feature). Strength: flexible routing, low-latency task queues, mature ops. Weakness: Kafka-level throughput aur long-retention replay native fit nahi (detail `../08_RabbitMQ/theory/01_basics_amqp_exchanges.md`).

---

## Apache Pulsar

Pulsar ko Yahoo ne banaya, ab Apache project hai. Iska killer differentiator: **storage aur serving alag layers hain.**

### Two-layer architecture

```
   Producers / Consumers
          │
          ▼
   ┌──────────────────┐     stateless serving layer
   │  Brokers          │ ←── (koi data local pe store nahi karte)
   │ (no local storage)│
   └────────┬──────────┘
            │ reads/writes
            ▼
   ┌──────────────────┐     durable storage layer
   │  BookKeeper       │ ←── "bookies" = storage nodes
   │  (Bookies)        │     (segments yahan replicate hote hain)
   └──────────────────┘
   ZooKeeper / metadata store cluster ko coordinate karta hai
```

- **Brokers** = stateless serving layer. Producer/consumer connect yahan karte hain, par broker apne paas data store **nahi** karta.
- **Apache BookKeeper** = durable storage layer. Storage nodes ko **bookies** kehte hain. Actual message bytes yahan likhe + replicate hote hain.
- Kyunki dono alag hain → **independently scale** kar sakte ho. Throughput chahiye → brokers badhao. Storage chahiye → bookies badhao. Kafka mein dono ek hi node pe coupled hain.

### Segment-centric vs partition-centric storage

Yeh **sabse important** Pulsar concept hai (interview gold):

- **Kafka = partition-centric.** Ek partition ka pura data ek broker (+replicas) pe rehta hai. Partition badi ho to ek node ka disk limit hit karti hai; rebalance pe data copy hota hai.
- **Pulsar = segment-centric.** Ek topic/partition andar se chhote **segments (ledgers)** mein toot-ta hai, aur har segment alag bookies set pe spread ho sakta hai. Isse ek "partition" kisi single node ke disk se **bandhi nahi** — capacity poore BookKeeper cluster pe distribute hoti hai, aur naye bookie add karna seamless hota hai (broker-side rebalance ke bina).

### Topics + Subscriptions (4 modes)

Pulsar mein consumer **subscription** ke through topic se consume karta hai. Subscription ek **named cursor** hai (kahan tak padha track karta hai). Ek topic pe multiple subscriptions ho sakti hain — har subscription independently message stream consume karti hai.

> **Kafka analogy (par identical NAHI):** Pulsar subscription ≈ Kafka consumer group jaisa lagta hai (dono progress track karte hain, dono multiple readers ke beech load batt-te hain). **Farak:** Kafka mein parallelism partition count se bound hai (1 partition → 1 consumer). Pulsar ki `shared` subscription mein ek partition ko bhi **multiple consumers** consume kar sakte hain (message-level dispatch, round-robin) — yahan ordering chhod do par scaling partition se decouple ho jaati hai. Yeh fundamental difference hai, isliye "subscription = consumer group" bolna technically galat hai.

Char subscription modes:

| Mode | Kitne consumers active | Ordering | Use case |
|---|---|---|---|
| **Exclusive** | Sirf 1 (baaki reject) | Full topic order | Single ordered reader. |
| **Failover** | 1 active + standby(s); active marne pe standby promote | Per-partition order | HA single-consumer (active/standby). |
| **Shared** | N consumers, round-robin message dispatch | **No** ordering guarantee | Queue jaisa work-sharing, max throughput. |
| **Key_Shared** | N consumers, par same **key** hamesha same consumer ko | Per-**key** order | Ordering + scaling dono chahiye (Kafka key-partitioning jaisa, but dynamic). |

`shared` mode Pulsar ko **queue** (RabbitMQ jaisa competing-consumers) bana deta hai; `exclusive`/`failover` use **log** (Kafka jaisa) banate hain. Isiliye Pulsar ko "unified messaging + streaming" bolte hain.

### Tiered storage (S3 offload)

Kyunki storage decoupled hai, Pulsar purane segments ko BookKeeper se **object storage (S3, GCS, Azure Blob)** pe offload kar sakta hai automatically. Topic infinite-retention rakh sakta ho, hot data BookKeeper pe, cold data S3 pe — consumer ko transparent. (Kafka ne yeh "Tiered Storage" feature 3.6+ mein baad mein add kiya.)

### Built-in geo-replication

Pulsar mein **geo-replication first-class** hai. Namespace pe multiple clusters configure karo, Pulsar automatically un regions ke beech messages replicate karega (async ya sync). Kafka mein yeh kaam **MirrorMaker 2** (separate process) se karna padta hai.

### Multi-tenancy (tenants / namespaces)

Pulsar natively **multi-tenant** hai. Hierarchy:

```
persistent://<tenant>/<namespace>/<topic>
persistent://acme-corp/payments/transactions
```

- **Tenant** = top-level isolation unit (ek team / customer / business unit).
- **Namespace** = tenant ke andar policy bucket (retention, quota, geo-rep, auth ek saath set hoti hai).
- Ek hi physical cluster pe kayi teams safely co-exist kar sakti hain — alag auth, quotas, isolation. Kafka mein yeh natively itna strong nahi (ACLs hain par true tenant hierarchy nahi).

### Pulsar Functions

Lightweight **serverless compute** Pulsar ke andar. Chhota function (Python/Java/Go) deploy karo jo ek topic se consume kare, transform/filter/route kare, doosre topic pe produce kare — bina alag stream-processing cluster (Flink/Kafka Streams) ke. Simple ETL / enrichment / routing ke liye perfect.

### Pulsar — Python client (pip install)

```bash
pip install pulsar-client
```

```python
import pulsar

client = pulsar.Client('pulsar://localhost:6650')

# Producer
producer = client.create_producer('persistent://public/default/orders')
producer.send(b'{"order_id": 1, "amount": 100}')

# Consumer — note: subscription_name + subscription type
consumer = client.subscribe(
    'persistent://public/default/orders',
    subscription_name='order-workers',
    consumer_type=pulsar.ConsumerType.Shared,   # Exclusive / Shared / Failover / KeyShared
)

msg = consumer.receive()
print(msg.data())
consumer.acknowledge(msg)        # ack mandatory (Kafka offset-commit jaisa)

client.close()
```

> Note: `pulsar-client` ka default API **synchronous/blocking** hai (internally C++ library wraps karta hai). Async ke liye `send_async` / callback pattern use hota hai. Yeh Kafka ke `aiokafka` jaisa pure-asyncio nahi hai.

---

## NATS / JetStream

NATS ek **ultra-lightweight, high-performance** messaging system hai (single Go binary, ~15MB, milliseconds mein boot). Cloud-native, edge, IoT, aur service-mesh ke liye banaya gaya. Do layers samajhna zaroori hai: **Core NATS** aur **JetStream**.

### Subjects (hierarchical + wildcards)

NATS mein topics ko **subjects** kehte hain. Dot-separated hierarchy + wildcards:

```
orders.us.created
orders.eu.created

orders.*.created     →  '*' = exactly one token  (us, eu, ...)
orders.>             →  '>' = one or more tokens (tail wildcard)
```

Yeh RabbitMQ ke **topic exchange** routing jaisa lagta hai, par NATS mein subject-based routing core mein built hai — koi exchange/binding setup nahi.

### Core NATS

- **At-most-once**, **fire-and-forget** pub/sub. Koi persistence nahi — agar subscriber online nahi to message **gaya** (no storage, no replay). Yeh feature hai, bug nahi: zero overhead, blazing latency (sub-millisecond, millions msg/sec).
- **Request-Reply** built-in: ek temporary reply-subject ke saath request bhejo, responder reply kare. Yeh NATS ko **RPC / service mesh / microservice control-plane** ke liye outstanding banata hai — synchronous-feeling calls async fabric pe.
- Best fit: **service-to-service RPC, edge/IoT telemetry, ephemeral signaling, service discovery** — jahan speed > durability.

### JetStream (persistence layer)

JetStream NATS ke upar **persistence** add karta hai (NATS 2.2+ mein built-in, alag install nahi). Yeh deta hai:

- **Streams** — subjects ko capture karke disk pe store karta hai (retention: limits / interest / work-queue policy).
- **Durable consumers** — server-side cursors jo progress yaad rakhte hain (consumer offline jaake wapas aaye to wahin se resume).
- **At-least-once** delivery (ack + redelivery), aur dedup window ke saath **exactly-once** publish/consume semantics.
- **Replay** — stream se purane messages dobara padho (Kafka offset-replay jaisa).
- **KV store** aur **Object store** — JetStream ke upar bana key-value aur blob storage (config, state, file distribution ke liye handy).

Matlab: Core NATS = speed/ephemeral, JetStream = durability/replay. Ek hi cluster dono de deta hai — isliye NATS "core ko lightweight rakho, persistence opt-in" philosophy follow karta hai.

### NATS — Python client (pip install)

```bash
pip install nats-py
```

```python
import asyncio
import nats

async def main():
    nc = await nats.connect("nats://localhost:4222")

    # --- Core NATS: at-most-once pub/sub ---
    await nc.subscribe("orders.us.created")
    await nc.publish("orders.us.created", b'{"order_id": 1}')

    # --- Core NATS: request-reply (RPC) ---
    reply = await nc.request("service.add", b'{"a":1,"b":2}', timeout=1.0)
    print(reply.data)

    # --- JetStream: durable / persistent ---
    js = nc.jetstream()
    await js.add_stream(name="ORDERS", subjects=["orders.>"])
    await js.publish("orders.eu.created", b'{"order_id": 2}')   # persisted

    sub = await js.pull_subscribe("orders.>", durable="order-workers")
    msgs = await sub.fetch(10)
    for m in msgs:
        print(m.data)
        await m.ack()           # at-least-once: ack required

    await nc.drain()

asyncio.run(main())
```

> `nats-py` pure-asyncio hai (`await nats.connect(...)`, `nc.jetstream()`) — `aiokafka` jaise FastAPI/async backends ke saath natural fit.

---

## The Big Decision Table

| Dimension | **Kafka** | **Pulsar** | **NATS / JetStream** | **RabbitMQ** |
|---|---|---|---|---|
| **Throughput** | Very high (millions/sec) | Very high (Kafka-class) | Core: extreme; JetStream: high | Medium-high |
| **Latency** | Low (ms) | Low (ms) | **Lowest** (sub-ms core) | Low (ms) |
| **Ordering** | Per-partition | Per-partition; per-key (`Key_Shared`) | Per-subject (JetStream stream) | Per-queue |
| **Retention / Replay** | ✓ offset replay; tiered (3.6+) | ✓ replay + **native tiered S3 offload** | JetStream: ✓ replay; Core: ✗ | ✗ (Streams feature: limited) |
| **Storage model** | Partition-centric (coupled) | **Segment-centric (decoupled, BookKeeper)** | File/memory store (JetStream) | In-memory + disk queues |
| **Multi-tenancy** | ACLs only (weak) | **Native (tenant/namespace)** | Accounts (good isolation) | vhosts (basic) |
| **Geo-replication** | MirrorMaker 2 (bolt-on) | **Built-in (native)** | Super-clusters / leaf nodes | Federation / Shovel (bolt-on) |
| **Routing flexibility** | Low (topic+partition) | Medium (subscriptions) | Medium (subject wildcards) | **Highest** (exchanges) |
| **Ops complexity** | High (brokers + KRaft/ZK) | **Highest** (brokers + BookKeeper + ZK/metadata) | **Lowest** (single Go binary) | Medium |
| **Footprint** | Heavy (JVM) | Heavy (JVM + bookies) | **Tiny** (~15MB, edge/IoT) | Medium (Erlang) |
| **Best-fit use case** | Event streaming, CDC, analytics, replay at scale | Streaming + queue **dono**, multi-tenant SaaS, geo-distributed, infinite retention | Microservice RPC, service mesh, edge/IoT, low-latency signaling (+JetStream for durable) | Complex routing, task queues, RPC, per-message control (TTL/DLX/priority) |

---

## Decision Framework — "Kab Kya?"

**Kafka chuno jab:**
- High-throughput event streaming + offset replay chahiye, aur ecosystem (Connect, Streams, Schema Registry) leverage karna hai.
- Team / hiring market mein Kafka expertise already hai (sabse mature, sabse zyada tooling).

**Pulsar chuno jab:**
- Streaming **aur** queueing dono ek system mein chahiye (`shared` + `exclusive` subscriptions).
- True **multi-tenancy** (kayi teams/customers ek cluster pe) ya **native geo-replication** ya **infinite retention with S3 offload** primary requirement hai.
- Storage aur compute ko **independently scale** karna hai (e.g., huge retention, modest throughput — ya ulta).
- Trade-off: operational complexity sabse zyada (broker + BookKeeper + metadata, teeno chalane padte hain).

**NATS / JetStream chuno jab:**
- **Low-latency service-to-service** communication, **request-reply RPC**, service mesh, ya **edge/IoT** — jahan lightweight footprint aur speed critical hain.
- Ops simplicity chahiye (single binary, K8s-native, almost-zero config).
- Persistence/replay bhi chahiye to **JetStream** on kar do — par jaante raho yeh Kafka-level retention ecosystem nahi (smaller, focused).
- Bad fit: heavy long-term analytics retention + rich stream-processing ecosystem.

**RabbitMQ chuno jab:**
- **Complex routing** (topic/fanout/headers exchanges), per-message **TTL/DLX/priority**, ya traditional **task queues** (Celery-style) chahiye.
- Throughput moderate hai (< ~100K msg/sec) par routing intelligence zyada chahiye.
- Bad fit: long-retention event replay at massive scale (Kafka/Pulsar better).

> **Rule of thumb:** Streaming + replay at scale → **Kafka** (ya Pulsar agar multi-tenant/geo/decoupled-storage chahiye). Routing + task queues → **RabbitMQ**. Ultra-low-latency RPC / edge / mesh → **NATS** (+ JetStream agar durability bhi chahiye).

---

## Interview Q&A

**Q1: Pulsar ka storage Kafka se fundamentally kaise alag hai?**
**A:** Kafka **partition-centric** hai — ek partition ka pura data ek broker (+replicas) pe rehta hai, isliye storage compute se coupled hai aur expansion pe data move karna padta hai. Pulsar **segment-centric** hai — topic andar se ledgers/segments mein toot-ta hai jo poore **BookKeeper** cluster (bookies) pe spread hote hain, aur **brokers stateless** hain. Result: storage aur serving independently scale, plus tiered S3 offload aur seamless capacity add.

**Q2: Pulsar subscription ko Kafka consumer group bolna kyun galat hai?**
**A:** Concept similar hai (named cursor + load sharing), par Kafka mein 1 partition → max 1 consumer (parallelism partition-bound). Pulsar ki **`shared`** subscription mein ek partition ko bhi multiple consumers consume kar sakte hain (message-level round-robin dispatch) — scaling partition count se decouple ho jaati hai (ordering chhod ke). Plus Pulsar mein 4 distinct modes hain (exclusive/failover/shared/key_shared) jo log aur queue dono semantics dete hain.

**Q3: Core NATS aur JetStream mein kya difference hai?**
**A:** **Core NATS** = at-most-once, fire-and-forget pub/sub + request-reply. Koi persistence nahi — subscriber offline to message gaya. Extreme low latency. **JetStream** = NATS ke upar persistence layer: streams, durable consumers, at-least-once / exactly-once, replay, plus KV + Object store. Core = speed, JetStream = durability — opt-in.

**Q4: NATS request-reply itna useful kyun hai?**
**A:** Built-in temporary reply-subject ke through synchronous-feeling RPC milta hai async messaging fabric pe — service mesh / microservice control-plane / RPC ke liye ideal, bina alag RPC framework ke. Latency sub-millisecond hone se yeh inter-service calls ke liye HTTP/gRPC ka lightweight alternative ban jaata hai.

**Q5: Multi-tenant SaaS bana rahe ho jahan har customer ko isolation + alag retention/quota chahiye — kaunsa broker?**
**A:** **Pulsar** — native multi-tenancy (tenant → namespace hierarchy) mein auth, quota, retention, geo-rep sab namespace pe set hota hai, ek hi cluster pe kayi tenants safely. Kafka mein bas ACLs hain (true tenant hierarchy nahi); RabbitMQ vhosts basic isolation dete hain.

**Q6: Edge devices se telemetry chahiye, ultra-low latency, minimal footprint — kaunsa?**
**A:** **NATS** — single ~15MB Go binary, sub-ms latency, leaf-node topology edge ke liye. Agar us telemetry ko durably store + replay karna ho to **JetStream** enable kar do.

**Q7: Pulsar geo-replication Kafka se kaise behtar hai?**
**A:** Pulsar mein geo-replication **first-class/native** hai — namespace pe clusters list karo, Pulsar khud regions ke beech replicate karta hai. Kafka mein **MirrorMaker 2** (separate process, alag operate/monitor) chalana padta hai. RabbitMQ similarly Federation/Shovel (bolt-on) use karta hai.

**Q8: Sirf complex routing (fanout + topic + per-message TTL) chahiye, throughput moderate — kaunsa?**
**A:** **RabbitMQ** — exchanges (direct/topic/fanout/headers) + DLX + TTL + priority sab native. Kafka/Pulsar/NATS routing itna rich nahi; unke liye yeh over-engineering hoga.

---

## TL;DR

- **Kafka** — partition-centric log; throughput + replay + mature ecosystem; storage compute se coupled.
- **Pulsar** — segment-centric, storage (BookKeeper bookies) serving (brokers) se **decoupled**; streaming + queue dono (4 subscription modes); native multi-tenancy, geo-replication, S3 tiered offload, Pulsar Functions. Trade-off: highest ops complexity.
- **NATS** — ultra-lightweight, subjects + wildcards; **Core** = at-most-once fire-and-forget + request-reply (RPC/mesh/edge/IoT); **JetStream** = persistence (streams, durable consumers, at-least-once/exactly-once, KV/Object store).
- **RabbitMQ** — AMQP smart broker; complex routing + task queues.
- Decision: **streaming+replay@scale → Kafka** (Pulsar agar multi-tenant/geo/decoupled chahiye); **routing/task-queues → RabbitMQ**; **low-latency RPC/edge → NATS** (+JetStream for durability).
- Pulsar subscription ≈ Kafka consumer group, but `shared` mode 1 partition ko multiple consumers de deta hai — identical nahi.

---

## Related Topics
- `01_kafka_fundamentals.md` — Kafka log, partitions, consumer groups (yeh lesson ka baseline).
- `02_producers_consumers_python.md` — Kafka Python clients (`aiokafka`) — Pulsar/NATS clients se contrast.
- `05_exactly_once_transactions.md` — Kafka exactly-once; JetStream/Pulsar dedup semantics se compare.
- `06_kafka_production_ops.md` — Kafka tiered storage, MirrorMaker 2, cluster ops — Pulsar BookKeeper/geo-rep se contrast.
- `../08_RabbitMQ/theory/01_basics_amqp_exchanges.md` — AMQP exchanges + routing (RabbitMQ smart-broker model).
- `../08_RabbitMQ/theory/05_quorum_queues_ha.md` — RabbitMQ HA/replication; Pulsar BookKeeper replication se compare.
- `../08_RabbitMQ/theory/06_federation_shovel.md` — RabbitMQ cross-cluster; Pulsar native geo-replication se contrast.
- `../08_RabbitMQ/theory/07_publisher_confirms_competing_consumers.md` — competing consumers; Pulsar `shared` subscription jaisa pattern.
