# gRPC Gateway — REST + gRPC Hybrid Services

## Quick Concepts

**WHAT:**
- **gRPC Gateway** = HTTP/REST → gRPC translator (Go-based, popular)
- **Hybrid service** = same backend exposes BOTH gRPC + REST
- **OpenAPI/Swagger** = auto-generated from .proto annotations
- **Single source of truth** = .proto defines API once

**WHY hybrid REST + gRPC:**
- ✅ Public API (REST for external developers)
- ✅ Internal microservices (gRPC for performance)
- ✅ One backend serves both
- ✅ Browser clients (REST) + mobile/services (gRPC)
- ✅ Easy migration path (old clients REST, new clients gRPC)

**HOW translation works:**
```
Browser  ─ HTTP/JSON ─→ Gateway ─ gRPC ─→ Backend
                          ↓
                     Translates:
                     - JSON ↔ Protobuf
                     - URL params ↔ Request fields
                     - HTTP methods ↔ RPC methods
```

---

## Interview Questions & Answers

### Q1: gRPC Gateway kab use karna chahiye? Pros aur cons?

**Answer:**

**WHEN to use:**

| Scenario | Use Gateway? |
|---|---|
| Need public REST API | ✅ Yes |
| Browser clients (no gRPC-Web setup) | ✅ Yes |
| Mobile apps (REST simpler) | ✅ Yes |
| Documentation via Swagger | ✅ Yes |
| Internal services only | ❌ No (use gRPC directly) |
| Want maximum performance | ❌ No (translation overhead) |
| Streaming heavy | ❌ Limited (REST streaming awkward) |

**Pros:**
- ✅ Single .proto = single source of truth
- ✅ Auto-generated OpenAPI/Swagger docs
- ✅ Browser clients without proxy setup
- ✅ Curl-friendly for debugging
- ✅ Existing REST clients work

**Cons:**
- ❌ Extra hop = latency (~1-5ms)
- ❌ Loses HTTP/2 benefits for REST clients
- ❌ Streaming complex (translates to chunked HTTP)
- ❌ Type safety lost in JSON translation

**HOW — Architecture:**

```
                          ┌──────────────────┐
                          │  gRPC Backend    │
                          │  (Python)        │
                          │   :50051         │
                          └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
        ┌───────────▼─────┐ ┌──────▼──────┐ ┌─────▼───────┐
        │ gRPC Gateway    │ │  Envoy      │ │  Direct gRPC│
        │ (HTTP/REST)     │ │ (gRPC-Web)  │ │  Clients    │
        │   :8080         │ │  :8081      │ │             │
        └───────┬─────────┘ └──────┬──────┘ └─────────────┘
                │                  │
        ┌───────▼───────┐  ┌───────▼────────┐
        │ REST Clients  │  │ Browser SPA    │
        │ (mobile/curl) │  │  (React)       │
        └───────────────┘  └────────────────┘
```

---

### Q2: .proto file mein REST mappings kaise add karein?

**Answer:**

**WHAT:** Use `google.api.http` annotations to define REST endpoints.

**HOW — Annotated .proto:**

```protobuf
// user_service.proto
syntax = "proto3";

package userservice;

// ⭐ Import Google API annotations
import "google/api/annotations.proto";

service UserService {

  // GET /v1/users/{user_id}
  rpc GetUser(GetUserRequest) returns (User) {
    option (google.api.http) = {
      get: "/v1/users/{user_id}"
    };
  }

  // GET /v1/users?role=admin&page=1
  rpc ListUsers(ListUsersRequest) returns (ListUsersResponse) {
    option (google.api.http) = {
      get: "/v1/users"
    };
  }

  // POST /v1/users (body = request message as JSON)
  rpc CreateUser(CreateUserRequest) returns (User) {
    option (google.api.http) = {
      post: "/v1/users"
      body: "*"                     // ⭐ Use entire request body
    };
  }

  // POST /v1/users/{user_id}/activate
  rpc ActivateUser(ActivateUserRequest) returns (User) {
    option (google.api.http) = {
      post: "/v1/users/{user_id}/activate"
    };
  }

  // PATCH /v1/users/{user_id} (partial update)
  rpc UpdateUser(UpdateUserRequest) returns (User) {
    option (google.api.http) = {
      patch: "/v1/users/{user.id}"
      body: "user"                  // ⭐ Body field name = "user"
    };
  }

  // DELETE /v1/users/{user_id}
  rpc DeleteUser(DeleteUserRequest) returns (google.protobuf.Empty) {
    option (google.api.http) = {
      delete: "/v1/users/{user_id}"
    };
  }

  // Additional bindings (multiple URLs for same method)
  rpc GetCurrentUser(google.protobuf.Empty) returns (User) {
    option (google.api.http) = {
      get: "/v1/users/me"
      additional_bindings {
        get: "/v1/me"               // ⭐ Alternative URL
      }
    };
  }
}

message GetUserRequest {
  int32 user_id = 1;                // ⭐ Mapped to {user_id} in URL
}

message ListUsersRequest {
  string role_filter = 1;           // ⭐ Mapped to ?role_filter=X
  int32 page = 2;
  int32 page_size = 3;
}
```

