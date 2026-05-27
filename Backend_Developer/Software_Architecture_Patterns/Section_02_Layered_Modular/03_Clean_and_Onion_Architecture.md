# Lecture 3: Clean & Onion Architecture

> *"Keep your domain independent — always."*

**Section 2 — Layered & Modular Architecture Patterns**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Domain-centric architecture** kyun important hai
- **Clean Architecture** — Uncle Bob ka famous pattern
- Clean architecture ke **4 layers** (Entities, Use Cases, Adapters, Frameworks)
- **Onion Architecture** — Jeffrey Palermo ka domain-driven approach
- Onion ke **5 layers** (Domain Model, Domain Services, App Services, Infrastructure)
- **Dependency Inversion** — kaise both architectures ka heart hai
- Clean vs Onion — **similarities aur key differences**
- **Kab kaunsa use** karein
- **Common mistakes** avoid karne ke liye

---

## 1. Why Domain-Centric Architecture?

### The Big Shift in Thinking

> Your system's **business logic** — the rules, decisions, workflows that make your product valuable — should NOT depend on:
> - Frameworks
> - Databases
> - User interfaces
> - External services

### The Key Idea

```
🎯 Keep DOMAIN at the CENTER

Benefits:
✅ Business rules stay independent
✅ Protected from technology changes
✅ Isolated for easy unit testing
✅ Easier to evolve over time
```

### Domain-Centric vs Infrastructure-Centric

```
INFRASTRUCTURE-CENTRIC (BAD):              DOMAIN-CENTRIC (GOOD):
─────────────────                          ──────────────────
                                            
Database choices drive design               Business model drives design
Framework conventions = code                Domain logic = pure
                                            
"Spring's @Entity says..."                  "The Order has a Customer..."
"SQLAlchemy needs this..."                  "Pricing rule says..."
                                            
Hard to test                                Easy to test
Tied to tech stack                          Framework-agnostic
```

### Visual: The Onion Approach

```
                    ┌──────────────────────────────┐
                    │     Presentation Layer        │
                    │   ┌────────────────────┐     │
                    │   │   Application       │     │
                    │   │   ┌──────────────┐  │     │
                    │   │   │              │  │     │
                    │   │   │   Domain     │  │     │ ← center
                    │   │   │              │  │     │
                    │   │   └──────────────┘  │     │
                    │   └────────────────────┘     │
                    │       Persistence              │ Infrastructure
                    └──────────────────────────────┘
                                  ↓
                              ┌──────┐
                              │  DB  │
                              └──────┘
```

### Common Foundation

Whether you choose **Clean** or **Onion**, the principle is same:

> **Treat your domain as the center of gravity.**

---

## 2. Deep Dive into Clean Architecture

### The Origin

- **Invented by Robert C. Martin (Uncle Bob)**
- Author of "Clean Code", "Clean Architecture"
- Famous for deep obsession with separation of concerns

### The Concentric Circles Model

```
       ┌──────────────────────────────────┐
      │  Frameworks & Drivers (Outer)       │
      │  ┌────────────────────────────────┐│
      │  │  Interface Adapters             ││
      │  │  ┌──────────────────────────┐  ││
      │  │  │  Use Cases (Application)  │  ││
      │  │  │  ┌──────────────────────┐ │  ││
      │  │  │  │   Entities (Core)     │ │  ││
      │  │  │  └──────────────────────┘ │  ││
      │  │  └──────────────────────────┘  ││
      │  └────────────────────────────────┘│
      └────────────────────────────────────┘
                       ↑
              All dependencies point inward
```

### The Dependency Rule

> **Dependencies always point INWARD.**

- Outer layers can depend on inner layers
- Inner layers know **nothing** about outer layers

### Why It Works

```
✅ Inner core is COMPLETELY ISOLATED
✅ Outer layers (UI, DB, web) can change without touching core
✅ Could swap React for Vue, PostgreSQL for MongoDB
✅ Domain logic would not notice
```

### The Golden Rule

> **The inner circles should NOT know anything about the outer circles.**
> Only outer layers can depend on the inner ones, **never** the other way round.

---

## 3. Layers of Clean Architecture

Clean architecture has **4 main layers** — innermost to outermost:

### Layer 1: 🟡 Entities (Innermost)

```
🟡 Entities Layer
   "Enterprise-wide Business Rules"
   
   What lives here:
   - Pure business objects (Order, Customer, Invoice)
   - Core business rules (don't change frequently)
   - Pure logic, NO dependencies
   
   What's NOT here:
   - Database annotations
   - Framework imports
   - Library dependencies
```

