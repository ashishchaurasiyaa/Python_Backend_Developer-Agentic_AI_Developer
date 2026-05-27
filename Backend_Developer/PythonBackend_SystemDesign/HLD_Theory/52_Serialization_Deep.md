# 52. Serialization — JSON vs Protobuf vs Avro vs MessagePack

## What is Serialization?

Converting in-memory objects → bytes that can be:
- Sent over network
- Stored in DB / files
- Cached in Redis

**Two parts:**
1. **Serialize** (encode): object → bytes
2. **Deserialize** (decode): bytes → object

---

## Why Serialization Format Matters

```
Choosing wrong format costs you:
- Bandwidth (10x payload size)
- CPU (10x parse time)
- Storage ($$$ at scale)
- Latency (network + parse adds up)
- Schema evolution headaches (can't add fields without breaking)
```

**Example impact (1M requests/sec):**
| Format | Avg payload | Bandwidth/day |
|---|---|---|
| JSON | 5 KB | 432 TB |
| Protobuf | 1.5 KB | 130 TB |
| Avro | 1 KB | 86 TB |

Bandwidth savings = real money.

---

## Major Formats Compared

### Quick Comparison

| Format | Type | Schema | Size | Speed | Human-readable |
|---|---|---|---|---|---|
| **JSON** | Text | No | Large | Medium | ✅ Yes |
| **XML** | Text | Optional | Largest | Slow | ✅ Yes |
| **YAML** | Text | No | Large | Slow | ✅ Yes |
| **CSV** | Text | No | Compact | Fast | ✅ Yes |
| **MessagePack** | Binary | No | Small | Fast | ❌ No |
| **BSON** | Binary | No | Medium | Medium | ❌ No |
| **Protobuf** | Binary | ✅ Required | Smallest | Fastest | ❌ No |
| **Avro** | Binary | ✅ Required | Small | Fast | ❌ No |
| **Thrift** | Binary | ✅ Required | Small | Fast | ❌ No |
| **FlatBuffers** | Binary | ✅ Required | Small | Fastest (zero-copy) | ❌ No |
| **Cap'n Proto** | Binary | ✅ Required | Small | Fastest (zero-copy) | ❌ No |

---

## JSON — The Default

```json
{
  "user_id": 42,
  "name": "Alice",
  "email": "alice@example.com",
  "tags": ["admin", "beta"]
}
```

**Python:**
```python
import json

# Encode
data = json.dumps({"user_id": 42, "name": "Alice"})

# Decode
obj = json.loads(data)

# Faster alternatives:
import orjson         # 3-5x faster
data = orjson.dumps({"user_id": 42})

import ujson          # 2-3x faster
data = ujson.dumps(...)
```

**Pros:**
- Universal (every language)
- Human readable / debuggable
- No schema needed
- Native JS / browser support
- Easy logging

**Cons:**
- Large payload (verbose)
- Slow to parse
- No native types (no datetime, decimal, binary)
- No schema enforcement
- No backwards compatibility guarantees

**Use when:**
- Public APIs (REST)
- Configuration files
- Debugging matters
- Small-to-medium scale (< 1K req/sec)

---

## Protobuf (Protocol Buffers) — Google's Choice

**Schema-first** — define types in `.proto` file.

```protobuf
// user.proto
syntax = "proto3";

message User {
    int64 user_id = 1;
    string name = 2;
    string email = 3;
    repeated string tags = 4;
    google.protobuf.Timestamp created_at = 5;
}
```

**Compile to Python:**
```bash
protoc --python_out=. user.proto
```

**Use:**
```python
import user_pb2

# Encode
user = user_pb2.User()
user.user_id = 42
user.name = "Alice"
user.email = "alice@example.com"
user.tags.extend(["admin", "beta"])

data = user.SerializeToString()  # bytes

# Decode
user2 = user_pb2.User()
user2.ParseFromString(data)
```

**Pros:**
- **Tiny payload** (3-10x smaller than JSON)
- **Fast** (5-10x faster parse)
- **Type-safe** (compiler catches errors)
- **Schema evolution** (add fields without breaking)
- **gRPC native**
- **Cross-language** (codegen for 20+ languages)

