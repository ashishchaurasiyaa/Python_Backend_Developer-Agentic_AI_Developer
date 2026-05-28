# REST API | SOA | Microservices | Tier Architecture

## Quick Reference Card
```
1-Tier  → App + DB ek hi machine (desktop app)
2-Tier  → Client + Server (traditional web app)
3-Tier  → Presentation + Logic + Data (standard web architecture)
N-Tier  → Multiple layers (enterprise)
REST    → Stateless HTTP, resources, uniform interface
SOA     → Services + ESB, heavy XML/SOAP (enterprise)
Micro   → REST/gRPC, lightweight, DB per service
Interview hook → "Niroskos is 3-tier: React frontend + Django DRF backend + PostgreSQL"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Tier Architecture — Kya hota hai?

**"Tier" = physical/logical layer of separation**

Socho ek restaurant:
- **1-Tier**: Chef khud hi order leta hai, banata hai, serve karta hai (sab ek banda)
- **2-Tier**: Waiter (client) + Kitchen (server)
- **3-Tier**: Customer (browser) + Waiter/Manager (application logic) + Kitchen (database)
- **N-Tier**: Customer + Receptionist + Manager + Chef + Sous-chef + Storage room

---

### 1.2 Tier-by-Tier Explanation

#### 1-Tier Architecture
```
┌─────────────────────────────┐
│   UI + Logic + Database     │
│   (same machine/process)    │
└─────────────────────────────┘
  Example: MS Access app, Desktop calculator
  Problem: Scale karna impossible, no separation of concerns
```

#### 2-Tier Architecture
```
┌──────────────┐         ┌──────────────┐
│    Client    │ ──────> │   Server +   │
│  (Browser/   │         │   Database   │
│    App)      │ <────── │              │
└──────────────┘         └──────────────┘
  Example: Old school desktop app hitting DB directly
  Problem: Business logic client mein ya DB mein? Messy.
```

#### 3-Tier Architecture (Most Common)
```
┌──────────┐    ┌────────────────┐    ┌──────────┐
│Presentation│  │  Application   │    │   Data   │
│  Layer   │   │    Layer       │    │  Layer   │
│(React/   │──>│(Django/DRF/    │──> │(PostgreSQL│
│ Angular) │   │ FastAPI)       │    │ Redis)   │
│          │<──│                │<── │          │
└──────────┘   └────────────────┘    └──────────┘
  Example: Niroskos — React + Django DRF + PostgreSQL
  Benefit: Each layer independently scalable and replaceable
```

#### N-Tier (Enterprise)
```
Client → CDN → Load Balancer → API Gateway → 
Service Layer → Cache Layer → DB → Archive Storage

Example: Large e-commerce (Amazon, Flipkart)
```

---

### 1.3 REST API — Kya hota hai?

**REST = Representational State Transfer**

Analogy: **Library catalog system**
- Har book ka unique address (URL) hota hai
- Tum ek specific operation karte ho (GET, POST, PUT, DELETE)
- Library apni internal database state nahi share karti tumhare saath
- Har request self-contained hoti hai (stateless)

**6 REST Principles:**
```
1. Stateless      → Server client ki state nahi rakhta
                    Har request mein authentication info saath
                    
2. Client-Server  → UI aur backend separately evolve kar sakte hain

3. Cacheable      → Response mein Cache-Control headers

4. Uniform Interface → Standard methods: GET/POST/PUT/PATCH/DELETE
                       Resources as URLs: /bookings/{id}

5. Layered System → Client ko nahi pata proxy/load balancer beech mein hai

6. Code on Demand → (Optional) Server client ko executable code bhej sakta hai
```

**REST URL Design Examples:**
```
GET    /bookings              → List all bookings
POST   /bookings              → Create new booking
GET    /bookings/{id}         → Get specific booking
PUT    /bookings/{id}         → Full update
PATCH  /bookings/{id}         → Partial update
DELETE /bookings/{id}         → Delete booking

