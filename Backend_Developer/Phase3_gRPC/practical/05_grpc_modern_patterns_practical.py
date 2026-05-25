"""
Phase3_gRPC — Modern Patterns: Streaming + Browser + Gateway + AWS
====================================================================
Topics covered:
  1. Long-running server streaming (notifications, log tailing)
  2. Stream cancellation handling (client + server)
  3. Bidirectional streaming (chat pattern)
  4. Client streaming (chunked file upload)
  5. Backpressure handling (HTTP/2 flow control + app-level)
  6. Resumable streams (resume tokens)
  7. gRPC-Web with Envoy proxy
  8. Connect-RPC (modern alternative)
  9. REST gateway (FastAPI wrapping gRPC)
  10. AWS ALB + ECS Fargate config
  11. AWS App Mesh + Cloud Map service discovery
  12. PrivateLink for cross-account gRPC

Run:
  python 05_grpc_modern_patterns_practical.py
"""

import asyncio
import json
import time
import uuid
import hashlib
import random
from typing import AsyncIterator, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Long-Running Server Streaming
# INTERVIEW: Notifications, log tailing, real-time updates
# ─────────────────────────────────────────────────────────────────────────────

LONG_RUNNING_STREAM_PATTERN = """
# Server: long-running stream that keeps connection open
class NotificationServicer:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def SubscribeNotifications(self, request, context):
        \"\"\"
        Stream notifications until client disconnects.
        Uses Redis pub/sub for real-time delivery.
        \"\"\"
        pubsub = self.redis.pubsub()
        channels = [f"notif:{request.user_id}:{t}" for t in request.types]
        await pubsub.subscribe(*channels)

        try:
            async for message in pubsub.listen():
                # ⭐ Check cancellation regularly
                if context.cancelled():
                    break

                if message["type"] != "message":
                    continue

                data = json.loads(message["data"])
                # ⭐ Yield sends to client
                yield Notification(
                    id=data["id"],
                    type=data["type"],
                    title=data["title"],
                    body=data["body"],
                )

        except asyncio.CancelledError:
            pass  # Client disconnected
        finally:
            # ⭐ ALWAYS clean up
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
"""