**Cons:**
- Not human-readable (need tools to inspect)
- Schema file required (sharing/versioning)
- Less native in browsers (use protobuf.js)
- Setup overhead

**Use when:**
- High-throughput internal services
- gRPC APIs
- Mobile (bandwidth-sensitive)
- Microservices

**Schema evolution rules:**
```protobuf
// V1
message User {
    int64 user_id = 1;
    string name = 2;
}

// V2 — backwards compatible
message User {
    int64 user_id = 1;
    string name = 2;
    string email = 3;           // ✅ Add new field with new tag — OLD readers ignore it
    // bool active = 2;          // ❌ NEVER reuse field numbers
    reserved 4;                  // ❌ Mark deleted field numbers as reserved
}
```

**Field number rules:**
- 1-15: 1-byte encoding (use for frequently-used fields)
- 16-2047: 2-byte encoding
- Never reuse field numbers after deletion (use `reserved`)
- Don't change field types (mostly)

---

## Avro — Hadoop / Kafka Default

```json
// user.avsc
{
  "type": "record",
  "name": "User",
  "namespace": "com.acme",
  "fields": [
    {"name": "user_id", "type": "long"},
    {"name": "name", "type": "string"},
    {"name": "email", "type": ["null", "string"], "default": null},
    {"name": "tags", "type": {"type": "array", "items": "string"}, "default": []}
  ]
}
```

**Python:**
```python
from fastavro import schemaless_writer, schemaless_reader, parse_schema
import io

schema = parse_schema(SCHEMA_DICT)

# Encode
buf = io.BytesIO()
schemaless_writer(buf, schema, {"user_id": 42, "name": "Alice"})
data = buf.getvalue()

# Decode
buf = io.BytesIO(data)
obj = schemaless_reader(buf, schema)
```

**Pros:**
- **Schema embedded** (or reference to schema registry)
- **Schema evolution** with reader/writer schema resolution
- **Compact** binary
- **Dynamic typing** (deserialize without code generation)
- **Kafka Schema Registry standard**
- Great for analytics (Hadoop, Spark)

**Cons:**
- Schema overhead per message (mitigated by Confluent Schema Registry)
- Slower than Protobuf (slightly)
- Smaller ecosystem outside JVM

**Use when:**
- Kafka pipelines
- Data lakes (Parquet often uses Avro schema)
- Long-term data storage
- Multiple writers, multiple readers, evolving schemas

### Schema Registry (Confluent)

```
Producer                                 Consumer
   │                                        │
   │ 1. Register schema → get schema_id     │
   │ 2. Serialize msg with schema           │
   │ 3. Prepend schema_id to message        │
   │    [schema_id][avro_bytes]             │
   │ ─────────────────────────────────→     │
   │                                        │ 4. Read schema_id
   │                                        │ 5. Fetch schema from registry
   │                                        │ 6. Deserialize
```

**Benefits:**
- Schemas centrally managed
- Compatibility checks (BACKWARD, FORWARD, FULL)
- Schemas not duplicated per message (just 4-byte ID)

```python
from confluent_kafka.avro import AvroProducer, AvroConsumer

producer = AvroProducer(
    {"bootstrap.servers": "kafka:9092", "schema.registry.url": "http://registry:8081"},
    default_value_schema=avro.load("user.avsc"),
)
producer.produce(topic="users", value={"user_id": 42, "name": "Alice"})
```

---

## MessagePack — JSON's Faster Cousin

Binary, schema-less, drop-in JSON replacement.

```python
import msgpack

# Encode
data = msgpack.packb({"user_id": 42, "name": "Alice"})

# Decode
obj = msgpack.unpackb(data)
```

**Pros:**
- **2-3x smaller** than JSON
- **2x faster** than JSON
- **Drop-in** (same data model)
- No schema needed
- Native datetime, binary

**Cons:**
- Less common than JSON
- Not human-readable
- No schema evolution

**Use when:**
- Need JSON's flexibility + binary efficiency
- Internal APIs
- Cache values (Redis MessagePack)
- Mobile APIs

---

## Thrift — Facebook's

Like Protobuf but predates it. Less popular now.

```thrift
struct User {
    1: i64 user_id,
    2: string name,
    3: string email
}

service UserService {
    User getUser(1: i64 id)
}
```

