"""
=============================================================================
DAY 48 — gRPC & PROTOCOL BUFFERS (PROTOBUF) DEEP DIVE
=============================================================================
Topics:
  1.  What is gRPC            — vs REST comparison table
  2.  Protobuf Syntax         — .proto file as multi-line string
  3.  4 RPC Types             — Unary, Server-stream, Client-stream, Bidi
  4.  Server                  — grpc.aio.server(), servicer, add_insecure_port
  5.  Client                  — grpc.aio.insecure_channel(), stub, calling RPCs
  6.  Interceptors            — ServerInterceptor for auth / logging / metrics
  7.  Error Handling          — grpc.StatusCode, RpcError, abort()
  8.  Metadata                — passing auth tokens via metadata
  9.  Deadlines               — timeout parameter, context.time_remaining()
  10. Reflection              — grpc_reflection for service discovery
  11. Patterns                — gRPC gateway, proto best practices
  12. Interview Q&A           — 12 questions
=============================================================================
Install:
    pip install grpcio grpcio-tools grpcio-reflection
    pip install protobuf
=============================================================================
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — WHAT IS gRPC vs REST
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 1 — gRPC vs REST COMPARISON")
print("=" * 70)

COMPARISON_TABLE = """
┌─────────────────────┬────────────────────────────┬────────────────────────────┐
│ Feature             │ REST (HTTP/1.1 + JSON)      │ gRPC (HTTP/2 + Protobuf)   │
├─────────────────────┼────────────────────────────┼────────────────────────────┤
│ Protocol            │ HTTP/1.1                    │ HTTP/2                     │
│ Payload format      │ JSON (text, human-readable) │ Protobuf (binary, compact) │
│ Payload size        │ Larger (verbose)            │ 3-10x smaller              │
│ Latency             │ Higher (text parsing)       │ Lower (binary, multiplexed)│
│ Streaming           │ Limited (SSE, WebSocket)    │ Native 4-type streaming    │
│ Browser support     │ Excellent (native fetch)    │ Needs gRPC-Web proxy       │
│ Contract (IDL)      │ Optional (OpenAPI/Swagger)  │ Required (.proto file)     │
│ Code generation     │ Optional                    │ Built-in (protoc compiler) │
│ Error model         │ HTTP status codes           │ Rich status codes + details│
│ Multiplexing        │ No (1 req per connection)   │ Yes (many streams, 1 conn) │
│ Header compression  │ No                          │ Yes (HPACK)                │
│ Backward compat     │ Manual versioning           │ Field numbers in proto     │
│ Language support    │ Universal                   │ ~12 languages              │
│ Best for            │ Public APIs, browsers       │ Internal microservices     │
└─────────────────────┴────────────────────────────┴────────────────────────────┘

gRPC Advantages:
  - Strongly typed contracts enforced at compile time
  - Bi-directional streaming built-in
  - Automatic client stub generation in 12+ languages
  - HTTP/2 multiplexing: no head-of-line blocking
  - Built-in deadlines, cancellation, and load balancing

gRPC Disadvantages:
  - Not human-readable (binary wire format)
  - Browser support requires grpc-web proxy
  - Harder to debug without tooling (use grpcurl, grpc UI)
  - Schema evolution requires discipline (never reuse field numbers)
