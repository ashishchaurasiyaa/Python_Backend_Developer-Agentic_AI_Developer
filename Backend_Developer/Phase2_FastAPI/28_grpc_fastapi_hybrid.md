# gRPC + FastAPI Hybrid — Inter-Service RPC

## Why It Matters

REST = external public APIs. gRPC = internal service-to-service:
- **10x faster** than JSON over HTTP (Protobuf binary)
- **Bidirectional streaming** (chat, telemetry)
- **Strong contracts** (.proto generates types)
- **HTTP/2 multiplexing** (multiple calls on one connection)

Hybrid pattern: same service exposes REST (external) + gRPC (internal). Senior interview: "Microservices internal comms — REST vs gRPC?"

---

## Core Concepts

### Protocol Buffer Definition (.proto)

```protobuf
// proto/article.proto
syntax = "proto3";

package article;

service ArticleService {
  rpc GetArticle (GetArticleRequest) returns (ArticleResponse);
  rpc ListArticles (ListArticlesRequest) returns (stream ArticleResponse);
  rpc CreateArticle (CreateArticleRequest) returns (ArticleResponse);
  rpc Chat (stream ChatMessage) returns (stream ChatMessage);
}

message GetArticleRequest {
  int32 id = 1;
}

message ListArticlesRequest {
  int32 limit = 1;
  int32 offset = 2;
}

message CreateArticleRequest {
  string title = 1;
  string body = 2;
  int32 author_id = 3;
}

message ArticleResponse {
  int32 id = 1;
  string title = 2;
  string body = 3;
  int32 author_id = 4;
  int64 created_at = 5;
}

message ChatMessage {
  string user = 1;
  string text = 2;
  int64 timestamp = 3;
}
```

### Generate Python Code

```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./generated \
    --grpc_python_out=./generated \
    --pyi_out=./generated \
    proto/article.proto
```

Generates `article_pb2.py`, `article_pb2_grpc.py`, `article_pb2.pyi`.

### gRPC Server (alongside FastAPI)

```python
import asyncio
import grpc
from generated import article_pb2, article_pb2_grpc
from concurrent import futures


# Shared business logic
async def fetch_article_from_db(article_id: int):
    return {'id': article_id, 'title': '...', 'body': '...', 'author_id': 1}


class ArticleService(article_pb2_grpc.ArticleServiceServicer):
    async def GetArticle(self, request, context):
        article = await fetch_article_from_db(request.id)
        return article_pb2.ArticleResponse(**article)

    async def ListArticles(self, request, context):
        for i in range(request.offset, request.offset + request.limit):
            article = await fetch_article_from_db(i)
            yield article_pb2.ArticleResponse(**article)

    async def CreateArticle(self, request, context):
        # Save
        return article_pb2.ArticleResponse(
            id=99,
            title=request.title,
            body=request.body,
            author_id=request.author_id,
        )

    async def Chat(self, request_iterator, context):
        async for msg in request_iterator:
            # Echo back
            yield article_pb2.ChatMessage(
                user='server',
                text=f'Echo: {msg.text}',
                timestamp=int(time.time()),
            )


async def serve_grpc():
    server = grpc.aio.server()
    article_pb2_grpc.add_ArticleServiceServicer_to_server(
        ArticleService(),
        server,
    )
    server.add_insecure_port('[::]:50051')
    await server.start()
    await server.wait_for_termination()


# Run both FastAPI + gRPC
if __name__ == '__main__':
    # Run gRPC in same event loop
    asyncio.run(serve_grpc())
```

### Run Both REST + gRPC

```python
# main.py
import asyncio
import uvicorn
import grpc


async def serve_grpc():
    server = grpc.aio.server()
    article_pb2_grpc.add_ArticleServiceServicer_to_server(ArticleService(), server)
    server.add_insecure_port('[::]:50051')
    await server.start()
    return server


async def serve_http():
    config = uvicorn.Config('main:app', host='0.0.0.0', port=8000, log_level='info')
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    grpc_server = await serve_grpc()
    try:
        await serve_http()
    finally:
        await grpc_server.stop(grace=30)


asyncio.run(main())
```

### gRPC Client

```python
import grpc
from generated import article_pb2, article_pb2_grpc


async def call_article_service():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = article_pb2_grpc.ArticleServiceStub(channel)

        # Unary
        response = await stub.GetArticle(article_pb2.GetArticleRequest(id=1))
        print(response.title)

        # Server streaming
        async for article in stub.ListArticles(
            article_pb2.ListArticlesRequest(limit=10, offset=0),
        ):
            print(article.title)

        # Bidirectional
        async def msg_generator():
            for i in range(5):
                yield article_pb2.ChatMessage(user='alice', text=f'msg {i}')

        async for reply in stub.Chat(msg_generator()):
            print(reply.text)
```

### Shared Service Layer

Avoid duplicating logic — REST + gRPC both call same service:

```python
# services/articles.py
async def get_article(article_id: int) -> dict:
    return await db.fetch_article(article_id)


async def create_article(title: str, body: str, author_id: int) -> dict:
    return await db.create_article(title, body, author_id)


# REST handler
@app.get("/articles/{article_id}")
async def rest_get_article(article_id: int):
    return await get_article(article_id)


# gRPC handler
class ArticleService(article_pb2_grpc.ArticleServiceServicer):
    async def GetArticle(self, request, context):
        article = await get_article(request.id)
        return article_pb2.ArticleResponse(**article)
```

### TLS / mTLS

