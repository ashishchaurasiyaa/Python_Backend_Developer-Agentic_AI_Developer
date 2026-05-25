# gRPC Streaming Patterns — Long-running, Cancellation, Backpressure

## Quick Concepts

**WHAT:**
- **Server streaming** = 1 request → N responses (e.g., live notifications)
- **Client streaming** = N requests → 1 response (e.g., bulk upload)
- **Bidirectional streaming** = N requests ↔ N responses (e.g., chat)
- **Long-running stream** = hours/days connection (live dashboards)
- **Cancellation** = client/server can abort stream gracefully
- **Backpressure** = slow consumer doesn't crash producer

**WHY streaming patterns matter:**
- Different from REST (no native streaming)
- Long-lived = different failure modes (connection drops, keepalive)
- Resource management critical (memory, goroutines/coroutines)
- Real-time use cases (chat, IoT, live updates) need it

**HOW 4 streaming types map to use cases:**
| Type | Use Cases | Example |
|---|---|---|
| Unary | CRUD operations | GetUser, CreateOrder |
| Server streaming | Live data, large lists | Stock prices, log tailing |
| Client streaming | Bulk ingest | File upload, sensor data |
| Bidirectional | Real-time interaction | Chat, multiplayer games |

---

## Interview Questions & Answers

### Q1: Server streaming long-running connection ka real example?

**Answer:**

**WHAT:** Server sends data continuously over hours/days.

**WHY use cases:**
- Live notification feeds
- Stock price ticks
- Log tailing
- Metrics streams
- IoT sensor data

**HOW — Live notification feed:**

```protobuf
// notifications.proto
service NotificationService {
  // Long-running: keeps connection open until cancelled
  rpc SubscribeNotifications(SubscribeRequest) returns (stream Notification);
}

message SubscribeRequest {
  string user_id = 1;
  repeated string types = 2;     // ["order", "chat", "system"]
}

message Notification {
  string id = 1;
  string type = 2;
  string title = 3;
  string body = 4;
  google.protobuf.Timestamp created_at = 5;
}
```

```python
# server.py
import asyncio
import grpc
import redis.asyncio as redis

class NotificationServicer(notification_pb2_grpc.NotificationServiceServicer):
    def __init__(self):
        self.redis = redis.from_url("redis://localhost:6379/3")

    async def SubscribeNotifications(self, request, context):
        """
        Long-running stream: holds connection until client disconnects.
        Uses Redis pub/sub to push notifications in real-time.
        """
        pubsub = self.redis.pubsub()

        # Subscribe to user's notification channels
        channels = [f"notif:{request.user_id}:{t}" for t in request.types]
        await pubsub.subscribe(*channels)

        try:
            # ⭐ Keep streaming until client cancels
            async for message in pubsub.listen():
                # Check cancellation regularly
                if context.cancelled():
                    break

                if message["type"] != "message":
                    continue

                # Parse message and yield to client
                import json
                data = json.loads(message["data"])
                notification = notification_pb2.Notification(
                    id=data["id"],
                    type=data["type"],
                    title=data["title"],
                    body=data["body"],
                )
                # ⭐ Yield = sends to client
                yield notification

        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            # ⭐ ALWAYS clean up resources
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
```

```python
# client.py
async def listen_for_notifications(stub, user_id):
    request = SubscribeRequest(
        user_id=user_id,
        types=["order", "chat"]
    )

    try:
        async for notification in stub.SubscribeNotifications(request):
            print(f"[{notification.type}] {notification.title}")
            await process_notification(notification)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.CANCELLED:
            print("Subscription cancelled")
        elif e.code() == grpc.StatusCode.UNAVAILABLE:
            print("Server disconnected — reconnect logic needed")
```

**Critical settings for long-running streams:**