**Example:**

```python
# Entity — pure Python, no dependencies
@dataclass
class Order:
    id: UUID
    customer_id: int
    items: List[OrderItem]
    total: Decimal
    
    def can_be_cancelled(self) -> bool:
        return self.status == OrderStatus.PENDING
```

### Layer 2: 🔴 Use Cases (Application Business Rules)

```
🔴 Use Cases Layer
   "Application Business Rules"
   
   What lives here:
   - Specific application workflows
   - PlaceOrder, RegisterUser, GenerateInvoice
   - Orchestrate entities
   - Define input/output models
   - Enforce business logic
```

**Example:**

```python
# Use case — orchestrates entities
class PlaceOrder:
    def __init__(self, order_repo: IOrderRepository, payment: IPaymentService):
        self.order_repo = order_repo
        self.payment = payment
    
    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        # Validate, charge, save — application workflow
        ...
```

### Layer 3: 🟢 Interface Adapters

```
🟢 Interface Adapters Layer
   
   What lives here:
   - Controllers (translate HTTP → use case)
   - Presenters (format data for UI)
   - Gateways (interfaces TO external systems)
   - Implements interfaces defined in use cases
```

**Example:**

```python
# Controller — adapter for HTTP
class OrderController:
    def __init__(self, place_order: PlaceOrder):
        self.place_order = place_order
    
    def post_order(self, http_request: HttpRequest) -> HttpResponse:
        # Translate HTTP → use case input
        request = PlaceOrderRequest(...)
        response = self.place_order.execute(request)
        return HttpResponse(json=response.to_dict())
```

### Layer 4: 🔵 Frameworks & Drivers (Outermost / Infrastructure)

```
🔵 Frameworks & Drivers Layer
   "The Outermost Ring"
   
   What lives here:
   - Web frameworks (ASP.NET, FastAPI, Django)
   - Database tools (SQLAlchemy, Entity Framework)
   - External APIs (Stripe, Twilio)
   - Message queues (Kafka)
   - UI frameworks
```

### Crucial Rule: Inward Dependencies

```
INFRASTRUCTURE  →  ADAPTERS  →  USE CASES  →  ENTITIES
   (outer)                                       (inner)
              All arrows point INWARD only
```

The infrastructure layer:
- **Depends on** Interface Adapters (which it implements)
- Adapters **depend on** Use Cases
- Use Cases **depend on** Entities
- Entities **depend on** NOTHING

### Visual with Colors

```
          🔵 Frameworks & Drivers
            (Devices)    (Web)
          ┌──────────────────────┐
          │   🟢 Controllers       │
          │   ┌──────────────────┐ │
          │   │   🔴 Use Cases    │ │
          │   │   ┌────────────┐  │ │
          │   │   │ 🟡 Entities │  │ │  ← Bull's eye
          │   │   └────────────┘  │ │
          │   │      Gateways     │ │
          │   └──────────────────┘ │
          │     Presenters         │
          └──────────────────────┘
            (DB)        (UI)
```

---

## 4. Dependency Inversion in Clean Architecture

This is the **key principle** that makes clean architecture work.

### How It Works

**Step 1:** Inner layers (Use Cases) **define interfaces** for what they need.

```python
# In use cases layer — DEFINES the interface
from abc import ABC, abstractmethod

class IOrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None: ...
    
    @abstractmethod
    def find_by_id(self, order_id: UUID) -> Order: ...
```

**Step 2:** Outer layer (Infrastructure) **implements** those interfaces.

```python
# In infrastructure layer — IMPLEMENTS the interface
from src.use_cases.interfaces import IOrderRepository

class OrderRepository(IOrderRepository):  # Implementation
    def __init__(self, db_context):
        self.db = db_context
    
    def save(self, order: Order) -> None:
        # Real PostgreSQL implementation
        ...
```

**Step 3:** Use case depends only on **abstraction**, not the implementation.

```python
class PlaceOrder:
    def __init__(self, order_repo: IOrderRepository):  # Interface!
        self.repo = order_repo  # Doesn't know if it's Postgres, Mongo, in-memory
```

### Why This Matters

```
✅ Use case depends only on ABSTRACTION
✅ Infrastructure adapts to the contract
✅ Can swap implementations at runtime
✅ Easy to mock for testing
```

### The Inversion

```
Without DI (traditional):                 With DI (clean):
─────────────────                         ────────────────
                                          
UseCase ────depends on──→ Postgres        UseCase ────depends on──→ Interface
                                                                        ↑
                                              implements ←──── Postgres
                                          
Domain depends on DB                       DB depends on Domain (via interface)
```

