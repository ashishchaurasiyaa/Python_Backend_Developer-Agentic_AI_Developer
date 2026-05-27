# Lecture 2: API Gateway and Backend for Frontend (BFF)

> *"The API Gateway is the front door. The BFF is the personal concierge."*

**Section 4 — Communication & Integration Patterns**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why we need API Gateways** — single entry point, cross-cutting concerns
- **Core gateway responsibilities** — routing, transformation, security
- **Path-based vs host-based routing**
- **Request/response transformation** — backward compatibility
- **Authentication & authorization** at the edge
- **Backend for Frontend (BFF)** — customized backends per client
- **Why BFF over plain gateway** — flexibility & client-specific APIs
- **BFF as anti-corruption layer** — shielding from legacy
- **Using gateway + BFF together** — layered architecture
- **Challenges & best practices** — bloated BFFs, security, versioning

---

## 1. Why API Gateways?

### The Problem Without a Gateway

```
                          ┌──────────────┐
                ┌────────►│ User Service │
                │         └──────────────┘
                │
                │         ┌──────────────┐
   ┌────────┐  │         │Order Service │
   │ Mobile │──┼────────►│              │
   │ Client │  │         └──────────────┘
   └────────┘  │
                │         ┌──────────────┐
                ├────────►│ Payment Svc  │
                │         └──────────────┘
                │
                │         ┌──────────────┐
                └────────►│ Catalog Svc  │
                          └──────────────┘
   
   Client needs to know:
   ✗ Every service URL
   ✗ Different auth for each
   ✗ Different protocols
   ✗ Internal structure
```

### With a Gateway

```
   ┌────────┐                ┌──────────────┐
   │ Mobile │                │User Service  │
   │ Client │                └──────────────┘
   └────┬───┘     ┌─────┐   ┌──────────────┐
        │         │ API │   │Order Service │
   ┌────┴───┐  ──►│ G/W │──►└──────────────┘
   │  Web   │     │     │   ┌──────────────┐
   │ Client │     └─────┘   │Payment Svc   │
   └────┬───┘                └──────────────┘
        │                    ┌──────────────┐
   ┌────┴───┐                │Catalog Svc   │
   │ B2B    │                └──────────────┘
   │Partner │
   └────────┘
   
   Clients see ONE endpoint.
   Gateway handles the rest.
```

### Benefits

```
✓ Single entry point for all clients
✓ Reduces client complexity
✓ Handles cross-cutting concerns once:
   • Authentication / Authorization
   • Rate limiting
   • Logging / Monitoring
   • Caching
   • SSL termination
✓ Backend services can evolve without breaking clients
✓ Hides internal structure (security + flexibility)
```

### Popular Gateways

```
┌──────────────────────────────────────────────────────────────┐
│  GATEWAY              │  WHO USES IT                         │
├───────────────────────┼──────────────────────────────────────┤
│  Kong                 │  Most popular open-source            │
│  AWS API Gateway      │  Native to AWS                       │
│  Apigee (Google)      │  Enterprise focus                    │
│  Tyk                  │  Open-source, self-hosted            │
│  Traefik              │  Cloud-native, K8s-friendly          │
│  NGINX                │  Lightweight, flexible               │
│  Envoy                │  Modern, used in service meshes      │
│  Express Gateway      │  Node.js-based                       │
└───────────────────────┴──────────────────────────────────────┘
```

---

## 2. Core Responsibilities of API Gateway

### Responsibility 1: Routing

```
Clients hit ONE endpoint, gateway routes to RIGHT service.

GET api.example.com/users/123    →   User Service
POST api.example.com/orders      →   Order Service
GET api.example.com/products     →   Catalog Service
POST api.example.com/payments    →   Payment Service
```

### Path-Based Routing

```
api.example.com/users/*    →  User Service (port 8001)
api.example.com/orders/*   →  Order Service (port 8002)
api.example.com/products/* →  Catalog Service (port 8003)
```

### Host-Based Routing

