"""
Phase3_gRPC — Advanced Protobuf + Performance Tuning Practical
================================================================
Topics covered:
  1. Field numbering best practices (1-15 vs 16+)
  2. Schema evolution (safe vs breaking changes)
  3. Reserved fields (prevent reuse)
  4. oneof (union types) usage
  5. map<K,V> + repeated patterns
  6. Well-known types (Timestamp, Duration, Empty, FieldMask, Any)
  7. Connection keepalive tuning
  8. Connection pooling
  9. Compression (gzip)
  10. Message size limits + streaming for large data
  11. HTTP/2 flow control
  12. Buf for proto management

Run:
  python 04_protobuf_performance_practical.py
"""

import asyncio
import time
import struct
import json
from typing import Iterator

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Field Numbering Best Practices
# INTERVIEW: 1-15 = 1 byte tag, 16+ = 2 bytes
# ─────────────────────────────────────────────────────────────────────────────

EFFICIENT_FIELD_NUMBERING = """
// ✅ EFFICIENT: Frequently accessed fields get 1-15
message User {
  int32 id = 1;             // 1 byte tag (FAST)
  string email = 2;         // 1 byte tag
  string name = 3;          // 1 byte tag
  Role role = 4;            // 1 byte tag
  bool is_active = 5;       // 1 byte tag

  // ⭐ Reserve gaps for future fields
  reserved 6 to 10;

  // Less frequent fields — 16+
  google.protobuf.Timestamp created_at = 16;
  google.protobuf.Timestamp updated_at = 17;
  map<string, string> metadata = 18;
  bytes profile_picture = 19;        // Rarely sent
}

// ❌ INEFFICIENT: Wasted 1-15 range
message User_BAD {
  string rarely_used = 1;            // ❌ Rare field gets cheap tag
  int32 id = 100;                    // ❌ Common field gets 2 byte tag
}
"""

# Calculate field tag bytes
def field_tag_bytes(field_number: int) -> int:
    """
    INTERVIEW: Field number determines tag byte size.
    Varint encoding: 1-15 → 1 byte, 16-2047 → 2 bytes, ...
    """
    if field_number < 16:
        return 1
    elif field_number < 2048:
        return 2
    elif field_number < 262144:
        return 3
    else:
        return 4


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Schema Evolution
# INTERVIEW: Backward + forward compatibility
# ─────────────────────────────────────────────────────────────────────────────

SAFE_SCHEMA_CHANGES = """
// ──── SAFE CHANGES (backward + forward compatible) ────

// 1. Add new field (with new number)
message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
  string phone = 4;        // ✅ New field — old clients ignore
}

// 2. Rename field (keep number same)
message User {
  int32 id = 1;
  string full_name = 2;    // ✅ Renamed from "name" — wire format unchanged
  string email = 3;
}

// 3. Compatible type widening
message User {
  int64 id = 1;            // ✅ int32 → int64 (compatible)
  string name = 2;
}

// 4. Add new enum value
enum Role {
  ROLE_UNSPECIFIED = 0;
  ROLE_USER = 1;
  ROLE_ADMIN = 2;
  ROLE_SUPER_ADMIN = 3;    // ✅ New value
}


// ──── BREAKING CHANGES (DON'T DO) ────

// ❌ Change field number
message User_BAD {
  int32 id = 100;          // ❌ Was id = 1
}

// ❌ Change field type incompatibly
message User_BAD {
  string id = 1;           // ❌ Was int32
}

// ❌ Remove field without reserving
message User_BAD {
  // Removed: string email = 3;  ❌ Number 3 can be reused → wire format conflict
}

// ❌ Make repeated → singular (or vice versa)
message User_BAD {
  string email = 3;        // ❌ Was: repeated string emails
}
"""