```python
# Server
server = grpc.aio.server(
    options=[
        # ⭐ Aggressive keepalive (detect dead clients fast)
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
        ("grpc.keepalive_permit_without_calls", True),

        # ⭐ Allow long-lived connections
        ("grpc.max_connection_idle_ms", 0),    # Never close idle
        ("grpc.max_connection_age_ms", 0),     # Never force close
    ]
)
```

---

### Q2: Stream cancellation — client side aur server side kaise handle karte ho?

**Answer:**

**WHAT:** Either side can abort stream early.

**WHY:**
- Client doesn't need more data (user closed page)
- Server runs out of data (end of result set)
- Resource cleanup needed on both sides

**HOW — Client-side cancellation:**

```python
# Method 1: Break out of async for
async def consume_until_match(stub, target):
    async for item in stub.ListItems(request):
        if item.id == target:
            print(f"Found: {item.name}")
            return  # ⭐ Returning from generator cancels stream
    print("Not found")


# Method 2: Explicit cancellation
async def consume_with_timeout(stub):
    call = stub.ListItems(request)

    try:
        async with asyncio.timeout(5):  # Python 3.11+
            async for item in call:
                yield item
    except asyncio.TimeoutError:
        # ⭐ Cancel the call
        call.cancel()
        raise


# Method 3: Cancellation token
class CancellationToken:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

token = CancellationToken()

async def consume_cancellable(stub, token):
    async for item in stub.ListItems(request):
        if token.cancelled:
            break
        await process(item)

# Cancel from another task
asyncio.create_task(consume_cancellable(stub, token))
await asyncio.sleep(5)
token.cancel()
```

**HOW — Server-side detection:**

```python
class StreamingServicer:
    async def ListItems(self, request, context):
        # ⭐ Method 1: Poll context.cancelled()
        for item in await db.get_items():
            if context.cancelled():
                print("Client cancelled — stopping")
                return  # Gracefully stop

            yield item


    async def WatchUser(self, request, context):
        # ⭐ Method 2: Cancellation callback
        cancelled = asyncio.Event()
        context.add_done_callback(lambda _: cancelled.set())

        while not cancelled.is_set():
            user = await db.get_user(request.user_id)
            yield user
            try:
                # Wait but be interruptible
                await asyncio.wait_for(cancelled.wait(), timeout=5)
            except asyncio.TimeoutError:
                continue  # Continue streaming


    async def StreamLogs(self, request, context):
        # ⭐ Method 3: Catch CancelledError
        try:
            async for log in tail_logs(request.file_path):
                yield log
        except asyncio.CancelledError:
            print("Stream cancelled")
            raise   # Re-raise to maintain cleanup chain
        finally:
            # ⭐ Cleanup always runs
            close_file_handle()
```

**Important: Cleanup order matters:**

```python
async def StreamWithCleanup(self, request, context):
    redis_pubsub = await self.redis.pubsub()
    await redis_pubsub.subscribe("channel")

    try:
        async for msg in redis_pubsub.listen():
            if context.cancelled():
                return
            yield Message(data=msg["data"])
    except Exception as e:
        log.error("stream_error", error=str(e))
        raise
    finally:
        # ⭐ ALWAYS clean up (cancellation, error, or completion)
        await redis_pubsub.unsubscribe("channel")
        await redis_pubsub.close()
```

---

### Q3: Bidirectional streaming — real chat example?

**Answer:**

**WHAT:** Both sides send messages independently.

**WHY:** Real-time interactive (chat, multiplayer, collaborative editing).

**HOW — Chat service:**

```protobuf
service ChatService {
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

message ChatMessage {
  string room_id = 1;
  string user_id = 2;
  string text = 3;
  google.protobuf.Timestamp sent_at = 4;
}
```