"""
print(COMPARISON_TABLE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — PROTOBUF SYNTAX
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 2 — PROTOBUF .proto FILE SYNTAX")
print("=" * 70)

PROTO_FILE = '''
// ── user_service.proto ────────────────────────────────────────────────────
syntax = "proto3";                          // always proto3 for new projects

package user;                               // namespace (maps to Python module)
option go_package = "github.com/co/svc/pb"; // language-specific options

import "google/protobuf/timestamp.proto";   // well-known types

// ── ENUMS ──────────────────────────────────────────────────────────────────
enum UserRole {
    USER_ROLE_UNSPECIFIED = 0;              // ALWAYS have a 0 value in proto3
    USER_ROLE_ADMIN       = 1;
    USER_ROLE_EDITOR      = 2;
    USER_ROLE_VIEWER      = 3;
}

// ── MESSAGES ───────────────────────────────────────────────────────────────
message Address {
    string street  = 1;
    string city    = 2;
    string country = 3;
    string pincode = 4;
}

message User {
    int64  id         = 1;                  // field number: NEVER change once used
    string name       = 2;
    string email      = 3;
    UserRole role     = 4;
    repeated string tags = 5;              // repeated = list/array
    Address address   = 6;                 // nested message
    google.protobuf.Timestamp created_at = 7;

    oneof contact {                        // exactly one of these fields set
        string phone  = 8;
        string slack  = 9;
    }

    map<string, string> metadata = 10;     // map type
}

message CreateUserRequest {
    string name  = 1;
    string email = 2;
    UserRole role = 3;
}

message GetUserRequest {
    int64 id = 1;
}

message ListUsersRequest {
    int32 page      = 1;
    int32 page_size = 2;
    string filter   = 3;
}

message DeleteUserRequest {
    int64 id = 1;
}

message DeleteUserResponse {
    bool success = 1;
}

message StreamUpdate {
    int64  user_id = 1;
    string field   = 2;
    string value   = 3;
}

// ── SERVICE DEFINITION ─────────────────────────────────────────────────────
service UserService {
    // Unary RPC: one request → one response
    rpc CreateUser(CreateUserRequest) returns (User);

    // Unary RPC with Get
    rpc GetUser(GetUserRequest) returns (User);

    // Server-streaming: one request → stream of responses
    rpc ListUsers(ListUsersRequest) returns (stream User);

    // Client-streaming: stream of requests → one response
    rpc BatchCreateUsers(stream CreateUserRequest) returns (User);

    // Bidirectional streaming: stream → stream
    rpc SyncUsers(stream StreamUpdate) returns (stream User);

    // Unary delete
    rpc DeleteUser(DeleteUserRequest) returns (DeleteUserResponse);
}
// ──────────────────────────────────────────────────────────────────────────

// PROTOBUF FIELD TYPE REFERENCE:
//   double, float        → Python float
//   int32, int64         → Python int
//   uint32, uint64       → Python int (unsigned)
//   bool                 → Python bool
//   string               → Python str (UTF-8)
//   bytes                → Python bytes
//   repeated <type>      → Python list
//   map<K, V>            → Python dict
//   optional <type>      → Python Optional (proto3 with explicit optional)

// GENERATE PYTHON CODE:
//   python -m grpc_tools.protoc \\
//       -I. \\
//       --python_out=. \\
//       --grpc_python_out=. \\
//       user_service.proto
// This generates:
//   user_service_pb2.py       (message classes)
//   user_service_pb2_grpc.py  (stubs and servicers)
'''

print(PROTO_FILE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — 4 RPC TYPES WITH asyncio CODE
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 3 — 4 RPC TYPES (Python asyncio patterns)")
print("=" * 70)

RPC_TYPES_CODE = '''
import asyncio
import grpc

# Assume generated files: user_service_pb2, user_service_pb2_grpc

# ═══════════════════════════════════════════════════════════════════════════
# TYPE 1: UNARY RPC  —  request → response
# ═══════════════════════════════════════════════════════════════════════════
# Proto: rpc GetUser(GetUserRequest) returns (User);

async def demo_unary(stub):
    request = user_service_pb2.GetUserRequest(id=1)
    response = await stub.GetUser(request)
    print(f"Got user: {response.name}, email: {response.email}")

# ═══════════════════════════════════════════════════════════════════════════
# TYPE 2: SERVER STREAMING  —  request → stream of responses
# ═══════════════════════════════════════════════════════════════════════════
# Proto: rpc ListUsers(ListUsersRequest) returns (stream User);

async def demo_server_streaming(stub):
    request = user_service_pb2.ListUsersRequest(page=1, page_size=10)
    # stub returns an async iterator
    async for user in stub.ListUsers(request):
        print(f"  User: {user.id} — {user.name}")

# ═══════════════════════════════════════════════════════════════════════════
# TYPE 3: CLIENT STREAMING  —  stream of requests → response
# ═══════════════════════════════════════════════════════════════════════════
# Proto: rpc BatchCreateUsers(stream CreateUserRequest) returns (User);

async def request_generator():
    """Async generator that yields multiple requests."""
    users_to_create = [
        ("Alice", "alice@example.com"),
        ("Bob",   "bob@example.com"),
        ("Carol", "carol@example.com"),
    ]
    for name, email in users_to_create:
        yield user_service_pb2.CreateUserRequest(name=name, email=email)
        await asyncio.sleep(0.1)   # simulate network delay

async def demo_client_streaming(stub):
    # Pass an async generator as the request
    response = await stub.BatchCreateUsers(request_generator())
    print(f"Batch created, last user: {response.name}")

# ═══════════════════════════════════════════════════════════════════════════
# TYPE 4: BIDIRECTIONAL STREAMING  —  stream ↔ stream
# ═══════════════════════════════════════════════════════════════════════════
# Proto: rpc SyncUsers(stream StreamUpdate) returns (stream User);

async def update_generator():
    updates = [
        (1, "name",  "Alice Updated"),
        (2, "email", "bob_new@example.com"),
    ]
    for user_id, field, value in updates:
        yield user_service_pb2.StreamUpdate(user_id=user_id, field=field, value=value)
        await asyncio.sleep(0.05)

async def demo_bidi_streaming(stub):
    async for updated_user in stub.SyncUsers(update_generator()):
        print(f"Updated: {updated_user.id} → {updated_user.name}")
'''

print(RPC_TYPES_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — SERVER IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 4 — gRPC ASYNC SERVER")
print("=" * 70)

SERVER_CODE = '''
import asyncio
import grpc
from grpc import aio
# from user_service_pb2_grpc import UserServiceServicer, add_UserServiceServicer_to_server
# from user_service_pb2 import User, DeleteUserResponse

# ── Servicer Implementation ────────────────────────────────────────────────
class UserServiceServicer:  # would extend UserServiceServicer from _pb2_grpc
    """Implements the UserService proto service methods."""

    # ── UNARY ──────────────────────────────────────────────────────────────
    async def GetUser(self, request, context):
        """Unary: look up a user by ID."""
        user_id = request.id
        # Fetch from DB...
        if user_id == 0:
            await context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"User {user_id} not found"
            )
        return User(id=user_id, name="Alice", email="alice@example.com")

    async def CreateUser(self, request, context):
        """Unary: create a new user."""
        # Validate
        if not request.email:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "email is required"
            )
        # Save to DB...
        return User(id=42, name=request.name, email=request.email)

    # ── SERVER STREAMING ───────────────────────────────────────────────────
    async def ListUsers(self, request, context):
        """Server-streaming: yield users one by one."""
        page      = request.page or 1
        page_size = request.page_size or 10
        # Simulate DB fetch
        fake_users = [
            User(id=i, name=f"User{i}", email=f"user{i}@example.com")
            for i in range((page-1)*page_size + 1, page*page_size + 1)
        ]
        for user in fake_users:
            if context.cancelled():   # client cancelled — stop early
                return
            yield user
            await asyncio.sleep(0)    # yield to event loop

    # ── CLIENT STREAMING ───────────────────────────────────────────────────
    async def BatchCreateUsers(self, request_iterator, context):
        """Client-streaming: consume stream of create requests."""
        count = 0
        last_user = None
        async for req in request_iterator:
            count += 1
            # Save each user...
            last_user = User(id=count, name=req.name, email=req.email)
        return last_user  # single response at the end

    # ── BIDIRECTIONAL STREAMING ────────────────────────────────────────────
    async def SyncUsers(self, request_iterator, context):
        """Bidi: receive update stream, yield updated users."""
        async for update in request_iterator:
            # Apply update to DB...
            updated = User(id=update.user_id, name=f"Updated_{update.user_id}")
            yield updated

    async def DeleteUser(self, request, context):
        # Delete from DB...
        return DeleteUserResponse(success=True)


# ── Server Bootstrap ───────────────────────────────────────────────────────
async def serve():
    server = aio.server()
    # add_UserServiceServicer_to_server(UserServiceServicer(), server)

    # Credentials: use secure_port for TLS
    server.add_insecure_port("[::]:50051")    # listen on all interfaces, port 50051

    # TLS example (production):
    # with open("server.key", "rb") as f: private_key = f.read()
    # with open("server.crt", "rb") as f: certificate = f.read()
    # creds = grpc.ssl_server_credentials([(private_key, certificate)])
    # server.add_secure_port("[::]:50051", creds)

    print("gRPC server listening on port 50051...")
    await server.start()
    await server.wait_for_termination()

# ── Graceful Shutdown ──────────────────────────────────────────────────────
async def serve_with_shutdown():
    server = aio.server()
    # add_UserServiceServicer_to_server(UserServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()

    import signal
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        stop_event.set()

    loop.add_signal_handler(signal.SIGTERM, handle_signal)
    loop.add_signal_handler(signal.SIGINT, handle_signal)

    await stop_event.wait()
    # Grace period: allow in-flight RPCs to finish
    await server.stop(grace=5)
    print("Server shut down gracefully")


if __name__ == "__main__":
    asyncio.run(serve())
'''

print(SERVER_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — CLIENT
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 5 — gRPC ASYNC CLIENT")
print("=" * 70)

CLIENT_CODE = '''
import asyncio
import grpc
from grpc import aio

# from user_service_pb2_grpc import UserServiceStub
# from user_service_pb2 import GetUserRequest, CreateUserRequest, ListUsersRequest

async def main():
    # ── Channel Creation ───────────────────────────────────────────────────
    # Insecure (dev)
    channel = aio.insecure_channel("localhost:50051")

    # Secure / TLS (production)
    # creds = grpc.ssl_channel_credentials()  # uses system CA roots
    # channel = aio.secure_channel("api.example.com:443", creds)

    # Channel options (connection pool, keep-alive, etc.)
    # channel = aio.insecure_channel(
    #     "localhost:50051",
    #     options=[
    #         ("grpc.max_send_message_length",    50 * 1024 * 1024),   # 50 MB
    #         ("grpc.max_receive_message_length", 50 * 1024 * 1024),
    #         ("grpc.keepalive_time_ms",          30_000),
    #         ("grpc.keepalive_timeout_ms",       5_000),
    #     ]
    # )

    async with channel:
        stub = UserServiceStub(channel)

        # ── Unary call ─────────────────────────────────────────────────────
        try:
            user = await stub.GetUser(
                GetUserRequest(id=1),
                timeout=5.0,          # deadline: 5 seconds
                metadata=[            # attach auth token
                    ("authorization", "Bearer my-jwt-token"),
                    ("x-request-id",  "req-abc-123"),
                ],
            )
            print(f"User: {user.name}")
        except grpc.RpcError as e:
            print(f"RPC failed: code={e.code()}, details={e.details()}")

        # ── Server streaming ───────────────────────────────────────────────
        print("\\nStreaming users:")
        async for user in stub.ListUsers(ListUsersRequest(page=1, page_size=5)):
            print(f"  - {user.id}: {user.name}")

        # ── Create user ────────────────────────────────────────────────────
        new_user = await stub.CreateUser(
            CreateUserRequest(name="Dave", email="dave@example.com")
        )
        print(f"Created: {new_user.id}")


asyncio.run(main())
'''

print(CLIENT_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — INTERCEPTORS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 6 — SERVER INTERCEPTORS")
print("=" * 70)

INTERCEPTOR_CODE = '''
import time
import grpc
from grpc import aio
from typing import Callable, Awaitable

# ── Logging Interceptor ────────────────────────────────────────────────────
class LoggingInterceptor(aio.ServerInterceptor):
    """Logs every RPC call with timing."""

    async def intercept_service(
        self,
        continuation: Callable,
        handler_call_details: grpc.HandlerCallDetails,
    ):
        method = handler_call_details.method
        start  = time.perf_counter()
        print(f"[gRPC] → {method}")
        response = await continuation(handler_call_details)
        elapsed  = (time.perf_counter() - start) * 1000
        print(f"[gRPC] ← {method} ({elapsed:.1f}ms)")
        return response


# ── Auth Interceptor ───────────────────────────────────────────────────────
class AuthInterceptor(aio.ServerInterceptor):
    """Validates Bearer token in metadata."""

    SKIP_AUTH = {"/grpc.reflection.v1alpha.ServerReflection/ServerReflectionInfo"}

    async def intercept_service(
        self,
        continuation: Callable,
        handler_call_details: grpc.HandlerCallDetails,
    ):
        if handler_call_details.method in self.SKIP_AUTH:
            return await continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata)
        token    = metadata.get("authorization", "")

        if not token.startswith("Bearer "):
            # Return an aborting handler
            async def abort_handler(request, context):
                await context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    "Missing or invalid Bearer token",
                )
            return grpc.unary_unary_rpc_method_handler(abort_handler)

        # Attach user info for downstream handlers via context
        # (use context.invocation_metadata() in servicer)
        return await continuation(handler_call_details)


# ── Metrics Interceptor ────────────────────────────────────────────────────
class MetricsInterceptor(aio.ServerInterceptor):
    """Records call counts and error rates (Prometheus-style)."""

    def __init__(self):
        self.call_counts  = {}
        self.error_counts = {}

    async def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        self.call_counts[method] = self.call_counts.get(method, 0) + 1
        try:
            return await continuation(handler_call_details)
        except Exception:
            self.error_counts[method] = self.error_counts.get(method, 0) + 1
            raise


# ── Wiring interceptors into the server ───────────────────────────────────
async def serve_with_interceptors():
    server = aio.server(
        interceptors=[
            LoggingInterceptor(),
            AuthInterceptor(),
            MetricsInterceptor(),
        ]
    )
    # add_UserServiceServicer_to_server(UserServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
'''

print(INTERCEPTOR_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — ERROR HANDLING
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 7 — ERROR HANDLING")
print("=" * 70)

ERROR_CODE = '''
import grpc

# ── gRPC Status Codes ──────────────────────────────────────────────────────
STATUS_CODES = """
grpc.StatusCode.OK                    — success
grpc.StatusCode.CANCELLED             — cancelled by client
grpc.StatusCode.UNKNOWN               — unknown error
grpc.StatusCode.INVALID_ARGUMENT      — bad request data (client bug)
grpc.StatusCode.DEADLINE_EXCEEDED     — timeout expired
grpc.StatusCode.NOT_FOUND             — resource not found
grpc.StatusCode.ALREADY_EXISTS        — duplicate resource
grpc.StatusCode.PERMISSION_DENIED     — authorized but no permission
grpc.StatusCode.UNAUTHENTICATED       — not authenticated
grpc.StatusCode.RESOURCE_EXHAUSTED    — rate limited / quota exceeded
grpc.StatusCode.FAILED_PRECONDITION   — system not in right state
grpc.StatusCode.ABORTED               — transaction conflict
grpc.StatusCode.OUT_OF_RANGE          — out of valid range
grpc.StatusCode.UNIMPLEMENTED         — RPC not implemented
grpc.StatusCode.INTERNAL              — server bug
grpc.StatusCode.UNAVAILABLE           — server temporarily down
grpc.StatusCode.DATA_LOSS             — unrecoverable data loss
"""

# ── In Servicer — raise errors with context.abort() ───────────────────────
async def GetUser(self, request, context):
    if request.id <= 0:
        await context.abort(
            grpc.StatusCode.INVALID_ARGUMENT,
            "user id must be positive"
        )

    user = await db.get_user(request.id)
    if user is None:
        await context.abort(
            grpc.StatusCode.NOT_FOUND,
            f"user with id={request.id} not found"
        )

    try:
        return build_response(user)
    except PermissionError:
        await context.abort(
            grpc.StatusCode.PERMISSION_DENIED,
            "you cannot access this user"
        )
    except Exception as exc:
        await context.abort(
            grpc.StatusCode.INTERNAL,
            f"unexpected error: {exc}"
        )

# ── In Client — catch grpc.RpcError ───────────────────────────────────────
async def safe_get_user(stub, user_id: int):
    try:
        return await stub.GetUser(GetUserRequest(id=user_id))
    except grpc.RpcError as e:
        code    = e.code()
        details = e.details()

        if code == grpc.StatusCode.NOT_FOUND:
            print(f"User not found: {details}")
            return None
        elif code == grpc.StatusCode.UNAUTHENTICATED:
            print("Need to re-authenticate")
            raise
        elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
            print("Request timed out — retry?")
            raise
        else:
            print(f"Unexpected gRPC error [{code.name}]: {details}")
            raise
'''

print(ERROR_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — METADATA
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 8 — METADATA (headers / auth tokens)")
print("=" * 70)

METADATA_CODE = '''
import grpc
from grpc import aio

# ── Client: send metadata with every call ─────────────────────────────────
async def get_user_with_token(stub, user_id: int, token: str):
    metadata = [
        ("authorization", f"Bearer {token}"),
        ("x-request-id",  "req-xyz-789"),
        ("x-client-version", "2.1.0"),
    ]
    response = await stub.GetUser(
        GetUserRequest(id=user_id),
        metadata=metadata,
    )
    return response

# ── Server: read metadata from context ────────────────────────────────────
async def GetUser(self, request, context):
    # context.invocation_metadata() → tuple of (key, value) pairs
    meta = dict(context.invocation_metadata())
    auth  = meta.get("authorization", "")
    req_id = meta.get("x-request-id", "unknown")

    print(f"[{req_id}] GetUser called, auth header present: {bool(auth)}")

    # Send trailing metadata back to client
    await context.send_initial_metadata([
        ("x-server-version", "1.0.0"),
    ])
    # ... process ...
    await context.set_trailing_metadata([
        ("x-processed-by", "pod-abc-123"),
    ])
    return User(id=request.id, name="Alice")

# ── Reading trailing metadata on the client ────────────────────────────────
async def client_read_trailing_meta(stub):
    call = stub.GetUser(GetUserRequest(id=1))
    user = await call

    trailing = await call.trailing_metadata()
    for key, val in trailing:
        print(f"Trailing: {key} = {val}")
'''

print(METADATA_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — DEADLINES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 9 — DEADLINES & TIMEOUTS")
print("=" * 70)

DEADLINES_CODE = '''
import asyncio
import grpc
from grpc import aio

# ── Client: set deadline via timeout= ─────────────────────────────────────
async def client_with_deadline(stub):
    try:
        # timeout in seconds — propagated to server automatically
        response = await stub.GetUser(
            GetUserRequest(id=1),
            timeout=2.0,   # deadline: 2 seconds from now
        )
        return response
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            print("Server did not respond in time")
        raise

# ── Server: check time remaining ──────────────────────────────────────────
async def LongOperation(self, request, context):
    # context.time_remaining() → seconds left before deadline
    remaining = context.time_remaining()
    print(f"Deadline in {remaining:.2f}s")

    for step in range(10):
        if context.cancelled():
            print("Client cancelled — stopping work")
            return

        remaining = context.time_remaining()
        if remaining is not None and remaining < 0.5:
            await context.abort(
                grpc.StatusCode.DEADLINE_EXCEEDED,
                "Not enough time to complete operation"
            )

        # Do one unit of work
        await asyncio.sleep(0.3)

    return SomeResponse(result="done")

# ── Deadline propagation through service chains ────────────────────────────
# When Service A calls Service B with the same deadline,
# the total budget is shared. This prevents cascading slow calls.

async def service_a_handler(self, request, context):
    remaining = context.time_remaining()
    # Reserve 200ms for ourselves, pass the rest to service B
    downstream_timeout = max(0.0, remaining - 0.2) if remaining else 5.0

    downstream_result = await service_b_stub.CallB(
        request,
        timeout=downstream_timeout,
    )
    return build_response(downstream_result)

# BEST PRACTICES:
# - Always set deadlines on client calls (no timeout = infinite hang)
# - Check context.cancelled() in long-running server operations
# - Propagate deadlines through service chains
# - Use shorter deadlines for health checks (50-200ms)
# - Use longer deadlines for batch operations (30-300s)
'''

print(DEADLINES_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — REFLECTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 10 — gRPC REFLECTION")
print("=" * 70)

REFLECTION_CODE = '''
# gRPC Server Reflection allows tools like grpcurl / gRPC UI to
# discover your service's methods without the .proto file.

# pip install grpcio-reflection

from grpc_reflection.v1alpha import reflection, reflection_pb2

async def serve_with_reflection():
    server = aio.server()

    # Add your servicer
    # add_UserServiceServicer_to_server(UserServiceServicer(), server)

    # Enable reflection — list the service names to expose
    service_names = (
        "user.UserService",
        reflection.SERVICE_NAME,   # reflection itself
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()

# ── Using grpcurl to interact with a reflection-enabled server ─────────────
GRPCURL_COMMANDS = """
# List all services
grpcurl -plaintext localhost:50051 list

