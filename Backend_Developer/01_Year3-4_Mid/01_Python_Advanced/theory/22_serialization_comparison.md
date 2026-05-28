# Serialization Deep — JSON vs orjson vs msgpack vs pickle vs Protobuf

## Quick Concepts

**WHAT:**
- **JSON** = Standard, human-readable, text format
- **orjson** = Fast JSON (Rust-based, drop-in replacement)
- **ujson** = Older fast JSON (C-based)
- **msgpack** = Binary, smaller than JSON, language-agnostic
- **pickle** = Python-specific binary (DANGEROUS for untrusted data)
- **Protocol Buffers** = Schema-based binary (gRPC)
- **MessagePack** = Same as msgpack
- **BSON** = MongoDB binary format
- **CBOR** = Concise Binary Object Representation

**WHY format matters:**
- Wrong choice = 10x performance hit
- Some are insecure (pickle)
- Schema vs schema-less trade-offs
- Network bandwidth costs

**HOW formats compare:**

```
┌──────────────┬─────────┬──────────┬──────────┬──────────┬────────────┐
│ Format       │ Speed   │ Size     │ Human    │ Schema   │ Cross-lang │
├──────────────┼─────────┼──────────┼──────────┼──────────┼────────────┤
│ json         │ Medium  │ Large    │ Yes      │ Schemaless│ Yes        │
│ orjson       │ Fastest │ Large    │ Yes      │ Schemaless│ Yes        │
│ ujson        │ Fast    │ Large    │ Yes      │ Schemaless│ Yes        │
│ msgpack      │ Fast    │ Medium   │ No       │ Schemaless│ Yes        │
│ pickle       │ Fast    │ Small    │ No       │ Schemaless│ Python only│
│ Protobuf     │ Fastest │ Smallest │ No       │ Required │ Yes (gen)  │
│ Avro         │ Fast    │ Small    │ No       │ Required │ Yes        │
│ BSON         │ Medium  │ Medium   │ No       │ Schemaless│ Yes        │
└──────────────┴─────────┴──────────┴──────────┴──────────┴────────────┘
```

---

## Interview Questions & Answers

### Q1: json vs orjson — which to use?

**Answer:**

**WHAT:**
- **json** (stdlib) = Python's built-in JSON
- **orjson** = Rust-based, 2-10x faster

**HOW — Comparison:**

```python
import json
import orjson
import time

data = {"users": [{"id": i, "name": f"User{i}"} for i in range(10000)]}


# stdlib json
start = time.time()
for _ in range(100):
    encoded = json.dumps(data)
    decoded = json.loads(encoded)
elapsed_json = time.time() - start


# orjson
start = time.time()
for _ in range(100):
    encoded = orjson.dumps(data)  # ⭐ Returns bytes (not str)
    decoded = orjson.loads(encoded)
elapsed_orjson = time.time() - start


print(f"json:   {elapsed_json:.2f}s")
print(f"orjson: {elapsed_orjson:.2f}s")
# Typical: orjson 3-5x faster
```

**HOW — orjson features:**

```python
import orjson

# ⭐ Returns BYTES (not str like stdlib)
data = orjson.dumps({"x": 1})
print(type(data))  # <class 'bytes'>

# Decode
parsed = orjson.loads(data)


# ⭐ Native datetime support
from datetime import datetime
data = {"timestamp": datetime.now()}
encoded = orjson.dumps(data)
# Output: {"timestamp": "2024-01-15T10:30:45.123456"}


# ⭐ Native UUID, Decimal
from uuid import uuid4
from decimal import Decimal

data = {
    "id": uuid4(),
    "amount": Decimal("99.99"),
}
encoded = orjson.dumps(data, option=orjson.OPT_PASSTHROUGH_SUBCLASS)


# ⭐ Pretty print
encoded = orjson.dumps(data, option=orjson.OPT_INDENT_2)


# ⭐ Sort keys (deterministic)
encoded = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)


# ⭐ NaN/Infinity (RFC compliant: rejects)
# orjson.dumps({"x": float("nan")})  # Raises TypeError (correct!)
# json.dumps({"x": float("nan")})    # Returns "NaN" (NOT valid JSON)
```

**HOW — Drop-in replacement:**