```python
# server.py
import asyncio
from collections import defaultdict

class ChatServicer:
    def __init__(self):
        # Room → set of active contexts (for broadcasting)
        self.rooms = defaultdict(set)

    async def Chat(self, request_iterator, context):
        """
        Bidirectional: receive messages from client,
        broadcast to all other clients in same room.
        """
        room_id = None
        user_id = None

        # Task to broadcast received messages to client
        outgoing_queue = asyncio.Queue()

        async def receive_from_client():
            """Receive messages from THIS client, broadcast to room."""
            nonlocal room_id, user_id

            async for msg in request_iterator:
                if context.cancelled():
                    return

                # First message: join room
                if room_id is None:
                    room_id = msg.room_id
                    user_id = msg.user_id
                    self.rooms[room_id].add(outgoing_queue)

                # Broadcast to all OTHER clients in room
                for queue in self.rooms[room_id]:
                    if queue is not outgoing_queue:  # Don't echo back
                        await queue.put(msg)

        # Run receiver in background
        receiver_task = asyncio.create_task(receive_from_client())

        try:
            # ⭐ Yield messages from queue to THIS client
            while not context.cancelled():
                try:
                    msg = await asyncio.wait_for(outgoing_queue.get(), timeout=1)
                    yield msg
                except asyncio.TimeoutError:
                    continue  # Check cancellation, try again
        finally:
            receiver_task.cancel()
            if room_id:
                self.rooms[room_id].discard(outgoing_queue)
```

```python
# client.py
async def chat_session(stub, room_id, user_id, user_input_queue):
    """
    Send user input → server, receive server broadcasts.
    """
    async def request_generator():
        # Initial message (join room)
        yield ChatMessage(room_id=room_id, user_id=user_id, text="<join>")

        # Send user inputs
        while True:
            text = await user_input_queue.get()
            yield ChatMessage(
                room_id=room_id,
                user_id=user_id,
                text=text,
            )

    call = stub.Chat(request_generator())

    # Receive broadcasts
    async for msg in call:
        print(f"[{msg.user_id}]: {msg.text}")
```

---

### Q4: Client streaming for bulk upload — implementation?

**Answer:**

**WHAT:** Client sends many messages, server responds once at end.

**WHY:**
- Large file uploads (chunks)
- Batch event ingestion
- Sensor data buffering

**HOW — Chunked file upload:**

```protobuf
service FileService {
  rpc UploadFile(stream FileChunk) returns (UploadResponse);
}

message FileChunk {
  oneof data {
    FileMetadata metadata = 1;   // First message
    bytes        chunk    = 2;   // Subsequent chunks
  }
}

message FileMetadata {
  string filename = 1;
  string content_type = 2;
  string sha256 = 3;             // For integrity check
}

message UploadResponse {
  string file_id = 1;
  string url = 2;
  int64 size_bytes = 3;
}
```

```python
# server.py
import hashlib

class FileServicer:
    async def UploadFile(self, request_iterator, context):
        """
        Client streaming: receive chunks, return file_id at end.
        """
        metadata = None
        chunks = []
        total_size = 0
        sha256_hasher = hashlib.sha256()

        async for request in request_iterator:
            if context.cancelled():
                return

            # First message must be metadata
            data_type = request.WhichOneof("data")

            if data_type == "metadata":
                if metadata is not None:
                    await context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "Metadata sent twice"
                    )
                metadata = request.metadata

            elif data_type == "chunk":
                if metadata is None:
                    await context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "Chunk received before metadata"
                    )

                chunks.append(request.chunk)
                total_size += len(request.chunk)
                sha256_hasher.update(request.chunk)

                # ⭐ Size limit check
                if total_size > 100 * 1024 * 1024:  # 100 MB
                    await context.abort(
                        grpc.StatusCode.RESOURCE_EXHAUSTED,
                        "File too large"
                    )

        # Verify integrity
        if metadata.sha256 != sha256_hasher.hexdigest():
            await context.abort(
                grpc.StatusCode.DATA_LOSS,
                "SHA256 mismatch"
            )

        # Save file
        file_id = await save_to_storage(b"".join(chunks), metadata.filename)

        # ⭐ Single response at end
        return UploadResponse(
            file_id=file_id,
            url=f"https://files.example.com/{file_id}",
            size_bytes=total_size,
        )
```

