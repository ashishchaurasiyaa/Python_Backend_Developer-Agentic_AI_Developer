# 10 — Schema Registry & Avro (Wire Format, Evolution, Compatibility)

> The schema IS the API contract of an event-driven system. Schema Registry is the thing that stops a producer deploy from silently breaking every consumer downstream — if you run Kafka between teams without it, you're one `git push` away from a multi-service outage.

---

## Why It Matters

In a REST API, a breaking change fails fast: the consumer gets a 400/500 at
request time and the caller's on-call gets paged. In Kafka, a breaking payload
change fails **late and asynchronously**: the producer happily writes the new
shape, messages pile up, and consumers start crashing minutes-to-hours later —
often a *different team's* consumers, often at 2 AM, often with the bad
messages already durably stored in the log where they'll re-break every replay.

Schema Registry moves that failure to **publish time**: an incompatible schema
is rejected with an HTTP 409 before a single bad message is produced.

Senior interview (the anchor question of this file): **"How do you evolve an
event schema without breaking consumers?"** — the full staged answer is below,
and it's worth rehearsing out loud. A weak answer says "we use Avro." A strong
answer covers compatibility mode choice, deploy ordering, transitive checking,
and CI-time compatibility gates.

> Basics-level summary (what Schema Registry is, one code snippet) already
> lives in [04_kafka_connect_integration.md](04_kafka_connect_integration.md#schema-registry)
> — this file is the deep dive: the actual bytes, all compatibility modes,
> subject naming, references, and production Python code.

---

## Quick-reference card — compatibility modes

| Mode | Check performed | Who upgrades FIRST | Safe changes |
|---|---|---|---|
| `BACKWARD` (default) | New schema can read data written with the **previous** schema | **Consumers** | Delete fields; add fields **with defaults** |
| `BACKWARD_TRANSITIVE` | New schema can read data of **all** previous schemas | Consumers | Same, checked against every version |
| `FORWARD` | Data written with new schema readable by the **previous** schema | **Producers** | Add fields; delete fields **that had defaults** |
| `FORWARD_TRANSITIVE` | ...readable by **all** previous schemas | Producers | Same, checked against every version |
| `FULL` | Both backward and forward vs previous version | Either order | Add/delete **only** fields with defaults |
| `FULL_TRANSITIVE` | Both, vs all versions | Either order | Same, checked against every version |
| `NONE` | Nothing | — | Anything (i.e., you're on your own) |

Memory hook: **BACKWARD = new reader, old data. FORWARD = old reader, new
data.** "Who upgrades first" falls out of that: BACKWARD protects a *new
consumer* against *old messages still in the topic*, so you ship consumers
first; FORWARD protects *old consumers* against *new messages*, so you ship
producers first.

---

## The wire format — what's actually in the message bytes

A Schema-Registry-serialized Kafka message value is NOT plain Avro. It's:

```
byte 0        bytes 1-4                bytes 5..N
┌──────────┬──────────────────────┬─────────────────────────────┐
│ magic 0x0│ schema ID (int32, BE)│ Avro binary-encoded payload │
└──────────┴──────────────────────┴─────────────────────────────┘
```

- **Magic byte** `0x00`: format version marker. Anything else → the message
  wasn't produced by a Schema Registry serializer (or is a future format).
- **Schema ID**: 4-byte big-endian int, **globally unique per registry**
  (not per subject). The consumer uses it to fetch the exact writer schema.
- **Payload**: Avro *binary* encoding — no field names, no types, just packed
  values in schema-field order. This is why Avro payloads are tiny and why
  you **cannot decode them without the writer schema**.

```python
import struct

def parse_wire_format(raw: bytes) -> tuple[int, int, bytes]:
    magic = raw[0]
    (schema_id,) = struct.unpack(">I", raw[1:5])   # big-endian uint32
    return magic, schema_id, raw[5:]
```

Two immediate consequences worth saying in an interview:

1. **`kafka-console-consumer` shows garbage** for Avro topics — use
   `kafka-avro-console-consumer` (it knows the wire format and calls the
   registry). A classic on-call confusion.
2. A **plain-Avro producer and a registry-aware consumer can't talk** (and
   vice versa): the 5-byte prefix is either wrongly present or wrongly
   expected. "Unknown magic byte!" in a stack trace = exactly this mismatch.

Protobuf's wire format adds one more element after the schema ID — a varint
list of **message indexes** (which nested message inside the `.proto` file was
used) — because one Protobuf schema file can define many message types.

---

## What Schema Registry actually is

A small REST service (default port 8081) in front of Kafka itself:

- **Storage**: every registered schema is a message in the compacted,
  single-partition `_schemas` topic. The registry is effectively stateless —
  restart it and it rebuilds its cache by replaying `_schemas`. Kafka is the
  database.
- **Subjects**: a *subject* is a named, versioned sequence of schemas —
  compatibility is enforced **per subject**. With the default naming strategy,
  `orders-value` and `orders-key` are the subjects for topic `orders`.
- **IDs vs versions**: a schema **ID** is global (`id=7` means the same schema
  text everywhere); a **version** is per-subject (`orders-value` version 3).
  The wire format carries the ID, not the version.
- **Caching**: serializers/deserializers cache schema↔ID lookups in memory.
  A running producer/consumer keeps working through a registry outage; a
  **freshly booted** one does not (cold cache → HTTP calls fail). This is the
  correct nuance for "is Schema Registry a single point of failure?" — it's on
  the *startup* path, not the *per-message* path.

```bash
# The REST API you'll actually use while debugging
curl http://localhost:8081/subjects
curl http://localhost:8081/subjects/orders-value/versions
curl http://localhost:8081/subjects/orders-value/versions/latest
curl http://localhost:8081/schemas/ids/7          # what's schema id 7?
curl http://localhost:8081/config                  # global compatibility mode
curl http://localhost:8081/config/orders-value     # per-subject override

# Set per-subject compatibility
curl -X PUT -H "Content-Type: application/json" \
  --data '{"compatibility": "BACKWARD_TRANSITIVE"}' \
  http://localhost:8081/config/orders-value

# Dry-run a schema against the compatibility rules (use this in CI!)
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"schema": "{...escaped avro json...}"}' \
  http://localhost:8081/compatibility/subjects/orders-value/versions/latest
```

---

## Subject naming strategies

The *subject* a schema registers under is decided by the serializer's naming
strategy — and it changes what "compatibility" even means:

| Strategy | Subject for value | Meaning |
|---|---|---|
| `TopicNameStrategy` (default) | `<topic>-value` | One schema lineage **per topic**. All records on `orders` must be mutually compatible. |
| `RecordNameStrategy` | `<record full name>` e.g. `com.shop.OrderCreated` | Schema lineage follows the **record type across all topics**. Allows many event types per topic. |
| `TopicRecordNameStrategy` | `<topic>-<record full name>` | Many event types per topic, but lineage scoped **per topic** — the usual choice for event-sourced "one entity's events in one topic" designs. |

Why you'd leave the default: the classic event-sourcing setup puts
`OrderCreated`, `OrderPaid`, `OrderShipped` on ONE `orders` topic (they must
share a partition for per-order ordering — see
[08_ordering_guarantees.md](08_ordering_guarantees.md)). Under
`TopicNameStrategy`, registering `OrderPaid` on `orders-value` fails the
compatibility check against `OrderCreated` — they're different records, not an
evolution of one. Switch to `TopicRecordNameStrategy` and each event type gets
its own independent lineage: `orders-com.shop.OrderCreated`,
`orders-com.shop.OrderPaid`, etc.

Trade-off to mention: with Record/TopicRecord strategies the **broker-side
topic no longer implies a single shape**, so generic consumers (Connect sinks,
ksqlDB) get harder to configure — the default strategy plus one-event-type-
per-topic stays the right call when you don't need entity-level ordering
across event types.

---

## Avro vs Protobuf vs JSON Schema on Kafka

All three are first-class in Schema Registry (`"AVRO"`, `"PROTOBUF"`,
`"JSON"` schema types). The decision matrix:

| | **Avro** | **Protobuf** | **JSON Schema** |
|---|---|---|---|
| Payload | Binary, no field names — smallest | Binary with field tags — small | Full JSON text — largest (3-10x) |
| Decode needs writer schema? | **Yes** (that's what the wire-format ID is for) | No (tags are self-describing enough) | No |
| Evolution model | **Reader/writer schema resolution** — defaults filled in, fields matched by name | Field-number based — unknown fields skipped, missing fields get zero-values | **Validation**, not resolution — compat rules are about constraint subsets, weakest of the three |
| Defaults | Explicit `"default"` in schema — evolution rules revolve around them | Implicit zero-values (0, "", false) — can't distinguish "absent" from "zero" without wrappers/optional | JSON Schema `default` is not applied by validators — informational |
| Codegen required? | No — Python works with plain dicts | Effectively yes (`protoc`) | No |
| Kafka ecosystem fit | **Native**: Connect, ksqlDB, Debezium, console tools all speak Avro first | Good, newer | OK |
| Pick it when | Default choice for Kafka-centric pipelines | Org already lives on gRPC/proto; sharing types with services | Consumers demand human-readable JSON but you still want a compat gate |

Interview-grade nuance: Avro's evolution is the *strongest* because
deserialization takes **both** schemas (writer's, fetched by ID; reader's,
compiled into the consumer) and resolves between them — renamed via aliases,
reordered fields fine, missing fields defaulted. Protobuf evolution is
mechanical field-number bookkeeping (never reuse a number!). JSON Schema
"evolution" is just "is the new validator more/less permissive", which is why
teams that start there usually end up on Avro or Protobuf.

---

## Compatibility modes — concrete evolve-a-field walkthroughs

Base schema, v1:

```json
{
  "type": "record",
  "name": "OrderCreated",
  "namespace": "com.shop.events",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "amount",   "type": "double"}
  ]
}
```

### BACKWARD (the default) — consumers upgrade first

Check: **new schema (reader) must decode data written by the previous schema
(writer).**

✅ v2 adds a field WITH a default:

```json
{"name": "currency", "type": "string", "default": "INR"}
```

Old v1 messages don't contain `currency` → the new reader fills in `"INR"`.
Deploy order: ship consumers (with v2) first — they can read both v1 and v2
data. Then ship producers. If producers shipped first, old consumers would see
unknown data... which is fine in Avro (extra writer fields are skipped), but
BACKWARD doesn't *promise* that — FORWARD does. Discipline: mode decides
deploy order, always.

✅ v2 deletes `amount`: new reader simply ignores that field in old data.
(Deleting is always backward-safe; it's *forward*-unsafe unless the field had
a default.)

❌ v2 adds `email` with NO default: new reader hits a v1 message, has no value
for `email`, no default to fall back on → resolution error. Registry rejects
the registration with **HTTP 409 Conflict** before you can deploy this bug.

✅ Type *promotions* are reader-widening only: `int → long/float/double`,
`long → float/double`, `float → double`, `string ↔ bytes`. Narrowing
(`long → int`) is incompatible.

❌ Renaming a field is a delete + an add-without-default → incompatible. The
escape hatch is an Avro **alias** on the reader schema
(`"aliases": ["old_name"]`), or the boring-but-robust route: add the new
field with a default, dual-write both fields, migrate consumers, delete the
old field two releases later.

### FORWARD — producers upgrade first

Check: **data written with the new schema must be readable by the previous
schema.**

✅ v2 adds any field (default or not): the old reader doesn't know about it
and Avro resolution skips unknown writer fields.

✅ v2 deletes a field **that had a default** in v1: old reader fills its own
default.

❌ v2 deletes `order_id` (no default in v1): old reader requires it, new data
doesn't have it → rejected.

When FORWARD is the right mode: you control the producer but consumers are
many/slow-moving (e.g., an events team publishing to a dozen analytics
consumers) — you must be able to deploy producer changes without waiting for
every consumer to upgrade.

### FULL — both directions, any deploy order

Only add/remove **fields with defaults**. Most restrictive, most freedom
operationally. Reasonable default for topics shared across many teams.

### The transitive trap (this is the interview differentiator)

Non-transitive modes check **only against the immediately previous version**.
Watch this perfectly legal sequence under plain `BACKWARD`:

```
v1: {order_id, amount}
v2: {order_id, amount, currency default "INR"}   ← vs v1: add-with-default ✅
v3: {order_id, amount, currency}  (default REMOVED)
        ← checked ONLY vs v2: field exists in both, no default needed ✅ passes!
        ← but vs v1: currency missing in old data, no default → 💥
```

The registry **accepts v3**. Everything looks fine — until a v3 consumer
replays the topic from offset 0 (reprocessing job, new service bootstrapping
state, compacted topic with years-old records still live) and hits v1-encoded
messages. Deserialization explodes in production on data that was written
months ago.

**Rule:** if a topic has long retention, is compacted, or is ever replayed —
which is *why you chose Kafka* — use `BACKWARD_TRANSITIVE` (or
`FULL_TRANSITIVE`). Non-transitive modes are only defensible for short-TTL
topics where pre-previous data is guaranteed gone.

---

## The anchor answer: "How do you evolve an event schema without breaking consumers?"

Rehearse this as a staged answer:

1. **Contract first**: every topic has a registered schema; compatibility mode
   is set per subject, `BACKWARD_TRANSITIVE` or `FULL_TRANSITIVE` for anything
   with real retention. The registry rejects incompatible registrations with a
   409 — breaking changes become *impossible to deploy*, not "hopefully caught
   in review."
2. **Mode decides deploy order**: BACKWARD → consumers first, FORWARD →
   producers first, FULL → either. Say this dependency out loud; most
   candidates miss it.
3. **Only make legal changes**: in practice ~90% of evolution is "add an
   optional field with a default." Never rename, never change a type except
   promotions; rename = add-new + dual-write + migrate + remove-old across
   releases (or reader-side aliases).
4. **Gate in CI, not at runtime**: run the schema against
   `POST /compatibility/subjects/<subject>/versions/latest` (or
   `client.test_compatibility(...)`) in the pipeline. Schemas live in git next
   to the code ("schema as code"); registration is a deliberate CI/CD step.
5. **`auto.register.schemas=false` in production producers**: otherwise any
   producer instance can mutate the subject as a *side effect of serializing a
   message* — schema management by accident. Pair with
   `use.latest.version=true` where appropriate.
6. **Truly breaking change?** Don't fight the registry — that's the contract
   telling you this is a new contract. New subject/topic (`orders.v2`),
   producers dual-write during migration, consumers move over, old topic
   retired. Same playbook as versioning a REST API.

---

## Schema references — composing schemas

Since Confluent Platform 5.5, a schema can **reference** other registered
schemas instead of inlining them. Two big uses:

**1. Shared common types** — one `Money` record, referenced everywhere:

```python
from confluent_kafka.schema_registry import SchemaRegistryClient, Schema, SchemaReference

sr = SchemaRegistryClient({"url": "http://localhost:8081"})

MONEY = """
{"type": "record", "name": "Money", "namespace": "com.shop.common",
 "fields": [{"name": "amount",   "type": "long"},
            {"name": "currency", "type": "string", "default": "INR"}]}
"""
sr.register_schema("com.shop.common.Money", Schema(MONEY, "AVRO"))

ORDER = """
{"type": "record", "name": "OrderCreated", "namespace": "com.shop.events",
 "fields": [{"name": "order_id", "type": "string"},
            {"name": "total",    "type": "com.shop.common.Money"}]}
"""
sr.register_schema(
    "orders-value",
    Schema(ORDER, "AVRO",
           references=[SchemaReference(name="com.shop.common.Money",
                                       subject="com.shop.common.Money",
                                       version=1)]),
)
```

Now `Money` evolves in ONE place, and its subject has its own compatibility
lineage. References are pinned to a **version** — upgrading a referenced
schema is an explicit re-registration of the referencing schema, not a silent
ripple.

**2. Multiple event types per topic, without giving up checking** — register a
top-level **union of references** as the topic's value schema:

```json
["com.shop.events.OrderCreated", "com.shop.events.OrderPaid"]
```

...with each union branch as a reference. You keep `TopicNameStrategy` (so
tooling still sees one subject per topic) but the subject is explicitly "one
of these N event types." Adding a new event type = evolving the union, which
is itself compatibility-checked.

---

## confluent-kafka Python — production-shaped serializer/deserializer code

The Schema Registry serializers live in `confluent-kafka`
(`pip install "confluent-kafka[avro]"`) — NOT in `aiokafka`/`kafka-python`.
Modern API (2.x): plain `Producer`/`Consumer` + explicit serializer calls
(`SerializingProducer`/`DeserializingConsumer` are deprecated).

### Producer

```python
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField

ORDER_V2 = """
{"type": "record", "name": "OrderCreated", "namespace": "com.shop.events",
 "fields": [{"name": "order_id", "type": "string"},
            {"name": "amount",   "type": "double"},
            {"name": "currency", "type": "string", "default": "INR"}]}
"""

sr = SchemaRegistryClient({"url": "http://localhost:8081"})

serializer = AvroSerializer(
    sr,
    ORDER_V2,
    conf={
        # PRODUCTION: producers must never mutate subjects as a side effect.
        # Schema registration is a CI step; here we only LOOK UP the id.
        "auto.register.schemas": False,
        # Optional: ignore local schema_str, serialize with subject's latest
        # "use.latest.version": True,
    },
)

producer = Producer({"bootstrap.servers": "localhost:9092",
                     "enable.idempotence": True})

value_bytes = serializer(
    {"order_id": "ord-1", "amount": 999.0, "currency": "USD"},
    SerializationContext("orders", MessageField.VALUE),
)
# value_bytes = 0x00 + schema_id(4B) + avro binary — the wire format above

producer.produce("orders", key=b"ord-1", value=value_bytes,
                 on_delivery=lambda err, m: err and print(f"FAIL: {err}"))
producer.flush()
```

### Consumer

```python
from confluent_kafka import Consumer
from confluent_kafka.schema_registry.avro import AvroDeserializer

# Passing schema_str makes ORDER_V2 the READER schema: the deserializer
# fetches the WRITER schema by the embedded id, then resolves writer→reader
# (this is where old messages get currency="INR" filled in).
# Omit schema_str → you get whatever shape the writer schema had.
deserializer = AvroDeserializer(sr, ORDER_V2)

consumer = Consumer({"bootstrap.servers": "localhost:9092",
                     "group.id": "order-workers",
                     "auto.offset.reset": "earliest",
                     "enable.auto.commit": False})
consumer.subscribe(["orders"])

while True:
    msg = consumer.poll(1.0)
    if msg is None or msg.error():
        continue
    order = deserializer(msg.value(),
                         SerializationContext(msg.topic(), MessageField.VALUE))
    print(order)               # plain dict: {"order_id": ..., "currency": ...}
    consumer.commit(msg)
```

### Registry admin operations (CI script material)

```python
from confluent_kafka.schema_registry import Schema

sr.set_compatibility(subject_name="orders-value", level="BACKWARD_TRANSITIVE")

ok = sr.test_compatibility("orders-value", Schema(ORDER_V2, "AVRO"))
if not ok:
    raise SystemExit("Schema is incompatible — fix it before merging")

schema_id = sr.register_schema("orders-value", Schema(ORDER_V2, "AVRO"))
```

---

## Production gotchas checklist

- **`auto.register.schemas=False`** on prod producers (see above). The number
  one Schema Registry misconfiguration.
- **Transitive compatibility** for compacted/long-retention/replayed topics —
  the default `BACKWARD` (non-transitive) has the replay trap shown above.
- **Never hard-delete subjects in prod.** Soft delete keeps IDs resolvable;
  hard delete means old messages on disk reference IDs that no longer exist →
  permanently undecodable data.
- **The `_schemas` topic needs the same care as your data**: replication
  factor 3, and it's in your DR story — lose it and every Avro message in the
  cluster is unreadable bytes.
- **Registry outage ≠ immediate outage**: warm clients run on cache;
  cold-starting pods fail. Run ≥2 registry instances behind a load balancer
  (they coordinate leadership through Kafka itself).
- **"Unknown magic byte!"** = a plain (non-registry) producer wrote to a topic
  a registry-aware deserializer is reading, or vice versa. Wire format
  mismatch, not corruption.
- **Same schema text ⇒ same global ID** — the registry dedupes. Useful when
  reasoning about multi-environment promotion; even more useful is not relying
  on IDs matching across *separate* registries (they won't in general — use
  Schema Linking / replication tools for cross-cluster).

---

## Interview Q&A

**Q: What exactly is in the bytes of an Avro message on a Kafka topic?**
A: A 5-byte prefix — magic byte `0x00` plus a 4-byte big-endian schema ID —
followed by Avro *binary* encoding of the record (no field names, values
packed in schema order). The consumer fetches the writer schema by that ID
from the registry (cached after first use) and decodes, optionally resolving
into its own reader schema.

**Q: How do you evolve an event schema without breaking consumers?**
A: (Staged answer from above.) Enforce compatibility per subject in the
registry — transitive mode for topics with real retention; let the mode
dictate deploy order (BACKWARD → consumers first, FORWARD → producers first);
restrict changes to legal ones — mostly adding fields with defaults; run
`test_compatibility` in CI with `auto.register.schemas=false` in producers;
and for genuinely breaking changes, cut a new subject/topic and migrate, like
versioning a REST API.

**Q: BACKWARD vs FORWARD — who deploys first and why?**
A: BACKWARD means the *new* schema reads *old* data, so upgraded consumers
handle everything already in the topic → consumers deploy first. FORWARD
means *old* readers handle *new* data → producers can deploy first while
consumers lag behind. Getting the order backwards means a window where
messages exist that the live readers can't decode.

**Q: The registry accepted my schema, but consumers still crashed on replay. How?**
A: Non-transitive compatibility. Each version was compatible with its
immediate predecessor, but not with older ones — e.g., v2 added a field with a
default, v3 removed the default; v3-vs-v2 passes, v3-vs-v1 doesn't. A replay
from offset 0 (or a compacted topic) surfaces v1-encoded data to the v3
reader and explodes. Fix: `BACKWARD_TRANSITIVE`/`FULL_TRANSITIVE`.

**Q: Why prefer Avro over JSON on Kafka?**
A: Size (binary, no repeated field names — matters at millions of msgs/sec),
enforced contracts (registry rejects incompatible changes at publish time,
vs JSON's "hope and pray"), and real evolution semantics via reader/writer
schema resolution with defaults. Choose Protobuf instead when the org is
already gRPC-native; JSON Schema only when consumers require raw JSON.

**Q: Is Schema Registry a single point of failure?**
A: On the *cold-start* path, not the per-message path. Serializers cache
schema↔ID mappings, so running clients survive an outage; new instances
can't boot. All registry state lives in the compacted `_schemas` Kafka topic,
so registry nodes are themselves nearly stateless — run two or more, and
protect `_schemas` like production data.

**Q: How do you rename a field?**
A: You don't, directly — a rename is a delete plus an add-without-default,
which fails every useful compatibility mode. Either use an Avro alias on the
reader schema, or do the multi-release dance: add the new field with a
default, dual-write both, migrate consumers, then drop the old field.

**Q: Multiple event types on one topic — how does that work with the registry?**
A: The default `TopicNameStrategy` forces all messages on a topic into one
schema lineage, which rejects a second record type. Options: switch the
serializer to `TopicRecordNameStrategy` (one subject per topic+record), or
keep the default and register a top-level union of schema references. You
want types on one topic when they must share partition-level ordering for the
same entity (order events keyed by `order_id`).

---

Related: [04_kafka_connect_integration.md](04_kafka_connect_integration.md)
(Connect + registry summary — Connect converters are the biggest registry
consumer in practice), [08_ordering_guarantees.md](08_ordering_guarantees.md)
(why event types end up sharing topics), [02_producers_consumers_python.md](02_producers_consumers_python.md)
(client fundamentals). Hands-on: [labs/06_schema_registry_evolution.py](labs/06_schema_registry_evolution.py)
— parse the wire format yourself, evolve a schema, and watch the registry
409 a breaking change.
