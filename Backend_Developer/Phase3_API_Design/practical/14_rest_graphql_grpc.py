"""
REST vs GraphQL vs gRPC — Side-by-Side Comparison
"""

# ==========================================================================
# 1. SAME ENDPOINT IN ALL 3 PROTOCOLS
# ==========================================================================

# Use case: Get article with author + comments


# ===== REST =====
"""
GET /api/v1/articles/123
Authorization: Bearer xyz

Response:
{
    "id": 123,
    "title": "Hello",
    "body": "...",
    "author_id": 5
}

# Client makes additional calls for author + comments
GET /api/v1/users/5
GET /api/v1/articles/123/comments

# 3 round-trips total
"""


from fastapi import FastAPI

rest_app = FastAPI()


@rest_app.get('/articles/{article_id}')
def get_article_rest(article_id: int):
    return {'id': article_id, 'title': 'Hello', 'body': '...', 'author_id': 5}


@rest_app.get('/users/{user_id}')
def get_user_rest(user_id: int):
    return {'id': user_id, 'name': 'Alice', 'email': 'a@example.com'}


@rest_app.get('/articles/{article_id}/comments')
def get_comments_rest(article_id: int):
    return [{'id': 1, 'body': 'Nice!'}, {'id': 2, 'body': 'Cool'}]


# ===== GraphQL =====
"""
POST /graphql
Content-Type: application/json

{
    "query": "query { article(id: 123) { title body author { name } comments(first: 5) { body } } }"
}


Response:
{
    "data": {
        "article": {
            "title": "Hello",
            "body": "...",
            "author": {"name": "Alice"},
            "comments": [{"body": "Nice!"}]
        }
    }
}

# 1 round-trip, only fields requested
"""


import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.dataloader import DataLoader


# Mock data
articles = {
    1: {'id': 1, 'title': 'Hello', 'body': '...', 'author_id': 5},
}

users = {
    5: {'id': 5, 'name': 'Alice', 'email': 'a@example.com'},
}


# DataLoader prevents N+1
async def load_users(ids: list[int]):
    return [users.get(i) for i in ids]


@strawberry.type
class User:
    id: int
    name: str
    email: str


@strawberry.type
class Article:
    id: int
    title: str
    body: str
    author_id: int

    @strawberry.field
    async def author(self, info) -> User | None:
        user = await info.context['user_loader'].load(self.author_id)
        return User(**user) if user else None


@strawberry.type
class Query:
    @strawberry.field
    async def article(self, id: int) -> Article | None:
        data = articles.get(id)
        return Article(**data) if data else None


schema = strawberry.Schema(query=Query)


async def get_context():
    return {'user_loader': DataLoader(load_users)}


graphql_app = FastAPI()
graphql_app.include_router(
    GraphQLRouter(schema, context_getter=get_context),
    prefix='/graphql',
)


# ===== gRPC =====
"""
# .proto definition
syntax = "proto3";

service ArticleService {
    rpc GetArticle(GetArticleRequest) returns (Article);
    rpc StreamArticles(ListRequest) returns (stream Article);
}

message GetArticleRequest {
    int32 id = 1;
}

message Article {
    int32 id = 1;
    string title = 2;
    string body = 3;
    User author = 4;
    repeated Comment comments = 5;
}

message User {
    int32 id = 1;
    string name = 2;
    string email = 3;
}

message Comment {
    int32 id = 1;
    string body = 2;
}


# Generate Python code
python -m grpc_tools.protoc -I./proto --python_out=./gen --grpc_python_out=./gen proto/article.proto
"""


"""
# Server
import grpc
from concurrent import futures
from gen import article_pb2, article_pb2_grpc


class ArticleService(article_pb2_grpc.ArticleServiceServicer):
    def GetArticle(self, request, context):
        article = articles.get(request.id)
        if not article:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return article_pb2.Article()

        return article_pb2.Article(
            id=article['id'],
            title=article['title'],
            body=article['body'],
            author=article_pb2.User(
                id=article['author_id'],
                name='Alice',
                email='a@example.com',
            ),
        )

    def StreamArticles(self, request, context):
        # Server streaming
        for article in articles.values():
            yield article_pb2.Article(**article)


server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
article_pb2_grpc.add_ArticleServiceServicer_to_server(ArticleService(), server)
server.add_insecure_port('[::]:50051')
server.start()


# Client
channel = grpc.insecure_channel('localhost:50051')
stub = article_pb2_grpc.ArticleServiceStub(channel)
response = stub.GetArticle(article_pb2.GetArticleRequest(id=123))
print(response.title)


# Streaming client
for article in stub.StreamArticles(article_pb2.ListRequest()):
    print(article.title)
"""