```python
# Replace stdlib usage everywhere
import orjson

# Where json.dumps used
def to_json(data):
    return orjson.dumps(data).decode()  # bytes → str

# Where json.loads used
def from_json(text):
    return orjson.loads(text)


# FastAPI integration
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

app = FastAPI(default_response_class=ORJSONResponse)
# ⭐ All responses use orjson (faster)
```

---

### Q2: msgpack — when to use binary JSON?

**Answer:**

**WHAT:** Binary serialization (like JSON but binary, smaller, faster).

**WHY:**
- 30-50% smaller than JSON
- 2-5x faster encode/decode
- Schema-less (like JSON)
- Cross-language support

**WHY NOT JSON:**
- JSON keys repeated (waste space)
- Numbers as strings ("123" = 3 bytes, int = 4 bytes)
- No native binary support (need base64)

**HOW — msgpack basic:**

```python
# pip install msgpack

import msgpack
import json

data = {
    "users": [{"id": i, "name": f"User{i}", "active": True} for i in range(1000)]
}

# Encode
msg_bytes = msgpack.packb(data)
json_bytes = json.dumps(data).encode()

print(f"msgpack: {len(msg_bytes)} bytes")
print(f"json:    {len(json_bytes)} bytes")
# Typical: msgpack 30-50% smaller


# Decode
data2 = msgpack.unpackb(msg_bytes)
```

**HOW — Streaming msgpack:**

```python
import msgpack

# ⭐ Write stream (one message per line)
with open("data.msgpack", "wb") as f:
    packer = msgpack.Packer()
    for item in items:
        f.write(packer.pack(item))


# ⭐ Read stream
with open("data.msgpack", "rb") as f:
    unpacker = msgpack.Unpacker(f)
    for item in unpacker:
        process(item)
```

**HOW — Use cases:**

```python
# 1. Redis cache (smaller = less memory)
import msgpack
import redis

r = redis.Redis()

# Store
user = {"id": 1, "name": "Alice", "preferences": {...}}
r.set("user:1", msgpack.packb(user))

# Retrieve
data = msgpack.unpackb(r.get("user:1"))


# 2. Inter-service communication (smaller bandwidth)
def send_to_worker(task):
    queue.put(msgpack.packb(task))

def worker():
    while True:
        task = msgpack.unpackb(queue.get())
        process(task)


# 3. File storage (smaller files)
def save_records(path, records):
    with open(path, "wb") as f:
        msgpack.pack(records, f)


# 4. WebSocket binary frames
async def ws_handler(ws):
    async for message in ws:
        data = msgpack.unpackb(message)
        await process(data)
```

**HOW — Custom types:**

```python
import msgpack
from datetime import datetime

# Encoder
def default(obj):
    if isinstance(obj, datetime):
        return {"__datetime__": True, "value": obj.isoformat()}
    raise TypeError

# Decoder
def object_hook(obj):
    if "__datetime__" in obj:
        return datetime.fromisoformat(obj["value"])
    return obj


# Use
data = {"timestamp": datetime.now()}
encoded = msgpack.packb(data, default=default)
decoded = msgpack.unpackb(encoded, object_hook=object_hook)
```

---

### Q3: pickle — when DANGEROUS, when OK?

**Answer:**

**WHAT:** Python-specific binary serialization.

**WHY DANGEROUS:**
```python
# ⚠️ pickle.loads() can execute ARBITRARY CODE
# Loading untrusted pickle = Remote Code Execution

malicious_pickle = b'\x80\x04...'  # crafted by attacker
data = pickle.loads(malicious_pickle)  # ⚠️ EXECUTES code!
```

**HOW — Safe uses:**

```python
import pickle

# ✅ OK: Internal data (you trust the source)
# - Caching computed values
# - Storing model weights (NumPy, sklearn)
# - IPC between trusted processes

# Save model
import pickle
with open("model.pkl", "wb") as f:
    pickle.dump(model, f)

# Load (only if you wrote the file)
with open("model.pkl", "rb") as f:
    model = pickle.load(f)
```

**❌ NEVER do these:**

```python
# ❌ Loading from network
data = pickle.loads(network_data)  # ⚠️ RCE risk

# ❌ Loading from user uploads
user_file = request.files["data"]
data = pickle.load(user_file)  # ⚠️ RCE risk

# ❌ Loading from cookies
data = pickle.loads(base64.b64decode(cookie))  # ⚠️ RCE risk

# ❌ Loading from message queue (unless verified)
data = pickle.loads(redis.get("user_data"))  # ⚠️ If Redis compromised, RCE
```