# Simulated implementation for demo
class FakeNotificationStream:
    def __init__(self, user_id, max_count=5):
        self.user_id = user_id
        self.max_count = max_count
        self.sent = 0

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self.sent >= self.max_count:
            raise StopAsyncIteration

        await asyncio.sleep(0.1)
        self.sent += 1
        return {
            "id": str(uuid.uuid4()),
            "type": "order",
            "title": f"Notification #{self.sent}",
            "body": f"For user {self.user_id}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Stream Cancellation
# INTERVIEW: Client-side break + Server-side detection
# ─────────────────────────────────────────────────────────────────────────────

CANCELLATION_PATTERNS = """
# Client-side cancellation

# Method 1: break from async for
async def consume_until_match(stub, target):
    async for item in stub.ListItems(request):
        if item.id == target:
            return item    # ⭐ Returning cancels stream

# Method 2: explicit cancel
async def consume_with_timeout(stub):
    call = stub.ListItems(request)
    try:
        async with asyncio.timeout(5):
            async for item in call:
                yield item
    except asyncio.TimeoutError:
        call.cancel()       # ⭐ Cancel the call
        raise

# Method 3: cancellation token
async def consume_cancellable(stub, token):
    async for item in stub.ListItems(request):
        if token.cancelled:
            break          # ⭐ External signal


# Server-side detection

class StreamingServicer:
    async def ListItems(self, request, context):
        # Method 1: Poll context.cancelled()
        for item in await db.get_items():
            if context.cancelled():
                print("Client cancelled — stopping")
                return
            yield item

    async def WatchUser(self, request, context):
        # Method 2: Cancellation callback
        cancelled = asyncio.Event()
        context.add_done_callback(lambda _: cancelled.set())

        while not cancelled.is_set():
            user = await db.get_user(request.user_id)
            yield user
            try:
                await asyncio.wait_for(cancelled.wait(), timeout=5)
            except asyncio.TimeoutError:
                continue

    async def StreamLogs(self, request, context):
        # Method 3: try/except/finally
        try:
            async for log in tail_logs(request.file_path):
                yield log
        except asyncio.CancelledError:
            print("Stream cancelled")
            raise
        finally:
            # ⭐ Cleanup always runs
            close_file_handle()
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Bidirectional Streaming (Chat Pattern)
# INTERVIEW: Both sides stream independently
# ─────────────────────────────────────────────────────────────────────────────

BIDIRECTIONAL_CHAT_SERVER = """
class ChatServicer:
    def __init__(self):
        # Room → set of active outgoing queues
        self.rooms = defaultdict(set)

    async def Chat(self, request_iterator, context):
        \"\"\"
        Bidirectional: receive messages, broadcast to room.
        \"\"\"
        room_id = None
        user_id = None
        outgoing_queue = asyncio.Queue()

        async def receive_from_client():
            \"\"\"Receive messages, broadcast to room.\"\"\"
            nonlocal room_id, user_id
            async for msg in request_iterator:
                if context.cancelled():
                    return
                if room_id is None:
                    room_id = msg.room_id
                    user_id = msg.user_id
                    self.rooms[room_id].add(outgoing_queue)

                # Broadcast to OTHER clients in room
                for q in self.rooms[room_id]:
                    if q is not outgoing_queue:
                        await q.put(msg)

        receiver_task = asyncio.create_task(receive_from_client())

        try:
            # Yield messages from queue to this client
            while not context.cancelled():
                try:
                    msg = await asyncio.wait_for(outgoing_queue.get(), timeout=1)
                    yield msg
                except asyncio.TimeoutError:
                    continue
        finally:
            receiver_task.cancel()
            if room_id:
                self.rooms[room_id].discard(outgoing_queue)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Client Streaming for Chunked Upload
# INTERVIEW: Large file upload pattern
# ─────────────────────────────────────────────────────────────────────────────

CHUNKED_UPLOAD_PROTO = """
service FileService {
  rpc UploadFile(stream FileChunk) returns (UploadResponse);
}

message FileChunk {
  oneof data {
    FileMetadata metadata = 1;  // First message
    bytes chunk = 2;             // Subsequent
  }
}

message FileMetadata {
  string filename = 1;
  string content_type = 2;
  string sha256 = 3;             // For integrity check
}

message UploadResponse {
  string file_id = 1;
  int64 size_bytes = 2;
}
"""

# Simulated chunked upload
class ChunkedUploadSimulator:
    """Simulates client streaming chunked upload."""

    @staticmethod
    async def upload(file_data: bytes, chunk_size: int = 1024):
        """Simulate streaming upload."""
        sha256 = hashlib.sha256(file_data).hexdigest()

        # Stream chunks
        chunks_sent = 0
        total_bytes = 0

        async def chunk_gen():
            nonlocal chunks_sent, total_bytes
            # First: metadata
            yield {"type": "metadata", "filename": "test.bin", "sha256": sha256}

            # Then: chunks
            for i in range(0, len(file_data), chunk_size):
                chunk = file_data[i:i + chunk_size]
                yield {"type": "chunk", "data": chunk}
                chunks_sent += 1
                total_bytes += len(chunk)
                await asyncio.sleep(0.001)  # Simulate network

        # Server processes
        received_sha = hashlib.sha256()
        received_metadata = None
        received_bytes = 0

        async for item in chunk_gen():
            if item["type"] == "metadata":
                received_metadata = item
            else:
                received_sha.update(item["data"])
                received_bytes += len(item["data"])

        # Verify integrity
        if received_sha.hexdigest() != received_metadata["sha256"]:
            raise ValueError("SHA256 mismatch")

        return {
            "file_id": str(uuid.uuid4()),
            "size_bytes": received_bytes,
            "chunks": chunks_sent,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Backpressure
# INTERVIEW: Slow consumer scenarios
# ─────────────────────────────────────────────────────────────────────────────

BACKPRESSURE_LEVELS = """
# Level 1: HTTP/2 Flow Control (automatic)
async def StreamLargeData(self, request, context):
    async for item in source:
        # ⭐ This await blocks if client is slow (automatic backpressure)
        yield item


# Level 2: Application-level pacing
async def StreamWithPacing(self, request, context):
    RATE_PER_SEC = 100
    interval = 1.0 / RATE_PER_SEC

    async for item in source:
        if context.cancelled():
            break
        yield item
        await asyncio.sleep(interval)


# Level 3: Bounded queue with drop policy
class BoundedQueueStreamer:
    def __init__(self, max_size=1000):
        self.queue = asyncio.Queue(maxsize=max_size)

    async def produce(self):
        while True:
            item = await fetch_next_item()
            # ⭐ Drop oldest if full
            if self.queue.full():
                try:
                    self.queue.get_nowait()  # Drop oldest
                except asyncio.QueueEmpty:
                    pass
            await self.queue.put(item)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Resumable Streams
# INTERVIEW: Continue from disconnection point
# ─────────────────────────────────────────────────────────────────────────────

RESUMABLE_STREAM_PROTO = """
service EventService {
  rpc SubscribeEvents(SubscribeRequest) returns (stream Event);
}

message SubscribeRequest {
  string topic = 1;
  // ⭐ Resume from this point (empty = new subscription)
  string resume_token = 2;
}

message Event {
  string id = 1;
  bytes payload = 2;
  // ⭐ Client saves this; sends in resume_token on reconnect
  string resume_token = 3;
}
"""

class ResilientEventClient:
    """
    INTERVIEW: Client with auto-reconnect + resume from last seen event.
    """
    def __init__(self, topic: str):
        self.topic = topic
        self.resume_token = ""
        self.events_received = 0

    async def subscribe_with_resume(self, max_events=5, fail_at=2):
        """
        Subscribe, simulate disconnect, resume from token.
        """
        attempts = 0
        while self.events_received < max_events:
            attempts += 1
            print(f"\n  Attempt {attempts}: subscribe with token='{self.resume_token[:8] if self.resume_token else 'EMPTY'}...'")

            try:
                # Simulated server stream
                async for event in self._simulate_stream(start_from=self.events_received,
                                                         fail_at=fail_at if attempts == 1 else None,
                                                         max_count=max_events):
                    print(f"    Received event #{event['id']}, saving token")
                    self.events_received += 1
                    self.resume_token = event['resume_token']

                    if self.events_received >= max_events:
                        return

            except ConnectionError as e:
                print(f"    ⚠️  Connection failed: {e}")
                if attempts > 3:
                    raise
                # Exponential backoff
                await asyncio.sleep(min(2 ** attempts, 10))
                continue

    async def _simulate_stream(self, start_from: int, fail_at: Optional[int], max_count: int):
        """Simulate server stream that may fail."""
        for i in range(start_from, max_count):
            await asyncio.sleep(0.05)

            if fail_at is not None and i == fail_at:
                raise ConnectionError("Simulated network failure")

            yield {
                "id": i,
                "resume_token": f"token-after-event-{i}",
            }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: gRPC-Web with Envoy
# INTERVIEW: Browser → Envoy → gRPC backend
# ─────────────────────────────────────────────────────────────────────────────

ENVOY_GRPC_WEB_CONFIG = """
# envoy.yaml — translate gRPC-Web ↔ gRPC
static_resources:
  listeners:
    - name: listener_0
      address: { socket_address: { address: 0.0.0.0, port_value: 8080 } }
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                codec_type: AUTO
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      # ⭐ CORS for browser
                      cors:
                        allow_origin_string_match:
                          - prefix: "*"
                        allow_methods: "GET, PUT, DELETE, POST, OPTIONS"
                        allow_headers: "keep-alive,user-agent,cache-control,content-type,content-transfer-encoding,custom-header-1,x-accept-content-transfer-encoding,x-accept-response-streaming,x-user-agent,x-grpc-web,grpc-timeout"
                        max_age: "1728000"
                      routes:
                        - match: { prefix: "/" }
                          route: { cluster: backend_service }
                http_filters:
                  # ⭐ gRPC-Web filter
                  - name: envoy.filters.http.grpc_web
                  - name: envoy.filters.http.cors
                  - name: envoy.filters.http.router

  clusters:
    - name: backend_service
      connect_timeout: 5s
      type: LOGICAL_DNS
      lb_policy: ROUND_ROBIN
      http2_protocol_options: {}      # ⭐ HTTP/2 to backend
      load_assignment:
        cluster_name: backend_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address: { address: user-service, port_value: 50051 }
"""

TYPESCRIPT_CLIENT_CODE = """
// user.service.ts
import { UserServiceClient } from './gen/user_service_grpc_web_pb';
import { GetUserRequest } from './gen/user_service_pb';

const client = new UserServiceClient(
  process.env.REACT_APP_API_URL,
  null,
  null
);

export async function getUser(userId: number) {
  return new Promise((resolve, reject) => {
    const request = new GetUserRequest();
    request.setUserId(userId);

    client.getUser(request, {
      'authorization': `Bearer ${getToken()}`
    }, (err, response) => {
      if (err) reject(err);
      else resolve(response.toObject());
    });
  });
}

// Server streaming
export function streamUsers(filter: string) {
  const request = new ListUsersRequest();
  request.setRoleFilter(filter);

  const stream = client.listUsers(request, {});

  stream.on('data', (user) => {
    console.log('Received:', user.toObject());
  });

  stream.on('end', () => console.log('Stream ended'));

  return stream;  // Caller can cancel via stream.cancel()
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Connect-RPC (Modern Alternative)
# INTERVIEW: No proxy needed, works in browsers natively
# ─────────────────────────────────────────────────────────────────────────────

CONNECT_RPC_COMPARISON = """
# Comparison: gRPC-Web vs Connect-RPC

| Feature           | gRPC-Web          | Connect-RPC       |
|-------------------|-------------------|-------------------|
| Proxy required    | Envoy needed      | ❌ No proxy       |
| Client API        | Callbacks         | Promises/async    |
| Debug via curl    | ❌ Hard           | ✅ Easy           |
| TypeScript types  | Manual            | Auto-generated    |
| Browser support   | All               | All               |
| Maturity          | High              | Newer             |


# Connect-RPC TypeScript client (modern!)
import { createPromiseClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import { UserService } from "./gen/user_service_connect";

const transport = createConnectTransport({
  baseUrl: "https://api.example.com",
  useBinaryFormat: false,    // ⭐ HTTP/1.1 + JSON (works everywhere)
});

const client = createPromiseClient(UserService, transport);

// Promise-based (no callbacks!)
const response = await client.getUser({ userId: 123 });
console.log(response.name);

// Server streaming
for await (const user of client.listUsers({ filter: "admin" })) {
  console.log(user.name);
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: REST Gateway (FastAPI wrapping gRPC)
# INTERVIEW: Same backend, both REST + gRPC clients
# ─────────────────────────────────────────────────────────────────────────────

REST_GATEWAY_FASTAPI = """
# rest_gateway.py
from fastapi import FastAPI, HTTPException, Depends
import grpc
from google.protobuf.json_format import MessageToDict, ParseDict

app = FastAPI(title="User Service REST API")

channel = grpc.aio.insecure_channel("user-grpc-backend:50051")
stub = user_service_pb2_grpc.UserServiceStub(channel)


# Map gRPC errors to HTTP
def grpc_to_http_status(code):
    return {
        grpc.StatusCode.OK: 200,
        grpc.StatusCode.INVALID_ARGUMENT: 400,
        grpc.StatusCode.UNAUTHENTICATED: 401,
        grpc.StatusCode.PERMISSION_DENIED: 403,
        grpc.StatusCode.NOT_FOUND: 404,
        grpc.StatusCode.ALREADY_EXISTS: 409,
        grpc.StatusCode.RESOURCE_EXHAUSTED: 429,
        grpc.StatusCode.UNAVAILABLE: 503,
        grpc.StatusCode.DEADLINE_EXCEEDED: 504,
    }.get(code, 500)


async def call_grpc(method, request_proto):
    try:
        return await method(request_proto, timeout=10)
    except grpc.RpcError as e:
        raise HTTPException(grpc_to_http_status(e.code()), e.details())


# REST endpoints (manual mapping from .proto)
@app.get("/v1/users/{user_id}")
async def get_user(user_id: int):
    request = user_service_pb2.GetUserRequest(user_id=user_id)
    response = await call_grpc(stub.GetUser, request)
    return MessageToDict(response, preserving_proto_field_name=True)


@app.post("/v1/users")
async def create_user(body: dict):
    request = user_service_pb2.CreateUserRequest()
    ParseDict(body, request)
    response = await call_grpc(stub.CreateUser, request)
    return MessageToDict(response)


# Server-Sent Events for streaming
from fastapi.responses import StreamingResponse

@app.get("/v1/users/{user_id}/notifications/stream")
async def stream_notifications(user_id: int):
    \"\"\"SSE wrapper around gRPC server streaming.\"\"\"
    async def event_generator():
        request = SubscribeRequest(user_id=str(user_id))
        try:
            async for notif in stub.SubscribeNotifications(request):
                data = MessageToDict(notif)
                yield f"data: {json.dumps(data)}\\n\\n"
        except grpc.RpcError as e:
            yield f"event: error\\ndata: {e.details()}\\n\\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: AWS ALB + ECS Fargate Config
# INTERVIEW: gRPC-specific ALB settings
# ─────────────────────────────────────────────────────────────────────────────

AWS_ALB_TERRAFORM = """
# Terraform for AWS ALB + gRPC

# ⭐ Target Group with GRPC protocol
resource "aws_lb_target_group" "grpc" {
  name             = "grpc-tg"
  port             = 50051
  protocol         = "HTTP"
  protocol_version = "GRPC"     # ⭐ CRITICAL: GRPC (not HTTP2)
  target_type      = "ip"        # ⭐ ip (for Fargate)
  vpc_id           = aws_vpc.main.id

  health_check {
    enabled             = true
    protocol            = "HTTP"
    path                = "/grpc.health.v1.Health/Check"  # ⭐ gRPC health
    matcher             = "0"                              # ⭐ gRPC OK = 0
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
  }
}

# ⭐ ALB Listener — HTTPS REQUIRED for HTTP/2
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate.api.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grpc.arn
  }
}

# ⭐ ALB with long idle timeout (for streams)
resource "aws_lb" "main" {
  name               = "grpc-alb"
  load_balancer_type = "application"
  idle_timeout       = 4000     # ⭐ 60s default kills streams
}
"""

ECS_TASK_DEFINITION = """
# ECS Task Definition for gRPC service
resource "aws_ecs_task_definition" "grpc" {
  family = "grpc-user-service"
  cpu    = "1024"
  memory = "2048"

  container_definitions = jsonencode([{
    name  = "grpc-user-service"
    image = "ECR_URL/grpc-user-service:latest"

    portMappings = [{
      containerPort = 50051
      protocol      = "tcp"
    }]

    # ⭐ gRPC health check (uses grpc_health_probe binary)
    healthCheck = {
      command     = ["CMD-SHELL", "grpc_health_probe -addr=:50051 || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }

    # ⭐ Graceful shutdown time
    stopTimeout = 30
  }])
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: AWS Cloud Map Service Discovery
# INTERVIEW: DNS-based gRPC service discovery
# ─────────────────────────────────────────────────────────────────────────────

CLOUD_MAP_SETUP = """
# AWS Cloud Map for service discovery

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "internal.local"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "user_grpc" {
  name = "user-grpc"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10   # ⭐ Low TTL for fast pod removal awareness
      type = "A"
    }
    routing_policy = "MULTIVALUE"   # Returns multiple A records
  }
}

resource "aws_ecs_service" "user_grpc" {
  # ... config
  service_registries {
    registry_arn = aws_service_discovery_service.user_grpc.arn
  }
}


# Client uses DNS:
channel = grpc.aio.secure_channel(
    "user-grpc.internal.local:50051",   # ⭐ Cloud Map DNS
    credentials,
    options=[("grpc.lb_policy_name", "round_robin")]
)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12: Demo Functions
# ─────────────────────────────────────────────────────────────────────────────

async def demo_long_running_stream():
    print("\n[Long-Running Stream Demo]")

    stream = FakeNotificationStream(user_id="user-123", max_count=5)
    print("  Streaming notifications...")

    count = 0
    async for notif in stream:
        count += 1
        print(f"    [{count}] {notif['title']}: {notif['body']}")

    print(f"  Total received: {count}")


async def demo_stream_cancellation():
    print("\n[Stream Cancellation Demo]")

    stream = FakeNotificationStream(user_id="user-456", max_count=100)
    print("  Receiving stream, cancelling after 3 messages...")

    received = 0
    async for notif in stream:
        received += 1
        print(f"    Received: {notif['title']}")
        if received >= 3:
            print("  Cancelling stream...")
            break  # ⭐ Cancels the stream

    print(f"  Total received before cancel: {received}")


async def demo_chunked_upload():
    print("\n[Chunked Upload Demo]")

    # Generate fake file data
    file_data = b"Hello, world! This is a test file." * 100  # ~3.4 KB
    print(f"  File size: {len(file_data)} bytes")

    result = await ChunkedUploadSimulator.upload(file_data, chunk_size=512)
    print(f"  ✅ Upload complete:")
    print(f"     File ID: {result['file_id']}")
    print(f"     Size: {result['size_bytes']} bytes")
    print(f"     Chunks sent: {result['chunks']}")


async def demo_resumable_stream():
    print("\n[Resumable Stream Demo]")

    client = ResilientEventClient(topic="orders")
    await client.subscribe_with_resume(max_events=5, fail_at=2)
    print(f"\n  ✅ Total events received across reconnects: {client.events_received}")


def demo_alb_config_summary():
    print("\n[AWS ALB Critical Settings for gRPC]")
    settings = {
        "protocol_version":           "GRPC (not HTTP2)",
        "target_type":                "ip (for Fargate)",
        "health_check.path":          "/grpc.health.v1.Health/Check",
        "health_check.matcher":       "0 (gRPC OK status)",
        "listener.protocol":          "HTTPS (HTTP/2 requires TLS)",
        "ssl_policy":                 "TLS-1-2 minimum",
        "idle_timeout":               "4000 (default 60s kills streams)",
    }
    for k, v in settings.items():
        print(f"  {k:<28}: {v}")


def demo_decision_matrix():
    print("\n[gRPC Browser Approach Decision Matrix]")
    print(f"  {'Approach':<22} {'Proxy':<12} {'Best For'}")
    print(f"  {'-'*22} {'-'*12} {'-'*30}")
    approaches = [
        ("gRPC-Web + Envoy", "Envoy req.", "Existing gRPC backend"),
        ("Connect-RPC", "❌ None", "New projects"),
        ("REST Gateway", "FastAPI/Go", "Polyglot teams"),
        ("GraphQL Wrapper", "GraphQL", "Complex queries"),
    ]
    for app, proxy, use in approaches:
        print(f"  {app:<22} {proxy:<12} {use}")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A Summary
# ─────────────────────────────────────────────────────────────────────────────

MODERN_PATTERNS_QA = [
    ("Why use streaming over polling REST?",
     "Real-time delivery (push vs pull)\n"
     "     Less server load (no repeated polling)\n"
     "     Lower latency (immediate)\n"
     "     Use cases: notifications, chat, live updates"),

    ("How to handle stream cancellation?",
     "Client: break from async for OR call.cancel()\n"
     "     Server: poll context.cancelled() OR add_done_callback\n"
     "     ALWAYS cleanup in finally block"),

    ("When use bidirectional vs unary?",
     "Bidirectional: real-time interaction (chat, multiplayer)\n"
     "     Unary: request-response (CRUD)\n"
     "     Server streaming: live feeds (notifications)\n"
     "     Client streaming: bulk upload"),

    ("Why not single big message for files?",
     "Max message size limit (default 4MB)\n"
     "     Memory bloat (holds whole file in RAM)\n"
     "     No progress indication\n"
     "     Use client streaming with 64KB chunks"),

    ("How does backpressure work in gRPC?",
     "HTTP/2 flow control (automatic at protocol level)\n"
     "     Sender's yield blocks when receiver's window full\n"
     "     App-level: bounded queues, pacing"),

    ("Why need resume tokens?",
     "Long streams (hours) — network drops happen\n"
     "     Don't want to restart from beginning\n"
     "     Server: include token in each response\n"
     "     Client: save token, send on reconnect"),

    ("gRPC-Web vs Connect-RPC?",
     "gRPC-Web: Standard but needs Envoy proxy\n"
     "     Connect-RPC: Modern, no proxy, promise-based API\n"
     "     Recommend Connect-RPC for new projects"),

    ("Why ALB protocol_version='GRPC' (not HTTP2)?",
     "GRPC protocol enables special gRPC handling:\n"
     "     - HTTP/2 trailers (gRPC status codes)\n"
     "     - gRPC health check protocol support\n"
     "     - Per-RPC LB (not just per-connection)"),

    ("Why Cloud Map TTL = 10 seconds?",
     "Low TTL = fast removal of dead pod IPs\n"
     "     Default DNS TTL (300s) too slow\n"
     "     Tradeoff: more DNS queries vs faster failover"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("gRPC MODERN PATTERNS PRACTICAL")
    print("Streaming + Browser + Gateway + AWS")
    print("=" * 60)

    await demo_long_running_stream()
    await demo_stream_cancellation()
    await demo_chunked_upload()
    await demo_resumable_stream()
    demo_alb_config_summary()
    demo_decision_matrix()

    print("\n[Streaming Best Practices]")
    practices = [
        "ALWAYS use try/finally for resource cleanup",
        "Check context.cancelled() in loops",
        "Use bounded queues to prevent OOM",
        "Aggressive keepalive (30s) for long streams",
        "Resume tokens for streams > 5 minutes",
        "ALB idle_timeout = 4000 (default 60s kills)",
        "Application-level pacing for known throughput",
    ]
    for p in practices:
        print(f"  ✓ {p}")

    print("\n[AWS Deployment Checklist]")
    aws = [
        "ALB protocol_version = 'GRPC'",
        "target_type = 'ip' (for Fargate)",
        "Health check path = '/grpc.health.v1.Health/Check'",
        "Health check matcher = '0'",
        "HTTPS listener (HTTP/2 requires TLS)",
        "grpc_health_probe binary in Docker image",
        "stopTimeout = 30 (graceful shutdown)",
        "Cloud Map TTL = 10s for fast discovery",
        "Same AZ for client/server (avoid inter-AZ cost)",
    ]
    for item in aws:
        print(f"  ✓ {item}")

    print("\n[Q&A Summary]")
    for q, a in MODERN_PATTERNS_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  servicer.py        → streaming endpoints (server/client/bidirectional)")
    print("  resilient_client.py → resume token + auto-reconnect logic")
    print("  envoy.yaml         → gRPC-Web proxy config")
    print("  rest_gateway.py    → FastAPI wrapping gRPC backend")
    print("  terraform/         → ALB + ECS + Cloud Map for AWS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
