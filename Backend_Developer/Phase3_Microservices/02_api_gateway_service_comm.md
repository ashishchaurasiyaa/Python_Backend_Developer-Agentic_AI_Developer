# Microservices — API Gateway & Service Communication
**Intermediate-Advanced | What, Why, How**

---

## Quick Concepts
- **API Gateway** = single entry point for all clients — routing, auth, rate limiting centrally handle karta hai
- **Service Discovery** = services dynamically ek doosre ko dhundte hain — hardcoded IPs nahi
- **Synchronous Comm** = HTTP/REST ya gRPC — caller response ka wait karta hai
- **Asynchronous Comm** = Events via RabbitMQ/Kafka — fire and forget, loose coupling
- **BFF (Backend for Frontend)** = alag-alag clients ke liye alag-alag gateways
- **Correlation ID** = ek request ka trace sab services mein karo — debugging easy

---

## Interview Questions & Answers

### Q1: API Gateway kyun zaruri hai? Without Gateway kya problem hoti hai?

**Answer:**
```
WITHOUT API GATEWAY:
  Client → directly calls User Service    (port 8001)
  Client → directly calls Product Service (port 8002)
  Client → directly calls Order Service   (port 8003)

  Problems:
  - CORS har service mein configure karo ❌
  - Auth/JWT verification har service mein likhni padegi ❌
  - Rate limiting har service mein implement karo ❌
  - SSL certificates har service ke liye ❌
  - Client ko sabke ports/IPs yaad rakhne padte hain ❌
  - Load balancing har service ke liye alag ❌

WITH API GATEWAY:
  Client → API Gateway (single entry point: port 8000)
               ↓ routes to appropriate service
    /api/users/*    → User Service (8001)
    /api/products/* → Product Service (8002)
    /api/orders/*   → Order Service (8003)

  Gateway centrally handle karta hai:
  ✅ Routing
  ✅ JWT Authentication & Authorization
  ✅ Rate Limiting
  ✅ SSL Termination
  ✅ Request/Response Transformation
  ✅ Logging & Monitoring
  ✅ Circuit Breaking
  ✅ Load Balancing
```

---

### Q2: API Gateway responsibilities kya hote hain? Nginx se kaise configure karein?

**Answer:**

**API Gateway Responsibilities:**
```
1. ROUTING         → path prefix se sahi service ko forward karo
2. AUTH            → JWT verify karo, invalid requests reject karo
3. RATE LIMITING   → per IP/user request throttle karo
4. SSL TERMINATION → HTTPS gateway pe handle karo, HTTP internally
5. TRANSFORMATION  → request/response headers modify karo
6. LOGGING         → sab requests log karo centrally
7. AGGREGATION     → multiple services ki calls combine karo (BFF)
8. CIRCUIT BREAKER → downstream service fail ho to fast-fail
```

**Nginx as Simple API Gateway:**
```nginx
# nginx.conf

upstream user_service {
    server user-service:8001;
}

upstream product_service {
    server product-service:8002;
}

upstream order_service {
    server order-service:8003;
}

server {
    listen 80;
    
    # Rate limiting zone
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    # User Service routes
    location /api/users/ {
        limit_req zone=api burst=20;
        proxy_pass http://user_service/;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Request-ID $request_id;  # correlation ID
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }
    
    # Product Service routes
    location /api/products/ {
        limit_req zone=api burst=50;   # products pe zyada burst allow
        proxy_pass http://product_service/;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Request-ID $request_id;
    }
    
    # Order Service routes
    location /api/orders/ {
        limit_req zone=api burst=10;   # orders pe strict
        proxy_pass http://order_service/;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Request-ID $request_id;
    }
    
    # Health check
    location /health {
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }
}
```

---

### Q3: Python mein custom API Gateway kaise likhte hain? FastAPI se implement karo.

**Answer:**