The inner layer **defines what it needs**. The outer layer **adapts to that**.

### Visual

```
┌─────────────────────────────────────┐
│  «interface» IOrderRepository        │ ← In Use Cases (inner)
│  + save(order)                       │
│  + findById(id)                      │
└──────────────┬──────────────────────┘
               │ implements
┌──────────────▼──────────────────────┐
│  OrderRepository                     │ ← In Infrastructure (outer)
│  + save(order)                       │
│  + findById(id)                      │
└─────────────────────────────────────┘
```

---

## 5. Clean Architecture in Action (Example)

### Use Case: Place Order

```
👤 User
   ↓
🟢 Controller    ← Interface Adapter
   ↓
🔴 Use Case      ← Application Business Rule
   ↓ (uses)
🟡 Domain Model  ← Entity
   ↓ (uses)
🔴 IOrderRepo    ← Interface defined in Use Case
   ↓ implemented by
🔵 OrderRepo     ← Concrete in Infrastructure
   ↓
🗄 PostgreSQL
```

### Step-by-Step Flow

1. **User sends HTTP request** (POST /orders)
2. **Controller** (interface adapter) receives it
3. Controller **calls the use case** (PlaceOrder)
4. Use case **processes business logic** — validates, calculates
5. Use case **calls IOrderRepository interface** (defined in use case layer)
6. **Infrastructure layer's OrderRepository** implements that interface
7. OrderRepository uses **Entity Framework / SQLAlchemy** to talk to DB
8. Response flows back: DB → Repo → Use Case → Controller → HTTP response

### The Beautiful Separation

```
Want to test the use case?
   → Mock IOrderRepository → no real DB needed

Want to switch to MongoDB?
   → New MongoOrderRepository implements IOrderRepository
   → Use case code DOESN'T CHANGE

Want to add gRPC?
   → New gRPC controller calls same use case
   → Use case code DOESN'T CHANGE
```

> **Every part of the system knows exactly what its job is and nothing more.**

That's the power of Clean Architecture.

---

## 6. Deep Dive into Onion Architecture

### The Origin

- **Proposed by Jeffrey Palermo** (2008)
- Just like clean architecture, emphasizes **separation of concerns**
- But with its own twist — more **Domain-Driven Design (DDD)** friendly

### The Onion Model

```
                  ┌───────────────────────────┐
                  │   Presentation Layer       │
                  │  ┌────────────────────┐   │
                  │  │  Application Svc    │   │
                  │  │  ┌──────────────┐   │   │
                  │  │  │              │   │   │
                  │  │  │  Domain      │   │   │ ← onion's core
                  │  │  │              │   │   │
                  │  │  └──────────────┘   │   │
                  │  └────────────────────┘   │
                  │   Persistence | Infra      │
                  └───────────────────────────┘
                            ↑           ↑
                            DB         External APIs
```

### Key Features

```
✅ Domain model is LITERALLY at the center
✅ Interfaces invert dependencies
✅ Application services coordinate use cases
✅ Outer layers depend on inner layers
✅ Domain stays pure
```

### The Onion Metaphor

> Each outer layer **depends on** the inner one — but the **core stays pure and untouched**.

You can:
- Peel away infrastructure
- Swap technologies
- And the **domain model remains safe at the heart**

---

## 7. Layers of Onion Architecture

Onion has **5 distinct layers**:

### Layer 1: 🟩 Domain Model (Core)

```
🟩 Domain Model
   "The Innermost Core"
   
   What's here:
   - Core business entities (Order, Product, Customer)
   - Aggregates, value objects
   - Domain rules + invariants
   - Pure Python — no dependencies on ANY other layer
```

**Examples:**

```python
@dataclass
class Order:  # Aggregate
    id: UUID
    lines: List[OrderLine]
    
    def can_be_cancelled(self) -> bool:
        return self.status == "pending"
```

### Layer 2: 🟪 Domain Services

```
🟪 Domain Services
   "Cross-Entity Business Logic"
   
   What's here:
   - Business logic that spans multiple entities
   - PricingService (uses Product + Customer + Discount)
   - InventoryChecker (uses Product + Order)
   - Pure logic, NO infrastructure
```

**Examples:**

```python
class PricingService:
    """Operates across multiple entities."""
    
    def calculate_final_price(
        self,
        product: Product,
        customer: Customer,
        discount: Optional[Discount],
    ) -> Money:
        # Cross-entity pricing logic
        ...
```

### Layer 3: 🔵 Application Services