```python
# client.py
async def upload_large_file(stub, file_path):
    async def chunk_generator():
        # First: metadata
        sha256 = await compute_sha256(file_path)
        yield FileChunk(metadata=FileMetadata(
            filename=os.path.basename(file_path),
            content_type="application/octet-stream",
            sha256=sha256,
        ))

        # Then: chunks (64 KB each)
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield FileChunk(chunk=chunk)

    response = await stub.UploadFile(chunk_generator())
    print(f"Uploaded: {response.file_id}, size: {response.size_bytes}")
```

---

### Q5: Backpressure — slow consumer kaise handle karein?

**Answer:**

**WHAT:** Mechanism for slow receiver to signal "slow down" to sender.

**WHY:**
```
Fast producer + slow consumer = memory bloat:
Server: 10k msgs/sec → buffer fills → OOM
Client: processes 100/sec → can't keep up
```

**HOW — 3 levels of backpressure:**

**Level 1: HTTP/2 Flow Control (Automatic)**
```python
# gRPC uses HTTP/2 flow control automatically
# When client doesn't read, sender's stream window fills
# Sender's yield blocks until window has space

async def StreamLargeData(self, request, context):
    async for item in source:
        # ⭐ This await blocks if client is slow
        # HTTP/2 windowing handles backpressure transparently
        yield item
```

**Level 2: Application-level Pacing**
```python
async def StreamWithPacing(self, request, context):
    """
    Throttle to N items per second.
    """
    rate_per_sec = 100
    interval = 1.0 / rate_per_sec

    async for item in source:
        if context.cancelled():
            break

        yield item
        await asyncio.sleep(interval)  # ⭐ Pacing
```

**Level 3: Bounded Queue with Drop Policy**
```python
import asyncio

class BoundedQueueStreamer:
    """
    Producer pushes to bounded queue.
    If queue full, drop oldest (or block).
    """
    def __init__(self, max_size=1000):
        self.queue = asyncio.Queue(maxsize=max_size)

    async def produce(self):
        while True:
            item = await fetch_next_item()

            # ⭐ Drop oldest if full (non-blocking)
            if self.queue.full():
                try:
                    self.queue.get_nowait()  # Drop oldest
                except asyncio.QueueEmpty:
                    pass

            await self.queue.put(item)

    async def stream_to_client(self, context):
        """gRPC handler streams from queue."""
        while not context.cancelled():
            item = await self.queue.get()
            yield item
```

**HOW — Client-side: signal "I'm slow" via streaming response acknowledgments:**

```protobuf
// Bidirectional with acks
service DataService {
  rpc StreamData(stream Ack) returns (stream Data);
}

message Ack { int64 last_received_id = 1; }
message Data { int64 id = 1; bytes payload = 2; }
```

```python
# Server only sends next batch after ack
async def StreamData(self, ack_iterator, context):
    last_acked = 0
    pending = []

    async for ack in ack_iterator:
        # Send up to N items past last_acked
        BATCH_SIZE = 10
        while len(pending) < BATCH_SIZE:
            item = await fetch_next_item()
            pending.append(item)
            yield item

        # Trim acknowledged
        last_acked = ack.last_received_id
        pending = [p for p in pending if p.id > last_acked]
```

---

### Q6: Resumable streams — connection drop ke baad continue kaise karein?

**Answer:**

**WHAT:** Client can resume from where it left off after disconnection.

**WHY:**
- Long streams (hours) — network drops happen
- Don't want to re-process from start
- Idempotency for streaming

**HOW — Resume token pattern:**

```protobuf
service EventService {
  rpc SubscribeEvents(SubscribeRequest) returns (stream Event);
}

message SubscribeRequest {
  string topic = 1;
  // ⭐ Resume from this point (empty for new subscription)
  string resume_token = 2;
}

message Event {
  string id = 1;
  string topic = 2;
  bytes payload = 3;
  // ⭐ Client saves this; sends in resume_token on reconnect
  string resume_token = 4;
}
```