```python
import httpx
import uuid
from fastapi import FastAPI, Request, HTTPException, Response
from collections import defaultdict
import time

app = FastAPI(title="API Gateway")

# Downstream services registry
SERVICES = {
    "users":    "http://user-service:8001",
    "products": "http://product-service:8002",
    "orders":   "http://order-service:8003",
}

# In-memory rate limiter (production mein Redis use karo)
rate_limit_store = defaultdict(list)
RATE_LIMIT = 10  # requests per minute per IP

def check_rate_limit(client_ip: str) -> bool:
    """IP per rate limit check karo"""
    now = time.time()
    # 1 minute se purani entries hata do
    rate_limit_store[client_ip] = [
        t for t in rate_limit_store[client_ip] if now - t < 60
    ]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return False  # limit exceed
    rate_limit_store[client_ip].append(now)
    return True

def verify_jwt(token: str) -> dict:
    """JWT verify karo — simplified demo"""
    import jwt as pyjwt
    try:
        payload = pyjwt.decode(token.replace("Bearer ", ""), "secret", algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

@app.api_route(
    "/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def gateway(service: str, path: str, request: Request):
    """Main gateway — sab requests yahan aati hain"""
    
    # 1. Service exists kya?
    if service not in SERVICES:
        raise HTTPException(404, f"Service '{service}' not found")
    
    # 2. Rate limit check
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(429, "Too many requests — slow down!")
    
    # 3. JWT Auth verify
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "Authorization header missing")
    user_payload = verify_jwt(token)
    
    # 4. Correlation ID generate karo (tracing ke liye)
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # 5. Forward request to downstream service
    url = f"{SERVICES[service]}/{path}"
    forward_headers = dict(request.headers)
    forward_headers["X-Request-ID"] = correlation_id
    forward_headers["X-User-ID"] = str(user_payload.get("sub", ""))
    forward_headers["X-Gateway"] = "python-gateway"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=forward_headers,
                content=await request.body(),
                params=dict(request.query_params),
                timeout=30.0
            )
    except httpx.TimeoutException:
        raise HTTPException(504, "Downstream service timeout")
    except httpx.ConnectError:
        raise HTTPException(502, f"Cannot connect to {service} service")
    
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"X-Request-ID": correlation_id}
    )

@app.get("/health")
async def health_check():
    """Sab downstream services ko ping karo"""
    results = {}
    async with httpx.AsyncClient() as client:
        for service, url in SERVICES.items():
            try:
                resp = await client.get(f"{url}/health", timeout=3.0)
                results[service] = "up" if resp.status_code == 200 else "degraded"
            except Exception:
                results[service] = "down"
    
    overall = "healthy" if all(v == "up" for v in results.values()) else "degraded"
    return {"status": overall, "services": results}
```

**Redis-based Rate Limiting (Production):**
```python
import redis.asyncio as aioredis

redis_client = aioredis.from_url("redis://redis:6379")

async def redis_rate_limit(client_ip: str, limit: int = 100, window: int = 60) -> bool:
    """Sliding window rate limiter using Redis"""
    key = f"rate_limit:{client_ip}"
    now = time.time()
    
    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)   # purane entries hata do
    pipe.zadd(key, {str(now): now})               # naya request add karo
    pipe.zcard(key)                                # count karo
    pipe.expire(key, window)                       # TTL set karo
    results = await pipe.execute()
    
    count = results[2]
    return count <= limit
```

---

### Q4: Service-to-Service communication kaise karte hain? Auth kaise handle hoti hai?

**Answer:**

**Internal Service HTTP Client (Retry + Error Handling):**
```python
import httpx
import asyncio

class ServiceClient:
    """Base HTTP client for internal services"""
    def __init__(self, base_url: str, service_name: str, service_token: str):
        self.base_url = base_url
        self.service_name = service_name
        self.headers = {
            "Authorization": f"Bearer {service_token}",
            "X-Service-Name": service_name,
        }
    
    async def get(self, path: str, **kwargs):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=10.0,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
    
    async def post(self, path: str, data: dict, **kwargs):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}{path}",
                json=data,
                headers=self.headers,
                timeout=10.0,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
```

**Service-to-Service JWT Auth:**
```python
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "internal-secret-do-not-expose"

def create_service_token(service_name: str) -> str:
    """Service-to-service JWT create karo"""
    payload = {
        "sub":  service_name,
        "type": "service",           # user token se different — important!
        "iss":  "auth-service",
        "exp":  datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_service_token(token: str) -> dict:
    """Incoming service token validate karo"""
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != "service":
        raise HTTPException(403, "Not a service token — user token se internal call mat karo")
    return payload

# Order Service apna token banata hai aur Inventory Service ko call karta hai
order_service_token = create_service_token("order-service")
inventory_client = ServiceClient(
    base_url="http://inventory-service:8002",
    service_name="order-service",
    service_token=order_service_token
)

# Usage
inventory = await inventory_client.get(f"/api/stock/{product_id}")
```

---

### Q5: Synchronous vs Asynchronous communication — kab kya use karein?