GET    /bookings/{id}/payments → Nested resource
POST   /bookings/{id}/cancel   → Action (not pure REST but practical)
```

**Niroskos mein REST:**
```python
# Django DRF ViewSet — clean REST
class BookingViewSet(ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Tenant isolation — har request mein tenant context
        return Booking.objects.filter(subsidiary=self.request.user.subsidiary)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        booking.transition_to(BookingStatus.CONFIRMED)
        return Response({'status': 'confirmed'})
```

---

### 1.4 SOA vs Microservices

**SOA (Service Oriented Architecture)**
```
Enterprise Service Bus (ESB) — central hub
         │
    ┌────┴────┐
    │   ESB   │ ← Heavy, complex, XML/SOAP based
    └────┬────┘
    ┌────┼────┐
    │    │    │
  CRM  HR   Finance
         Services
```

**Microservices**
```
No central bus — services talk directly

  User ──REST──> Order ──gRPC──> Inventory
         │                            │
         └──────Event Queue───────────┘
                (Kafka/RabbitMQ)
```

| Dimension | SOA | Microservices |
|-----------|-----|---------------|
| Communication | Central ESB | Direct REST/gRPC/Events |
| Protocol | SOAP/XML (heavy) | REST/gRPC/JSON (light) |
| Granularity | Larger services | Fine-grained services |
| DB sharing | Often shared | DB per service |
| Governance | Centralized | Decentralized |
| Use case | Enterprise integration | Cloud-native apps |

---

### 1.5 Ashish ke projects mein

**Youngman Beta:**
- 3-tier: Browser (Tailwind CSS) + Django DRF + PostgreSQL
- Async layer: Celery workers (4th logical tier)

**Niroskos:**
- N-tier: Client → AWS CloudFront (CDN) → Nginx → Django DRF → Redis + PostgreSQL + S3
- REST APIs: DRF ViewSets + `django-hosts` for subdomain routing per tenant

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **REST (Representational State Transfer)**: An architectural style for distributed hypermedia systems, defined by 6 constraints — stateless, client-server, cacheable, uniform interface, layered, and optionally code-on-demand. Resources are identified by URIs and manipulated using standard HTTP methods.

> **SOA (Service-Oriented Architecture)**: An architectural pattern where application components provide services to other components via a communication protocol over a network, typically mediated by an Enterprise Service Bus (ESB).

> **N-Tier Architecture**: A client-server architecture where the presentation, application logic, and data layers are separated into distinct physical or logical tiers, each independently scalable and replaceable.

---

### 2.2 HTTP Methods and Idempotency

| Method | Operation | Idempotent? | Safe? | Status Codes |
|--------|-----------|-------------|-------|--------------|
| GET | Read | Yes | Yes | 200, 404 |
| POST | Create | No | No | 201, 400, 409 |
| PUT | Full replace | Yes | No | 200, 204 |
| PATCH | Partial update | No (usually) | No | 200, 204 |
| DELETE | Delete | Yes | No | 204, 404 |

**Idempotent**: Same request multiple times = same result (safe to retry)
**Safe**: No side effects on server state

---

### 2.3 REST vs GraphQL vs gRPC

| Dimension | REST | GraphQL | gRPC |
|-----------|------|---------|------|
| Protocol | HTTP/1.1 | HTTP/1.1 | HTTP/2 |
| Data format | JSON/XML | JSON | Protocol Buffers (binary) |
| Over-fetching | Common | Eliminated | N/A |
| Under-fetching | Multiple calls needed | Single query | N/A |
| Type safety | Manual | Schema-based | Strict protobuf |
| Streaming | Limited | Subscriptions | Native streaming |
| Best for | Public APIs | Mobile/flexible clients | Internal microservices |
| Learning curve | Low | Medium | High |

---

### 2.4 3-Tier Architecture — Benefits

```
Presentation Layer (UI):
  - Scalable independently (CDN, multiple replicas)
  - Can be replaced (React → Vue) without touching backend
  
Application Layer (Business Logic):
  - Horizontally scalable behind load balancer
  - Stateless — any instance handles any request
  - Where all business rules live

Data Layer (DB):
  - Optimized for storage/retrieval
  - Read replicas for scaling reads
  - Separate from business logic → DB can change (MySQL → PostgreSQL)
```

---

### 2.5 Real Project Answer

> "Niroskos is a classic N-tier architecture. Requests come in through AWS CloudFront CDN → Nginx reverse proxy → Django DRF application layer → PostgreSQL + Redis data layer. We use subdomain-based multi-tenancy with django-hosts, so each tenant gets their own subdomain routing to the same application tier but isolated at the data layer. REST APIs follow resource-based URL design with DRF ViewSets, and we use JWT for stateless authentication — consistent with REST's statelessness constraint."

---

### 2.6 Common Follow-up Q&A

**Q1: What's the difference between REST and HTTP?**
> "HTTP is the protocol — the transport mechanism with methods, headers, status codes. REST is an architectural style that uses HTTP as its transport. REST adds constraints: statelessness, uniform interface, resource identification via URI. You can build non-RESTful APIs over HTTP (e.g., RPC-style with POST for everything)."

**Q2: What does stateless mean in REST, and what are the trade-offs?**
> "Stateless means the server holds no client session state between requests. Each request must contain all information needed to process it (auth token, filters). Trade-off: client must send auth header every request (slight overhead), but benefit is any server instance can handle any request — horizontally scalable without sticky sessions."

**Q3: What is HATEOAS?**
> "Hypermedia As The Engine Of Application State — the most complete REST constraint. The API response includes links to possible next actions. Example: GET /booking/123 response includes {status: 'confirmed', links: [{rel: 'cancel', href: '/booking/123/cancel', method: 'POST'}]}. Benefit: client doesn't hardcode URLs. Rarely fully implemented in practice."

**Q4: When would you choose gRPC over REST?**
> "For internal microservice-to-microservice communication where performance matters. gRPC uses HTTP/2 (multiplexing, header compression) and Protocol Buffers (binary, smaller payload, faster serialization). Especially useful for high-frequency calls or streaming. REST is better for public APIs where human readability and broad client compatibility matter."

---

## Interview Cheat Sheet

```
Tier Architecture:
- 1-Tier: everything same machine
- 2-Tier: client + server
- 3-Tier: presentation + logic + data (most common)
- N-Tier: + CDN, cache, queue layers

REST constraints (6):
1. Stateless  2. Client-Server  3. Cacheable
4. Uniform Interface  5. Layered  6. Code on Demand (optional)

HTTP Methods:
GET=read(safe,idempotent), POST=create, PUT=replace(idempotent),
PATCH=partial update, DELETE=delete(idempotent)

SOA vs Microservices:
SOA = central ESB, SOAP/XML, enterprise
Micro = direct REST/gRPC/events, lightweight, cloud-native

My project:
Niroskos: N-tier (CDN → Nginx → Django DRF → PostgreSQL/Redis)
REST APIs with DRF ViewSets, JWT auth, tenant isolation
```