EXPAND_CONTRACT_PATTERN = """
// ──── Expand-Contract for safe rename ────

// Version 1 (Deploy 1): Add new field, dual-write
message User {
  int32 id = 1;
  string customer_email = 2;     // OLD
  string customer_email_v2 = 4;  // NEW (will replace)
}

# Code (Release 1):
# - Writes to BOTH customer_email and customer_email_v2
# - Reads from customer_email (old)


// Version 2 (Deploy 2): Backfill + switch reads
# Run Celery task to populate customer_email_v2 from customer_email
# Code now reads from customer_email_v2


// Version 3 (Deploy 3): Drop old field
message User {
  int32 id = 1;
  reserved 2;                    // ⭐ Reserve old field number
  reserved "customer_email";     // ⭐ Reserve old name
  string customer_email_v2 = 4;
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: oneof (Union Types)
# INTERVIEW: Mutually exclusive fields
# ─────────────────────────────────────────────────────────────────────────────

ONEOF_PATTERN = """
// Discriminated union — only one field set
message NotificationRequest {
  string user_id = 1;

  oneof notification {                  // ⭐ One of these
    EmailNotification email = 2;
    SmsNotification sms = 3;
    PushNotification push = 4;
  }
}

message EmailNotification {
  string to = 1;
  string subject = 2;
  string body = 3;
}

message SmsNotification {
  string phone_number = 1;
  string text = 2;
}

message PushNotification {
  string device_token = 1;
  string message = 2;
}
"""

ONEOF_SERVER_HANDLING = """
async def SendNotification(self, request, context):
    # ⭐ WhichOneof returns the name of set field (or None)
    notif_type = request.WhichOneof("notification")

    if notif_type == "email":
        await send_email(request.email.to, request.email.subject, request.email.body)
    elif notif_type == "sms":
        await send_sms(request.sms.phone_number, request.sms.text)
    elif notif_type == "push":
        await send_push(request.push.device_token, request.push.message)
    else:
        await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "No notification type")
"""

# Simulated oneof in Python
class FakeNotificationRequest:
    """Simulates protobuf message with oneof."""
    def __init__(self, user_id):
        self.user_id = user_id
        self._notification_type = None
        self.email = None
        self.sms = None
        self.push = None

    def set_email(self, to, subject, body):
        self._clear_oneof()
        self._notification_type = "email"
        self.email = {"to": to, "subject": subject, "body": body}

    def set_sms(self, phone, text):
        self._clear_oneof()
        self._notification_type = "sms"
        self.sms = {"phone_number": phone, "text": text}

    def set_push(self, device_token, message):
        self._clear_oneof()
        self._notification_type = "push"
        self.push = {"device_token": device_token, "message": message}

    def WhichOneof(self, name):
        # Simulates protobuf's WhichOneof
        return self._notification_type

    def _clear_oneof(self):
        self.email = self.sms = self.push = None


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Map vs Repeated
# INTERVIEW: When to use which
# ─────────────────────────────────────────────────────────────────────────────

MAP_VS_REPEATED = """
// Option A: map (cleaner for simple key-value)
message User {
  map<string, string> metadata = 1;       // ✅ Simple K-V
  map<int64, User> users_by_id = 2;       // ✅ Lookup by ID
}

// Option B: repeated message (when you need extra fields)
message User {
  repeated KeyValue metadata = 1;
}
message KeyValue {
  string key = 1;
  string value = 2;
  int64 updated_at = 3;                   // ⭐ Extra fields possible
  string updated_by = 4;
}

// Map restrictions:
// ❌ map<float, string> — key cannot be float
// ❌ map<bytes, string> — key cannot be bytes
// ❌ map<User, int> — key cannot be message
// ✅ Allowed keys: int32, int64, uint32, uint64, sint32, sint64,
//                  fixed32, fixed64, sfixed32, sfixed64, bool, string
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Well-Known Types
# INTERVIEW: Pre-defined messages for common types
# ─────────────────────────────────────────────────────────────────────────────

WELL_KNOWN_TYPES = """
import "google/protobuf/timestamp.proto";
import "google/protobuf/duration.proto";
import "google/protobuf/empty.proto";
import "google/protobuf/wrappers.proto";
import "google/protobuf/struct.proto";
import "google/protobuf/any.proto";
import "google/protobuf/field_mask.proto";

message Event {
  google.protobuf.Timestamp occurred_at = 1;
  google.protobuf.Duration process_time = 2;
}

service UserService {
  // ⭐ Empty for methods returning nothing
  rpc DeleteUser(GetUserRequest) returns (google.protobuf.Empty);
}

message UpdateUserRequest {
  int32 user_id = 1;

  // ⭐ Wrapper types — distinguish "not set" from "set to default"
  google.protobuf.StringValue name = 2;     // null vs ""
  google.protobuf.Int32Value age = 3;       // null vs 0
  google.protobuf.BoolValue is_active = 4;  // null vs false

  // ⭐ FieldMask — partial updates
  google.protobuf.FieldMask update_mask = 5;
}

message Config {
  // ⭐ Struct — arbitrary JSON-like data
  google.protobuf.Struct settings = 1;
}

message AuditLog {
  string action = 1;
  // ⭐ Any — packed message of any type
  google.protobuf.Any payload = 2;
}
"""