**Answer:**
```
┌──────────────────────────────────────────────────────────────────────┐
│ Pattern     │ Protocol        │ Use When                             │
├──────────────────────────────────────────────────────────────────────┤
│ Sync HTTP   │ REST/JSON       │ Real-time response needed            │
│             │                 │ e.g. Get product details, user login │
├──────────────────────────────────────────────────────────────────────┤
│ Sync gRPC   │ HTTP/2+Protobuf │ High performance internal calls      │
│             │                 │ e.g. ML model inference, low latency │
├──────────────────────────────────────────────────────────────────────┤
│ Async Event │ RabbitMQ/Kafka  │ Fire and forget, background tasks    │
│             │                 │ e.g. Order placed → send email       │
├──────────────────────────────────────────────────────────────────────┤
│ Async Queue │ Celery/Redis    │ Long running jobs                    │
│             │                 │ e.g. PDF generate, image resize      │
└──────────────────────────────────────────────────────────────────────┘

Decision Rules:
  User response wait karta hai?           → Sync (HTTP/gRPC)
  Background mein ho sakta hai?           → Async (events)
  Multiple services notify karne hain?    → Events (pub/sub)
  Guaranteed delivery chahiye?            → RabbitMQ with acks
  High throughput, replay chahiye?        → Kafka
```

**Asynchronous Event Publishing (RabbitMQ):**
```python
import aio_pika
import json
from datetime import datetime

async def publish_event(event_type: str, payload: dict, source_service: str):
    """Event publish karo — koi direct HTTP call nahi"""
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
    channel = await connection.channel()
    
    # Topic exchange — routing key = event type
    exchange = await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC)
    
    message = aio_pika.Message(
        json.dumps({
            "event_type": event_type,
            "payload":    payload,
            "timestamp":  datetime.utcnow().isoformat(),
            "source":     source_service,
        }).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT  # broker restart pe bhi survive kare
    )
    
    await exchange.publish(message, routing_key=event_type)
    await connection.close()

# Order Service event publish karta hai
await publish_event(
    event_type="order.placed",
    payload={"order_id": 123, "user_id": 456, "amount": 5000, "items": [...]},
    source_service="order-service"
)

# Inventory Service subscribe karta hai "order.placed" events pe
# Email Service subscribe karta hai "order.placed" events pe
# Analytics Service subscribe karta hai "order.*" sab events pe
```

---

### Q6: Service Discovery kya hai? Docker Compose aur Kubernetes mein kaise kaam karta hai?

**Answer:**
```
PROBLEM:
  Service B ka IP/port kya hai?
  Hardcode karo?  ❌  (service restart pe IP change hoti hai)
  Environment variable mein dalo? Partial solution

SOLUTIONS:

1. DOCKER COMPOSE DNS (simplest):
   Docker automatically service name ko hostname bana deta hai
   
   order-service → http://inventory-service:8002/api/stock
                            ↑
                   Docker internal DNS resolve karta hai
   
   Koi extra setup nahi — bas docker-compose.yml mein service name likhna hai

2. KUBERNETES SERVICE RESOURCE:
   kubectl apply -f inventory-service.yaml → stable DNS milta hai
   
   http://inventory-service.default.svc.cluster.local/api/stock
            ↑             ↑         ↑
         svc-name      namespace  k8s domain
   
   Short form: http://inventory-service/api/stock  (same namespace mein)

3. CONSUL (Self-hosted Service Registry):
   Service start hoti hai → Consul mein register karti hai
   Service discover karna hai → Consul se address lo
   Health checks → Consul automatically unhealthy services remove karta hai
```

**Docker Compose Multi-Service Setup:**
```yaml
version: '3.8'

services:
  api-gateway:
    build: ./gateway
    ports: ["8000:8000"]
    environment:
      - USER_SERVICE_URL=http://user-service:8001
      - PRODUCT_SERVICE_URL=http://product-service:8002
      - ORDER_SERVICE_URL=http://order-service:8003
    depends_on: [user-service, product-service, order-service]

  user-service:
    build: ./user-service
    ports: ["8001:8001"]
    environment:
      - DATABASE_URL=postgresql://user:pass@users-db:5432/users
      - REDIS_URL=redis://redis:6379
    depends_on: [users-db, redis]

  product-service:
    build: ./product-service
    ports: ["8002:8002"]
    environment:
      - DATABASE_URL=postgresql://user:pass@products-db:5432/products
      - REDIS_URL=redis://redis:6379
    depends_on: [products-db, redis]

  order-service:
    build: ./order-service
    ports: ["8003:8003"]
    environment:
      - DATABASE_URL=postgresql://user:pass@orders-db:5432/orders
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
      # Service discovery — naam hi kafi hai!
      - INVENTORY_SERVICE_URL=http://product-service:8002
      - PAYMENT_SERVICE_URL=http://payment-service:8004
    depends_on: [orders-db, rabbitmq]

  users-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: users
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes: [users_data:/var/lib/postgresql/data]

  products-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: products
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes: [products_data:/var/lib/postgresql/data]

  orders-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes: [orders_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"    # AMQP
      - "15672:15672"  # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest

volumes:
  users_data:
  products_data:
  orders_data:
```

