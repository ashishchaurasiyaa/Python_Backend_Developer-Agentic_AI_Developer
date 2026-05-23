# Communication Protocols — HTTP/HTTPS, WebSocket, gRPC, REST vs GraphQL

## Quick Reference Card
```
HTTP/1.1   → Request-response, new TCP per request (or persistent with keep-alive)
HTTP/2     → Multiplexing — multiple requests on 1 TCP connection — 2-3x faster
HTTPS      → HTTP + TLS encryption — SSL termination at load balancer
WebSocket  → Full-duplex — server pushes to client — real-time apps
gRPC       → Binary protocol (Protocol Buffers) — fast, typed, microservices
REST       → Resource-based, stateless, HTTP verbs, JSON
GraphQL    → Client specifies exact data shape — no over/under-fetching
Interview hook → "DRF REST APIs + HTTPS | WebSocket = real-time booking updates"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 HTTP — The Foundation

```
HTTP (HyperText Transfer Protocol):
  Client → Request → Server → Response
  
  REQUEST:
  GET /api/packages/?destination=kerala HTTP/1.1
  Host: api.niroskos.com
  Authorization: Bearer eyJhbGc...
  Accept: application/json
  
  RESPONSE:
  HTTP/1.1 200 OK
  Content-Type: application/json
  Cache-Control: max-age=300
  
  {"packages": [...]}

HTTP METHODS:
  GET    → Read resource (idempotent, safe)
  POST   → Create resource (not idempotent)
  PUT    → Replace resource completely (idempotent)
  PATCH  → Update partially (idempotent)
  DELETE → Remove resource (idempotent)

HTTP STATUS CODES:
  2xx: Success
    200 OK, 201 Created, 204 No Content
  3xx: Redirect
    301 Permanent Redirect, 302 Temporary, 304 Not Modified (cached)
  4xx: Client Error
    400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
    409 Conflict, 422 Unprocessable Entity, 429 Too Many Requests
  5xx: Server Error
    500 Internal Server Error, 503 Service Unavailable, 504 Gateway Timeout
```

---

### 1.2 HTTP/1.1 vs HTTP/2 vs HTTP/3

```
HTTP/1.1 PROBLEMS:
  - One request at a time per TCP connection
  - Browser opens 6 TCP connections per domain (workaround)
  - Head-of-line blocking: Slow request blocks all subsequent
  - Headers sent as plain text, not compressed, sent every request
  
  ──────────────────────────────────────────────
  TCP conn 1: [Request 1] ─── [Response 1]
  TCP conn 2: [Request 2] ─── [Response 2]
  ──────────────────────────────────────────────

HTTP/2 IMPROVEMENTS:
  1. Multiplexing: Multiple requests on SAME TCP connection
  2. Header compression (HPACK): Repeated headers compressed
  3. Server Push: Server can send resources before client asks
  4. Binary protocol (not text) — faster parsing
  
  ──────────────────────────────────────────────
  Single TCP connection:
  Stream 1: ──Request 1─────────────────────────Response 1──
  Stream 2: ──────────Request 2───────Response 2────────────
  Stream 3: ──────────────────Request 3──────────Response 3─
  ──────────────────────────────────────────────
  All interleaved on same connection!

HTTP/3:
  HTTP/2 over QUIC (UDP-based) instead of TCP
  Eliminates TCP head-of-line blocking
  Faster TLS handshake (0-RTT)
  Better for unreliable networks (mobile)
  Chrome/Firefox: Support HTTP/3

Django + HTTP/2:
  Nginx handles HTTP/2 automatically
  server {
      listen 443 ssl http2;  # Enable HTTP/2
      ...
  }
  (No Django code changes needed — Nginx handles it)
```

---

### 1.3 HTTPS and TLS

```
HTTPS = HTTP + TLS (Transport Layer Security)

WHY TLS:
  Without TLS: "username=ashish&password=secret123" sent as plain text
  Anyone on same WiFi can read it (packet sniffing)
  
  With TLS: Encrypted — interceptor sees random bytes

