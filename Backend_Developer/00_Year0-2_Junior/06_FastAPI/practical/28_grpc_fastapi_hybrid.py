"""
gRPC + FastAPI Hybrid — Production Patterns

Note: requires generated proto code. Generation command at bottom.
"""

import asyncio
import time
from concurrent import futures
from typing import AsyncIterator

import grpc
from grpc.aio import ServerInterceptor
from fastapi import FastAPI


# ==========================================================================
# .proto FILE (save as proto/article.proto)
# ==========================================================================

PROTO_FILE = """
syntax = "proto3";

package article;

service ArticleService {
  rpc GetArticle(GetArticleRequest) returns (ArticleResponse);
  rpc ListArticles(ListArticlesRequest) returns (stream ArticleResponse);
  rpc CreateArticle(CreateArticleRequest) returns (ArticleResponse);
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
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
"""

# Generate with:
# python -m grpc_tools.protoc -I./proto --python_out=./generated \
#   --grpc_python_out=./generated --pyi_out=./generated proto/article.proto


# ==========================================================================
# 1. SHARED BUSINESS LOGIC (called from both REST + gRPC)
# ==========================================================================

# Mock DB
_articles = {
    1: {'id': 1, 'title': 'gRPC intro', 'body': '...', 'author_id': 1, 'created_at': int(time.time())},
}


async def service_get_article(article_id: int) -> dict | None:
    return _articles.get(article_id)


async def service_create_article(title: str, body: str, author_id: int) -> dict:
    new_id = max(_articles.keys(), default=0) + 1
    article = {
        'id': new_id,
        'title': title,
        'body': body,
        'author_id': author_id,
        'created_at': int(time.time()),
    }
    _articles[new_id] = article
    return article


async def service_list_articles(limit: int, offset: int) -> list[dict]:
    return list(_articles.values())[offset:offset + limit]


# ==========================================================================
# 2. gRPC SERVICER
# ==========================================================================

# Pseudo-code — assumes generated stubs available
"""
from generated import article_pb2, article_pb2_grpc


class ArticleService(article_pb2_grpc.ArticleServiceServicer):
    async def GetArticle(self, request, context):
        article = await service_get_article(request.id)
        if not article:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Article {request.id} not found")
            return article_pb2.ArticleResponse()
        return article_pb2.ArticleResponse(**article)

    async def ListArticles(self, request, context):
        articles = await service_list_articles(request.limit, request.offset)
        for article in articles:
            yield article_pb2.ArticleResponse(**article)

    async def CreateArticle(self, request, context):
        if not request.title.strip():
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Title required")
            return article_pb2.ArticleResponse()
        article = await service_create_article(
            request.title,
            request.body,
            request.author_id,
        )
        return article_pb2.ArticleResponse(**article)

    async def Chat(self, request_iterator, context):
        # Bidirectional streaming
        async for msg in request_iterator:
            # Echo back
            yield article_pb2.ChatMessage(
                user='server',
                text=f'You said: {msg.text}',
                timestamp=int(time.time()),
            )
"""


# ==========================================================================
# 3. AUTH INTERCEPTOR (validate JWT in metadata)
# ==========================================================================

import jwt as pyjwt


JWT_SECRET = "your-secret"


class AuthInterceptor(ServerInterceptor):
    """Validates JWT from metadata."""

    PUBLIC_METHODS = {'/article.ArticleService/GetArticle'}  # no auth required

    async def intercept_service(self, continuation, handler_call_details):
        if handler_call_details.method in self.PUBLIC_METHODS:
            return await continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata)
        token = metadata.get('authorization', '').removeprefix('Bearer ')

        if not token:
            # Reject by setting up an aborting handler
            return self._make_unauth_handler()

        try:
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            # Could pass to handler via context if needed
        except pyjwt.InvalidTokenError:
            return self._make_unauth_handler()

        return await continuation(handler_call_details)

    def _make_unauth_handler(self):
        async def abort(req, context):
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid or missing token")
        # ... build RpcMethodHandler
        # Simplified — see grpcio examples for full pattern


# ==========================================================================
# 4. SERVER STARTUP — combined gRPC + FastAPI
# ==========================================================================

app = FastAPI()


@app.get("/articles/{article_id}")
async def rest_get_article(article_id: int):
    """REST endpoint using same service layer."""
    article = await service_get_article(article_id)
    if not article:
        from fastapi import HTTPException
        raise HTTPException(404, "Article not found")
    return article


@app.post("/articles")
async def rest_create_article(title: str, body: str, author_id: int):
    return await service_create_article(title, body, author_id)


