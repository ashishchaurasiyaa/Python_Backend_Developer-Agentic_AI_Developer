# gRPC Performance Tuning — Keepalive, Compression, Pooling, HTTP/2

## Quick Concepts

**WHAT:**
- **Keepalive** = TCP-level pings to detect dead connections
- **Connection pooling** = reuse channels across requests
- **Compression** = gzip messages to reduce bandwidth
- **HTTP/2 multiplexing** = many RPCs over single TCP connection
- **Flow control** = backpressure mechanism for streaming
- **Message size limits** = max bytes per RPC

**WHY performance tuning matters:**
- Default settings often suboptimal for production
- Connection drops cause cascading failures
- Wrong settings = wasted CPU/memory/bandwidth
- Streaming without flow control = OOM crashes

**HOW HTTP/2 differs from HTTP/1.1:**
```
HTTP/1.1: Each request = new connection (or queue on existing)
          ↓
          1 request → 1 TCP connection (or head-of-line block)

HTTP/2:   Multiple requests share single connection
          ↓
          Streams multiplex over 1 TCP → much faster
          ↓
          BUT: 1 dead connection = all streams die (need keepalive)
```

---

## Interview Questions & Answers

### Q1: Keepalive settings kya hain? Production me kaise tune karein?

**Answer:**

**WHAT:** Periodic pings to detect dead connections (especially across NAT/firewalls).

**WHY needed:**
- TCP connections can be silently dropped by NAT/firewalls (idle timeout)
- gRPC long-lived connections = vulnerable
- Without keepalive: client thinks connection alive, requests hang until timeout
- With keepalive: detect dead connection in 30s, reconnect quickly

**HOW — Server keepalive config:**

```python
import grpc

server = grpc.aio.server(
    options=[
        # ⭐ Send keepalive ping every 30s if no activity
        ("grpc.keepalive_time_ms", 30000),

        # ⭐ Connection dead if no ping ack in 10s
        ("grpc.keepalive_timeout_ms", 10000),

        # ⭐ Allow keepalive pings even with no active calls
        ("grpc.keepalive_permit_without_calls", True),

        # ⭐ Max pings without data (prevents abuse)
        ("grpc.http2.max_pings_without_data", 0),  # 0 = unlimited

        # ⭐ Min ping interval from clients (server enforces)
        ("grpc.http2.min_time_between_pings_ms", 10000),

        # ⭐ Min ping interval when no active streams
        ("grpc.http2.min_ping_interval_without_data_ms", 5000),
    ]
)
```

**HOW — Client keepalive config:**

```python
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        # Same client-side options
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
        ("grpc.keepalive_permit_without_calls", True),

        # ⭐ Auto-reconnect on connection loss
        ("grpc.enable_retries", 1),
    ]
)
```

**HOW — Common keepalive scenarios:**

| Scenario | Server keepalive_time_ms | Notes |
|---|---|---|
| **Public internet** | 30000 (30s) | NAT timeout ~60s, ping at 30s catches it |
| **Internal cluster** | 60000 (1min) | Less NAT, can be longer |
| **AWS ALB** | 30000 | ALB idle_timeout 60s default |
| **High-frequency RPCs** | 120000 (2min) | Less overhead, requests keep alive |
| **Long-running streams** | 10000 (10s) | Detect breaks quickly |

**Gotcha — too aggressive keepalive:**
```python
# ❌ DON'T: ping every 1 second
("grpc.keepalive_time_ms", 1000),
# Server may close connection: "ENHANCE_YOUR_CALM" error
# (gRPC rate-limits keepalive abuse)
```

---

### Q2: Connection pooling — kab aur kaise?

**Answer:**

**WHAT:** Reuse gRPC channel across requests instead of creating new.

**WHY:**
- ❌ Creating channel = TCP handshake + TLS = 100-300ms
- ✅ Reusing channel = 0ms (HTTP/2 multiplexing)
- ❌ Many channels = many connections = resource exhaustion

**HOW — Single channel per service (Recommended):**

```python
# ❌ BAD: New channel per request
async def call_user_service():
    channel = grpc.aio.secure_channel("user-service:50051", creds)
    stub = UserServiceStub(channel)
    response = await stub.GetUser(...)
    await channel.close()   # Wasteful


# ✅ GOOD: Module-level singleton channel
class UserServiceClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_channel()
        return cls._instance

    def _init_channel(self):
        self.channel = grpc.aio.secure_channel(
            "user-service:50051",
            credentials,
            options=[
                ("grpc.keepalive_time_ms", 30000),
                ("grpc.keepalive_timeout_ms", 10000),
                ("grpc.lb_policy_name", "round_robin"),
                # ⭐ HTTP/2 max concurrent streams
                ("grpc.http2.max_concurrent_streams", 100),
            ]
        )
        self.stub = UserServiceStub(self.channel)

    async def get_user(self, user_id):
        return await self.stub.GetUser(GetUserRequest(user_id=user_id))


# Usage
client = UserServiceClient()
user = await client.get_user(123)
```