---

### Q3: gRPC Gateway Python mein kaise setup karein?

**Answer:**

**NOTE:** Original `grpc-gateway` is Go-based. Python alternatives:
- **`sonora`** — pure Python implementation
- **`python-grpc-gateway`** — community fork
- **Run Go gateway alongside** Python backend

**HOW — Option 1: Sonora (Python gRPC-Web + REST):**

```bash
pip install sonora
```

```python
# server.py — Backend (regular gRPC)
import grpc
from generated import user_service_pb2_grpc

async def serve_grpc():
    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

```python
# gateway.py — REST/HTTP front
from sonora.asgi import grpcASGI
import uvicorn
from generated import user_service_pb2_grpc

# Sonora ASGI app
grpc_asgi_app = grpcASGI(your_servicer)

# Run with uvicorn (HTTP/1.1 + HTTP/2 + REST endpoints)
uvicorn.run(grpc_asgi_app, host="0.0.0.0", port=8080)
```

**HOW — Option 2: Manual REST wrapper with FastAPI:**

```python
# rest_gateway.py
from fastapi import FastAPI, HTTPException, Depends
from generated import user_service_pb2, user_service_pb2_grpc
import grpc
from google.protobuf.json_format import MessageToDict, ParseDict

app = FastAPI(title="User Service REST API")

# Setup gRPC channel (singleton)
channel = grpc.aio.insecure_channel("user-grpc-backend:50051")
stub = user_service_pb2_grpc.UserServiceStub(channel)


# Map gRPC errors to HTTP
def grpc_to_http_status(code: grpc.StatusCode) -> int:
    mapping = {
        grpc.StatusCode.OK: 200,
        grpc.StatusCode.INVALID_ARGUMENT: 400,
        grpc.StatusCode.UNAUTHENTICATED: 401,
        grpc.StatusCode.PERMISSION_DENIED: 403,
        grpc.StatusCode.NOT_FOUND: 404,
        grpc.StatusCode.ALREADY_EXISTS: 409,
        grpc.StatusCode.RESOURCE_EXHAUSTED: 429,
        grpc.StatusCode.UNAVAILABLE: 503,
        grpc.StatusCode.DEADLINE_EXCEEDED: 504,
    }
    return mapping.get(code, 500)


async def call_grpc(method, request_proto):
    """Helper to call gRPC + handle errors."""
    try:
        return await method(request_proto, timeout=10)
    except grpc.RpcError as e:
        raise HTTPException(
            status_code=grpc_to_http_status(e.code()),
            detail=e.details()
        )


# REST endpoints (manual mapping)
@app.get("/v1/users/{user_id}")
async def get_user(user_id: int):
    request = user_service_pb2.GetUserRequest(user_id=user_id)
    response = await call_grpc(stub.GetUser, request)
    return MessageToDict(response, preserving_proto_field_name=True)


@app.post("/v1/users")
async def create_user(body: dict):
    request = user_service_pb2.CreateUserRequest()
    ParseDict(body, request)  # ⭐ JSON → protobuf
    response = await call_grpc(stub.CreateUser, request)
    return MessageToDict(response, preserving_proto_field_name=True)


@app.get("/v1/users")
async def list_users(role_filter: str = "", page: int = 1, page_size: int = 20):
    request = user_service_pb2.ListUsersRequest(
        role_filter=role_filter,
        page=page,
        page_size=page_size,
    )
    response = await call_grpc(stub.ListUsers, request)
    return MessageToDict(response, preserving_proto_field_name=True)
```

```bash
# Run REST gateway
uvicorn rest_gateway:app --port 8080
```

**HOW — Option 3: Use Go gateway alongside Python:**

```bash
# Go gateway generates HTTP→gRPC translator
# Python backend handles gRPC

# Folder structure:
backend/         # Python gRPC server
gateway/         # Go HTTP→gRPC translator (auto-gen)
protos/          # Shared .proto files