WELL_KNOWN_USAGE = """
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.field_mask_pb2 import FieldMask
from datetime import datetime, timezone

# Timestamp usage
ts = Timestamp()
ts.FromDatetime(datetime.now(timezone.utc))
# OR: ts.GetCurrentTime()

# Convert back to Python
dt = ts.ToDatetime(tzinfo=timezone.utc)

# ISO string conversion
ts.FromJsonString("2024-01-15T10:30:00Z")
iso_str = ts.ToJsonString()


# FieldMask usage (partial update)
async def UpdateUser(self, request, context):
    user = await db.get_user(request.user_id)

    # ⭐ Only update fields specified in FieldMask
    for path in request.update_mask.paths:
        if path == "name":
            user.name = request.user.name
        elif path == "email":
            user.email = request.user.email
        # Fields NOT in mask = unchanged

    await db.save(user)
    return user

# Client side
request = UpdateUserRequest(
    user=User(id=1, name="New Name", email="ignored"),
    update_mask=FieldMask(paths=["name"])   # Only update name
)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Connection Keepalive Tuning
# INTERVIEW: Detect dead connections via TCP pings
# ─────────────────────────────────────────────────────────────────────────────

KEEPALIVE_CONFIG = """
# Server keepalive options
server = grpc.aio.server(
    options=[
        ("grpc.keepalive_time_ms", 30000),                # ⭐ Ping every 30s
        ("grpc.keepalive_timeout_ms", 10000),             # ⭐ Dead if no ack in 10s
        ("grpc.keepalive_permit_without_calls", True),    # ⭐ Allow pings idle
        ("grpc.http2.max_pings_without_data", 0),         # 0 = unlimited
        ("grpc.http2.min_time_between_pings_ms", 10000),  # Min interval enforcement
        ("grpc.http2.min_ping_interval_without_data_ms", 5000),
    ]
)


# Client (same options)
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
        ("grpc.keepalive_permit_without_calls", True),
        ("grpc.enable_retries", 1),                      # Auto-reconnect
    ]
)
"""

KEEPALIVE_SCENARIOS = {
    "Public internet": (30000, "NAT timeout ~60s, ping at 30s catches it"),
    "Internal cluster": (60000, "Less NAT, can be longer"),
    "AWS ALB": (30000, "ALB idle_timeout 60s default"),
    "High-frequency RPCs": (120000, "Less overhead — requests keep alive"),
    "Long-running streams": (10000, "Detect breaks quickly"),
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Connection Pooling
# INTERVIEW: Single channel reuse OR pool for high RPS
# ─────────────────────────────────────────────────────────────────────────────

class FakeChannelPool:
    """
    INTERVIEW: Channel pool for very high RPS (10K+).
    Below 1K RPS: single channel is fine (HTTP/2 multiplexing).
    """
    def __init__(self, target: str, pool_size: int = 5):
        from itertools import cycle
        self.target = target
        self.channels = [f"channel-{i}" for i in range(pool_size)]
        self._cycle = cycle(self.channels)
        self._lock = asyncio.Lock()
        self.calls = {ch: 0 for ch in self.channels}

    async def get_channel(self):
        async with self._lock:
            ch = next(self._cycle)
            self.calls[ch] += 1
            return ch


CHANNEL_POOL_GUIDANCE = """
# Pool size guidance based on RPS
RPS estimate     | Channel pool size
< 1000 RPS       | 1 channel (HTTP/2 plenty)
1k-10k RPS       | 2-3 channels
10k-100k RPS     | 5-10 channels
> 100k RPS       | Service mesh (Envoy)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Compression
# INTERVIEW: gzip for text-heavy payloads > 1 KB
# ─────────────────────────────────────────────────────────────────────────────