```
🔵 Application Services
   "Workflow Coordination"
   
   What's here:
   - Orchestrate use cases
   - Coordinate domain services
   - Manage transactions
   - Define interfaces for outer layers
```

**Examples:**

```python
class OrderService:
    """Application service — coordinates workflow."""
    
    def __init__(
        self,
        order_repo: IOrderRepository,    # Interface
        pricing: PricingService,           # Domain service
        payment: IPaymentGateway,           # Interface
    ):
        self.order_repo = order_repo
        self.pricing = pricing
        self.payment = payment
    
    def place_order(self, request) -> OrderResult:
        # Workflow: validate → price → pay → save
        ...
```

### Layer 4: 🟧 Infrastructure (Outermost)

```
🟧 Infrastructure
   "Text-Specific Implementations"
   
   What's here:
   - Database access (SQL Order Repository)
   - External API calls (Stripe Adapter)
   - Email/SMS sending (EmailSender)
   - Web framework (Controllers)
   - All technology-specific code
```

**Examples:**

```python
class SqlOrderRepository(IOrderRepository):
    """Infrastructure — implements interface from inner layer."""
    
    def __init__(self, session):
        self.session = session
    
    def save(self, order: Order) -> None:
        # Real PostgreSQL implementation
        ...
```

### Layer 5: Cross-Cutting (Often Shown Outside)

- **User Interface** (web pages, mobile apps)
- **Tests** (test code that uses all layers)

### Complete Onion Visual

```
                  ┌────────────────────┐
                  │ 👤 User Interface   │
                  │  ┌──────────────┐  │
                  │  │ 🔵 App Svc    │  │
                  │  │  ┌─────────┐  │  │
                  │  │  │🟪 Domain │  │  │
                  │  │  │  Services │  │  │
                  │  │  │ ┌───────┐ │  │  │
                  │  │  │ │🟩Model │ │  │  │ ← center
                  │  │  │ └───────┘ │  │  │
                  │  │  └─────────┘  │  │
                  │  └──────────────┘  │
                  │ 🟧 Infrastructure  │ ← outermost
                  │                     │
                  │  ┌─────┐ ┌────────┐│
                  │  │Tests│ │External││
                  │  └─────┘ └────────┘│
                  └────────────────────┘
```

### Dependency Direction

> **Inner layers define interfaces. Outer layers implement them. All dependencies point INWARD toward the domain core.**

```
Domain Model       ← ONLY pure logic
   ↑ used by
Domain Services    ← pure cross-entity logic
   ↑ used by
Application Svc    ← orchestrates + defines interfaces
   ↑ implements
Infrastructure     ← concrete technology code
```

---

## 8. Dependency Inversion in Onion

Same principle as Clean Architecture but with **onion-specific naming**.

### Pattern

```python
# Domain layer (or app service) — defines interface
class IOrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None: ...
    @abstractmethod
    def findById(self, id: UUID) -> Order: ...


# Infrastructure layer — implements interface
class OrderRepository(IOrderRepository):
    def save(self, order: Order) -> None:
        # SQL implementation
        ...
    def findById(self, id: UUID) -> Order:
        # SQL implementation
        ...
```

### The Critical Rule

> **Outer layers must have NO knowledge of domain internals.**

- Domain should NEVER have to know about controllers, HTTP, or SQL
- Outer layers should NEVER leak into business logic
- Domain defines **WHAT** it needs (clean contract)
- Infrastructure decides **HOW** to fulfill (concrete implementation)

### Visual: The Inversion

```
┌───────────────────────────────┐
│ «interface» IOrderRepository   │ ← Defined in App Service/Domain layer
│  + save(order)                 │
│  + findById(id)                │
└──────────────┬────────────────┘
               │ implements
┌──────────────▼────────────────┐
│  OrderRepository                │ ← Implemented in Infrastructure layer
│  + save(order)                  │
│  + findById(id)                 │
└────────────────────────────────┘
```

### The Power

```
Want to swap PostgreSQL → MongoDB?
   ✅ Just replace OrderRepository implementation
   ✅ Domain doesn't notice

Want to mock for testing?
   ✅ Plug in FakeOrderRepository
   ✅ Same interface, different behavior

Want to add caching?
   ✅ Wrap real repo with caching layer
   ✅ Domain code unchanged
```

### Clean Separation: What vs How

```
Domain says (WHAT):
   "I need to save an Order"
   "I need to find Order by ID"

Infrastructure says (HOW):
   "I'll execute SQL INSERT"
   "I'll execute SQL SELECT"
```

---

## 9. Onion Architecture in Action (Example)

### Use Case: Place Order

