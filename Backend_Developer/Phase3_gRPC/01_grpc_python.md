# gRPC — Protocol Buffers, Python Server/Client, gRPC vs REST

## Quick Concepts
- **gRPC** = Google's RPC framework — HTTP/2 + Protocol Buffers
- **Protobuf** = binary serialization format — JSON se 3-10x faster + smaller
- **Unary RPC** = ek request, ek response (like REST)
- **Server Streaming** = server multiple responses bhejta hai
- **Client Streaming** = client multiple requests bhejta hai
- **Bidirectional Streaming** = dono taraf streaming

---

## Interview Questions & Answers

### Q1: gRPC kya hai? REST se kaise alag hai? Kab use karo?
**Answer:**
```
gRPC vs REST:

PROTOCOL:
  REST   → HTTP/1.1 + JSON (text)
  gRPC   → HTTP/2 + Protobuf (binary)

PERFORMANCE:
  REST   → JSON parse karna padta hai (slow)
  gRPC   → binary, 3-10x faster, 60-80% smaller payload

STREAMING:
  REST   → SSE ya WebSocket (workaround)
  gRPC   → native bidirectional streaming

SCHEMA:
  REST   → optional (OpenAPI)
  gRPC   → mandatory .proto file (type-safe)

CODE GENERATION:
  REST   → manual
  gRPC   → auto-generate client/server in any language

BROWSER:
  REST   → native support
  gRPC   → grpc-web needed (extra setup)

USE gRPC WHEN:
  ✓ Internal microservices (high performance)
  ✓ Real-time streaming (chat, live data)
  ✓ Polyglot services (Python → Go → Java)
  ✓ Low latency critical

USE REST WHEN:
  ✓ Public API (external developers)
  ✓ Browser clients
  ✓ Simple CRUD
  ✓ Team gRPC se unfamiliar
```

---

### Q2: .proto file kaise likhte hain?
**Answer:**
```protobuf
// user_service.proto
syntax = "proto3";

package userservice;

// Import karo
import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";

// Message definitions
message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
  string role = 4;
  bool is_active = 5;
  google.protobuf.Timestamp created_at = 6;
}

message CreateUserRequest {
  string name = 1;
  string email = 2;
  string password = 3;
}

message GetUserRequest {
  int32 user_id = 1;
}

message ListUsersRequest {
  int32 page = 1;
  int32 page_size = 2;
  string role_filter = 3;  // optional
}

message ListUsersResponse {
  repeated User users = 1;
  int32 total = 2;
  bool has_next = 3;
}

message UpdateUserRequest {
  int32 user_id = 1;
  optional string name = 2;   // proto3 optional
  optional string role = 3;
}

// Service definition
service UserService {
  // Unary RPC
  rpc CreateUser(CreateUserRequest) returns (User);
  rpc GetUser(GetUserRequest) returns (User);
  rpc UpdateUser(UpdateUserRequest) returns (User);
  rpc DeleteUser(GetUserRequest) returns (google.protobuf.Empty);

  // Server streaming — live user activity
  rpc WatchUser(GetUserRequest) returns (stream User);

  // Client streaming — bulk import
  rpc BulkImportUsers(stream CreateUserRequest) returns (ListUsersResponse);

  // Bidirectional streaming — real-time sync
  rpc SyncUsers(stream User) returns (stream User);

  // Server streaming paginated list
  rpc ListUsers(ListUsersRequest) returns (stream User);
}
```

```bash
# Python code generate karo
pip install grpcio grpcio-tools

python -m grpc_tools.protoc \
  -I ./protos \
  --python_out=./generated \
  --grpc_python_out=./generated \
  ./protos/user_service.proto

# Generated files:
# generated/user_service_pb2.py       (message classes)
# generated/user_service_pb2_grpc.py  (server/client stubs)
```

---

### Q3: gRPC Server Python mein kaise banate hain?
**Answer:**
```python
# server.py
import grpc
import asyncio
from concurrent import futures
from generated import user_service_pb2, user_service_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp
from datetime import datetime

class UserServiceServicer(user_service_pb2_grpc.UserServiceServicer):

    async def CreateUser(self, request, context):
        # Validation
        if not request.email:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Email is required")
            return user_service_pb2.User()

        try:
            user = await create_user_in_db(request.name, request.email, request.password)
        except DuplicateEmailError:
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            context.set_details(f"Email {request.email} already registered")
            return user_service_pb2.User()

        return self._user_to_proto(user)

    async def GetUser(self, request, context):
        user = await get_user_from_db(request.user_id)
        if not user:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"User {request.user_id} not found")
            return user_service_pb2.User()
        return self._user_to_proto(user)

    async def ListUsers(self, request, context):
        """Server streaming — ek ek user bhejo"""
        async for user in stream_users_from_db(request.page_size):
            yield self._user_to_proto(user)

    async def WatchUser(self, request, context):
        """Server streaming — user changes real-time"""
        while not context.cancelled():
            user = await get_user_from_db(request.user_id)
            yield self._user_to_proto(user)
            await asyncio.sleep(5)   # 5s mein check karo

    async def BulkImportUsers(self, request_iterator, context):
        """Client streaming — sab users receive karo, phir response"""
        created = 0
        async for req in request_iterator:
            await create_user_in_db(req.name, req.email, req.password)
            created += 1
        return user_service_pb2.ListUsersResponse(total=created)

    def _user_to_proto(self, user) -> user_service_pb2.User:
        ts = Timestamp()
        ts.FromDatetime(user.created_at)
        return user_service_pb2.User(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=ts,
        )

async def serve():
    server = grpc.aio.server(
        options=[
            ("grpc.max_receive_message_length", 10 * 1024 * 1024),  # 10MB
            ("grpc.keepalive_time_ms", 10000),
        ]
    )
    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server
    )

    # TLS ke saath (production)
    with open("server.key", "rb") as f:
        private_key = f.read()
    with open("server.crt", "rb") as f:
        certificate_chain = f.read()

    credentials = grpc.ssl_server_credentials([(private_key, certificate_chain)])
    server.add_secure_port("[::]:50051", credentials)

    # Ya development ke liye insecure
    # server.add_insecure_port("[::]:50051")

    await server.start()
    print("gRPC server running on :50051")
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
```