# List methods of a service
grpcurl -plaintext localhost:50051 list user.UserService

# Describe a message
grpcurl -plaintext localhost:50051 describe user.User

# Call a unary RPC
grpcurl -plaintext -d \'{"id": 1}\' localhost:50051 user.UserService/GetUser

# Call with auth metadata
grpcurl -plaintext \\
    -H "authorization: Bearer my-token" \\
    -d \'{"name": "Alice", "email": "alice@example.com"}\' \\
    localhost:50051 user.UserService/CreateUser

# Server streaming
grpcurl -plaintext \\
    -d \'{"page": 1, "page_size": 5}\' \\
    localhost:50051 user.UserService/ListUsers
"""
print(GRPCURL_COMMANDS)
'''

print(REFLECTION_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 — PATTERNS & BEST PRACTICES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 11 — PATTERNS & BEST PRACTICES")
print("=" * 70)

PATTERNS = """
── gRPC GATEWAY (HTTP/JSON → gRPC) ───────────────────────────────────────────
  Problem: browsers can't call gRPC directly.
  Solution: grpc-gateway (Go) or envoy proxy translates HTTP/JSON → gRPC.

  Annotate your .proto with HTTP options:
    import "google/api/annotations.proto";
    rpc GetUser(GetUserRequest) returns (User) {
        option (google.api.http) = {
            get: "/v1/users/{id}"
        };
    }

  Then grpc-gateway generates a REST proxy.
  For Python: use grpcio-httpjson-transcoding or put an Envoy sidecar.