```
api.mobile.example.com    →  Mobile-optimized services
api.web.example.com       →  Web-optimized services
api.partner.example.com   →  Partner API endpoints
```

### Method-Based Routing

```
GET /products/*    →  Read replica (read-only)
POST /products/*   →  Primary DB (write)
DELETE /products/* →  Admin service (extra auth)
```

### Header-Based Routing

```
Accept: application/json+v2 → New API
Accept: application/json+v1 → Legacy API

X-Mobile-Version: ios-2.0   → New mobile backend
X-Mobile-Version: ios-1.0   → Legacy backend
```

### Visual

```
                       API GATEWAY
                          │
                          │ Examines request
                          │
       ┌──────────────────┼──────────────────────┐
       │                  │                       │
       │  Path:           │  Headers:             │  Host:
       │  /orders/* →     │  Accept: v2 →         │  api.mobile →
       │  Order Svc       │  New service          │  Mobile BFF
       │                  │                       │
       ▼                  ▼                       ▼
  Order Service     New API Service        Mobile Backend
```

---

## 3. Request & Response Transformation

### Why Transform?

```
Different parts of system have different conventions.
Gateway acts as TRANSLATOR.
```

### Use Case 1: Convention Translation

```
Frontend expects camelCase:
{
  "firstName": "Ashish",
  "lastName": "Chaurasiya"
}

Backend uses snake_case:
{
  "first_name": "Ashish",
  "last_name": "Chaurasiya"
}

Gateway translates between them.
```

### Use Case 2: Backward Compatibility

```
Backend changed API:
   /users/{id} → /v2/users/profile/{id}

But old clients still use:
   /users/{id}

Gateway:
   - Receives: /users/123
   - Translates to: /v2/users/profile/123
   - Returns response in old format

→ Old clients keep working
→ Backend can evolve
```

### Use Case 3: Field Mapping

```
Old backend response:
{
    "user_id": 123,
    "user_name": "Ashish",
    "user_email": "ashish@example.com"
}

Gateway maps to modern shape:
{
    "id": 123,
    "name": "Ashish",
    "email": "ashish@example.com"
}
```

### Use Case 4: Aggregation

```
Client calls: GET /dashboard

Gateway aggregates:
   ├─ Call User Service     (/users/123)
   ├─ Call Order Service    (/orders?user=123)
   ├─ Call Notification Svc (/notifs?user=123)
   └─ Combine into single response
```

### Visual

```
   Client Request                    Backend Reality
   ───────────                       ───────────────
   
   GET /me                ┌─────┐    
        ↓                 │     │    GET /v2/users/profile/123
   {camelCase keys}  ────►│ G/W │───►{snake_case keys}
                          │     │    
   {old format}      ◄────│     │◄───{new format}
                          └─────┘    
```

---

## 4. Authentication & Authorization at the Gateway

### Centralized Security

```
Without gateway:
   Each service must:
   ✗ Validate tokens independently
   ✗ Maintain auth logic
   ✗ Update when auth changes
   
   = Duplicated logic + security gaps

With gateway:
   ✓ Auth validated ONCE at gateway
   ✓ Services trust gateway's verification
   ✓ Update auth in one place
   ✓ Unauthorized requests rejected EARLY
```

### Auth Flow

```
   ┌────────┐                   ┌─────────┐                 ┌─────────┐
   │ Client │                   │ Gateway │                 │ Service │
   └────┬───┘                   └────┬────┘                 └────┬────┘
        │                             │                            │
        │ Request + Bearer Token     │                            │
        ├────────────────────────────►│                            │
        │                             │                            │
        │                             │ 1. Validate JWT/token     │
        │                             │ 2. Check expiry           │
        │                             │ 3. Check permissions      │
        │                             │                            │
        │                             │ Valid? Forward + X-User-Id│
        │                             ├────────────────────────────►
        │                             │                            │
        │                             │ ◄──── Response ────────────┤
        │  ◄────── Response ──────────┤                            │
        │                             │                            │
```

### What Gateway Validates