COMPRESSION_CONFIG = """
# Server: default compression for all responses
server = grpc.aio.server(
    compression=grpc.Compression.Gzip,
)

# Or per-handler control
async def GetUser(self, request, context):
    await context.set_compression(grpc.Compression.Gzip)
    return user_pb2.User(...)


# Client side
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        ("grpc.default_compression_algorithm", grpc.Compression.Gzip.value),
        ("grpc.default_compression_level", 3),  # 1-9, higher = more CPU
    ]
)

# Per-call override
response = await stub.GetUser(
    GetUserRequest(user_id=123),
    compression=grpc.Compression.Gzip
)
"""

COMPRESSION_DECISION_MATRIX = {
    "Small message (< 1 KB)": "❌ Don't compress (overhead > savings)",
    "Text-heavy (JSON, logs)": "✅ Gzip (3-5x ratio)",
    "Binary data (images, video)": "❌ Already compressed",
    "Internal LAN low latency": "❌ CPU costs > bandwidth savings",
    "Cross-region traffic": "✅ Significant bandwidth savings",
    "Mobile clients": "✅ Save user data",
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Message Size Limits + Streaming for Large Data
# INTERVIEW: Default 4MB — increase or use streaming
# ─────────────────────────────────────────────────────────────────────────────

SIZE_LIMITS_CONFIG = """
# Increase limits (when needed)
server = grpc.aio.server(
    options=[
        ("grpc.max_receive_message_length", 50 * 1024 * 1024),  # 50 MB
        ("grpc.max_send_message_length", 50 * 1024 * 1024),
    ]
)

channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ("grpc.max_send_message_length", 50 * 1024 * 1024),
    ]
)
"""

LARGE_FILE_STREAMING_PATTERN = """
// ❌ DON'T: Single huge message (limit issues, memory issues)
service FileService {
  // rpc UploadFile(UploadRequest) returns (UploadResponse);
}

// ✅ DO: Client streaming with chunks
service FileService {
  rpc UploadFileChunked(stream FileChunk) returns (UploadResponse);
}

message FileChunk {
  oneof data {
    FileMetadata metadata = 1;   // First message
    bytes chunk = 2;              // Subsequent (e.g., 64 KB each)
  }
}

# Client uploads in chunks
async def upload_file(stub, file_path):
    async def chunk_gen():
        # First: metadata
        yield FileChunk(metadata=FileMetadata(
            filename="video.mp4",
            content_type="video/mp4",
            total_size=os.path.getsize(file_path),
        ))
        # Then: 64 KB chunks
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield FileChunk(chunk=chunk)

    return await stub.UploadFileChunked(chunk_gen())
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: HTTP/2 Flow Control + Backpressure
# INTERVIEW: Prevents fast sender from overwhelming slow receiver
# ─────────────────────────────────────────────────────────────────────────────

FLOW_CONTROL_PATTERN = """
# HTTP/2 flow control is AUTOMATIC at protocol level
# When client doesn't read, sender's stream window fills
# Next yield blocks until client consumes

async def StreamLargeData(self, request, context):
    async for item in source:
        # ⭐ This await blocks if client is slow (automatic backpressure)
        yield item


# Application-level pacing (if you want strict rate)
async def StreamWithPacing(self, request, context):
    RATE_PER_SEC = 100
    interval = 1.0 / RATE_PER_SEC

    async for item in source:
        if context.cancelled():
            break
        yield item
        await asyncio.sleep(interval)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: Buf Tool Examples
# INTERVIEW: Modern protobuf toolchain
# ─────────────────────────────────────────────────────────────────────────────

BUF_COMMANDS = """
# Install
brew install bufbuild/buf/buf

# Initialize project
cd protos/
buf mod init buf.build/myorg/userapi

# Lint .proto files (catches anti-patterns)
buf lint
# Catches:
# - Missing UNSPECIFIED enum 0 value
# - Field naming violations (snake_case)
# - Service/package naming

# Check breaking changes vs main branch
buf breaking --against '.git#branch=main'
# Catches:
# - Field number changes
# - Field removal without reserve
# - Type changes (incompatible)
# - Message/service removal

# Format files (in-place)
buf format -w

# Generate code (replaces protoc)
buf generate
# Uses buf.gen.yaml plugins

# Push to Buf Schema Registry
buf push
"""

BUF_GEN_YAML = """
# buf.gen.yaml — code generation config
version: v1
plugins:
  # Python message types
  - plugin: buf.build/protocolbuffers/python
    out: gen/python
    opt:
      - paths=source_relative

  # gRPC Python service stubs
  - plugin: buf.build/grpc/python
    out: gen/python
    opt:
      - paths=source_relative

  # OpenAPI spec
  - plugin: buf.build/grpc-ecosystem/openapiv2
    out: gen/openapi
    opt:
      - output_format=json

  # TypeScript for browser
  - plugin: buf.build/grpc/web
    out: gen/typescript
    opt:
      - import_style=typescript
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12: Demo Functions
# ─────────────────────────────────────────────────────────────────────────────

def demo_field_numbering():
    print("\n[Field Numbering Demo]")
    fields = [1, 5, 15, 16, 100, 1000, 2048, 100000]
    print(f"  {'Field #':<10} {'Tag bytes':<12} {'Notes'}")
    print(f"  {'-'*10} {'-'*12} {'-'*30}")
    for f in fields:
        bytes_used = field_tag_bytes(f)
        note = "1-15 range (cheap)" if f < 16 else \
               "16-2047 range" if f < 2048 else \
               "2048-262143 range" if f < 262144 else "Beyond — expensive"
        print(f"  {f:<10} {bytes_used:<12} {note}")


def demo_oneof():
    print("\n[Oneof Pattern Demo]")

    request = FakeNotificationRequest(user_id="user-123")

    # Set email
    request.set_email("alice@example.com", "Hello", "Welcome")
    print(f"  Set email: WhichOneof = {request.WhichOneof('notification')}")

    # Set sms (clears email automatically)
    request.set_sms("555-1234", "Hello via SMS")
    print(f"  Set sms: WhichOneof = {request.WhichOneof('notification')}")
    print(f"  Email after switch: {request.email} (cleared)")
    print(f"  SMS after switch: {request.sms}")


def demo_compression_decision():
    print("\n[Compression Decision Matrix]")
    for scenario, decision in COMPRESSION_DECISION_MATRIX.items():
        print(f"  {scenario:<30} → {decision}")


def demo_keepalive_scenarios():
    print("\n[Keepalive Tuning by Scenario]")
    for scenario, (ms, reason) in KEEPALIVE_SCENARIOS.items():
        seconds = ms / 1000
        print(f"  {scenario:<25}: {seconds}s ({reason})")


async def demo_connection_pool():
    print("\n[Connection Pool Demo]")
    pool = FakeChannelPool("user-service:50051", pool_size=3)

    # Simulate 10 concurrent calls
    for i in range(10):
        ch = await pool.get_channel()

    print(f"  Pool size: 3 channels")
    print(f"  After 10 calls, distribution:")
    for ch, count in pool.calls.items():
        print(f"    {ch}: {count} calls")


def demo_schema_evolution():
    print("\n[Schema Evolution Rules]")
    rules = [
        ("Add new field", "✅ Safe (use new number)"),
        ("Remove field", "⚠️ Safe IF you reserve number + name"),
        ("Rename field (number same)", "✅ Safe (wire format unchanged)"),
        ("Change field number", "❌ BREAKING"),
        ("Type widening (int32→int64)", "✅ Safe"),
        ("Type narrowing (int64→int32)", "⚠️ Risky (truncation)"),
        ("Type change (int→string)", "❌ BREAKING"),
        ("repeated → singular", "❌ BREAKING"),
        ("Add enum value", "✅ Safe"),
        ("Remove enum value", "⚠️ Use 'reserved'"),
        ("Mark field 'optional'", "✅ Safe (proto3.15+)"),
    ]
    for change, safety in rules:
        print(f"  {change:<35} {safety}")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

PROTOBUF_QA = [
    ("Why field numbers 1-15 special?",
     "Wire format encodes field tag as varint.\n"
     "     1-15 fit in 1 byte; 16+ need 2 bytes.\n"
     "     Use 1-15 for frequently accessed fields."),

    ("How to safely rename a field?",
     "Wire format uses field NUMBER, not name.\n"
     "     Renaming is safe IF number stays same.\n"
     "     If number changes → 3-deploy expand-contract pattern."),

    ("Why reserved fields?",
     "Prevent accidental reuse of old field numbers.\n"
     "     Old clients with old wire format would deserialize wrong field.\n"
     "     'reserved' makes compiler error if reused."),

    ("When to use oneof?",
     "Mutually exclusive fields (only one set).\n"
     "     Examples: notification type, search query type, result variant."),

    ("Why wrapper types?",
     "Proto3 doesn't distinguish 'not set' from 'set to default'.\n"
     "     Int32Value, StringValue etc. give nullable semantics.\n"
     "     Useful for PATCH/UPDATE APIs (FieldMask alternative)."),

    ("What is FieldMask?",
     "Specifies which fields to update in partial PATCH.\n"
     "     Server iterates mask paths and updates only those fields.\n"
     "     Cleaner than wrapper types for complex partial updates."),

    ("Should I always use compression?",
     "No — overhead for small messages (< 1KB).\n"
     "     Yes for text-heavy payloads (3-5x ratio).\n"
     "     No for already-compressed binary (images, video)."),

    ("How to handle huge messages?",
     "Don't increase max_message_length blindly.\n"
     "     Use streaming with chunks (64 KB typical).\n"
     "     Client streaming for uploads, server streaming for downloads."),

    ("Single channel or pool?",
     "Single channel for < 1K RPS (HTTP/2 multiplexes well).\n"
     "     Pool of 2-5 channels for 10K+ RPS.\n"
     "     Service mesh (Envoy) beyond 100K RPS."),

    ("Why use buf over protoc?",
     "Better CLI ergonomics, built-in linting.\n"
     "     Breaking change detection (critical for CI).\n"
     "     Schema registry (Buf Schema Registry)."),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("PROTOBUF + PERFORMANCE TUNING PRACTICAL")
    print("=" * 60)

    demo_field_numbering()
    demo_schema_evolution()
    demo_oneof()
    demo_compression_decision()
    demo_keepalive_scenarios()
    await demo_connection_pool()

    print("\n[Well-Known Types Cheatsheet]")
    types = {
        "Timestamp":  "UTC timestamps (microsecond precision)",
        "Duration":   "Time intervals (job runtime)",
        "Empty":      "Methods returning nothing",
        "FieldMask":  "Partial updates (which fields to change)",
        "StringValue/Int32Value/etc": "Nullable primitives (wrapper types)",
        "Any":        "Polymorphic message (pack any type)",
        "Struct":     "Arbitrary JSON-like data",
    }
    for k, v in types.items():
        print(f"  {k:<28}: {v}")

    print("\n[Performance Tuning Summary]")
    perf = [
        ("Async server", "Use grpc.aio.server() (not grpc.server)"),
        ("Worker count", "Async: CPU count | Mixed: (2×CPU)+1"),
        ("Keepalive", "30s ping, 10s timeout"),
        ("Compression", "Gzip for > 1KB text payloads"),
        ("Connection pool", "Single channel < 1K RPS, pool > 10K RPS"),
        ("Max msg size", "4 MB default; streaming for larger"),
        ("uvloop", "Drop-in replacement for asyncio (faster)"),
    ]
    for k, v in perf:
        print(f"  {k:<18}: {v}")

    print("\n[Buf Commands Cheatsheet]")
    cmds = [
        ("buf lint", "Check for anti-patterns"),
        ("buf breaking", "Detect breaking changes vs main"),
        ("buf format -w", "Format .proto files"),
        ("buf generate", "Generate code (multi-language)"),
        ("buf push", "Push to Buf Schema Registry"),
    ]
    for cmd, desc in cmds:
        print(f"  {cmd:<22} → {desc}")

    print("\n[Q&A Summary]")
    for q, a in PROTOBUF_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  user_service.proto    → schema with well-known types + reserved fields")
    print("  buf.yaml              → buf config (linting + breaking rules)")
    print("  buf.gen.yaml          → code generation plugins")
    print("  server.py             → keepalive options, compression, pooling")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