---

### Q7: BFF (Backend for Frontend) pattern kya hai? Kab use karein?

**Answer:**
```
PROBLEM:
  Mobile app ko lightweight response chahiye (bandwidth save)
  Web app ko rich response chahiye (extra fields)
  Public API aur Internal API alag honi chahiye

BFF PATTERN:
  Mobile Client   → Mobile BFF Gateway   → downstream services
  Web Client      → Web BFF Gateway      → downstream services
  Third-party     → Public API Gateway   → downstream services

BENEFITS:
  - Har client ke liye optimized response
  - Mobile BFF → heavy fields strip karo, response compress karo
  - Web BFF → multiple calls aggregate karo ek mein
  - Security: public API limited endpoints expose kare

REQUEST AGGREGATION EXAMPLE:
  Mobile app ne product page open kiya
  Web BFF internally calls:
    GET /api/products/123          → product details
    GET /api/reviews/product/123   → reviews
    GET /api/inventory/123         → stock info
  ...aur sab combine karke ek response deta hai ← efficiency!
```

```python
# BFF — Order Dashboard (Web ke liye aggregate response)
@app.get("/dashboard/order/{order_id}")
async def order_dashboard_bff(order_id: int, token: str = Header(None)):
    """Web app ke liye — ek call mein sab data"""
    
    async with httpx.AsyncClient() as client:
        # Parallel calls for speed
        order_task     = client.get(f"{ORDER_SERVICE}/orders/{order_id}")
        user_task      = client.get(f"{USER_SERVICE}/users/me")
        
        order_resp, user_resp = await asyncio.gather(order_task, user_task)
        
        order = order_resp.json()
        
        # Product details fetch karo (order items ke liye)
        product_ids = [item["product_id"] for item in order["items"]]
        product_tasks = [
            client.get(f"{PRODUCT_SERVICE}/products/{pid}")
            for pid in product_ids
        ]
        product_resps = await asyncio.gather(*product_tasks)
        products = {p.json()["id"]: p.json() for p in product_resps}
    
    # Aggregate response — single API call for everything
    return {
        "order":    order,
        "user":     user_resp.json(),
        "products": products,
        "summary":  {
            "total_items": len(order["items"]),
            "total_amount": sum(i["price"] * i["quantity"] for i in order["items"])
        }
    }
```

---

## Summary Table

```
┌────────────────────┬──────────────────────────────┬───────────────────────────────┐
│ Concept            │ Kya karta hai                 │ Example                       │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ API Gateway        │ Single entry point, routing,  │ Client → Gateway → Services   │
│                    │ auth, rate limiting centrally │                               │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Nginx Gateway      │ Simple reverse proxy +        │ location /api/users/ →        │
│                    │ load balancer                 │ proxy_pass user-service       │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ FastAPI Gateway    │ Custom logic — JWT, rate      │ Python mein full control      │
│                    │ limit, transformation         │ middleware as code            │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Service Token      │ Service-to-service auth       │ type: "service" JWT           │
│                    │ user token se alag            │ vs type: "user" JWT           │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Sync HTTP          │ Direct REST call — wait       │ GET /products/123             │
│                    │ for response                  │ real-time data                │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Async Events       │ Publish event, no wait        │ order.placed → inventory,     │
│                    │ consumers independently       │ email, analytics subscribe    │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Docker DNS         │ Service name = hostname       │ http://inventory-service:8002 │
│ (Service Discovery)│ automatic, no config          │ works in docker-compose       │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ BFF Pattern        │ Per-client gateway            │ Mobile BFF vs Web BFF         │
│                    │ aggregate + optimize          │ different response shapes     │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Correlation ID     │ Request trace across          │ X-Request-ID header           │
│                    │ all services                  │ sab logs mein same ID         │
├────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ Rate Limiting      │ Abuse prevent karo            │ 10 req/min per IP             │
│                    │ gateway level pe              │ Redis sliding window          │
└────────────────────┴──────────────────────────────┴───────────────────────────────┘
```