```
✓ Token format (JWT, OAuth, API Key)
✓ Token signature (not tampered)
✓ Token expiry
✓ User permissions (scopes/roles)
✓ Rate limits per user/IP
✓ IP allow/block lists
✓ Request method permissions
```

### Common Auth Strategies

```
1. JWT (JSON Web Token)
   ✓ Self-contained
   ✓ No DB lookup
   ✓ Used by most modern APIs
   
2. OAuth 2.0
   ✓ Industry standard
   ✓ Delegated auth
   ✓ Refresh tokens
   
3. API Keys
   ✓ Simple
   ✓ For server-to-server
   ✓ Long-lived
   
4. mTLS (Mutual TLS)
   ✓ Both sides authenticate
   ✓ For high-security B2B
```

---

## 5. Other Gateway Capabilities

### Rate Limiting

```
Per-IP:      10 req/sec
Per-User:    100 req/min
Per-API key: 1000 req/hour

Beyond limit → 429 Too Many Requests
```

### Caching

```
GET /products/123
   ├─ Check cache (Redis)
   │   ├─ HIT  → Return cached response (fast!)
   │   └─ MISS → Call backend, cache result
   └─ Cache TTL: 5 minutes

Saves backend load for read-heavy endpoints.
```

### Logging & Monitoring

```
Every request logged centrally:
{
    "timestamp": "...",
    "method": "GET",
    "path": "/users/123",
    "status": 200,
    "latency_ms": 45,
    "user_id": "u-123",
    "client_ip": "1.2.3.4",
    "user_agent": "Mozilla/...",
    "trace_id": "abc-123"
}

→ Metrics, alerts, debugging
```

### Circuit Breaking

```
If backend is failing:
   Gateway opens circuit
   → Returns 503 immediately
   → Doesn't hammer failing service
   → Recovers after cooldown
```

### Request Validation

```
Validate request BEFORE forwarding:
   ✓ Required fields present
   ✓ Field types correct
   ✓ Field constraints (length, range)
   ✓ JSON schema validation

Invalid → 400 Bad Request at gateway
Backend never sees malformed data
```

---

## 6. Backend for Frontend (BFF)

### The Problem Gateway Doesn't Solve

```
Gateway is uniform — same response shape for everyone.

But:
   📱 Mobile needs LITTLE data (bandwidth)
   💻 Web needs RICH data (more details)
   📺 TV needs DIFFERENT data (different UI)
   🤝 B2B needs SPECIALIZED data (their format)

One-size-fits-all doesn't work.
```

### What Is a BFF?

**A Backend for Frontend is a customized backend layer that sits between a specific client and the core services, tailoring the API for that client's needs.**

### Visual

```
   ┌────────┐      ┌────────┐      ┌──────────┐
   │ Mobile │  ──► │ Mobile │  ──► │ Core     │
   │ Client │      │ BFF    │      │ Services │
   └────────┘      └────────┘      └──────────┘
                                          ▲
   ┌────────┐      ┌────────┐             │
   │  Web   │  ──► │  Web   │  ──────────┘
   │ Client │      │ BFF    │
   └────────┘      └────────┘
                                          ▲
   ┌────────┐      ┌────────┐             │
   │  TV    │  ──► │  TV    │  ──────────┘
   │ Client │      │ BFF    │
   └────────┘      └────────┘
```

### Netflix BFF Example

```
🎬 Same content, different BFFs:

Mobile BFF:
   {
       "title": "Stranger Things",
       "thumbnail": "small.jpg",  ← compressed for mobile
       "duration": "55:00"
   }

Web BFF:
   {
       "title": "Stranger Things",
       "thumbnail": "hd.jpg",
       "duration": "55:00",
       "description": "...long description...",
       "cast": [...],
       "reviews": [...],
       "related": [...]
   }

TV BFF:
   {
       "title": "Stranger Things",
       "thumbnail": "4k.jpg",      ← 4K thumbnail
       "playback_url": "...",
       "next_episode": {...}        ← TV-specific
   }
```

---