# ==========================================================================
# 2. PERFORMANCE COMPARISON
# ==========================================================================

PERFORMANCE_BENCHMARK = """
Same endpoint: Get article with author + comments

| Protocol | Round-trips | Bytes (compressed) | Latency P99 |
|----------|-------------|---------------------|-------------|
| REST     | 3           | ~2KB JSON           | ~150ms      |
| GraphQL  | 1           | ~500 bytes JSON     | ~80ms       |
| gRPC     | 1           | ~150 bytes Protobuf | ~10ms       |

Tested: 1Gbps LAN, simple object


REST wins:
- CDN caching
- Browser native fetch
- Tool ecosystem (curl, Postman)

GraphQL wins:
- Single request flexibility
- Strong types via codegen
- Subscriptions (live data)

gRPC wins:
- Raw speed (binary + HTTP/2)
- Strong types from .proto
- Bidirectional streaming
- Multi-language inter-op
"""


# ==========================================================================
# 3. WHEN TO USE WHICH (CHEAT SHEET)
# ==========================================================================

DECISION_GUIDE = """
USE REST WHEN:
  ✓ Public API (unknown consumers)
  ✓ Browser-facing apps
  ✓ Simple CRUD operations
  ✓ Caching matters (CDN, browser)
  ✓ Tooling matters (Postman, curl, every SDK)
  ✓ Team unfamiliar with GraphQL/gRPC
  ✓ Stateless, request-response

USE GRAPHQL WHEN:
  ✓ Mobile clients (bandwidth)
  ✓ BFF pattern (multiple clients need different shapes)
  ✓ Evolving schema (deprecate, don't version)
  ✓ Complex graph queries (nested relationships)
  ✓ Real-time subscriptions
  ✓ Internal product where clients are known
  ✓ Frontend team owns API shape

USE GRPC WHEN:
  ✓ Service-to-service (microservices)
  ✓ Polyglot environment (Python ↔ Go ↔ Java)
  ✓ High throughput required (10K+ RPS)
  ✓ Strong typing critical
  ✓ Streaming (telemetry, real-time)
  ✓ Low latency requirements
  ✓ Mobile (Android/iOS native, not browser)

USE HYBRID:
  ✓ Public REST + Internal gRPC
  ✓ GraphQL BFF over REST/gRPC backends
  ✓ REST + WebSocket for real-time
"""


# ==========================================================================
# 4. SAME PYTHON CODE — REUSABLE BUSINESS LOGIC
# ==========================================================================

# Extract business logic into services — share across protocols

class ArticleService:
    """Same logic used by REST, GraphQL, gRPC."""

    def __init__(self, db):
        self.db = db

    async def get_article(self, article_id: int) -> dict | None:
        return self.db.get(article_id)

    async def list_articles(self, offset: int = 0, limit: int = 20) -> list[dict]:
        return list(self.db.values())[offset:offset + limit]

    async def create_article(self, title: str, body: str, author_id: int) -> dict:
        new_id = max(self.db.keys(), default=0) + 1
        article = {'id': new_id, 'title': title, 'body': body, 'author_id': author_id}
        self.db[new_id] = article
        return article


service = ArticleService(articles)


# REST handler
@rest_app.get('/articles/{id}')
async def rest_get_article(id: int):
    article = await service.get_article(id)
    return article or {'error': 'not found'}


# GraphQL resolver
@strawberry.type
class QueryReusable:
    @strawberry.field
    async def article(self, id: int) -> Article | None:
        data = await service.get_article(id)
        return Article(**data) if data else None


# gRPC servicer (pseudo-code)
"""
class ArticleServicer(article_pb2_grpc.ArticleServiceServicer):
    async def GetArticle(self, request, context):
        data = await service.get_article(request.id)
        if not data:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return article_pb2.Article()
        return article_pb2.Article(**data)
"""


# ==========================================================================
# 5. HYBRID PATTERN — REST GATEWAY + gRPC INTERNAL
# ==========================================================================

