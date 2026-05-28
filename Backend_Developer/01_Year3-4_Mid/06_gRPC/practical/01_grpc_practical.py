"""
Phase3_gRPC — Complete gRPC Practical
======================================
Topics covered:
  1. .proto file patterns (shown as strings with explanations)
  2. gRPC Server: Unary, Server-Streaming, Client-Streaming, Bidirectional
  3. gRPC Client with timeout, metadata, error handling
  4. Interceptors: Auth + Logging
  5. Error handling with StatusCode
  6. Protobuf vs JSON size comparison
  7. gRPC vs REST vs GraphQL decision guide
  8. Simulated gRPC patterns (runs without grpc installed)

Install (for real gRPC usage):
  pip install grpcio grpcio-tools

Run:
  python 01_grpc_practical.py
"""

import asyncio
import json
import time
import struct
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Any

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: .proto File Patterns
# INTERVIEW: Proto3 syntax, message fields, service definition
# ─────────────────────────────────────────────────────────────────────────────

USER_SERVICE_PROTO = """
// user_service.proto
syntax = "proto3";

package userservice;

import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";

// ─── Message Types ───
message User {
  int32  id       = 1;   // Field numbers 1-15 → 1 byte tag (use for frequent fields)
  string name     = 2;   // Field numbers 16-2047 → 2 bytes tag
  string email    = 3;
  string role     = 4;
  bool   is_active = 5;
  // INTERVIEW: google.protobuf.Timestamp = UTC timestamp
  google.protobuf.Timestamp created_at = 6;
}

message CreateUserRequest {
  string name     = 1;
  string email    = 2;
  string password = 3;  // INTERVIEW: Never store plain password — this is just the API input
}

message GetUserRequest {
  int32 user_id = 1;
}

message ListUsersRequest {
  int32  page        = 1;
  int32  page_size   = 2;
  string role_filter = 3;  // optional in proto3 (zero-value = empty string = omitted)
}

message ListUsersResponse {
  repeated User users = 1;  // repeated = list/array
  int32        total  = 2;
  bool         has_next = 3;
}

// INTERVIEW: proto3 optional = field presence tracking
message UpdateUserRequest {
  int32           user_id = 1;
  optional string name    = 2;   // optional means "can distinguish missing vs empty string"
  optional string role    = 3;
}

// ─── Service Definition ───
// INTERVIEW: 4 types of RPC
service UserService {
  // 1. Unary: 1 request → 1 response (like REST)
  rpc CreateUser(CreateUserRequest)   returns (User);
  rpc GetUser(GetUserRequest)         returns (User);
  rpc UpdateUser(UpdateUserRequest)   returns (User);
  rpc DeleteUser(GetUserRequest)      returns (google.protobuf.Empty);

  // 2. Server Streaming: 1 request → stream of responses
  rpc ListUsers(ListUsersRequest)     returns (stream User);
  rpc WatchUser(GetUserRequest)       returns (stream User);  // real-time updates

  // 3. Client Streaming: stream of requests → 1 response
  rpc BulkImportUsers(stream CreateUserRequest) returns (ListUsersResponse);

  // 4. Bidirectional Streaming: stream → stream (real-time sync)
  rpc SyncUsers(stream User)          returns (stream User);
}
"""

GENERATE_CODE_COMMANDS = """
# ─── Generate Python code from .proto ───
pip install grpcio grpcio-tools

python -m grpc_tools.protoc \\
  -I ./protos \\
  --python_out=./generated \\
  --grpc_python_out=./generated \\
  ./protos/user_service.proto

# Generated files:
# generated/user_service_pb2.py       ← Message classes
# generated/user_service_pb2_grpc.py  ← Server/Client stubs

# INTERVIEW: grpc_python_out generates:
# - UserServiceServicer (abstract server class — you implement methods)
# - UserServiceStub    (client class — you call methods)
# - add_UserServiceServicer_to_server() (registers your implementation)
"""

print("=" * 60)
print("SECTION 1: .proto File Patterns")
print("=" * 60)
print("Key .proto concepts:")
print("  Field numbers 1-15  → 1 byte (use for most common fields)")
print("  Field numbers 16+   → 2 bytes")
print("  repeated = list/array")
print("  optional = track field presence (missing vs empty)")
print("  4 RPC types: Unary, Server-Stream, Client-Stream, Bidi-Stream")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Protobuf Binary Encoding vs JSON
# INTERVIEW: Why Protobuf is faster/smaller than JSON
# ─────────────────────────────────────────────────────────────────────────────