## 7. Why BFF Over Plain Gateway?

### Reason 1: Tailored Responses

```
Without BFF:
   Gateway returns one big response
   Mobile parses what it needs (waste bandwidth + battery)
   Web parses what it needs

With BFF:
   Mobile BFF: 200 bytes (just essentials)
   Web BFF:    5 KB (everything needed)
   
   → No extra processing on client
   → Faster on mobile
   → Cleaner code
```

### Reason 2: Client-Specific Orchestration

```
Web dashboard needs: profile + orders + recommendations + notifications

Without BFF: Web makes 4 API calls (slow!)
With BFF:    Web makes 1 call to BFF (BFF orchestrates 4)
```

### Reason 3: Frontend Team Ownership

```
Frontend team owns BFF:
   ✓ Don't wait for backend team
   ✓ Iterate quickly on UI needs
   ✓ Add new fields easily
   ✓ Optimize for specific UX

Backend team focuses on:
   ✓ Core business services
   ✓ Stable contracts
   ✓ Performance
```

### Reason 4: Different Protocols per Client

```
Mobile BFF:  GraphQL (flexible queries)
Web BFF:     REST (simple)
TV BFF:      WebSockets (real-time)
Partner BFF: SOAP (B2B legacy)
```

---

## 8. BFF Pattern in Action

### Use Case: Dashboard Aggregation

```
Mobile app dashboard needs:
   1. User profile
   2. Recent transactions (5)
   3. Loyalty score
   4. Active offers

Without BFF (mobile makes 4 calls):
   ┌────────┐
   │ Mobile │
   └───┬────┘
       ├──► User Service       (200ms)
       ├──► Transaction Svc    (300ms)
       ├──► Loyalty Service    (150ms)
       └──► Offers Service     (250ms)
       
   Sequential: 900ms total
   Parallel:   300ms total
   
   But still 4 round-trips on slow network!

With BFF (single call):
   ┌────────┐                ┌────────────┐
   │ Mobile │ ─────────────► │ Mobile BFF │
   └────────┘                └──────┬─────┘
                                    │
                                    ├──► User Service     ┐
                                    ├──► Transaction Svc  │  PARALLEL
                                    ├──► Loyalty Service  │
                                    └──► Offers Service   ┘
                                    
                                    Combine into one response
   ◄──────────────────────────────  Return aggregated response

   Mobile sees: ONE call, ~300ms
   Even on slow networks, just one round-trip
```

---

## 9. BFF as Anti-Corruption Layer

### The Legacy Problem

```
Modern frontend talks to:
   ✓ Modern microservices (clean APIs)
   ✗ Legacy system (mainframe, inconsistent fields)

If frontend talks to legacy directly:
   - Frontend code becomes ugly
   - Hard to upgrade legacy later
   - UI changes when legacy changes
```

### BFF as Translator

```
   ┌──────────┐      ┌──────────┐      ┌──────────────┐
   │ Modern   │  ──► │   BFF    │  ──► │   Legacy     │
   │ Frontend │      │ (Adapter)│      │   System     │
   └──────────┘      └──────────┘      └──────────────┘
   
   {clean modern format}  {ugly legacy format}
```

### Example: Legacy CRM

```
Legacy CRM response:
{
    "CUST_ID": "0000000123",
    "CUST_NM_FRST": "ASHISH",
    "CUST_NM_LST": "CHAURASIYA",
    "CUST_EMAIL_ADDR": "ashish@example.com",
    "CUST_STAT_CD": "A"   // A=Active, I=Inactive
}

BFF translates to modern shape:
{
    "id": "123",
    "firstName": "Ashish",
    "lastName": "Chaurasiya",
    "email": "ashish@example.com",
    "isActive": true
}

Frontend remains clean.
Legacy can be modernized later — frontend doesn't change.
```

---

## 10. When to Use What

### Use API Gateway When:

```
✓ You need a single entry point for ALL clients
✓ Cross-cutting concerns (auth, rate limit, logging)
✓ Standardizing access to backend
✓ DevOps owns shared infrastructure
✓ Multiple internal services share common patterns
```