TLS HANDSHAKE (simplified):
  Client → "Hello" → Server
  Server → Certificate (public key) + "Hello" → Client
  Client verifies certificate (signed by trusted CA)
  Client → encrypted session key (using server's public key) → Server
  Server decrypts session key (using its private key)
  Both now share session key → symmetric encryption begins
  
  TLS 1.3 (modern): 1 round-trip (was 2 in TLS 1.2)

SSL TERMINATION AT LOAD BALANCER:
  Client → HTTPS → ALB (decrypts) → HTTP → Django
  
  Benefits:
  - Single SSL certificate managed at LB
  - Backend (Django) doesn't need certificate
  - Offloads encryption CPU from app servers
  
  AWS ALB: Handles SSL termination + certificate renewal (ACM)
  LetsEncrypt: Free certificate (90-day renewal via certbot)

HSTS (HTTP Strict Transport Security):
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  Browser: "Never send HTTP to this domain — ALWAYS HTTPS"
  Prevents SSL stripping attacks
```

---

### 1.4 WebSocket — Bidirectional Real-Time

```
HTTP (request-response):
  Client initiates: "Give me data"
  Server responds: "Here's data"
  Connection closes
  
  Client must POLL for updates:
  Every 2 sec: GET /booking/123/status
  → Wasteful (99% times no change)

WebSocket (full-duplex):
  Upgrade request:
  GET /ws/booking/123 HTTP/1.1
  Upgrade: websocket
  Connection: Upgrade
  
  Connection STAYS OPEN:
  Client → Server: "I want booking updates"
  Server → Client: "Status changed to CONFIRMED!" (push!)
  Server → Client: "Driver arriving in 5 min!" (push!)
  Client → Server: "Send my current location"
  
  No polling needed — server pushes when something changes

USE CASES:
  ✓ Live booking status updates
  ✓ Chat applications
  ✓ Real-time dashboards (stock prices, analytics)
  ✓ Multiplayer games
  ✓ Collaborative editing (Google Docs-like)
  ✓ Ride tracking (Uber-like driver location)
  ✓ Live support chat

DJANGO CHANNELS (WebSocket in Django):
  pip install channels channels-redis
  
  # routing.py
  from channels.routing import ProtocolTypeRouter, URLRouter
  
  application = ProtocolTypeRouter({
      'http': get_asgi_application(),
      'websocket': URLRouter([
          path('ws/booking/<int:booking_id>/', BookingConsumer.as_asgi()),
      ]),
  })
  
  # consumers.py
  from channels.generic.websocket import AsyncWebsocketConsumer
  import json
  
  class BookingConsumer(AsyncWebsocketConsumer):
      async def connect(self):
          self.booking_id = self.scope['url_route']['kwargs']['booking_id']
          self.group_name = f'booking_{self.booking_id}'
          
          # Join room group
          await self.channel_layer.group_add(self.group_name, self.channel_name)
          await self.accept()
      
      async def disconnect(self, close_code):
          await self.channel_layer.group_discard(self.group_name, self.channel_name)
      
      # Receive message from room group (sent by server logic)
      async def booking_update(self, event):
          await self.send(text_data=json.dumps({
              'type': 'booking_update',
              'status': event['status'],
              'message': event['message'],
          }))
  
  # Trigger from views.py (when booking status changes):
  from channels.layers import get_channel_layer
  from asgiref.sync import async_to_sync
  
  def update_booking_status(booking_id, new_status):
      channel_layer = get_channel_layer()
      async_to_sync(channel_layer.group_send)(
          f'booking_{booking_id}',
          {
              'type': 'booking_update',
              'status': new_status,
              'message': f'Booking status: {new_status}'
          }
      )

Long Polling (alternative to WebSocket):
  Client: GET /events?last_id=100 (blocks up to 30 seconds)
  Server: Holds connection until new event → returns event
  Client: Gets event, immediately requests next: GET /events?last_id=101
  
  Simpler than WebSocket, compatible with all HTTP infrastructure
  Higher overhead (HTTP headers on every poll)
  Good when: Infrequent updates, simpler infrastructure
```

---

### 1.5 gRPC — High Performance RPC

```
gRPC = Google Remote Procedure Call
  - Binary protocol (Protocol Buffers — not JSON)
  - HTTP/2 based (multiplexing, streaming)
  - Strongly typed (schema defined in .proto file)
  - Code generation (client/server stubs auto-generated)
  - 5-10x smaller payload vs JSON, 3-5x faster

HOW IT WORKS:
  1. Define service in .proto file
  2. Generate client/server code (grpc_tools)
  3. Server implements methods
  4. Client calls methods like local functions

  # booking_service.proto
  syntax = "proto3";
  
  service BookingService {
    rpc CreateBooking(BookingRequest) returns (BookingResponse);
    rpc GetBookingStatus(BookingQuery) returns (BookingStatus);
    rpc StreamBookingUpdates(BookingQuery) returns (stream BookingUpdate);
  }
  
  message BookingRequest {
    int32 user_id = 1;
    int32 package_id = 2;
    string travel_date = 3;
    float amount = 4;
  }
  
  message BookingResponse {
    int32 booking_id = 1;
    string status = 2;
    string confirmation_code = 3;
  }

4 COMMUNICATION PATTERNS:
  1. Unary RPC: Single request, single response (like HTTP REST)
  2. Server Streaming: Client sends request, server streams N responses
  3. Client Streaming: Client streams N requests, server gives 1 response
  4. Bidirectional Streaming: Both sides stream simultaneously

USE CASES:
  ✓ Microservices internal communication (not exposed to browser)
  ✓ High-performance service-to-service calls
  ✓ Real-time bidirectional streaming
  ✓ Polyglot systems (auto-generate clients in Python, Go, Java)

NOT GOOD FOR:
  ✗ Browser clients (limited gRPC support — use gRPC-Web)
  ✗ Human-readable APIs (binary, not debuggable with curl)
  ✗ Simple CRUD apps (REST is simpler)

Youngman: Not using gRPC — Django REST Framework sufficient
          Would use if split into microservices needing fast internal calls
```

---

### 1.6 REST vs GraphQL

```
REST:
  Resource-based URLs
  GET /packages/         → list all packages
  GET /packages/123/     → get specific package
  GET /packages/123/hotels/ → get hotels for package
  
  PROBLEM: Over-fetching
  User wants: package name + price only
  REST returns: FULL package object (name, price, description, hotels, itinerary...)
  → Wasted bandwidth for mobile clients
  
  PROBLEM: Under-fetching (N+1 requests)
  Need: List of packages with their first hotel name
  REST:
    GET /packages/ → 20 packages
    GET /hotels/?package_id=1  → hotel for pkg 1
    GET /hotels/?package_id=2  → hotel for pkg 2
    ...20 more requests!
  
  SOLUTION: REST with ?include=hotels (manual expansion)
  → Works but requires API design effort per case

GRAPHQL:
  Single endpoint: POST /graphql
  Client specifies EXACTLY what it wants:
  
  query {
    packages(filter: {destination: "Kerala"}) {
      name
      price
      primaryHotel {
        name
        starRating
      }
    }
  }
  
  Server returns ONLY what was asked:
  {
    "packages": [
      {"name": "Kerala Tour", "price": 25000, "primaryHotel": {"name": "Taj", "starRating": 5}}
    ]
  }
  
  ONE request! Exact fields! No over-fetching!

GRAPHQL BENEFITS:
  ✓ No over-fetching (only requested fields)
  ✓ No under-fetching (related data in same query)
  ✓ Self-documenting (introspection)
  ✓ Strongly typed schema
  ✓ Rapid frontend iteration (no backend changes for new data shapes)

GRAPHQL CHALLENGES:
  ✗ N+1 query problem (need DataLoader)
  ✗ Caching harder (POST requests, custom query as cache key)
  ✗ File uploads complex (multipart workaround)
  ✗ Learning curve
  ✗ Complexity for simple CRUD

Niroskos:
  Currently: REST (DRF) — familiar, simpler
  If mobile app team needs to iterate rapidly → GraphQL worth evaluating
  For now: REST with ?fields=name,price expansion handles needs

REST vs GraphQL Decision:
  REST when:
    Simple CRUD
    Team knows REST well
    Caching important (GET requests cached by default)
    Public API (widely understood)
  
  GraphQL when:
    Multiple clients (web + mobile + tablet) with different data needs
    Rapidly changing data requirements
    Complex nested data
    Avoid multiple round-trips
```

---

### 1.7 Protocols Comparison Table

```
           HTTP/REST   WebSocket   gRPC        GraphQL
           ───────────────────────────────────────────────
Pattern    Request-    Full-duplex RPC +        Query
           Response    persistent  streaming    language
Data format JSON/XML   Text/Binary  Protobuf    JSON
Performance Medium      Good         Best        Medium
Typing     No          No           Strong       Strong
Browser    Yes         Yes          Limited      Yes
           support
Streaming  No (HTTP/2  Yes          Yes          Subscriptions
           Server Push)
Caching    Easy (GET)   Hard         Hard         Hard
Use case   CRUD APIs   Real-time   Microservice Frontend-
                       apps        internal     driven APIs
Debugging  Easy (curl)  Medium       Complex      Playground
```

---

### 1.8 Ashish ke projects mein

```
Youngman:
  REST (DRF): All public/internal APIs
    - Invoice creation: POST /api/invoices/
    - SAP sync: POST /api/sap/invoices/{id}/sync/
    - Company listing: GET /api/companies/
  
  HTTPS: AWS ALB handles SSL termination
    - ACM certificate (auto-renewal)
    - HSTS header set in Nginx config
  
  HTTP/2: Nginx configured with "listen 443 ssl http2;"
    - Reduces multiple API call overhead on frontend
  
  WebSocket: NOT yet (future: real-time invoice SAP status)
  gRPC: NOT needed (not microservices yet)
  GraphQL: NOT needed (simple CRUD, DRF works well)

Niroskos:
  REST (DRF): All booking/package APIs
  
  Future WebSocket use case:
  - Booking confirmation real-time status
  - Driver tracking (if ride component added)
  
  Exotel webhook (HTTP POST from external):
    Exotel → POST /api/webhooks/exotel/ → Django
    HMAC signature verification on request
    (See Resume_Based_LLD_Interview_Prep.md for code)

Key protocol decisions:
  "Browser clients → REST is fine, simple, well-understood"
  "Mobile app with complex data needs → consider GraphQL"
  "Real-time push from server → WebSocket or Server-Sent Events"
  "Internal microservice calls → gRPC for performance"
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **HTTP**: Application-layer protocol for client-server communication. Stateless request-response model. HTTP/2 adds multiplexing and header compression over HTTP/1.1.

> **HTTPS**: HTTP over TLS (Transport Layer Security). Provides encryption, server authentication, and data integrity. TLS handshake establishes encrypted session.

> **WebSocket**: Full-duplex communication protocol over a single TCP connection. Enables server-initiated messages to clients. Established via HTTP upgrade request.

> **gRPC**: High-performance RPC framework using Protocol Buffers for serialization and HTTP/2 for transport. Strongly typed, code-generated clients/servers, 3-5x more efficient than JSON REST.

---

### 2.2 REST Constraints (for interviews)

```
6 REST Constraints (Roy Fielding's dissertation):

1. Client-Server: Separation of UI and data storage
2. Stateless: Each request contains all information (no server-side session)
3. Cacheable: Responses must declare if cacheable (Cache-Control header)
4. Uniform Interface: 
   - Resource identification (URI)
   - Manipulation via representations (JSON body)
   - Self-descriptive messages (Content-Type)
   - HATEOAS (links to related resources — rarely followed in practice)
5. Layered System: Client can't tell if talking to real server or proxy
6. Code on Demand (optional): Server can send executable code (JS)

"RESTful" API follows these constraints (loosely in practice).
Most "REST APIs" are actually HTTP APIs with JSON.
True REST (with HATEOAS) is rarely implemented.
```

---

### 2.3 Real Project Answer

> "In our projects, we use REST with Django REST Framework for all API endpoints — it's the standard for our use case and the team knows it well. HTTPS is handled at the AWS ALB level with ACM-managed certificates; Django only handles HTTP internally. We configure Nginx with HTTP/2 for the HTTPS listeners, which reduces overhead when the frontend makes multiple API calls. For Exotel webhook integration, incoming POST requests carry HMAC-SHA256 signatures that we validate before processing. WebSocket is on our roadmap — we'd use Django Channels to implement real-time booking status updates rather than having clients poll every 2 seconds. gRPC would be relevant if we split into microservices, but at our current monolithic architecture, DRF is the right tool."

---

### 2.4 Common Follow-up Q&A

**Q1: What is the difference between HTTP/1.1 and HTTP/2?**
> "HTTP/1.1 uses a new TCP connection (or one persistent connection) per request-response pair, and requests are sequential — you wait for response before sending next request (head-of-line blocking). HTTP/2 introduces multiplexing — multiple requests and responses are interleaved on a single TCP connection as independent streams. This eliminates the need for browser hacks like domain sharding. HTTP/2 also compresses headers (HPACK) — repeated headers like Authorization and User-Agent aren't sent repeatedly. Result: 2-3x fewer TCP connections and measurably better page load times. Enabled in Nginx with just `listen 443 ssl http2;`."

**Q2: When would you use Server-Sent Events instead of WebSockets?**
> "Server-Sent Events (SSE) is a simpler alternative to WebSockets for one-way server-to-client streaming. With SSE, the client makes a normal HTTP GET request with `Accept: text/event-stream`, and the server keeps the connection open and sends events as they occur. Key differences: SSE is unidirectional (server → client only), works over HTTP (no upgrade needed), automatically reconnects, and is natively supported by browsers. Use SSE for: live feeds, notifications, status updates where client doesn't need to send data. Use WebSocket for: chat (bidirectional), gaming, collaborative editing. SSE is simpler to implement and works through HTTP proxies and load balancers that might not handle WebSocket upgrades."

**Q3: What are the security concerns with REST APIs?**
> "Main concerns: (1) Authentication — use JWT or session tokens; avoid API keys in URL params (they end up in logs). (2) Authorization — ensure user A can't access user B's data; check ownership on every resource. (3) Rate limiting — prevent brute force and DDoS; use 429 Too Many Requests with Retry-After header. (4) Input validation — validate all inputs; never trust client data. (5) HTTPS everywhere — no plain HTTP; HSTS header prevents downgrade attacks. (6) CORS — configure CORS_ALLOWED_ORIGINS precisely; never use `*` in production. (7) SQL injection — use ORM (Django ORM parameterizes queries automatically). (8) Webhook signature verification — HMAC-SHA256 to verify webhook sender is legitimate."

---

## Interview Cheat Sheet

```
HTTP Methods:
  GET (idempotent, safe), POST (create), PUT (replace),
  PATCH (update), DELETE (idempotent)

HTTP Status Codes:
  200 OK, 201 Created, 204 No Content
  400 Bad Request, 401 Unauth, 403 Forbidden, 404 Not Found
  409 Conflict, 422 Unprocessable, 429 Rate Limited
  500 Server Error, 503 Unavailable, 504 Gateway Timeout

HTTP/2 benefits over HTTP/1.1:
  Multiplexing (multiple requests, 1 TCP)
  Header compression (HPACK)
  Binary protocol (faster parsing)

HTTPS + TLS:
  Encryption + authentication
  SSL termination at load balancer (ALB)
  HSTS prevents HTTP downgrade

WebSocket:
  Full-duplex over single TCP connection
  Server can push to client without polling
  Use: Chat, real-time dashboards, tracking
  Django Channels: channels + channels-redis

gRPC:
  Binary (Protobuf) + HTTP/2 = 5-10x faster than REST+JSON
  Strongly typed, code generated
  Use: Microservice internal communication
  Not for: Browsers (use REST/GraphQL instead)

REST vs GraphQL:
  REST: Simple, cacheable, universal understanding
        Problem: over/under-fetching
  GraphQL: Exact data shape, one request for nested data
           Problem: Caching harder, N+1 needs DataLoader

My stack:
  REST (DRF): All APIs
  HTTPS: ALB SSL termination (ACM cert)
  HTTP/2: Nginx configuration
  WebSocket: Future (booking real-time status)
  gRPC: Not needed (not microservices yet)
```