── PROTO BEST PRACTICES ──────────────────────────────────────────────────────
  1. NEVER reuse or reassign field numbers (breaks backward compatibility)
  2. Deprecate fields with [deprecated=true] — don't delete them
  3. Add new fields freely (unknown fields are ignored in proto3)
  4. Reserve removed field numbers: reserved 5, 9 to 11;
  5. Use well-known types: google.protobuf.Timestamp (not string dates)
  6. Use google.protobuf.Duration for time spans
  7. Use google.protobuf.Struct for flexible JSON-like payloads
  8. Prefix enum values with the enum name: enum Color { COLOR_RED = 0; }
  9. Put the 0 enum value as *_UNSPECIFIED — it's the default in proto3
  10. Version your packages: package user.v1; → user.v2;

── CHANNEL MANAGEMENT ────────────────────────────────────────────────────────
  - Reuse channels — creating a channel is expensive (TLS handshake)
  - Use a single global channel per target address
  - Channels are thread-safe and goroutine/coroutine-safe
  - Use channel.channel_ready() to check connection health

── LOAD BALANCING ────────────────────────────────────────────────────────────
  # Round-robin across multiple backends
  channel = aio.insecure_channel(
      "dns:///my-service.default.svc.cluster.local:50051",
      options=[("grpc.lb_policy_name", "round_robin")]
  )