### Use BFF When:

```
✓ Different clients have DIFFERENT needs
✓ Need to aggregate/orchestrate per client
✓ Want frontend teams to own backend logic
✓ Need anti-corruption layer over legacy
✓ Each client uses different protocols
```

### Use BOTH When:

```
✓ Want centralized cross-cutting concerns
✓ AND client-specific customization
✓ Need defense in depth (multiple security layers)
✓ Large system with many client types
```

---

## 11. Combining Gateway + BFF (Layered Approach)

### Architecture

```
                       ┌──────────────────┐
                       │  Public Internet │
                       └──────────┬───────┘
                                  │
                       ┌──────────▼───────┐
                       │   API Gateway    │
                       │   (Kong/AWS)     │
                       │                  │
                       │  • Auth          │
                       │  • Rate limit    │
                       │  • SSL term      │
                       │  • Routing       │
                       │  • Logging       │
                       └────┬─────────┬───┘
                            │         │
                ┌───────────┘         └───────────┐
                ▼                                  ▼
       ┌────────────────┐                ┌────────────────┐
       │  Mobile BFF    │                │   Web BFF      │
       │                │                │                │
       │ • Aggregate    │                │ • Aggregate    │
       │ • Format       │                │ • Format       │
       │ • Optimize     │                │ • Optimize     │
       └───┬────────────┘                └────────┬───────┘
           │                                       │
           └─────────────┬─────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Core Services      │
              │  ─────────────────  │
              │  • User Service     │
              │  • Order Service    │
              │  • Payment Service  │
              │  • etc...           │
              └─────────────────────┘
```

### Layer Responsibilities

```
LAYER 1: API Gateway (Edge)
   ✓ Authentication
   ✓ SSL/TLS termination
   ✓ Rate limiting
   ✓ Request validation
   ✓ Logging & monitoring
   ✓ Routing to right BFF

LAYER 2: BFF (Client-specific)
   ✓ Aggregation
   ✓ Format transformation
   ✓ Client-optimized responses
   ✓ Orchestration
   ✓ Anti-corruption

LAYER 3: Core Services (Business logic)
   ✓ Domain logic
   ✓ Data ownership
   ✓ Service contracts
```

### Real Example: Netflix

```
1. Client → Edge servers (CDN + gateway)
2. Edge → Authentication, routing
3. Edge → Appropriate BFF based on client:
   • Mobile BFF
   • Web BFF
   • Smart TV BFF
   • Game Console BFF
4. BFF aggregates from 700+ microservices
5. BFF returns optimized response
```

---

## 12. Challenges & Best Practices

### Challenge 1: Bloated BFF

```
🚨 Anti-pattern: BFF becomes a mini-monolith

   - Business logic creeps in
   - Validation duplicated
   - Hard to test
   - Becomes a single point of failure

✅ Best practice:
   - Keep BFF FOCUSED on presentation logic
   - No business rules in BFF
   - BFF = orchestration + transformation ONLY
   - Business logic stays in core services
```

### Challenge 2: BFF Multiplication

```
🚨 Anti-pattern: 50 BFFs for 50 clients

   - Maintenance nightmare
   - Code duplication
   - Each BFF needs DevOps

✅ Best practice:
   - Group similar clients (mobile-ios + mobile-android = mobile BFF)
   - Use templates for common patterns
   - Share libraries across BFFs
```

### Challenge 3: Versioning

```
BFF is close to UI → frequent changes

Challenges:
   - Old mobile apps need old BFF
   - New mobile apps need new BFF

✅ Best practice:
   - Version BFFs (/v1, /v2)
   - Support N+1 versions
   - Deprecation policy with timeline
   - Mobile apps especially need long support
```

### Challenge 4: Internal Communication Security

```
Gateway ←→ BFF ←→ Core Services
   These should also be secured!

✅ Best practice:
   - Use mTLS between services
   - OR use service mesh (Istio, Linkerd)
   - Network policies (only allowed services)
   - Service identity (SPIFFE/SPIRE)
```