```python
# server.py
class EventServicer:
    async def SubscribeEvents(self, request, context):
        # Resume token = last event ID seen by client
        last_seen_id = self._parse_resume_token(request.resume_token)

        # Fetch events after that ID
        async for event in self._stream_events_after(request.topic, last_seen_id):
            yield Event(
                id=event.id,
                topic=event.topic,
                payload=event.data,
                # ⭐ Include resume token (for client to save)
                resume_token=self._build_resume_token(event.id)
            )

    def _build_resume_token(self, event_id):
        import base64, json
        return base64.b64encode(json.dumps({"id": event_id}).encode()).decode()
```

```python
# client.py with reconnect logic
class ResilientEventClient:
    def __init__(self, stub, topic):
        self.stub = stub
        self.topic = topic
        self.resume_token = ""    # Saved across reconnects

    async def subscribe_with_resume(self):
        """
        Auto-reconnect on failure, resume from last event.
        """
        while True:
            try:
                request = SubscribeRequest(
                    topic=self.topic,
                    resume_token=self.resume_token   # ⭐ Resume from here
                )
                async for event in self.stub.SubscribeEvents(request):
                    yield event
                    # ⭐ Save token for resume
                    self.resume_token = event.resume_token

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    # Reconnect with exponential backoff
                    await asyncio.sleep(min(2 ** retry_count, 30))
                    continue
                raise
```

---

### Q7: Streaming testing strategies?

**Answer:**

**HOW — Test streaming with limited data:**

```python
import pytest

@pytest.mark.asyncio
async def test_server_streaming(grpc_stub):
    """Consume entire stream, verify count + content."""
    results = []
    async for item in grpc_stub.ListItems(ListRequest(limit=5)):
        results.append(item)

    assert len(results) == 5
    assert all(r.valid for r in results)


@pytest.mark.asyncio
async def test_stream_cancellation(grpc_stub):
    """Cancel after N items."""
    received = 0
    async for item in grpc_stub.LongStream(LongRequest()):
        received += 1
        if received >= 3:
            break  # Cancels stream

    assert received == 3


@pytest.mark.asyncio
async def test_bidirectional_chat(grpc_stub):
    """Send N messages, expect N responses."""
    async def request_gen():
        for i in range(5):
            yield ChatMessage(text=f"msg{i}")

    responses = []
    async for resp in grpc_stub.Chat(request_gen()):
        responses.append(resp)

    assert len(responses) >= 5


@pytest.mark.asyncio
async def test_stream_with_timeout(grpc_stub):
    """Stream that doesn't return — verify timeout."""
    with pytest.raises(grpc.RpcError) as exc_info:
        async with asyncio.timeout(2):
            async for item in grpc_stub.SlowStream(SlowRequest()):
                pass

    assert exc_info.value.code() == grpc.StatusCode.CANCELLED
```

---

## Streaming Best Practices

```markdown
### Resource Management
- [ ] Always use try/finally for cleanup
- [ ] Close Redis/DB connections on stream end
- [ ] Check context.cancelled() in loops
- [ ] Use bounded queues (prevent OOM)

### Performance
- [ ] Use server streaming over many unary calls
- [ ] Application-level pacing for known throughput
- [ ] HTTP/2 flow control for automatic backpressure
- [ ] Keepalive aggressive (30s) for long streams

### Reliability
- [ ] Resume tokens for long streams
- [ ] Exponential backoff reconnect on client
- [ ] Idempotent operations (allow safe retries)
- [ ] Heartbeat messages if no real data flowing

### Testing
- [ ] Cancellation tested
- [ ] Empty stream tested
- [ ] Large stream tested (bounded)
- [ ] Concurrent streams tested
```
