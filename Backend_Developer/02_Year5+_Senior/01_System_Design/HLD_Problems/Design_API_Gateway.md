# Design API Gateway

---

## 1. Requirements

### Functional
- Route incoming HTTP requests to backend services.
- Authentication & authorization.
- Rate limiting per client / route.
- Request/response transformation.
- Caching of responses.
- Logging / metrics / tracing.
- WebSocket and gRPC support.
- Multi-protocol: HTTP/1.1, HTTP/2, HTTP/3.
- Plugin/middleware architecture.
- Dynamic configuration (route updates without restart).

### Non-Functional
- 100K-1M RPS sustained.
- p99 added latency < 10ms.
- 99.99% availability.
- Horizontally scalable.
- Multi-region.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| RPS sustained | 500K |
| Peak RPS | 1M |
| Active backend services | 500 |
| Routes | 5000 |
| Active API keys | 10M |
| Cached responses | 1M (in Redis) |
| Avg added latency | 5ms |

---

## 3. High-Level Architecture

```
        Clients (mobile, web, partners)
              │
              ▼
        ┌──────────────┐
        │ Load Balancer│ (TCP / L4)
        └──────┬───────┘
               │
       ┌───────┴────────┐
       │                │
   ┌───▼────┐     ┌─────▼──┐
   │Gateway │ ... │Gateway │ (stateless instances)
   │ Node   │     │ Node   │
   └───┬────┘     └────────┘
       │
       │ in-memory + Redis + Kafka
       │
   ┌───▼─────────────────────────────────┐
   │ Auth → Rate-limit → Transform →     │
   │ Cache → Route → Forward → Log       │
   └───┬─────────────────────────────────┘
       │
   ┌───▼────────────────────────┐
   │ Backend Services           │
   │ (gRPC / HTTP / WS)         │
   └────────────────────────────┘
```

---

## 4. Request Flow

```
1. Client sends HTTPS request to gateway VIP.
2. LB picks a gateway node (consistent hash on connection / round robin).
3. Gateway middleware chain:
   - TLS terminate.
   - Parse request.
   - Authenticate (API key, JWT, OAuth2).
   - Rate limit check.
   - Transform request (rewrite headers, add tracing).
   - Check cache for cached response.
   - Resolve route → upstream service.
   - Forward to backend.
   - Receive response.
   - Transform response (strip internal headers, add CORS).
   - Cache response (if cacheable).
   - Log request + metrics.
   - Return to client.
```

p99 budget < 10ms across all middleware.

---

## 5. Routing

### Static routes (from config)
```yaml
routes:
  - path_prefix: "/api/v1/orders"
    methods: ["GET", "POST"]
    upstream: "http://orders-svc:8080"
    auth: required
    rate_limit: 100/min

  - path_regex: "/api/v1/users/(\\d+)/profile"
    upstream: "http://users-svc:8080"
    auth: required

  - host: "api.example.com"
    path_prefix: "/"
    upstream: "http://backend:8080"
```

### Dynamic routing (via service discovery)
Gateway pulls service registry (Consul, K8s services).

```python
async def resolve_upstream(route, request):
    upstream_service = route.upstream_service
    instances = await service_registry.list(upstream_service)
    return pick_instance(instances, strategy="round_robin")
```

Service goes down → registry removes instance → gateway stops routing to it.

---

## 6. Authentication

### Multiple methods supported

```yaml
auth_providers:
  - name: api_key
    type: header
    header: X-API-Key

  - name: jwt
    type: bearer
    issuer: https://auth.example.com
    audience: api.example.com
    jwks_url: https://auth.example.com/.well-known/jwks.json

  - name: oauth2
    type: introspection
    introspection_url: https://auth.example.com/oauth/introspect
```

### Verification

```python
async def authenticate(request, route):
    auth_method = route.auth_method
    if auth_method == "api_key":
        key = request.headers.get("X-API-Key")
        user = await lookup_api_key(key)
    elif auth_method == "jwt":
        token = parse_bearer(request)
        user = await verify_jwt(token)
    elif auth_method == "oauth2":
        token = parse_bearer(request)
        user = await introspect_token(token)

    if not user:
        raise UnauthorizedError()

    request.user = user
    return user
```

### JWKS caching
JWT verification needs public key. Cache JWKS for 1 hour:
```python
async def get_jwks():
    cached = await redis.get("jwks")
    if cached: return json.loads(cached)
    jwks = await httpx.get(JWKS_URL)
    await redis.setex("jwks", 3600, jwks.text)
    return jwks.json()
```

---

## 7. Rate Limiting