# Docker Compose runs both
```

```yaml
# docker-compose.yml
services:
  backend-grpc:
    build: ./backend
    ports: ["50051:50051"]

  gateway-rest:
    build: ./gateway   # Go gateway
    ports: ["8080:8080"]
    environment:
      GRPC_BACKEND: backend-grpc:50051
```

---

### Q4: OpenAPI/Swagger auto-generation kaise karein?

**Answer:**

**WHAT:** Generate Swagger UI from .proto annotations.

**HOW — Using buf + plugin:**

```yaml
# buf.gen.yaml
version: v1
plugins:
  - plugin: buf.build/grpc-ecosystem/openapiv2
    out: gen/openapi
    opt:
      - logtostderr=true
      - output_format=json
```

```bash
buf generate
# Outputs: gen/openapi/user_service.swagger.json
```

**HOW — Serve Swagger UI:**

```python
# In FastAPI app
from fastapi.openapi.docs import get_swagger_ui_html
import json

@app.get("/api-docs/openapi.json")
async def openapi_spec():
    with open("gen/openapi/user_service.swagger.json") as f:
        return json.load(f)


@app.get("/api-docs")
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/api-docs/openapi.json",
        title="User Service API"
    )
```

**HOW — Add descriptions in .proto:**

```protobuf
import "google/api/annotations.proto";
import "protoc-gen-openapiv2/options/annotations.proto";

option (grpc.gateway.protoc_gen_openapiv2.options.openapiv2_swagger) = {
  info: {
    title: "User Service API";
    version: "1.0";
    description: "Manages users in the platform";
  };
  host: "api.example.com";
  schemes: HTTPS;
};

service UserService {
  rpc GetUser(GetUserRequest) returns (User) {
    option (google.api.http) = { get: "/v1/users/{user_id}" };
    option (grpc.gateway.protoc_gen_openapiv2.options.openapiv2_operation) = {
      summary: "Get user by ID";
      description: "Returns user details by their unique ID.";
      tags: ["Users"];
      responses: {
        key: "404"
        value: { description: "User not found" }
      };
    };
  }
}
```

---

### Q5: Path parameters, query params, body mappings exactly kaise kaam karte hain?

**Answer:**

**HOW — Path parameters:**

```protobuf
// URL: GET /v1/users/{user_id}/orders/{order_id}
rpc GetOrder(GetOrderRequest) returns (Order) {
  option (google.api.http) = {
    get: "/v1/users/{user_id}/orders/{order_id}"
  };
}

message GetOrderRequest {
  int32 user_id = 1;     // ⭐ {user_id} in URL
  int32 order_id = 2;    // ⭐ {order_id} in URL
}
```

**HOW — Query parameters (everything not in path/body):**

```protobuf
// URL: GET /v1/users?role=admin&page=1&page_size=20
rpc ListUsers(ListUsersRequest) returns (ListUsersResponse) {
  option (google.api.http) = {
    get: "/v1/users"
  };
}

message ListUsersRequest {
  // All fields → query params (since GET has no body)
  string role = 1;          // ?role=admin
  int32 page = 2;            // ?page=1
  int32 page_size = 3;       // ?page_size=20
  bool include_inactive = 4; // ?include_inactive=true
}
```

**HOW — Body (entire message):**

```protobuf
// URL: POST /v1/users
// Body: { "name": "Alice", "email": "..." }
rpc CreateUser(CreateUserRequest) returns (User) {
  option (google.api.http) = {
    post: "/v1/users"
    body: "*"                  // ⭐ * = use entire request as body
  };
}
```

**HOW — Body (specific field):**

```protobuf
// URL: PUT /v1/users/{user_id}
// Body: { "name": "...", "email": "..." } (the User object)
rpc UpdateUser(UpdateUserRequest) returns (User) {
  option (google.api.http) = {
    put: "/v1/users/{user_id}"
    body: "user"               // ⭐ Only `user` field is body
  };
}

message UpdateUserRequest {
  int32 user_id = 1;            // From URL path
  User user = 2;                 // From body
}
```

**HOW — Mixed:**

```protobuf
// URL: POST /v1/users/{user_id}/preferences?notify=true
// Body: { "theme": "dark", "language": "en" }
rpc UpdatePreferences(UpdatePrefsRequest) returns (Empty) {
  option (google.api.http) = {
    post: "/v1/users/{user_id}/preferences"
    body: "preferences"
  };
}