**Use when:** Already in Facebook/Twitter ecosystem.

---

## FlatBuffers / Cap'n Proto — Zero-Copy

**Zero-copy** = access fields without full deserialization.

```cpp
// FlatBuffers — Google
auto user = GetUser(buffer);
int64_t id = user->user_id();  // direct memory access, no parse step
```

**Pros:**
- Fastest possible (no allocation)
- Mobile games, IoT
- Use when nanoseconds matter

**Cons:**
- Complex API
- Niche use cases

---

## BSON — MongoDB's Binary JSON

```python
import bson

data = bson.dumps({"user_id": 42, "name": "Alice", "created": datetime.now()})
```

**Pros:**
- Native datetime, ObjectId, binary
- MongoDB native

**Cons:**
- Larger than Protobuf
- Slower than MessagePack

**Use:** MongoDB applications.

---

## Performance Benchmark (representative)

Encoding/decoding 1MB of typical user data:

| Format | Encode | Decode | Size (bytes) |
|---|---|---|---|
| JSON (stdlib) | 50 ms | 80 ms | 1,000,000 |
| JSON (orjson) | 12 ms | 25 ms | 1,000,000 |
| MessagePack | 15 ms | 20 ms | 600,000 |
| Protobuf | 5 ms | 8 ms | 250,000 |
| Avro | 8 ms | 12 ms | 280,000 |
| FlatBuffers | 1 ms | 0.1 ms | 280,000 |

(Numbers vary by data shape; benchmark your own.)

---

## Schema Evolution Strategies

### Compatibility Modes

| Mode | Old reader + new writer | New reader + old writer |
|---|---|---|
| **BACKWARD** | ✅ Works | — |
| **FORWARD** | — | ✅ Works |
| **FULL** | ✅ Works | ✅ Works |
| **NONE** | ❌ Broken | ❌ Broken |

**Default: BACKWARD** (most common — old readers must work with new data).

### Safe Changes (Backward Compatible)