```
Controller
   ↓ (calls application service)
Application Service (OrderService)
   ↓ (invokes domain logic)
Domain Service (PricingService)
   ↓ (uses)
Domain Model (Order, Product)
   ↓ (calls interface)
IOrderRepository ← interface in App Service layer
   ↑ implemented by
Infrastructure (SqlOrderRepository)
```

### Flow

1. **Controller** receives HTTP POST /orders (Infrastructure)
2. Controller calls **Application Service** (OrderService)
3. OrderService calls **Domain Service** (PricingService)
4. PricingService uses **Domain Model** (Order, Product entities)
5. Domain logic needs to **save** → calls IOrderRepository interface
6. **Infrastructure** (SqlOrderRepository) implements that interface
7. Real DB save happens
8. Response flows back up

### Code Sketch

```python
# 🟧 Infrastructure layer
class OrderController:
    def __init__(self, order_service):
        self.order_service = order_service
    
    def post_order(self, http_request):
        result = self.order_service.place_order(http_request.json)
        return HttpResponse(json=result)


# 🔵 Application Service
class OrderService:
    def __init__(self, order_repo, pricing_service):
        self.order_repo = order_repo
        self.pricing_service = pricing_service
    
    def place_order(self, request):
        # 🟪 Domain Service
        total = self.pricing_service.calculate(request.items)
        
        # 🟩 Domain Model
        order = Order.create(request.customer_id, request.items, total)
        
        # Save (via interface implemented in infrastructure)
        self.order_repo.save(order)
        
        return order


# 🟧 Infrastructure
class SqlOrderRepository(IOrderRepository):
    def save(self, order):
        # Real SQL
        ...
```

### Key Takeaway

> **Domain drives the application; infrastructure adapts to the domain.**

NOT the other way around.

---

## 10. Core Similarities — Onion vs Clean

Both share these powerful principles:

### 1. Domain-Centric Core

```
🎯 Both put DOMAIN at the center
   Whether you call it "Entity" (Clean) or "Domain Model" (Onion)
```

### 2. Inward Dependencies

```
🔄 In BOTH:
   Outer layers depend on inner
   Inner layers know nothing about outer
   Dependency arrows point INWARD
```

### 3. Framework Agnostic

```
🔓 In BOTH:
   Core works without ASP.NET, Spring, FastAPI, etc.
   Tomorrow you can swap frameworks
```

### 4. Easy Unit Testing

```
🧪 In BOTH:
   Test domain logic without DB
   Test without web server
   Test in milliseconds
```

### 5. Interfaces Owned by Core

```
📐 In BOTH:
   Domain/App layer defines interfaces
   Infrastructure implements them
   Inversion of control
```

### Quick Summary

| Aspect | Both Clean & Onion |
|---|---|
| **Core** | Domain logic at center |
| **Dependencies** | Inward-pointing |
| **Framework dependence** | Agnostic |
| **Test isolation** | Easy (use mocks) |
| **Interface ownership** | Core defines |
| **Long-term maintainability** | Excellent |

> **At their heart, they are two sides of the same coin.**

---

## 11. Key Differences — Clean vs Onion

Despite similarities, they differ in subtle but important ways:

### 1. Terminology & Naming

| | Clean Architecture | Onion Architecture |
|---|---|---|
| Core terms | **Entities, Use Cases, Interface Adapters, Frameworks** | **Domain Model, Domain Services, Application Services, Infrastructure** |
| Philosophy | Software engineering vocabulary | DDD-aligned vocabulary |

### 2. Layer Granularity

| | Clean | Onion |
|---|---|---|
| Layer count | 4 explicit | 5 (incl. domain services) |
| Boundaries | More prescriptive | More flexible |
| Style | "Use Case" oriented | "Domain Service" oriented |

### 3. Flow Emphasis

```
CLEAN:                                ONION:
─────                                 ──────

Use Cases at the heart                Domain Model at the heart
of activity                           of activity
                                      
"What can the app DO?"                "What does the app KNOW?"
Application behavior drives           Domain model drives
                                      
PlaceOrder, RegisterUser              Order, Customer, Product
ApproveLoan                           Loan, Payment
```

### 4. Infrastructure Role

| | Clean | Onion |
|---|---|---|
| Naming | **Frameworks & Drivers** (more specific) | **Infrastructure** (single ring) |
| Adapters | Explicitly separate from frameworks | Includes everything outside core |
| Structure | More distinct layers | Single outer ring |

### 5. Adoption Style

```
USE CLEAN IF:                        USE ONION IF:
─────────────                        ────────────

Framework-agnostic apps              Domain-heavy systems
Clear use case separation needed     Heavy DDD adoption
Behavior + workflows = important     Domain modeling = priority
Application logic = central          Domain entities = central
```