message UpdatePrefsRequest {
  int32 user_id = 1;             // URL path
  bool notify = 2;                // Query param
  Preferences preferences = 3;    // Body
}
```

---

### Q6: REST clients ke liye streaming kaise expose karein?

**Answer:**

**WHAT:** gRPC streaming → REST equivalent (server-sent events or chunked transfer).

**HOW — Server streaming → SSE (Server-Sent Events):**

```python
from fastapi.responses import StreamingResponse
import json

@app.get("/v1/users/{user_id}/notifications/stream")
async def stream_notifications_sse(user_id: int):
    """SSE endpoint that wraps gRPC streaming."""
    request = SubscribeRequest(user_id=str(user_id))

    async def event_generator():
        try:
            async for notif in stub.SubscribeNotifications(request):
                # Format as SSE
                data = MessageToDict(notif, preserving_proto_field_name=True)
                yield f"data: {json.dumps(data)}\n\n"
        except grpc.RpcError as e:
            yield f"event: error\ndata: {e.details()}\n\n"
        finally:
            yield "event: close\ndata: stream ended\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )
```

**Browser usage:**

```javascript
const evtSource = new EventSource('/v1/users/123/notifications/stream');

evtSource.onmessage = (e) => {
  const notif = JSON.parse(e.data);
  console.log(notif.title);
};

evtSource.addEventListener('error', (e) => {
  console.error('Stream error');
  evtSource.close();
});
```

**HOW — Server streaming → NDJSON (newline-delimited JSON):**

```python
@app.get("/v1/users/export")
async def export_users_ndjson():
    """Stream users as NDJSON (one JSON per line)."""
    async def generator():
        async for user in stub.ListUsers(ListRequest(page_size=10000)):
            data = MessageToDict(user, preserving_proto_field_name=True)
            yield json.dumps(data) + "\n"

    return StreamingResponse(
        generator(),
        media_type="application/x-ndjson"
    )
```

---

### Q7: Authentication aur error handling REST + gRPC dono mein kaise consistent rakhein?

**Answer:**

**HOW — Shared auth via interceptor + middleware:**

```python
# auth.py — Shared logic
async def validate_jwt(token: str) -> dict:
    """Validate JWT, return user claims."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


# gRPC interceptor (Q2 from 03_grpc_security_mtls.md)
class JWTServerInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        # ... validate JWT, abort with UNAUTHENTICATED


# FastAPI dependency
from fastapi import HTTPException, Header

async def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    try:
        return await validate_jwt(authorization.replace("Bearer ", ""))
    except ValueError as e:
        raise HTTPException(401, str(e))


# Use in REST endpoint
@app.get("/v1/users/me")
async def get_me(user=Depends(get_current_user)):
    request = GetUserRequest(user_id=user["sub"])
    # Pass token to gRPC backend
    metadata = [("authorization", f"Bearer {user['raw_token']}")]
    response = await stub.GetUser(request, metadata=metadata)
    return MessageToDict(response)
```

**HOW — Consistent error responses:**

```python
# REST error format (matches gRPC error structure)
{
    "error": {
        "code": "NOT_FOUND",            # gRPC status code name
        "message": "User 123 not found",
        "status_code": 404,             # HTTP status
        "details": [],                  # Additional context (like google.rpc.Status)
        "request_id": "abc-123"         # Correlation
    }
}


# Exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    grpc_code_name = {
        400: "INVALID_ARGUMENT",
        401: "UNAUTHENTICATED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        409: "ALREADY_EXISTS",
    }.get(exc.status_code, "UNKNOWN")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": grpc_code_name,
                "message": exc.detail,
                "status_code": exc.status_code,
                "request_id": request.headers.get("x-request-id", ""),
            }
        }
    )
```

---

## Gateway Best Practices

```markdown
### Design
- [ ] One .proto = source of truth for both REST + gRPC
- [ ] REST URLs follow REST conventions (verbs, plural nouns)
- [ ] Use HTTP methods semantically (GET=read, POST=create)
- [ ] Version in URL (/v1/, /v2/)

### Performance
- [ ] Cache gRPC channel (don't create per request)
- [ ] Set timeouts on REST → gRPC calls
- [ ] Don't double-encode (binary protobuf only at gRPC layer)

### Security
- [ ] Same auth logic for both REST + gRPC
- [ ] Same RBAC checks
- [ ] CORS configured for browser REST calls
- [ ] Rate limiting at gateway

### Operations
- [ ] OpenAPI docs auto-generated
- [ ] Same metrics tagged with protocol (rest|grpc)
- [ ] Request IDs propagated through gateway
- [ ] Errors consistent format
```