---

### Q4: gRPC Client Python mein kaise banate hain?
**Answer:**
```python
# client.py
import grpc
import asyncio
from generated import user_service_pb2, user_service_pb2_grpc

class UserServiceClient:
    def __init__(self, host: str = "localhost:50051"):
        self.channel = grpc.aio.insecure_channel(
            host,
            options=[
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_permit_without_calls", True),
            ]
        )
        self.stub = user_service_pb2_grpc.UserServiceStub(self.channel)

    async def create_user(self, name: str, email: str, password: str):
        try:
            user = await self.stub.CreateUser(
                user_service_pb2.CreateUserRequest(
                    name=name, email=email, password=password
                ),
                timeout=10,   # 10 second timeout
                metadata=[    # auth headers
                    ("authorization", f"Bearer {get_internal_token()}")
                ]
            )
            return user
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.ALREADY_EXISTS:
                raise DuplicateEmailError(e.details())
            elif e.code() == grpc.StatusCode.NOT_FOUND:
                raise NotFoundException(e.details())
            raise

    async def list_users_stream(self, page_size: int = 100):
        """Server streaming response iterate karo"""
        async for user in self.stub.ListUsers(
            user_service_pb2.ListUsersRequest(page_size=page_size)
        ):
            yield user

    async def bulk_import(self, users_data: list[dict]):
        """Client streaming"""
        async def request_iterator():
            for user in users_data:
                yield user_service_pb2.CreateUserRequest(**user)

        response = await self.stub.BulkImportUsers(request_iterator())
        return response.total

    async def close(self):
        await self.channel.close()

# FastAPI mein gRPC client use karo
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.user_client = UserServiceClient("user-service:50051")
    yield
    await app.state.user_client.close()

@app.post("/users")
async def create_user(user: UserCreate, request: Request):
    client: UserServiceClient = request.app.state.user_client
    grpc_user = await client.create_user(user.name, user.email, user.password)
    return {"id": grpc_user.id, "name": grpc_user.name}
```

---

### Q5: gRPC Interceptors (middleware jaisa) kaise likhte hain?
**Answer:**
```python
import grpc
import time
import structlog

log = structlog.get_logger()

class LoggingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        start = time.perf_counter()
        method = handler_call_details.method
        log.info("grpc_request", method=method)

        try:
            response = await continuation(handler_call_details)
            duration = (time.perf_counter() - start) * 1000
            log.info("grpc_success", method=method, duration_ms=round(duration, 2))
            return response
        except Exception as e:
            log.error("grpc_error", method=method, error=str(e))
            raise

class AuthInterceptor(grpc.aio.ServerInterceptor):
    EXCLUDED = ["/grpc.health.v1.Health/Check"]

    async def intercept_service(self, continuation, handler_call_details):
        if handler_call_details.method in self.EXCLUDED:
            return await continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata)
        token = metadata.get("authorization", "").replace("Bearer ", "")

        if not verify_internal_token(token):
            async def abort(request, context):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Invalid token")
            return grpc.unary_unary_rpc_method_handler(abort)

        return await continuation(handler_call_details)

# Server mein interceptors add karo
server = grpc.aio.server(
    interceptors=[AuthInterceptor(), LoggingInterceptor()]
)
```

---

### Q6: gRPC vs REST vs GraphQL — Quick Comparison
**Answer:**
```
| Feature          | REST       | gRPC         | GraphQL     |
|------------------|------------|--------------|-------------|
| Protocol         | HTTP/1.1   | HTTP/2       | HTTP/1.1    |
| Format           | JSON       | Protobuf     | JSON        |
| Speed            | Medium     | Fast         | Medium      |
| Streaming        | Limited    | Native       | Subscriptions|
| Schema           | Optional   | Required     | Required    |
| Browser          | Yes        | grpc-web     | Yes         |
| Learning curve   | Low        | Medium       | High        |
| Code generation  | Optional   | Yes          | Yes         |
| Best for         | Public API | Microservices| Flexible queries |
```