**HOW — Safer alternatives:**

```python
# Instead of pickle for untrusted data:

# 1. JSON for simple types
import json
data = json.dumps(simple_data)

# 2. msgpack for binary needs (no code execution risk)
import msgpack
data = msgpack.packb(complex_data)

# 3. Pydantic for typed data
from pydantic import BaseModel
class User(BaseModel):
    id: int
    name: str

user_json = user.model_dump_json()  # Safe
user = User.model_validate_json(user_json)  # Safe

# 4. For numpy arrays specifically:
import numpy as np
np.save("array.npy", arr)  # Safer than pickle
arr = np.load("array.npy")
```

**HOW — Pickle with HMAC (sign + verify):**

```python
import pickle
import hmac
import hashlib

SECRET = b"signing-key"


def safe_pickle_dumps(obj) -> bytes:
    """Pickle + sign."""
    data = pickle.dumps(obj)
    signature = hmac.new(SECRET, data, hashlib.sha256).digest()
    return signature + data


def safe_pickle_loads(blob: bytes):
    """Verify signature THEN unpickle."""
    signature, data = blob[:32], blob[32:]
    expected = hmac.new(SECRET, data, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Signature mismatch — pickle data tampered!")
    return pickle.loads(data)


# Even with signing, prefer JSON/msgpack when possible
```

---

### Q4: Protocol Buffers — schema-based?

**Answer:**

**WHAT:** Google's binary format with required schema.

**WHY:**
- Smallest size (typically 30-50% of JSON)
- Fastest parsing
- Schema evolution (backward/forward compatible)
- Cross-language (codegen)
- Used by gRPC

**HOW — Define schema (.proto file):**

```protobuf
// user.proto
syntax = "proto3";

message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
  bool is_active = 4;
}

message UserList {
  repeated User users = 1;
}
```

**HOW — Generate Python code:**

```bash
# Install
pip install protobuf grpcio-tools

# Generate
python -m grpc_tools.protoc \
    -I . \
    --python_out=. \
    --pyi_out=. \
    user.proto

# Creates:
# user_pb2.py     (generated code)
# user_pb2.pyi    (type stubs)
```

**HOW — Use in code:**

```python
import user_pb2

# Create
user = user_pb2.User(id=1, name="Alice", email="a@x.com", is_active=True)

# Serialize
encoded = user.SerializeToString()
print(f"Size: {len(encoded)} bytes")

# Deserialize
user2 = user_pb2.User()
user2.ParseFromString(encoded)
print(user2.name)


# Lists
user_list = user_pb2.UserList()
user_list.users.append(user)
user_list.users.append(user_pb2.User(id=2, name="Bob"))

encoded = user_list.SerializeToString()
```

**HOW — Size comparison:**

```python
import json
import msgpack
import user_pb2

user_data = {
    "id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "is_active": True,
}

# JSON
json_bytes = json.dumps(user_data).encode()
print(f"JSON: {len(json_bytes)} bytes")  # ~80 bytes

# MessagePack
msg_bytes = msgpack.packb(user_data)
print(f"msgpack: {len(msg_bytes)} bytes")  # ~50 bytes

# Protobuf
user = user_pb2.User(**user_data)
pb_bytes = user.SerializeToString()
print(f"Protobuf: {len(pb_bytes)} bytes")  # ~30 bytes
```

---

### Q5: BSON — when use over JSON?

**Answer:**

**WHAT:** Binary JSON used by MongoDB.

**WHY:**
- MongoDB native format
- Native types (ObjectId, Date, Binary)
- Slightly faster than JSON

**HOW:**

```python
# pip install bson (or use pymongo)

import bson
from bson import ObjectId
from datetime import datetime

data = {
    "_id": ObjectId(),  # MongoDB native ID
    "name": "Alice",
    "created_at": datetime.now(),
    "tags": ["python", "developer"],
}

# Encode
encoded = bson.encode(data)
print(f"Size: {len(encoded)} bytes")

# Decode
decoded = bson.decode(encoded)
print(decoded["name"])

# Use case: store in MongoDB
import pymongo
client = pymongo.MongoClient()
client["mydb"]["users"].insert_one(data)  # BSON internally
```

---

### Q6: Avro — schema registry use case?

**Answer:**

**WHAT:** Schema-based serialization with registry.