def simulate_protobuf_encode(user: dict) -> bytes:
    """
    INTERVIEW: Protobuf encodes as:
    [field_number << 3 | wire_type] [length] [value]
    Wire types: 0=varint, 2=length-delimited(string/bytes/nested)

    This is a SIMULATION to show the concept — real protobuf is generated code.
    """
    result = bytearray()

    # id (field 1, wire type 0=varint)
    result.extend([0x08])  # (1 << 3) | 0 = 8 = 0x08
    result.extend(_encode_varint(user["id"]))

    # name (field 2, wire type 2=length-delimited)
    name_bytes = user["name"].encode("utf-8")
    result.extend([0x12])  # (2 << 3) | 2 = 18 = 0x12
    result.extend(_encode_varint(len(name_bytes)))
    result.extend(name_bytes)

    # email (field 3, wire type 2)
    email_bytes = user["email"].encode("utf-8")
    result.extend([0x1A])  # (3 << 3) | 2 = 26 = 0x1A
    result.extend(_encode_varint(len(email_bytes)))
    result.extend(email_bytes)

    return bytes(result)


def _encode_varint(value: int) -> bytes:
    """Varint encoding: 7 bits per byte, MSB=1 if more bytes follow."""
    result = []
    while value > 127:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


print("\n" + "=" * 60)
print("SECTION 2: Protobuf vs JSON Size Comparison")
print("=" * 60)

sample_user = {"id": 42, "name": "Alice Johnson", "email": "alice@example.com", "role": "admin", "is_active": True}

json_bytes = json.dumps(sample_user).encode()
proto_sim  = simulate_protobuf_encode(sample_user)

print(f"JSON size:      {len(json_bytes)} bytes  → {json_bytes.decode()}")
print(f"Protobuf (sim): {len(proto_sim)} bytes  → {proto_sim.hex()}")
print(f"Size reduction: ~{(1 - len(proto_sim)/len(json_bytes))*100:.0f}%")
print("\nINTERVIEW: Real Protobuf is 3-10x smaller than JSON because:")
print("  • Field names not stored (field numbers used instead)")
print("  • Integers: varint encoding (small numbers = 1-2 bytes)")
print("  • No quotes, braces, colons (pure binary)")
print("  • Parsing: binary decode vs JSON string parse")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Simulated gRPC Server (Pattern Demo without grpc installed)
# ─────────────────────────────────────────────────────────────────────────────

class StatusCode(Enum):
    OK               = 0
    CANCELLED        = 1
    UNKNOWN          = 2
    INVALID_ARGUMENT = 3
    NOT_FOUND        = 5
    ALREADY_EXISTS   = 6
    PERMISSION_DENIED = 7
    UNAUTHENTICATED  = 16
    RESOURCE_EXHAUSTED = 8
    INTERNAL         = 13


@dataclass
class RpcContext:
    """Simulates grpc.ServicerContext"""
    _code:    StatusCode = StatusCode.OK
    _details: str = ""
    _cancelled: bool = False
    _metadata: dict = field(default_factory=dict)

    def set_code(self, code: StatusCode): self._code = code
    def set_details(self, details: str):  self._details = details
    def cancelled(self) -> bool:          return self._cancelled
    def invocation_metadata(self) -> dict: return self._metadata
    def abort(self, code, details):
        self._code = code
        self._details = details
        raise RpcError(code, details)


class RpcError(Exception):
    def __init__(self, code: StatusCode, details: str):
        self.code_val = code
        self._details = details
        super().__init__(f"gRPC Error [{code.name}]: {details}")

    def code(self): return self.code_val
    def details(self): return self._details


# Fake in-memory user database
USERS_DB: dict[int, dict] = {
    1: {"id": 1, "name": "Alice Johnson", "email": "alice@example.com", "role": "admin",   "is_active": True},
    2: {"id": 2, "name": "Bob Smith",     "email": "bob@example.com",   "role": "user",    "is_active": True},
    3: {"id": 3, "name": "Charlie Lee",   "email": "charlie@example.com","role": "moderator","is_active": False},
}
_next_id = 4