```python
# Server
server_credentials = grpc.ssl_server_credentials([
    (open('server.key', 'rb').read(), open('server.crt', 'rb').read()),
])
server.add_secure_port('[::]:50051', server_credentials)


# Client
channel_credentials = grpc.ssl_channel_credentials(
    root_certificates=open('ca.crt', 'rb').read(),
)
async with grpc.aio.secure_channel('host:50051', channel_credentials) as channel:
    ...
```

### gRPC-Gateway / grpc-web

Browser can't speak gRPC directly. Solutions:
- **gRPC-Web** (proxy translates browser HTTP to gRPC)
- **grpc-gateway** (REST↔gRPC translation; Go-based)
- **Connect-Web** (modern alternative)

---

## How It Works Internally

### Protobuf Binary Format

```
title field tag=2 string "Hello":
[tag: 0x12, len: 0x05, "Hello"]
```

10x smaller than JSON, faster to parse.

### HTTP/2 Multiplexing

Multiple gRPC calls share single TCP connection. Each call = stream. No head-of-line blocking like HTTP/1.1.

### Streaming Modes

| Mode | Client → Server | Server → Client |
|---|---|---|
| Unary | 1 msg | 1 msg |
| Server streaming | 1 msg | stream |
| Client streaming | stream | 1 msg |
| Bidirectional | stream | stream |

---

## Common Pitfalls

### 1. Mixing Sync + Async gRPC

`grpc.server` vs `grpc.aio.server` — async version recommended for FastAPI co-location.

### 2. Field Number Reuse

```protobuf
message Foo {
  reserved 3;             // never reuse old field number
  string old_field = 3;   // BAD — breaks clients with old binary
}
```

### 3. Default Values Ambiguity

`int32 count = 0` is indistinguishable from "not set". Use `optional` keyword (proto3.15+) or wrapper types.

### 4. Authentication

gRPC has metadata (similar to HTTP headers). Pass tokens via metadata, validate in interceptor.

```python
class AuthInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        token = metadata.get('authorization', '')
        # Validate
        return await continuation(handler_call_details)
```

### 5. Browser Can't Call gRPC

Need gRPC-Web proxy (envoy, nginx grpc_web module).

### 6. Schema Versioning

Use proto3 conventions: add fields with new tags, never reuse, mark deprecated.

### 7. Error Handling

gRPC uses status codes (UNAVAILABLE, NOT_FOUND, PERMISSION_DENIED) — different from HTTP.

```python
context.set_code(grpc.StatusCode.NOT_FOUND)
context.set_details("Article not found")
```

---

## Interview Q&A

**Q1:** REST vs gRPC — kab kya?
**A:** REST: external public APIs, browser clients, CDN cacheable GETs, simple CRUD. gRPC: internal microservices, high throughput, streaming, strong contracts. Hybrid pattern: REST gateway → gRPC internal services. Browser can't speak gRPC directly.

**Q2:** Protobuf vs JSON?
**A:** Protobuf: binary, compact (1/10 size), fast parse, schema-required, language-neutral. JSON: text, larger, no schema, ubiquitous. For service-to-service: Protobuf. For browser/public API: JSON.

**Q3:** gRPC streaming modes?
**A:** (1) Unary (1↔1, like REST). (2) Server streaming (client request → server stream — like SSE). (3) Client streaming (client stream → server response — file upload). (4) Bidirectional (both stream — chat, telemetry).

**Q4:** gRPC authentication kaise?
**A:** mTLS for service-to-service (cert-based, strong). For tokens: pass via metadata header (`authorization`), validate in server interceptor. JWT works fine. For user context, pass user_id in metadata after validating token at edge.

**Q5:** REST + gRPC same service kaise design karoge?
**A:** Extract business logic into service layer. REST handlers + gRPC servicers both call same functions. Run both on different ports (8000 HTTP, 50051 gRPC). Share Pydantic models for HTTP, generated proto for gRPC. Document mapping.

**Q6:** gRPC error handling?
**A:** Status codes (16 standard) — OK, NOT_FOUND, INVALID_ARGUMENT, etc. Plus details (string + optional error proto). Servicer: `context.set_code(grpc.StatusCode.X)` + `set_details()`. Client: catches `grpc.RpcError`, inspects `.code()` and `.details()`.

**Q7:** Browser se gRPC kaise call karein?
**A:** Direct nahi — browser doesn't support gRPC over HTTP/2 in Fetch. Options: (1) gRPC-Web (Envoy proxy translates). (2) Connect-Web (modern, simpler protocol). (3) grpc-gateway (REST→gRPC translation server). For SPAs, often REST API + gRPC backend is simpler.

**Q8:** gRPC observability?
**A:** OpenTelemetry has gRPC instrumentation — auto-traces calls + metadata. Service mesh (Istio, Linkerd) traces gRPC calls between services. Metrics via Prometheus (request count, latency, errors per method).

---

## Real-World Use Cases

### 1. Microservices Backbone

User Service ↔ Order Service ↔ Payment Service all gRPC. API Gateway exposes REST to clients.

### 2. AI Model Serving

Triton Inference Server uses gRPC for high-throughput inference. Python client streams predictions.

### 3. Telemetry / Logging

OpenTelemetry exporters use gRPC to ship traces/metrics to collector.

---

## References

- [gRPC Python](https://grpc.io/docs/languages/python/)
- [Protobuf docs](https://protobuf.dev/)
- [Connect-Web](https://connectrpc.com/) — modern alternative
- Buf — protobuf tooling