**WHY:**
- Kafka ecosystem standard
- Schema evolution support
- Compact binary
- Self-describing (schema in header)

**HOW:**

```python
# pip install fastavro

import fastavro
from io import BytesIO

# Define schema
schema = {
    "type": "record",
    "name": "User",
    "fields": [
        {"name": "id", "type": "int"},
        {"name": "name", "type": "string"},
        {"name": "email", "type": "string"},
        {"name": "is_active", "type": "boolean", "default": True},
    ],
}

# Serialize
data = [
    {"id": 1, "name": "Alice", "email": "a@x.com", "is_active": True},
    {"id": 2, "name": "Bob", "email": "b@x.com", "is_active": False},
]

with open("users.avro", "wb") as f:
    fastavro.writer(f, schema, data)


# Deserialize
with open("users.avro", "rb") as f:
    reader = fastavro.reader(f)
    for record in reader:
        print(record)
```

---

### Q7: Performance benchmark — real numbers?

**Answer:**

```python
import json
import orjson
import ujson
import msgpack
import pickle
import time

# Test data
data = {
    "users": [
        {
            "id": i,
            "name": f"User{i}",
            "email": f"user{i}@example.com",
            "age": 20 + (i % 50),
            "active": i % 2 == 0,
            "tags": ["python", "developer"],
            "scores": [random() for _ in range(10)],
        }
        for i in range(1000)
    ]
}


def benchmark(name, encode_fn, decode_fn, iterations=100):
    # Warmup
    for _ in range(10):
        encoded = encode_fn(data)
        decode_fn(encoded)

    # Measure encode
    start = time.perf_counter()
    for _ in range(iterations):
        encoded = encode_fn(data)
    encode_time = time.perf_counter() - start

    # Measure decode
    start = time.perf_counter()
    for _ in range(iterations):
        decode_fn(encoded)
    decode_time = time.perf_counter() - start

    size = len(encoded) if isinstance(encoded, (bytes, str)) else 0
    print(f"{name:12} encode: {encode_time*1000/iterations:.2f}ms "
          f"decode: {decode_time*1000/iterations:.2f}ms "
          f"size: {size:,}")


benchmark("json (stdlib)", json.dumps, json.loads)
benchmark("orjson", orjson.dumps, orjson.loads)
benchmark("ujson", ujson.dumps, ujson.loads)
benchmark("msgpack", msgpack.packb, msgpack.unpackb)
benchmark("pickle", pickle.dumps, pickle.loads)


# Typical results:
# json (stdlib)  encode: 12.50ms decode: 8.30ms  size: 350,000
# orjson         encode: 2.10ms  decode: 3.50ms  size: 320,000
# ujson          encode: 5.50ms  decode: 4.80ms  size: 350,000
# msgpack        encode: 3.00ms  decode: 4.20ms  size: 220,000
# pickle         encode: 4.50ms  decode: 5.10ms  size: 280,000
```

---

### Q8: Custom JSON encoders?

**Answer:**

**WHAT:** Handle non-JSON types (datetime, Decimal, UUID).

**HOW — stdlib JSON:**

```python
import json
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)  # Or float(obj) — careful with precision
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


data = {
    "timestamp": datetime.now(),
    "amount": Decimal("99.99"),
    "id": UUID("12345678-1234-5678-1234-567812345678"),
}

json_str = json.dumps(data, cls=CustomEncoder)
print(json_str)
```

**HOW — Custom decoder:**

```python
def custom_decoder(obj):
    if "_type" in obj:
        if obj["_type"] == "datetime":
            return datetime.fromisoformat(obj["value"])
        if obj["_type"] == "decimal":
            return Decimal(obj["value"])
    return obj


# Encode with type info
def encode_with_types(obj):
    if isinstance(obj, datetime):
        return {"_type": "datetime", "value": obj.isoformat()}
    if isinstance(obj, Decimal):
        return {"_type": "decimal", "value": str(obj)}
    raise TypeError


data = {"timestamp": datetime.now()}
encoded = json.dumps(data, default=encode_with_types)
decoded = json.loads(encoded, object_hook=custom_decoder)
```

**HOW — Pydantic handles everything:**

```python
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from uuid import UUID

class Order(BaseModel):
    id: UUID
    amount: Decimal
    created_at: datetime

order = Order(id=UUID("..."), amount=Decimal("99.99"), created_at=datetime.now())

# ⭐ Pydantic handles all types automatically
json_str = order.model_dump_json()
order2 = Order.model_validate_json(json_str)
```