── KEEPALIVE ─────────────────────────────────────────────────────────────────
  # Prevent idle connections from being dropped by NAT/firewalls
  options = [
      ("grpc.keepalive_time_ms",                  30_000),   # ping every 30s
      ("grpc.keepalive_timeout_ms",               5_000),    # wait 5s for ACK
      ("grpc.keepalive_permit_without_calls",     True),     # ping even idle
      ("grpc.http2.min_time_between_pings_ms",    10_000),
  ]
"""
print(PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12 — INTERVIEW Q&A
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 12 — INTERVIEW Q&A (12 Questions)")
print("=" * 70)

QA = """
Q1. What is gRPC and what makes it faster than REST?
A1. gRPC is a high-performance RPC framework using HTTP/2 and Protocol Buffers.
    Faster because: (a) binary Protobuf serialization is 3-10x smaller than JSON,
    (b) HTTP/2 multiplexing sends multiple RPCs over one TCP connection,
    (c) header compression (HPACK) reduces overhead, (d) no JSON parsing cost.

Q2. What are the 4 types of gRPC RPCs?
A2. 1. Unary        — single request, single response (like a normal function call)
    2. Server-stream — single request, stream of responses (e.g., live feed)
    3. Client-stream — stream of requests, single response (e.g., file upload)
    4. Bidi-stream   — stream of requests AND stream of responses (e.g., chat)