**Protobuf:**
- ✅ Add new field with new tag number
- ✅ Add field to oneof
- ✅ Remove `singular` field (don't reuse number)

**Avro:**
- ✅ Add field with default value
- ✅ Remove field with default value
- ✅ Add alias

### Unsafe Changes

- ❌ Change field type
- ❌ Reuse field number / name
- ❌ Add required field (use optional + default)
- ❌ Rename fields (use alias instead)

---

## Choosing Format — Decision Tree

```
Need human-readable?
├── Yes → JSON (with orjson for speed)
└── No → continue

Need schema enforcement?
├── No → MessagePack
└── Yes → continue

Using Kafka / data pipelines?
├── Yes → Avro (Schema Registry)
└── No → continue

Using gRPC / microservices?
├── Yes → Protobuf
└── No → continue

Mobile game / nanosecond critical?
├── Yes → FlatBuffers
└── No → Protobuf (default best choice)
```

---

## Real-World Examples

| Company | Choice | Why |
|---|---|---|
| Google | Protobuf | They invented it; gRPC |
| Netflix | Protobuf + Avro | gRPC services; Kafka data pipelines |
| Uber | Thrift, Protobuf | Legacy + modernization |
| Facebook | Thrift | Legacy |
| LinkedIn | Avro | Kafka-heavy infrastructure |
| Discord | Protobuf | Real-time messaging |
| Slack | JSON | Public APIs + web UI |
| Stripe | JSON | Public APIs prioritize DX |
| Twitter | Thrift → Protobuf | Migration in progress |

**Pattern:** JSON for public, binary for internal.

---

## Python-Specific Tips

### Faster JSON
```python
# Stdlib (slow)
import json
json.dumps(data)

# orjson (fast, dumps to bytes, native datetime/UUID)
import orjson
orjson.dumps(data)  # 3-5x faster

# Pydantic v2 — uses orjson internally
model.model_dump_json()

# msgspec — fastest pure-Python
import msgspec
msgspec.json.encode(data)
```

### Pydantic Schema-First (Modern Python)

```python
from pydantic import BaseModel
from datetime import datetime

class User(BaseModel):
    user_id: int
    name: str
    email: str | None = None
    created_at: datetime

# Validates AND serializes
user = User(user_id=42, name="Alice", email="a@b.c", created_at=datetime.now())

# To JSON
data = user.model_dump_json()  # str
data = user.model_dump()        # dict

# From JSON
user = User.model_validate_json(json_str)
```

Pydantic v2 = fast (Rust-backed via pydantic-core), schema-enforced, JSON-friendly.

---

## Binary in Python — protobuf example

```bash
pip install protobuf grpcio grpcio-tools
```

```bash
# Compile schema
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. user.proto
```

```python
import user_pb2
import time

# Encode 1M messages
start = time.time()
for i in range(1_000_000):
    msg = user_pb2.User(user_id=i, name=f"User{i}", email=f"u{i}@a.com")
    data = msg.SerializeToString()
print(f"Protobuf encode 1M: {time.time() - start:.2f}s")

# Compare to JSON
import json
start = time.time()
for i in range(1_000_000):
    data = json.dumps({"user_id": i, "name": f"User{i}", "email": f"u{i}@a.com"})
print(f"JSON encode 1M: {time.time() - start:.2f}s")
```

---

## Interview Q&A

### Q: Why is Protobuf smaller than JSON?

**Answer:**
- **Field numbers instead of names** (1 byte vs "user_id" = 7 bytes)
- **Variable-length integers** (varint encoding)
- **No quotes, no whitespace** (binary, not text)
- **Compact tag encoding** (field number + wire type in 1-2 bytes)
- **Default values omitted**

### Q: When would you choose Avro over Protobuf?

**Answer:**
- Already using Kafka + Schema Registry
- Need to read schema at runtime (dynamic deserialization)
- Long-term storage (Parquet)
- Big data analytics (Spark, Hive)

Choose Protobuf for: gRPC, internal microservices, compile-time codegen preferred.

### Q: How do you handle schema evolution in production?

**Answer:**
1. **Use schema registry** (Confluent, Apicurio)
2. **Set compatibility mode** (BACKWARD typically)
3. **Test compatibility in CI** before deploying
4. **Roll out producers first**, then consumers (for BACKWARD)
5. **Document field changes** in PR
6. **Never reuse field numbers/names** (use `reserved`)

### Q: How do you serialize Python objects with custom types (datetime, Decimal, UUID)?

**Answer:**
- **JSON stdlib:** custom encoder (subclass `JSONEncoder`)
- **orjson:** native support for datetime, UUID, dataclass
- **Pydantic:** automatic via field types
- **Protobuf:** define as `google.protobuf.Timestamp` etc.
- **MessagePack:** custom extension types

### Q: What's the cost of using JSON at scale?

**Answer:** Real example — 1M req/sec, avg 5KB payload:
- **Bandwidth**: 432 TB/day vs 130 TB/day for Protobuf → ~$30K/month CDN savings
- **CPU**: JSON parse takes 5-10x more cycles → larger fleet
- **Latency**: 5-15ms parse time vs < 1ms binary

For internal hot paths, binary wins. For public APIs, JSON is worth the cost.

---

## Cheat Sheet

```
Public API (REST):           JSON (orjson)
Internal RPC:                Protobuf (gRPC)
Kafka events:                Avro (Schema Registry)
Cache values:                MessagePack
Config files:                JSON / YAML
Mobile API:                  Protobuf / MessagePack
Data lake:                   Parquet (with Avro schema)
Game / IoT (latency):        FlatBuffers
MongoDB:                     BSON
Logs (text):                 JSON Lines (newline-delimited)
```

---

## Related Docs
- [23_Communication_Protocols.md](23_Communication_Protocols.md) — HTTP/gRPC
- [Phase3_gRPC/](../../Phase3_gRPC/) — gRPC + Protobuf practical
- [Phase2_Kafka/](../../Phase2_Kafka/) — Avro with Kafka
- [Phase3_API_Design/19_asyncapi_event_driven_spec.md](../../Phase3_API_Design/19_asyncapi_event_driven_spec.md) — AsyncAPI specs

## External References
- Protobuf docs: https://protobuf.dev
- Apache Avro: https://avro.apache.org
- MessagePack: https://msgpack.org
- Confluent Schema Registry: https://docs.confluent.io/platform/current/schema-registry
- FlatBuffers: https://flatbuffers.dev