---

### Q9: Streaming JSON — large files?

**Answer:**

**WHAT:** Parse JSON incrementally (don't load all into memory).

**WHY:**
- Large files (GB+)
- API responses with streaming
- Memory-constrained environments

**HOW — ijson (incremental JSON):**

```python
# pip install ijson

import ijson

# ⭐ Stream parse — only one object in memory at a time
def stream_users(filepath):
    with open(filepath, "rb") as f:
        # Parse items in "users" array
        objects = ijson.items(f, "users.item")
        for user in objects:
            yield user


# Usage
for user in stream_users("huge_file.json"):
    process(user)
    # Memory stays low even for 100GB files
```

**HOW — JSON Lines (NDJSON):**

```python
# Format: one JSON object per line
# users.jsonl:
# {"id": 1, "name": "Alice"}
# {"id": 2, "name": "Bob"}

import json

# Write
def write_ndjson(items, path):
    with open(path, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


# Read (streaming)
def read_ndjson(path):
    with open(path) as f:
        for line in f:
            yield json.loads(line)


# Async streaming with httpx
import httpx

async def stream_api():
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "https://api.example.com/users.jsonl") as response:
            async for line in response.aiter_lines():
                user = json.loads(line)
                yield user
```

---

### Q10: Decision matrix — which format when?

**Answer:**

| Need | Use | Why |
|---|---|---|
| **REST API JSON** | orjson (or stdlib) | Standard, debuggable |
| **High-performance API** | orjson + FastAPI | 3-5x faster |
| **Internal microservices** | Protobuf or msgpack | Smaller, faster |
| **Public API** | JSON | Universal compat |
| **Browser ↔ Server** | JSON | Native browser support |
| **Cache (Redis)** | msgpack | Smaller memory |
| **MongoDB** | BSON (auto) | Native format |
| **gRPC** | Protobuf | Required |
| **Kafka events** | Avro + Schema Registry | Schema evolution |
| **Cross-language** | Protobuf or msgpack | Language-neutral |
| **Python-only internal** | pickle (trusted only!) | Native, supports all types |
| **Large files streaming** | NDJSON or msgpack | Incremental |
| **WebSocket binary** | msgpack | Compact |
| **Mobile apps** | Protobuf | Battery (parsing speed) |
| **Logs** | JSON (NDJSON) | Searchable |
| **Config files** | YAML or TOML | Human-friendly |

---

## Serialization Checklist

```markdown
### Choice
- [ ] Default: JSON (orjson for speed)
- [ ] Internal: msgpack or Protobuf for size
- [ ] Schema needed: Protobuf or Avro
- [ ] NEVER pickle for untrusted data

### Performance
- [ ] orjson for FastAPI (3-5x faster)
- [ ] msgpack for Redis cache
- [ ] Streaming for files > 100MB
- [ ] NDJSON for log-like data

### Security
- [ ] No pickle from network
- [ ] No pickle from user uploads
- [ ] Sign untrusted data (HMAC)
- [ ] Validate after deserialize (Pydantic)

### Types
- [ ] Use Pydantic for type-safe JSON
- [ ] Custom encoders for datetime/Decimal/UUID
- [ ] Don't lose precision (Decimal as string)
- [ ] Handle None/null consistently

### Production
- [ ] Schema versioning (Protobuf/Avro)
- [ ] Forward/backward compat
- [ ] Schema registry (Kafka)
- [ ] Compression for large payloads (gzip)
```

---

## Quick Code Recipes

```python
# 1. Fastest JSON API response
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
app = FastAPI(default_response_class=ORJSONResponse)


# 2. Compact Redis cache
import msgpack
def cache_set(key, value, ttl=300):
    r.setex(key, ttl, msgpack.packb(value))


# 3. Safe pickle (signed)
def safe_pickle(obj, secret):
    data = pickle.dumps(obj)
    sig = hmac.new(secret, data, hashlib.sha256).digest()
    return sig + data


# 4. NDJSON streaming
def stream_jsonl(file_path):
    with open(file_path) as f:
        for line in f:
            yield json.loads(line)


# 5. Datetime in JSON
import orjson
encoded = orjson.dumps({"now": datetime.now()})  # Auto handles datetime
```