class UserServiceServicer:
    """
    INTERVIEW: This is what you implement when using gRPC server.
    Inherits from generated UserServiceServicer (stub methods raise NotImplementedError).
    """

    # ── Unary RPC ──────────────────────────────────────────────────────────
    async def GetUser(self, request: dict, context: RpcContext) -> dict:
        """Unary: 1 request → 1 response"""
        user_id = request["user_id"]
        user = USERS_DB.get(user_id)

        if not user:
            context.set_code(StatusCode.NOT_FOUND)
            context.set_details(f"User {user_id} not found")
            return {}

        return user

    async def CreateUser(self, request: dict, context: RpcContext) -> dict:
        """Unary with validation"""
        global _next_id

        if not request.get("email"):
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details("Email is required")
            return {}

        # Check duplicate
        for user in USERS_DB.values():
            if user["email"] == request["email"]:
                context.set_code(StatusCode.ALREADY_EXISTS)
                context.set_details(f"Email {request['email']} already registered")
                return {}

        new_user = {
            "id": _next_id,
            "name": request["name"],
            "email": request["email"],
            "role": "user",
            "is_active": True,
        }
        USERS_DB[_next_id] = new_user
        _next_id += 1
        return new_user

    # ── Server Streaming RPC ───────────────────────────────────────────────
    async def ListUsers(self, request: dict, context: RpcContext) -> AsyncGenerator[dict, None]:
        """
        INTERVIEW: Server streaming — server yields multiple responses.
        Client iterates: async for user in stub.ListUsers(request): ...
        Use for: paginated lists, large datasets, real-time feeds
        """
        page_size  = request.get("page_size", 10)
        role_filter = request.get("role_filter", "")

        users = list(USERS_DB.values())
        if role_filter:
            users = [u for u in users if u["role"] == role_filter]

        for user in users[:page_size]:
            await asyncio.sleep(0.05)  # Simulate DB read time
            yield user

    async def WatchUser(self, request: dict, context: RpcContext) -> AsyncGenerator[dict, None]:
        """
        INTERVIEW: Long-running server stream (real-time updates).
        context.cancelled() check karo — client disconnect hone par stop karo.
        """
        user_id = request["user_id"]
        for _ in range(3):  # 3 updates for demo
            if context.cancelled():
                return
            user = USERS_DB.get(user_id, {})
            if user:
                yield user
            await asyncio.sleep(0.1)

    # ── Client Streaming RPC ───────────────────────────────────────────────
    async def BulkImportUsers(self, request_iterator, context: RpcContext) -> dict:
        """
        INTERVIEW: Client streaming — client sends stream, server sends 1 response.
        Use for: bulk uploads, file chunks, batch processing
        """
        created = 0
        errors  = 0

        async for req in request_iterator:
            try:
                ctx = RpcContext()
                result = await self.CreateUser(req, ctx)
                if ctx._code == StatusCode.OK:
                    created += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        return {"total": created + errors, "created": created, "errors": errors}

    # ── Bidirectional Streaming RPC ────────────────────────────────────────
    async def SyncUsers(self, request_iterator, context: RpcContext) -> AsyncGenerator[dict, None]:
        """
        INTERVIEW: Bidi streaming — both sides send stream simultaneously.
        Use for: real-time sync, chat, collaborative editing
        """
        async for request in request_iterator:
            user_id = request.get("id")
            if user_id and user_id in USERS_DB:
                # Update + yield back confirmed state
                USERS_DB[user_id].update({k: v for k, v in request.items() if v})
                yield USERS_DB[user_id]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: gRPC Interceptors (Server-side Middleware)
# INTERVIEW: Interceptors = gRPC middleware (auth, logging, metrics)
# ─────────────────────────────────────────────────────────────────────────────

class BaseInterceptor:
    """Simulates grpc.aio.ServerInterceptor"""
    async def intercept(self, method_name: str, request: dict, context: RpcContext, handler):
        return await handler(request, context)


class LoggingInterceptor(BaseInterceptor):
    async def intercept(self, method_name: str, request: dict, context: RpcContext, handler):
        start = time.perf_counter()
        print(f"  [gRPC LOG] → {method_name} | request: {request}")
        try:
            result = await handler(request, context)
            duration = (time.perf_counter() - start) * 1000
            print(f"  [gRPC LOG] ← {method_name} | {context._code.name} | {duration:.1f}ms")
            return result
        except Exception as e:
            print(f"  [gRPC LOG] ✗ {method_name} | ERROR: {e}")
            raise