### Algorithms
- Token bucket (default).
- Sliding window (more accurate).
- Fixed window (cheaper but bursty).

### Distributed: Redis
```python
LUA_SLIDING = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, window)
    return 1
end
return 0
"""

async def rate_limit(user_id, route_id, limit, window_sec):
    key = f"rl:{user_id}:{route_id}"
    result = await redis.eval(
        LUA_SLIDING, 1, key,
        int(time.time() * 1000),
        window_sec * 1000,
        limit
    )
    return bool(result)
```

### Levels
- Per IP (block bots).
- Per API key.
- Per route.
- Per organization (B2B).

Combine: most restrictive wins.

### Response headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1700000000
Retry-After: 60   (on 429)
```

---

## 8. Caching

Some endpoints cache-friendly (GET, idempotent):
- Public data.
- Stable for some duration.

### Cache key
```python
def cache_key(request):
    return hashlib.sha256(
        f"{request.method}:{request.path}:{sorted(request.query)}:{request.user.id}".encode()
    ).hexdigest()
```

User ID in key if response is user-specific. Otherwise omit for sharing across users.

### Logic
```python
async def with_cache(request, handler):
    if request.method != "GET" or not route.cacheable:
        return await handler(request)

    key = cache_key(request)
    cached = await redis.get(f"cache:{key}")
    if cached:
        return Response.from_cached(cached)

    response = await handler(request)
    if response.status_code == 200:
        await redis.setex(f"cache:{key}", route.cache_ttl, response.serialize())
    return response
```

### Invalidation
- TTL-based (simple).
- Event-based (purge on data change via Kafka).
- Versioned keys.

---

## 9. Transformations

### Request transformations
- Strip internal headers.
- Add tracing headers (X-Request-ID, B3).
- Rewrite paths (`/api/v1/users` → `/users`).
- Add user context (X-User-ID).

### Response transformations
- Filter fields (e.g., strip internal fields).
- Add CORS headers.
- Add cache-control.
- Convert formats (JSON → XML if Accept header demands).

```yaml
route:
  request_transform:
    - strip_header: Authorization (replaced with X-User-ID)
    - add_header: X-User-ID: "{user.id}"
  response_transform:
    - filter_fields: [internal_*, debug_*]
    - add_header: X-Server: "api-gw"
```

---

## 10. Load Balancing to Backends

Strategies:
- **Round-robin**: simple, even.
- **Least connections**: prefers idle.
- **Weighted**: heterogeneous backends.
- **Hash**: consistent hash on header/cookie for sticky.
- **Latency-aware**: prefer faster instances.

```python
class LoadBalancer:
    def __init__(self, instances, strategy="round_robin"):
        self.instances = instances
        self.strategy = strategy
        self.counter = 0

    def pick(self):
        if self.strategy == "round_robin":
            self.counter = (self.counter + 1) % len(self.instances)
            return self.instances[self.counter]
        elif self.strategy == "least_conn":
            return min(self.instances, key=lambda i: i.active_conns)
        elif self.strategy == "latency":
            return min(self.instances, key=lambda i: i.p99_latency_ms)
```

### Health checks
Active: periodic probe each instance.
Passive: count failed requests; eject after threshold.

```python
class Instance:
    def __init__(self, url):
        self.url = url
        self.healthy = True
        self.failures = 0

    def on_failure(self):
        self.failures += 1
        if self.failures > 5:
            self.healthy = False
            asyncio.create_task(self.recheck_after(30))

    async def recheck_after(self, seconds):
        await asyncio.sleep(seconds)
        try:
            await httpx.get(f"{self.url}/health", timeout=2)
            self.healthy = True
            self.failures = 0
        except:
            await self.recheck_after(seconds * 2)
```

---

## 11. Observability

### Per-request log
```json
{
  "timestamp": "...",
  "request_id": "abc",
  "method": "POST",
  "path": "/api/v1/orders",
  "user_id": "u_123",
  "status": 200,
  "duration_ms": 47,
  "upstream": "orders-svc-prod",
  "upstream_duration_ms": 32
}
```

### Metrics (Prometheus)
- Request count per route.
- Latency histogram per route.
- Error rate per route.
- Active connections.
- Rate limit hits.
- Cache hits/misses.

### Tracing
Propagate trace context (W3C traceparent / B3) to backends. Combine logs+metrics+traces by request_id.

---

## 12. Plugins / Middleware

```python
class Plugin:
    async def pre_request(self, request): ...
    async def post_response(self, request, response): ...