**HOW — Channel pool (when single channel isn't enough):**

```python
import asyncio
from itertools import cycle

class ChannelPool:
    """
    INTERVIEW: Use channel pool when:
    - Single channel becomes bottleneck (100k+ RPS)
    - Need to isolate failures
    - HTTP/2 stream limit reached
    """
    def __init__(self, target: str, pool_size: int = 5):
        self.channels = [
            grpc.aio.secure_channel(target, credentials, options=[...])
            for _ in range(pool_size)
        ]
        self.stubs = [UserServiceStub(ch) for ch in self.channels]
        self._cycle = cycle(self.stubs)
        self._lock = asyncio.Lock()

    async def get_stub(self):
        async with self._lock:
            return next(self._cycle)

    async def close(self):
        for ch in self.channels:
            await ch.close()


# Usage
pool = ChannelPool("user-service:50051", pool_size=5)
stub = await pool.get_stub()
user = await stub.GetUser(GetUserRequest(user_id=123))
```

**Channel pool size guidance:**
```
RPS estimate → channel pool size:
< 1000 RPS    → 1 channel (HTTP/2 multiplexes plenty)
1k-10k RPS    → 2-3 channels
10k-100k RPS  → 5-10 channels
> 100k RPS    → Consider service mesh (Envoy/Linkerd)
```

---

### Q3: Compression — kab kab use karein? gzip vs others?

**Answer:**

**WHAT:** Compress message payload before sending.

**WHY use compression:**
- ✅ Reduce bandwidth (especially text/JSON-like data)
- ✅ Faster transmission over slow networks
- ❌ CPU cost for compress/decompress
- ❌ Small messages: overhead exceeds savings

**WHY NOT compress:**
- Binary data (images, video) → already compressed
- Small messages (< 1KB) → overhead > savings
- Local network (low latency) → CPU more expensive than bandwidth

**HOW — Server-side default compression:**

```python
import grpc

server = grpc.aio.server(
    compression=grpc.Compression.Gzip,  # ⭐ Default for all responses
    options=[]
)

# Or per-message control in handler
async def GetUser(self, request, context):
    await context.set_compression(grpc.Compression.Gzip)
    return user_pb2.User(...)
```

**HOW — Client-side compression:**

```python
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        # ⭐ Send compressed requests
        ("grpc.default_compression_algorithm",
            grpc.Compression.Gzip.value),
        # Accept compressed responses
        ("grpc.default_compression_level", 3),  # 1-9, higher = more CPU
    ]
)

# Per-call override
response = await stub.GetUser(
    GetUserRequest(user_id=123),
    compression=grpc.Compression.Gzip
)
```

**Compression algorithm comparison:**

| Algorithm | Ratio | Speed | When to use |
|---|---|---|---|
| **None** | 1x | Fastest | Small msg, low latency, binary data |
| **gzip** | 3-5x | Medium | General purpose, text data |
| **deflate** | 3-5x | Medium | Like gzip but no header overhead |

**Custom compression decision logic:**

```python
class SmartCompressionInterceptor:
    """
    Compress only when payload > threshold.
    """
    SIZE_THRESHOLD = 1024  # 1 KB

    async def intercept(self, call, request):
        if request.ByteSize() > self.SIZE_THRESHOLD:
            await call.set_compression(grpc.Compression.Gzip)
        return await call.continue_()
```

---

### Q4: Message size limits — kab badhane chahiye?

**Answer:**

**WHAT:** Max bytes per RPC message (default 4 MB).

**WHY default 4 MB:**
- Prevents accidental DoS (huge messages eating memory)
- Forces design discipline (use streaming for big data)

**HOW — Increase limits:**

```python
# Server side
server = grpc.aio.server(
    options=[
        ("grpc.max_receive_message_length", 50 * 1024 * 1024),  # 50 MB
        ("grpc.max_send_message_length", 50 * 1024 * 1024),
    ]
)

# Client side (same options)
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ("grpc.max_send_message_length", 50 * 1024 * 1024),
    ]
)
```

**WHEN to increase vs WHEN to use streaming:**

| Scenario | Recommended Approach |
|---|---|
| Image upload (5 MB avg) | Increase limit to 10 MB |
| Video upload (100 MB+) | ⭐ Client streaming with chunks |
| Batch DB query (1000 rows) | Server streaming (one row at a time) |
| ML model inference (large input) | Increase limit + compression |
| Log streaming | Bidirectional streaming |

**HOW — Streaming for large files:**

```protobuf
service FileService {
  // ❌ DON'T: Single huge message
  // rpc UploadFile(UploadRequest) returns (UploadResponse);

  // ✅ DO: Client streaming with chunks
  rpc UploadFileChunked(stream FileChunk) returns (UploadResponse);
}

message FileChunk {
  oneof data {
    FileMetadata metadata = 1;  // First message
    bytes chunk = 2;             // Subsequent chunks
  }
}

message FileMetadata {
  string filename = 1;
  string content_type = 2;
  int64 total_size = 3;
}

message UploadResponse {
  string file_id = 1;
  string url = 2;
}
```

```python
# Client
async def upload_file(stub, file_path: str):
    async def chunk_generator():
        # First: metadata
        yield FileChunk(metadata=FileMetadata(
            filename="video.mp4",
            content_type="video/mp4",
            total_size=os.path.getsize(file_path)
        ))

        # Then: chunks of 64 KB
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield FileChunk(chunk=chunk)

    response = await stub.UploadFileChunked(chunk_generator())
    return response.file_id
```

---

### Q5: HTTP/2 flow control kya hai? Streaming me kyu matter karta hai?

**Answer:**

**WHAT:** Mechanism to prevent fast sender from overwhelming slow receiver.

**WHY for gRPC streaming:**
```
Without flow control:
Server streams 10,000 records/sec
Client processes 100/sec (slow)
→ Records pile up in client buffer
→ Memory exhaustion → OOM
```

**HOW HTTP/2 flow control works:**
```
1. Receiver advertises "window" (e.g., 64 KB)
2. Sender can send up to window size
3. Receiver acks bytes consumed (window updates)
4. Sender pauses if window = 0
```

**HOW — Configure window size:**

```python
# Larger windows = higher throughput, more memory
server = grpc.aio.server(
    options=[
        # Initial flow control window per stream
        ("grpc.http2.write_buffer_size", 64 * 1024),

        # Max frame size
        ("grpc.max_metadata_size", 16 * 1024),
    ]
)
```

**HOW — Application-level backpressure (better than HTTP/2 only):**

```python
class UserServiceServicer:
    async def ListUsers(self, request, context):
        """
        Server streaming with application-level backpressure.
        """
        async for user in stream_users_from_db(request.page_size):
            # ⭐ Check if client cancelled (avoids buffering)
            if context.cancelled():
                break

            try:
                # Send with timeout to detect slow client
                yield self._user_to_proto(user)
            except grpc.RpcError:
                # Client gave up
                break

            # ⭐ Optional: throttle if client is slow
            # await asyncio.sleep(0.01)  # 100 records/sec max
```

**HOW — Client consumer with backpressure:**

```python
async def consume_users_with_backpressure(stub):
    async for user in stub.ListUsers(ListUsersRequest(page_size=10000)):
        # ⭐ Process slowly — server pauses sending (via HTTP/2 flow control)
        await process_user(user)  # If this is slow, server waits
```

---

### Q6: Worker thread tuning — async vs sync server?

**Answer:**

**WHAT:** gRPC Python has 2 server types:
- `grpc.server()` — sync, uses ThreadPoolExecutor
- `grpc.aio.server()` — async, uses asyncio

**WHY async preferred:**
- ✅ Higher concurrency (10k+ vs 100s threads)
- ✅ Lower memory (no thread stack overhead)
- ✅ Better for I/O bound (most gRPC services)
- ❌ Slightly more complex code

**HOW — Sync server tuning:**

```python
from concurrent import futures
import grpc

server = grpc.server(
    futures.ThreadPoolExecutor(
        max_workers=100,    # ⭐ Tune based on concurrent RPCs
    ),
    options=[...]
)
```

**Worker count formula (sync):**
```
Use case             | max_workers
---------------------|------------
CPU bound            | CPU cores
I/O bound (DB calls) | CPU cores * 5-10
Mixed                | CPU cores * 3
```

**HOW — Async server (recommended):**

```python
import asyncio
import grpc

async def serve():
    server = grpc.aio.server(
        # ⭐ migration_thread_pool for blocking calls if needed
        migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10),
        options=[
            # Max concurrent streams per connection
            ("grpc.http2.max_concurrent_streams", 1000),
        ]
    )

    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")

    await server.start()
    await server.wait_for_termination()

asyncio.run(serve())
```

**HOW — Mixing async + blocking (when forced):**

```python
import asyncio

class HybridServicer:
    async def GetUser(self, request, context):
        # ⭐ Run blocking code in thread pool (don't block event loop)
        result = await asyncio.get_event_loop().run_in_executor(
            None,                       # Use default executor
            blocking_db_call,           # Blocking function
            request.user_id             # Args
        )
        return self._user_to_proto(result)
```

---

### Q7: Profiling gRPC server bottlenecks?

**Answer:**

**WHAT:** Identify slow parts of gRPC service.

**HOW — Tools + techniques:**

**1. CPU profiling with py-spy (no restart needed)**

```bash
# Install py-spy
pip install py-spy

# Profile running process
sudo py-spy record -o profile.svg --pid $(pgrep -f "python.*server") --duration 60

# Live flame graph
sudo py-spy top --pid <PID>
```

**2. Memory profiling**

```bash
pip install memray

# Track memory
memray run --output mem.bin server.py
memray flamegraph mem.bin --output mem.html
```

**3. gRPC-specific tracing**

```python
# Wrap handler with timing
import time
from prometheus_client import Histogram

HANDLER_DURATION = Histogram(
    "grpc_handler_duration_seconds",
    "Time spent in handler",
    ["method", "stage"]
)

class TimingServicer:
    async def GetUser(self, request, context):
        # Validation phase
        with HANDLER_DURATION.labels("GetUser", "validation").time():
            self._validate(request)

        # DB phase
        with HANDLER_DURATION.labels("GetUser", "db").time():
            user = await db.get_user(request.user_id)

        # Serialization phase
        with HANDLER_DURATION.labels("GetUser", "serialize").time():
            return self._user_to_proto(user)
```

**4. Async event loop monitoring**

```python
import asyncio

# Detect slow callbacks
asyncio.get_event_loop().slow_callback_duration = 0.1  # 100ms

# Custom debug callback
loop = asyncio.get_event_loop()
loop.set_debug(True)
```

---

### Q8: Production performance benchmarks gRPC ke?

**Answer:**

**Reference numbers** (single Python async gRPC server, 1 vCPU, 2 GB RAM):

| Workload | RPS | p99 latency | Notes |
|---|---|---|---|
| **Echo (no DB)** | 50,000+ | < 1ms | Pure CPU/network |
| **Simple DB read** | 5,000-10,000 | < 50ms | Single SELECT |
| **DB read + cache hit** | 20,000+ | < 5ms | Redis cached |
| **Streaming (small msgs)** | 100,000+ msgs/s | N/A | Single connection |
| **Heavy computation** | 100-1000 | varies | CPU bound |

**Optimization checklist for high RPS:**

```python
# 1. Use async server
server = grpc.aio.server(...)  # NOT grpc.server()

# 2. Connection-level options
options = [
    ("grpc.keepalive_time_ms", 30000),
    ("grpc.http2.max_concurrent_streams", 1000),
    ("grpc.max_receive_message_length", 10 * 1024 * 1024),
]

# 3. Compression for large payloads
compression=grpc.Compression.Gzip

# 4. Connection pooling on client
# (single channel + HTTP/2 multiplexing)

# 5. Tune Python
# - Use uvloop instead of asyncio default
import uvloop
uvloop.install()

# - Use orjson for JSON if needed
# - Use Cython for hot paths

# 6. Profile + optimize hot paths
# py-spy → find bottlenecks → optimize

# 7. Scale horizontally
# Multiple replicas behind L7 LB (Envoy)
```

---

## Performance Tuning Checklist

```markdown
### Connection Management
- [ ] Keepalive enabled (30s ping, 10s timeout)
- [ ] Single channel per downstream (HTTP/2 multiplexing)
- [ ] Channel pooling for very high RPS (10k+)
- [ ] Graceful shutdown with 30s grace period

### Message Handling
- [ ] Compression enabled for payloads > 1KB
- [ ] Max message size set appropriately (not default 4MB)
- [ ] Streaming used for large payloads (instead of single big message)
- [ ] Flow control honored (don't fill buffers)

### Server Tuning
- [ ] Using async server (grpc.aio.server)
- [ ] uvloop installed
- [ ] HTTP/2 max_concurrent_streams = 1000+
- [ ] CPU profiling done (py-spy)
- [ ] No blocking calls in async handlers

### Monitoring
- [ ] Latency histogram by method
- [ ] Active stream count
- [ ] Connection count
- [ ] Memory usage per process
```