# ==========================================================================
# 5. UNIFIED ENTRY POINT
# ==========================================================================

"""
async def serve_grpc():
    server = grpc.aio.server(
        interceptors=[AuthInterceptor()],
        options=[
            ('grpc.max_send_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ],
    )
    article_pb2_grpc.add_ArticleServiceServicer_to_server(
        ArticleService(),
        server,
    )

    # TLS in prod
    # creds = grpc.ssl_server_credentials([
    #     (open('server.key', 'rb').read(), open('server.crt', 'rb').read()),
    # ])
    # server.add_secure_port('[::]:50051', creds)

    server.add_insecure_port('[::]:50051')  # dev only

    await server.start()
    print("gRPC server on :50051")
    return server


async def serve_http():
    import uvicorn
    config = uvicorn.Config(
        app=app,
        host='0.0.0.0',
        port=8000,
        log_level='info',
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    grpc_server = await serve_grpc()
    try:
        await serve_http()
    finally:
        await grpc_server.stop(grace=30)


if __name__ == '__main__':
    asyncio.run(main())
"""


# ==========================================================================
# 6. CLIENT EXAMPLES
# ==========================================================================

"""
import grpc
from generated import article_pb2, article_pb2_grpc


async def example_unary_call():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = article_pb2_grpc.ArticleServiceStub(channel)
        response = await stub.GetArticle(
            article_pb2.GetArticleRequest(id=1),
            metadata=[('authorization', 'Bearer token')],
        )
        print(response.title)


async def example_server_streaming():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = article_pb2_grpc.ArticleServiceStub(channel)
        async for article in stub.ListArticles(
            article_pb2.ListArticlesRequest(limit=10, offset=0)
        ):
            print(article.title)


async def example_bidirectional():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = article_pb2_grpc.ArticleServiceStub(channel)

        async def send_messages():
            for i in range(5):
                yield article_pb2.ChatMessage(
                    user='alice',
                    text=f'msg {i}',
                    timestamp=int(time.time()),
                )

        async for reply in stub.Chat(send_messages()):
            print(reply.text)
"""


# ==========================================================================
# 7. ERROR HANDLING
# ==========================================================================

"""
# Server-side
async def MyMethod(self, request, context):
    try:
        # ... work
    except ValueError as e:
        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
        context.set_details(str(e))
        return article_pb2.ArticleResponse()
    except PermissionError:
        context.set_code(grpc.StatusCode.PERMISSION_DENIED)
        context.set_details("Not allowed")
        return article_pb2.ArticleResponse()
    except Exception as e:
        context.set_code(grpc.StatusCode.INTERNAL)
        context.set_details("Internal error")
        # Log full exception server-side
        return article_pb2.ArticleResponse()


# Client-side
try:
    response = await stub.GetArticle(...)
except grpc.RpcError as e:
    if e.code() == grpc.StatusCode.NOT_FOUND:
        print("Not found")
    elif e.code() == grpc.StatusCode.UNAVAILABLE:
        print("Service down, retry")
    else:
        print(f"Error: {e.details()}")
"""


# ==========================================================================
# 8. PROTO GENERATION COMMAND
# ==========================================================================

PROTO_GEN_CMD = """
# Install
pip install grpcio grpcio-tools

# Generate from proto
python -m grpc_tools.protoc \\
    -I./proto \\
    --python_out=./generated \\
    --grpc_python_out=./generated \\
    --pyi_out=./generated \\
    proto/article.proto

# Or with buf (recommended):
# buf generate
"""


# ==========================================================================
# 9. OBSERVABILITY (OpenTelemetry)
# ==========================================================================

"""
# pip install opentelemetry-instrumentation-grpc

from opentelemetry.instrumentation.grpc import (
    GrpcInstrumentorServer,
    GrpcInstrumentorClient,
)

GrpcInstrumentorServer().instrument()
GrpcInstrumentorClient().instrument()

# Now all gRPC calls produce spans (server + client side)
"""


# ==========================================================================
# 10. PROD CHECKLIST
# ==========================================================================
"""
[ ] mTLS — cert per service for authentication
[ ] Auth interceptor — JWT/token validation
[ ] Rate limiting per method
[ ] Request size limits (max_receive_message_length)
[ ] Timeout per call (deadline)
[ ] Retries with backoff (built-in retry policy)
[ ] OpenTelemetry tracing enabled
[ ] Health check endpoint (grpc.health.v1)
[ ] Reflection for debug (grpc_reflection)
[ ] Graceful shutdown (server.stop(grace=30))
"""