"""
                    [Browser]
                        |
                        v
                [REST API Gateway]
                        |
            +-----------+-----------+
            |                       |
        gRPC call               gRPC call
            |                       |
    [User Service]          [Article Service]


# Gateway converts REST → gRPC
@app.get('/api/articles/{id}')
async def article_endpoint(id: int):
    # gRPC call to internal service
    async with grpc.aio.insecure_channel('article-svc:50051') as channel:
        stub = article_pb2_grpc.ArticleServiceStub(channel)
        response = await stub.GetArticle(article_pb2.GetArticleRequest(id=id))
        return {
            'id': response.id,
            'title': response.title,
            'body': response.body,
        }
"""


# ==========================================================================
# 6. GRAPHQL BFF OVER REST
# ==========================================================================

"""
# GraphQL layer wraps existing REST microservices

import httpx


async def fetch_article_from_rest(article_id: int):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f'http://article-svc/api/articles/{article_id}')
        return resp.json()


async def fetch_user_from_rest(user_id: int):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f'http://user-svc/api/users/{user_id}')
        return resp.json()


@strawberry.type
class Article:
    id: int
    title: str

    @strawberry.field
    async def author(self) -> User:
        user_data = await fetch_user_from_rest(self.author_id)
        return User(**user_data)


@strawberry.type
class Query:
    @strawberry.field
    async def article(self, id: int) -> Article:
        data = await fetch_article_from_rest(id)
        return Article(**data)


# Frontend sends GraphQL query, gateway calls multiple REST services
# Reduces client round-trips while keeping REST microservices
"""


# ==========================================================================
# 7. MIGRATION PATTERN — REST → GRAPHQL
# ==========================================================================

MIGRATION_GUIDE = """
Phase 1: Add GraphQL alongside REST
  - GraphQL resolvers call existing REST endpoints
  - Both APIs active

Phase 2: Migrate frontend gradually
  - New features built with GraphQL
  - Legacy uses REST

Phase 3: Move business logic to GraphQL resolvers
  - Reduces REST → GraphQL → DB hops
  - Better N+1 control

Phase 4: Sunset REST
  - Document deprecation
  - Set sunset date
  - Remove after grace period


No-go signs (stay with REST):
  - Heavy file uploads
  - Cache-critical reads (CDN)
  - Public API with diverse clients
  - Small team without GraphQL expertise
"""


# ==========================================================================
# 8. CLIENT EXAMPLES (all 3)
# ==========================================================================

CLIENT_EXAMPLES = """
# REST (httpx)
import httpx

async with httpx.AsyncClient() as client:
    resp = await client.get('https://api.example.com/articles/123')
    article = resp.json()


# GraphQL (gql)
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

transport = AIOHTTPTransport(url='https://api.example.com/graphql')
client = Client(transport=transport, fetch_schema_from_transport=True)

query = gql(\"\"\"
    query GetArticle($id: Int!) {
        article(id: $id) {
            title body author { name }
        }
    }
\"\"\")
result = await client.execute_async(query, variable_values={'id': 123})


# gRPC
import grpc
from gen import article_pb2, article_pb2_grpc

async with grpc.aio.insecure_channel('localhost:50051') as channel:
    stub = article_pb2_grpc.ArticleServiceStub(channel)
    response = await stub.GetArticle(article_pb2.GetArticleRequest(id=123))
    print(response.title)
"""


# ==========================================================================
# 9. INTEROPERABILITY TIPS
# ==========================================================================

INTEROP_TIPS = """
1. Strong contracts everywhere:
   - REST: OpenAPI spec (generate from FastAPI)
   - GraphQL: SDL schema (built-in)
   - gRPC: .proto (mandatory)

2. Generate clients automatically:
   - REST: openapi-generator (40+ languages)
   - GraphQL: GraphQL Code Generator
   - gRPC: protoc + plugins

3. Share types between protocols:
   - Define core types once (Pydantic, dataclasses)
   - Map to protocol-specific (Strawberry, protobuf)

4. Standardize errors:
   - REST: RFC 7807 Problem Details
   - GraphQL: errors[] array with extensions
   - gRPC: status codes + error details
"""


# ==========================================================================
# 10. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
Whichever protocol(s) you choose:

[ ] Schema/contract committed to repo
[ ] Generated clients in repo (or CI-built)
[ ] OpenAPI / SDL / .proto reviewable in PRs
[ ] Versioning strategy documented
[ ] Deprecation policy + sunset dates
[ ] Auth/authz consistent across protocols
[ ] Rate limiting at appropriate layer
[ ] Observability (latency, errors, throughput)
[ ] Documentation for external consumers
[ ] Test coverage including contract tests
[ ] Migration path if multiple protocols
[ ] Performance budgets (P99 latency)
"""