Q3. Why do Protobuf fields have numbers and what happens if you change them?
A3. Field numbers identify fields on the wire (not names). Changing a field
    number for an existing field is a BREAKING CHANGE — old clients can't read
    new messages. Always add new fields with new numbers; use `reserved` to
    block reuse of old numbers.

Q4. What is a discriminated union in gRPC? (oneof)
A4. `oneof` in Protobuf means only ONE of the listed fields can be set at a
    time. Useful for sum types / variants. Setting one clears all others.
    In Python: check which field is set with HasField() or the *_oneof* name.

Q5. How do gRPC deadlines work differently from HTTP timeouts?
A5. gRPC deadlines are absolute points in time that propagate through service
    chains. If Service A calls B with a deadline of T, B's handler knows the
    same T and can check context.time_remaining(). This prevents cascading
    slowness — every hop shares the same budget.

Q6. What is gRPC reflection and why is it useful?
A6. Server Reflection exposes your service schema at runtime without sharing
    .proto files. Tools like grpcurl and gRPC UI use it to discover methods,
    call RPCs, and inspect messages — critical for debugging and API exploration.

Q7. How do you handle authentication in gRPC?
A7. Via metadata (equivalent to HTTP headers). Send "authorization: Bearer <token>"
    in the client call's metadata list. The server reads context.invocation_metadata()
    in a ServerInterceptor or the servicer, validates the token, and aborts with
    UNAUTHENTICATED if invalid.