class AuthInterceptor(BaseInterceptor):
    EXCLUDED_METHODS = ["/Health/Check"]

    def __init__(self, valid_tokens: set[str]):
        self.valid_tokens = valid_tokens

    async def intercept(self, method_name: str, request: dict, context: RpcContext, handler):
        if any(exc in method_name for exc in self.EXCLUDED_METHODS):
            return await handler(request, context)

        token = context._metadata.get("authorization", "").replace("Bearer ", "")
        if token not in self.valid_tokens:
            context.set_code(StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid or missing token")
            raise RpcError(StatusCode.UNAUTHENTICATED, "Invalid token")

        return await handler(request, context)


class GrpcServer:
    """Simulated gRPC server with interceptor chain."""

    def __init__(self, servicer: UserServiceServicer, interceptors: list[BaseInterceptor]):
        self.servicer    = servicer
        self.interceptors = interceptors

    async def _run_interceptors(self, method_name, request, context, handler, idx=0):
        if idx >= len(self.interceptors):
            return await handler(request, context)
        interceptor = self.interceptors[idx]
        return await interceptor.intercept(
            method_name, request, context,
            lambda req, ctx: self._run_interceptors(method_name, req, ctx, handler, idx + 1)
        )

    async def call(self, method: str, request: dict, metadata: dict = None) -> dict | list:
        context = RpcContext(_metadata=metadata or {})
        handler = getattr(self.servicer, method)
        return await self._run_interceptors(method, request, context, handler)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: gRPC Client Pattern
# INTERVIEW: How client calls look, error handling
# ─────────────────────────────────────────────────────────────────────────────

GRPC_CLIENT_CODE = '''
# ─── Real gRPC Client (needs grpcio + generated code) ───
import grpc
from generated import user_service_pb2, user_service_pb2_grpc

class UserServiceClient:
    def __init__(self, host: str = "localhost:50051"):
        # INTERVIEW: Channel = connection to server (reuse it!)
        self.channel = grpc.aio.insecure_channel(
            host,
            options=[
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_permit_without_calls", True),
                ("grpc.max_receive_message_length", 10 * 1024 * 1024),
            ]
        )
        self.stub = user_service_pb2_grpc.UserServiceStub(self.channel)

    async def get_user(self, user_id: int) -> dict:
        try:
            user = await self.stub.GetUser(
                user_service_pb2.GetUserRequest(user_id=user_id),
                timeout=10,                     # ← CRITICAL: always set timeout
                metadata=[                      # ← Auth header
                    ("authorization", f"Bearer {get_service_token()}")
                ]
            )
            return {"id": user.id, "name": user.name, "email": user.email}
        except grpc.RpcError as e:
            # INTERVIEW: Always handle grpc.RpcError
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            elif e.code() == grpc.StatusCode.UNAUTHENTICATED:
                raise AuthError("Service token expired")
            raise ServiceUnavailableError(f"UserService error: {e.details()}")

    async def list_users_stream(self, page_size: int = 100):
        """INTERVIEW: Server streaming — async for loop"""
        async for user in self.stub.ListUsers(
            user_service_pb2.ListUsersRequest(page_size=page_size),
            timeout=30
        ):
            yield {"id": user.id, "name": user.name}

    async def bulk_import(self, users: list[dict]) -> dict:
        """INTERVIEW: Client streaming — async generator as request"""
        async def request_gen():
            for u in users:
                yield user_service_pb2.CreateUserRequest(**u)
                await asyncio.sleep(0)  # yield control

        response = await self.stub.BulkImportUsers(request_gen(), timeout=60)
        return {"total": response.total}

    async def close(self):
        await self.channel.close()

# ─── FastAPI integration ───
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create once at startup, share across requests
    app.state.user_client = UserServiceClient("user-service:50051")
    yield
    await app.state.user_client.close()

app = FastAPI(lifespan=lifespan)

@app.get("/users/{user_id}")
async def get_user(user_id: int, request: Request):
    client: UserServiceClient = request.app.state.user_client
    user = await client.get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user
'''


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Error Status Codes
# INTERVIEW: gRPC uses StatusCode instead of HTTP status codes
# ─────────────────────────────────────────────────────────────────────────────

STATUS_CODE_MAP = {
    "INVALID_ARGUMENT":   "400 Bad Request — validation failed",
    "NOT_FOUND":          "404 Not Found — resource missing",
    "ALREADY_EXISTS":     "409 Conflict — duplicate resource",
    "PERMISSION_DENIED":  "403 Forbidden — authenticated but no permission",
    "UNAUTHENTICATED":    "401 Unauthorized — not authenticated",
    "RESOURCE_EXHAUSTED": "429 Too Many Requests — rate limited",
    "INTERNAL":           "500 Internal Server Error",
    "UNAVAILABLE":        "503 Service Unavailable — server down",
    "DEADLINE_EXCEEDED":  "504 Gateway Timeout — timeout hit",
    "UNIMPLEMENTED":      "501 Not Implemented — method not implemented",
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Full Demo Runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_demo():
    print("\n" + "=" * 60)
    print("SECTION 3: gRPC Server + Interceptors Demo")
    print("=" * 60)

    servicer    = UserServiceServicer()
    server      = GrpcServer(
        servicer=servicer,
        interceptors=[
            AuthInterceptor(valid_tokens={"service-token-abc123"}),
            LoggingInterceptor(),
        ]
    )

    # ── Test Unary: GetUser ──
    print("\n[Unary] GetUser(user_id=1):")
    result = await server.call("GetUser", {"user_id": 1},
                               metadata={"authorization": "Bearer service-token-abc123"})
    print(f"  Result: {result}")

    # ── Test Unary: Not Found ──
    print("\n[Unary] GetUser(user_id=999) — NOT_FOUND:")
    try:
        await server.call("GetUser", {"user_id": 999},
                          metadata={"authorization": "Bearer service-token-abc123"})
    except Exception as e:
        print(f"  Error caught: {e}")

    # ── Test Auth Interceptor ──
    print("\n[Auth] GetUser with wrong token — UNAUTHENTICATED:")
    try:
        await server.call("GetUser", {"user_id": 1},
                          metadata={"authorization": "Bearer WRONG-TOKEN"})
    except RpcError as e:
        print(f"  Error: [{e.code_val.name}] {e._details}")

    # ── Test CreateUser ──
    print("\n[Unary] CreateUser:")
    result = await server.call(
        "CreateUser",
        {"name": "Dave Wilson", "email": "dave@example.com", "password": "hashed"},
        metadata={"authorization": "Bearer service-token-abc123"}
    )
    print(f"  Created: {result}")

    # ── Test Server Streaming ──
    print("\n[Server Stream] ListUsers:")
    context  = RpcContext()
    count    = 0
    async for user in servicer.ListUsers({"page_size": 10}, context):
        print(f"  Streaming user: {user['name']} ({user['role']})")
        count += 1
    print(f"  Total streamed: {count} users")

    # ── Test Client Streaming ──
    print("\n[Client Stream] BulkImportUsers:")

    async def bulk_requests():
        for i, u in enumerate([
            {"name": "User E", "email": "usere@example.com", "password": "pw"},
            {"name": "User F", "email": "userf@example.com", "password": "pw"},
            {"name": "", "email": "",  "password": "pw"},   # invalid
        ]):
            yield u

    context = RpcContext()
    result  = await servicer.BulkImportUsers(bulk_requests(), context)
    print(f"  Bulk import: {result}")

    # ── Status Code Map ──
    print("\n" + "=" * 60)
    print("SECTION 6: gRPC StatusCode → HTTP Status Code Mapping")
    print("=" * 60)
    for code, http in STATUS_CODE_MAP.items():
        print(f"  {code:<22} → {http}")

    # ── Decision Guide ──
    print("\n" + "=" * 60)
    print("SECTION 7: gRPC vs REST vs GraphQL — When to Use")
    print("=" * 60)
    guide = [
        ("Internal microservice calls", "gRPC", "HTTP/2 + binary = fastest"),
        ("Public API for developers",   "REST", "Easy to use, curl/browser support"),
        ("Browser client (web app)",    "REST", "gRPC needs grpc-web proxy"),
        ("Multiple client shapes",      "GraphQL", "Mobile vs web vs desktop needs"),
        ("Real-time chat / game",        "gRPC Bidi", "Native bidirectional streaming"),
        ("Bulk data streaming",          "gRPC Server-Stream", "Efficient chunked delivery"),
        ("Simple CRUD microservice",     "REST", "Lower learning curve"),
        ("Polyglot services (Go+Python)","gRPC", "Proto schema = any language client"),
    ]
    for use_case, choice, reason in guide:
        print(f"  {use_case:<35} → {choice:<20} ({reason})")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_demo())