# Built-in plugins:
- TLSPlugin
- AuthPlugin
- RateLimitPlugin
- CachePlugin
- TransformPlugin
- ProxyPlugin (forwards to upstream)
- LogPlugin
- MetricsPlugin
```

Chain executes in order. Each can short-circuit (return early without proxying).

---

## 13. Configuration Management

### Static config files
- YAML in Git.
- ArgoCD applies to gateway pods.
- Restart required to apply.

### Dynamic config
- Gateway watches Kafka / Redis pub/sub for changes.
- Hot-reloads in seconds without restart.

```python
async def watch_config():
    pubsub = redis.pubsub()
    await pubsub.subscribe("gateway:config:updates")
    async for msg in pubsub.listen():
        if msg["type"] == "message":
            await reload_config()
```

---

## 14. WebSocket Support

Gateway proxies WS too:
```yaml
- path: "/ws/{id}"
  upstream: "ws://chat-svc:8080"
  protocol: websocket
```

After HTTP upgrade, gateway acts as a TCP proxy for the WS connection.

Sticky session: same client returns to same backend (consistent hash on connection).

---

## 15. gRPC Support

Gateway can proxy gRPC (binary HTTP/2):
```yaml
- path: "/grpc/orders.OrderService"
  upstream: "grpc://orders-svc:50051"
  protocol: grpc
```

Some gateways: HTTP/JSON → gRPC translation (grpc-gateway pattern).

---

## 16. Multi-Region

```
                       ┌────────────────┐
                       │   Anycast DNS  │
                       └────────┬───────┘
              ┌────────────────┼─────────────────┐
              ▼                ▼                 ▼
        ┌─────────┐      ┌─────────┐       ┌─────────┐
        │ Gateway │      │ Gateway │       │ Gateway │
        │  US     │      │  EU     │       │  Asia   │
        └────┬────┘      └────┬────┘       └────┬────┘
             ▼                ▼                 ▼
        Backend US        Backend EU        Backend Asia
```

Each region has full stack. DNS routes by latency.

Cross-region writes coordinated via global services (Aurora Global, Spanner).

---

## 17. Real-World Implementations

### Kong
Open-source, plugin-rich. Lua-based (built on OpenResty/NGINX).

### Envoy
Modern, used by Istio service mesh.

### Tyk
Open-source, Go.

### AWS API Gateway
Managed. Tight AWS integration.

### Apigee
Google's enterprise gateway.

### Krakend
Aggregator gateway: combines multiple backend calls into one response.

### Custom
Build with FastAPI/Go for specific needs.

---

## 18. Trade-offs

| Decision | Trade-off |
|---|---|
| Add gateway hop | +5ms latency; centralized control |
| Auth in gateway | Backends simpler; gateway becomes auth bottleneck |
| Rate limit in Redis | Distributed accurate; Redis is dependency |
| Caching in gateway | Reduces backend load; stale data risk |
| Dynamic config | Faster updates; complexity |
| Multi-region | Lower latency globally; replication complexity |

---

## 19. Failure Modes

### Gateway down
- Redundant nodes behind LB.
- LB health checks remove dead ones.
- Multi-region failover.

### Backend down
- Circuit breaker in gateway.
- Fallback response if configured.
- Return 503 to client.

### Redis down (rate limit, cache)
- Fail open: allow requests through (or fail closed if strict).
- Reduced functionality (no rate limiting), but service alive.

### Config service down
- Use last-known-good config from local cache.
- Don't crash on config service unavailable.

---

## 20. APIs (Management)

```
GET    /admin/routes               # list
POST   /admin/routes               # create
PATCH  /admin/routes/{id}          # update
DELETE /admin/routes/{id}          # remove

GET    /admin/services             # list backends
POST   /admin/services
DELETE /admin/services/{id}

GET    /admin/consumers            # API key holders
POST   /admin/consumers

GET    /admin/plugins              # enabled plugins
POST   /admin/plugins              # enable
```

Authenticated via separate admin API key.

---

## 21. Follow-up Questions

- **"Where do you put business logic?"** → Backends. Gateway is for cross-cutting concerns only.
- **"Latency comparison between API Gateway languages?"** → Lua/OpenResty fastest. Go (Envoy/Krakend) next. Python last.
- **"How to roll out a new route safely?"** → Deploy to canary instances first; promote after metrics OK.
- **"Backend-for-Frontend pattern vs API Gateway?"** → BFF: one per frontend, business logic. Gateway: one shared, no business logic. Often combined.
- **"How to do request aggregation (1 client request → many backend calls)?"** → Aggregator pattern; Krakend does this. Often a layer above the gateway.
- **"How to do canary deploys at gateway?"** → Route 5% of traffic to new backend version; metrics-based promote.