Q8. What is the difference between PERMISSION_DENIED and UNAUTHENTICATED?
A8. UNAUTHENTICATED — caller identity unknown (missing/invalid token).
    PERMISSION_DENIED — caller is authenticated but lacks authorization
    for this specific action (wrong role, wrong resource).

Q9. How do you do streaming in Python asyncio with gRPC?
A9. Server-streaming: iterate the stub call with `async for`.
    Client-streaming: pass an async generator to the stub call.
    Bidi-streaming: pass async generator; iterate the returned async iterator.
    The aio (asyncio) variant of the gRPC library is required.

Q10. What is a gRPC ServerInterceptor used for?
A10. Cross-cutting concerns that apply to all RPCs: authentication, logging,
     metrics/tracing, rate limiting, request ID injection. Interceptors wrap
     the `continuation` callable and run before/after every handler.

Q11. How do you ensure backward compatibility in Protobuf?
A11. Rules: (a) never change existing field numbers, (b) never rename fields
     you removed — reserve their numbers, (c) new optional fields are safe to
     add (old clients ignore unknown fields), (d) never change a field's type
     incompatibly (e.g., int32 → string), (e) version packages when breaking.

Q12. When would you choose REST over gRPC?
A12. REST is better when: (a) clients are browsers (no gRPC-Web proxy available),
     (b) the API is public and consumers use varied languages/tools, (c) human
     readability of requests/responses matters, (d) team is unfamiliar with
     Protobuf tooling. gRPC wins for internal microservices, real-time streaming,
     and high-throughput low-latency scenarios.
"""
print(QA)