### 6. Diagram Style

```
CLEAN:                       ONION:
─────                        ──────

Concentric circles           Concentric circles
Bull's eye / target diagram   Onion-layered diagram

Labels:                      Labels:
- Entities (yellow)          - Domain Model (green)
- Use Cases (red)            - Domain Services (purple)
- Adapters (green)           - App Services (blue)
- Frameworks (blue)          - Infrastructure (orange)
```

### Side-by-Side Summary

| Aspect | Clean Architecture | Onion Architecture |
|---|---|---|
| **Inventor** | Robert C. Martin | Jeffrey Palermo |
| **Year** | ~2012 (book 2017) | 2008 |
| **Philosophy** | Use case-centric | Domain-centric |
| **Layer naming** | Entity, Use Case, Adapter, Framework | Domain Model, Domain Service, App Service, Infrastructure |
| **DDD alignment** | Less DDD focus | Strong DDD alignment |
| **Best fit** | Application orchestration | Rich domain modeling |
| **Diagram** | Bull's eye | Onion |

### But Honestly...

In practice, **they're VERY similar** and many people use the **terms interchangeably**.

The key is the **underlying principle**: **keep domain pure, depend inward**.

---

## 12. Choosing the Right Architecture

```
                Are you using Domain-Driven Design?
                          │
                ┌─────────┴─────────┐
                │ Yes              │ No
                ↓                   ↓
         Use Onion         Do you need clearly
         Architecture       separated Use Cases?
                                    │
                          ┌─────────┴─────────┐
                          │ Yes              │ No
                          ↓                   ↓
                  Use Clean          Is framework-
                  Architecture       independence priority?
                                              │
                                    ┌─────────┴─────────┐
                                    │ Yes              │ No
                                    ↓                   ↓
                            Use Clean       Want lighter,
                            Architecture   flexible domain
                                            centric design?
                                                    │
                                          ┌─────────┴─────────┐
                                          │ Yes              │ No
                                          ↓                   ↓
                                    Use Onion        Either works —
                                    Architecture     pick by team style
```

### When To Use Clean

```
✅ Want clear separation of concerns
✅ Large or growing codebase
✅ System revolves around explicit USE CASES
   (PlaceOrder, RegisterUser, ApproveLoan)
✅ Framework-agnostic design priority
✅ Team needs clarity around application behavior
✅ Structured layering matters
```

### When To Use Onion

```
✅ Already using Domain-Driven Design (DDD)
✅ Rich, evolving business domain
✅ Want domain model to drive everything
✅ Building service-oriented system / microservices
✅ Each service has strong, self-contained domain model
✅ Domain rules are complex
✅ Modeling accurately is your top priority
```

### Honest Truth

> **Both work well.**  
> They share the same core values:
> - Isolation
> - Inversion of dependencies
> - Long-term maintainability

The difference is **what you want to emphasize**:

- **Behavior + workflows** → Clean
- **Rich domain model** → Onion

### Real-World Reality

> **Many real-world systems blend elements of both.**
> Choose what fits your **team, domain, and architectural goals**.

---

## 13. Common Mistakes to Avoid

### Mistake 1: Domain Calling Infrastructure Directly

```python
# ❌ BAD — domain reaches into infrastructure
class Order:
    def save(self):
        connection = pg.connect("postgres://...")  # ❌ Domain → DB!
        connection.execute("INSERT INTO orders ...")
```

**Why it's bad:**
- Breaks dependency inversion
- Domain becomes tightly coupled to DB
- Can't test without real DB

**✅ Fix:**

```python
# Domain defines interface
class IOrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None: ...

# Infrastructure implements (in outer layer)
class SqlOrderRepository(IOrderRepository):
    def save(self, order: Order) -> None:
        # Real DB call
        ...
```

### Mistake 2: Leaky Abstractions

```python
# ❌ BAD — interface exposes DB-specific types
class IOrderRepository(ABC):
    def get_orders(self) -> SqlResultSet:  # ❌ DB type in interface!
        ...
    
    def query(self, dbcontext: DbContext):  # ❌ Framework leak!
        ...
```

**Why it's bad:**
- Domain now knows about SQLAlchemy / Entity Framework
- Defeats the purpose of abstraction

**✅ Fix:**

```python
# Clean interface — domain types only
class IOrderRepository(ABC):
    def get_orders(self) -> List[Order]:  # Pure domain type
        ...
    
    def save(self, order: Order) -> None:  # No framework leak
        ...
```