### Challenge 5: Gateway as Bottleneck

```
🚨 If gateway goes down → entire system unreachable!

✅ Best practice:
   - Run gateway in HA (high availability)
   - Multiple instances + load balancer
   - Auto-scaling
   - Health checks
   - Fallback strategies
```

### Challenge 6: Gateway Doing Too Much

```
🚨 Anti-pattern: Gateway = ESB
   - Business logic
   - Workflows
   - Data transformations beyond shape
   - Stateful operations

✅ Best practice:
   - Gateway = edge concerns ONLY
   - Stateless
   - Fast pass-through
   - Heavy logic → services or BFFs
```

---

## 13. Real-World Decisions

### Startup (< 10 services)

```
✓ Simple API Gateway (or just LB)
✗ No BFFs needed yet
✓ Focus on shipping
```

### Mid-size (10-50 services)

```
✓ API Gateway with proper config
✓ Maybe 1-2 BFFs for major clients
✓ Service mesh for internal traffic
```

### Large-scale (50+ services, multiple clients)

```
✓ Full API Gateway with all features
✓ Multiple BFFs (mobile, web, partner, admin)
✓ Service mesh
✓ Edge computing for global users
```

---

## 14. Anti-Patterns to Avoid

### Anti-Pattern 1: Gateway as Business Logic Container

```
❌ "Let's add billing logic to the gateway since it sees all requests"

→ Gateway becomes coupling point
→ Hard to test
→ Cross-cutting concerns mixed with business logic

✅ Keep business logic in services
```

### Anti-Pattern 2: BFF Duplicating Core Services

```
❌ BFF reimplements user service logic

→ Two places to update
→ Inconsistencies arise
→ Defeats purpose of microservices

✅ BFF calls services, doesn't duplicate them
```

### Anti-Pattern 3: Direct Service Access Bypassing Gateway

```
❌ Mobile app calls services directly when gateway is slow

→ Security holes
→ Inconsistent auth
→ Defeats purpose of gateway

✅ Fix the gateway, don't bypass it
```

### Anti-Pattern 4: No BFF, Mobile Talking to Many Services

```
❌ Mobile app calls 10 services for one screen

→ Slow on mobile networks
→ Battery drain
→ Complex error handling on client

✅ Add a BFF for aggregation
```

---

## 15. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ API Gateway = single entry point + cross-cutting concerns │
│  ✅ Centralizes: auth, rate limit, logging, routing           │
│  ✅ Backend services evolve without breaking clients          │
│  ✅ BFF = client-specific backend layer                       │
│  ✅ BFF tailors APIs for mobile, web, TV, B2B etc.            │
│  ✅ BFF enables frontend team autonomy                        │
│  ✅ BFF can serve as anti-corruption layer over legacy        │
│  ✅ Use BOTH for best results in large systems                │
│  ✅ Avoid bloated BFFs (no business logic!)                   │
│  ✅ Gateway should never become an ESB                        │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Gateway handles EDGE concerns (auth, rate limit, routing)
2. BFF handles CLIENT-SPECIFIC concerns (aggregation, formatting)
3. Services handle BUSINESS LOGIC
4. Don't mix layer responsibilities
5. Match architecture to client diversity
6. Gateway is not a substitute for good service design
7. Secure ALL internal communication (mTLS or service mesh)
8. Keep BFFs focused — presentation, not business logic
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll explore **Messaging and Event Brokers** — how services communicate asynchronously through events, with Kafka, RabbitMQ, and pub/sub patterns.

> **Practical file:** [02_Practical_Hands_On.md](02_Practical_Hands_On.md)

---

## 📚 References

- Sam Newman — *Building Microservices*
- Pattern: Backend for Frontend (samnewman.io/patterns/architectural/bff/)
- Kong documentation (konghq.com)
- AWS API Gateway docs
- Netflix Tech Blog on BFFs
- Phil Calçado — *Building Adaptive Microservices*