### Mistake 3: Too Much Logic in Controllers

```python
# ❌ BAD — business logic in controller
class OrderController:
    def post_order(self, request):
        # ❌ Business logic in controller
        if request.total > 1000:
            request.discount = 0.10
        
        # ❌ Direct DB query
        existing = db.query(Order).filter(...)
        
        # ❌ Validation
        if not existing:
            raise HTTPException(400)
        
        # ... 50 more lines
```

**Why it's bad:**
- Controllers should be **thin**
- Business logic belongs in use cases / domain
- Skipping architectural layers

**✅ Fix:**

```python
# Thin controller — just translates HTTP
class OrderController:
    def __init__(self, place_order: PlaceOrder):
        self.place_order = place_order
    
    def post_order(self, request):
        result = self.place_order.execute(request.to_dto())
        return HttpResponse(json=result)


# Use case has the logic
class PlaceOrder:
    def execute(self, request):
        # All business logic here
        ...
```

### Mistake 4: Overengineering for Simple Apps

```python
# ❌ BAD — CRUD app with 5 layers
"""
For a simple admin dashboard with 3 CRUD endpoints:
   - 5 interface contracts
   - 4 layers of abstractions
   - Dependency injection framework
   - Repository pattern
   - 100 files for a 1000-line app
"""
```

**Why it's bad:**
- Clean/Onion are **fantastic for complex systems**
- But overkill for **CRUD admin dashboards** or **throwaway prototypes**
- Layers of indirection slow you down

**✅ Fix:**

```python
# Simple CRUD? Just write it simply.
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return db.query(User).filter(User.id == user_id).first()

# No use cases, no domain services, no over-engineering
```

### When To Use Patterns

```
✅ Use Clean/Onion when:
   - Domain is complex
   - System will live > 2 years
   - High testability required
   - Multiple integration channels

❌ Don't use Clean/Onion when:
   - Simple CRUD
   - MVP / prototype
   - < 1000 LOC app
   - Team can't maintain patterns
```

---

## 14. Summary & Key Takeaways

```
✅ Clean & Onion share POWERFUL CORE IDEAS
✅ Both enable TESTABILITY, MAINTAINABILITY, FLEXIBILITY
✅ Pick the approach that suits YOUR TEAM and CONTEXT
✅ Keep your DOMAIN INDEPENDENT — always
```

### The Common Foundation

Both architectures help you build systems that are:
- **Testable** — domain isolated from infrastructure
- **Maintainable** — clear separation of concerns
- **Flexible** — can swap frameworks, DBs, APIs
- **Long-living** — survive technology shifts

### Common Principles

```
🎯 Keep domain at center
🔄 Dependencies point inward
🔓 Domain is framework-agnostic
🧪 Easy unit testing
📐 Interfaces owned by core
```

### Selection Guidance

```
Clean Architecture:
   → If you focus on USE CASES and BEHAVIOR

Onion Architecture:
   → If you focus on RICH DOMAIN MODELING

In doubt:
   → Either works. Pick what your team gravitates to.

Most important:
   → ALWAYS protect your domain.
```

### Memorable Quote

> **"That's where the real value of your system lives. Everything else is just delivery."**

---

## 15. Interview Questions

### Q1: "What's the difference between Clean and Onion Architecture?"

**Answer:**
"Both promote separation of concerns with domain at the center, but differ in emphasis:

**Clean (Uncle Bob, ~2012):**
- Focuses on **use cases** / application behavior
- Layers: Entities → Use Cases → Interface Adapters → Frameworks
- More prescriptive about layer boundaries
- Bull's eye / target diagram

**Onion (Jeffrey Palermo, 2008):**
- Focuses on **domain model**
- Layers: Domain Model → Domain Services → App Services → Infrastructure
- More aligned with Domain-Driven Design (DDD)
- Onion-shaped diagram

Both share core principles: dependencies point INWARD, domain stays pure, framework-agnostic, easy unit testing.

In practice, many systems blend both. Choose based on:
- Use case-centric → Clean
- Domain-centric → Onion"

### Q2: "Explain the Dependency Rule in Clean Architecture."

**Answer:**
"The dependency rule states that **source code dependencies always point INWARD**:

- Outer layers (frameworks, drivers) can depend on inner layers (use cases, entities)
- Inner layers know NOTHING about outer layers
- An entity can't import a controller, but a controller can use an entity

This is achieved via **Dependency Inversion** — the inner layer **defines an interface**, and the outer layer **implements it**:

```python
# Use Case (inner) defines:
class IOrderRepository(ABC):
    def save(self, order: Order) -> None: ...

# Infrastructure (outer) implements:
class SqlOrderRepository(IOrderRepository):
    def save(self, order: Order) -> None:
        # Real SQL
```

This makes the system testable (mock interfaces), flexible (swap implementations), and protects domain from infrastructure changes."

### Q3: "What is a Use Case in Clean Architecture?"

**Answer:**
"A **Use Case** in Clean Architecture is an **application-specific business rule** — it orchestrates the workflow for a specific user goal.

Examples: `PlaceOrder`, `RegisterUser`, `GenerateInvoice`, `CancelSubscription`.

Each use case:
1. Defines input/output models (DTOs)
2. Validates business rules
3. Coordinates between entities and external systems
4. Returns a result

```python
class PlaceOrder:
    def __init__(self, order_repo: IOrderRepository, payment: IPaymentGateway):
        ...
    
    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        # Validate, charge, save
        ...
```

Use cases sit between **Entities** (pure business logic) and **Interface Adapters** (HTTP, DB). They're the **application's behavior layer**."

### Q4: "What are Domain Services in Onion Architecture?"

**Answer:**
"**Domain Services** in Onion Architecture encapsulate business logic that **spans multiple entities** — logic that doesn't naturally fit inside any single entity.

Example: A `PricingService` that calculates final price using:
- `Product` (base price)
- `Customer` (loyalty tier)
- `Discount` (promotions)
- `TaxRule` (jurisdiction)

This logic shouldn't live in any of those entities alone — it's a cross-cutting domain concern.

```python
class PricingService:
    def calculate_final_price(
        self,
        product: Product,
        customer: Customer,
        discount: Optional[Discount],
        tax_rule: TaxRule,
    ) -> Money:
        # Cross-entity pricing logic
        ...
```

Domain Services are pure business logic — no infrastructure, no I/O, just rules. They sit just outside the Domain Model in Onion architecture."

### Q5: "When would you avoid using Clean / Onion Architecture?"

**Answer:**
"They're powerful but overkill for some scenarios:

**Avoid for:**

1. **Simple CRUD apps** — admin dashboards, basic data entry. Just write the simple code.

2. **MVP / prototypes** — you're optimizing for speed, not architecture purity.

3. **Throwaway scripts** — internal tools, one-offs.

4. **Tiny apps (<1000 LOC)** — abstraction layers add more complexity than value.

5. **Small teams who can't maintain patterns** — discipline cost > value.

**Use Clean/Onion when:**
- Complex business domain
- System will live > 2 years
- High testability requirements
- Multiple inbound channels (web, mobile, API)
- Team values long-term maintainability

The trade-off is **flexibility vs simplicity**. For simple problems, simpler architectures (3-tier layered, just FastAPI + SQLAlchemy) are often the right choice."

---

## 16. Key Slide References (from PDF)

- 📄 **Slide 25**: Why Domain-Centric Architecture?
- 📄 **Slide 26**: Deep Dive into Clean Architecture
- 📄 **Slide 27**: Layers of Clean Architecture
- 📄 **Slide 28**: Dependency Inversion in Clean Architecture
- 📄 **Slide 29**: Clean Architecture in Action
- 📄 **Slide 30**: Deep Dive into Onion Architecture
- 📄 **Slide 31**: Layers of Onion Architecture
- 📄 **Slide 32**: Dependency Inversion in Onion
- 📄 **Slide 33**: Onion Architecture in Action
- 📄 **Slide 34**: Core Similarities — Onion and Clean
- 📄 **Slide 35**: Key Differences — Clean vs Onion
- 📄 **Slide 36**: Choosing the Right Architecture
- 📄 **Slide 37**: Common Mistakes to Avoid

---

## 17. What's Next?

**Lecture 4: Applying Modular Architectures in Real Systems** — Practical application of layered, hexagonal, clean, and onion in enterprise + legacy systems.

➡️ **[Lecture 4: Applying Modular Architectures](04_Applying_Modular_Architectures.md)**

➡️ **For working code:** **[Practical Hands-On](03_Practical_Hands_On.md)**

---

## 🎓 Related Backend_Developer Curriculum

- [Phase2_FastAPI/12_clean_architecture_ddd.md](../../Phase2_FastAPI/12_clean_architecture_ddd.md)
- [PythonBackend_SystemDesign/LLD_Theory/](../../PythonBackend_SystemDesign/LLD_Theory/) — Design patterns
- [Phase3_Microservices/09_domain_driven_design.md](../../Phase3_Microservices/09_domain_driven_design.md)
- [Section_01_Foundations/](../Section_01_Foundations/)
