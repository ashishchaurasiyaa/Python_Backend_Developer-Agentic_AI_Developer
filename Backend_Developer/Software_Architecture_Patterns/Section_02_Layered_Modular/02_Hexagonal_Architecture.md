# Lecture 2: Hexagonal Architecture (Ports & Adapters)

> *"The outside world adapts to the core — not the other way around."*

**Section 2 — Layered & Modular Architecture Patterns**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Hexagonal Architecture** kya hai aur kyun famous hai
- **Core, Ports, Adapters** ka anatomy
- **Inbound ports vs Outbound ports** difference
- **Plug-and-play model** kaise kaam karta hai
- **Dependency inversion** in action
- **Hexagonal vs Layered** comparison
- **Testing made easy** with hexagonal
- Real example: **Place Order use case**

---

## 1. What is Hexagonal Architecture?

### The Origin

- **Proposed by Alistair Cockburn** (2005)
- Also known as **Ports & Adapters Pattern**
- Designed to solve a specific problem: **tightly coupled code**

### The Core Problem It Solves

> Have you ever worked on a codebase where **changing a database, UI, or API client** meant **rewriting core logic**?

If yes, **hexagonal architecture** is your answer.

### Definition

> **Hexagonal Architecture isolates domain logic from external concerns** (databases, UIs, APIs, frameworks) using **abstract interfaces (ports)** and **concrete implementations (adapters)**.

### Visual Concept

```
                    Web
                     ☁
                     │
                    Adapter
                     │
                   ╭─Port─╮
                  ╱         ╲
                 ╱           ╲
               Port         Port
                ╲    Domain    ╱
                 ╲           ╱
                  ╲         ╱
                   ╲       ╱
        Adapter   Port    Adapter
            │       │        │
            │       │        │
        ☁           Database
        Message Bus
```

### Key Idea

Instead of letting the outside world directly poke into your logic, you put up a **clear boundary**:

- **Domain logic** does NOT know about HTTP or SQL
- **Domain** only communicates through **abstract interfaces** = **PORTS**
- **External systems** (DB, API, UI) implement those ports via **ADAPTERS**

### The Result

> Much more **flexible, modular, and testable** architecture where **changing infrastructure doesn't affect business logic at all**.

---

## 2. Anatomy of a Hexagonal App

### The 3 Key Pieces

```
                  ┌────────────────────────┐
                  │                          │
              Adapter                   Adapter
                  │       Web App         │
                  │       Domain          │
                  │  ┌───────────┐        │
              Adapter│           │   Adapter
                  │  │   Core    │        │
                  │  │  Logic    │        │
                  │  │           │        │
              Adapter│           │   Adapter
                  │  └───────────┘        │
                  │                       │
                  │      Adapter           │
                  └──────────┬─────────────┘
                             │
                          External
                          Systems
```

### 1. 🟪 Core (The Heart)

```
🧠 The heart of the application
   - Domain models
   - Business rules
   - Use cases (e.g., PlaceOrder, GetInvoice)
   
🚫 PURE LOGIC:
   - NO frameworks
   - NO I/O code
   - NO HTTP knowledge
   - NO SQL knowledge
```

**Examples of core content:**
- `Order` entity with business invariants
- `PlaceOrder` use case
- `PricingRules`
- `CartTotalCalculator`

### 2. 🔌 Ports (The Contracts)

Ports are **abstract interfaces** — like contractual boundaries.

#### Two Types of Ports:

**A. Inbound Ports (Driver Ports)**
> How the **outside world** can invoke your app.

Examples:
- `PlaceOrder` use case (callable via HTTP, CLI, batch job)
- `GetInvoice` use case
- `CancelOrder` use case

**Same port** can be triggered by:
- A REST API
- A CLI command
- A scheduled batch job
- A test case

**B. Outbound Ports (Driven Ports)**
> What your **app needs** from external systems.

Examples:
- `UserRepository` (need to load/save users)
- `PaymentService` (need to charge customer)
- `EmailSender` (need to send emails)
- `EventBus` (need to publish events)

> **Core defines these interfaces but doesn't care who fulfills them.**

### 3. 🔄 Adapters (The Implementations)

Adapters are **concrete implementations** of ports.

```
Inbound Adapters (call the core):
  📡 REST Controller → calls PlaceOrder
  💻 CLI Command → calls PlaceOrder
  🧪 Test code → calls PlaceOrder

Outbound Adapters (called by the core):
  🗄 PostgreSQL Repository → implements UserRepository
  💳 Stripe Client → implements PaymentService
  📧 SendGrid Client → implements EmailSender
  🧪 Fake Repository → implements UserRepository (for tests)
```

### Golden Rule

> **Adapters depend on the core. Never the other way around.**

Your business logic remains **clean and untouched** even if:
- You change database
- You change API framework
- You change UI framework
- You change payment gateway

### 4. 🎯 Direction of Control

This is the **most important shift in mindset** in hexagonal architecture.

```
TRADITIONAL LAYERED:           HEXAGONAL:
─────────────────              ──────────
Domain depends on              Outside world adapts
infrastructure                 to core
                               
UI → Logic → DB                Inbound Adapter
   (top-down)                       ↓ (calls port)
                                  CORE
                                    ↑ (calls port)
                               Outbound Adapter
```

- Input comes in via **inbound port**
- Output leaves via **outbound port**
- **Outer world adapts to the core**, not vice versa

This **direction of flow** makes the architecture:
- ✅ Modular
- ✅ Flexible
- ✅ Easy to test
- ✅ Long-living

---

## 3. Ports & Adapters = Plug & Play

### The Universal Socket Analogy

Think of hexagonal architecture like a **universal socket system**:

```
            Domain Logic (Appliance)
                     │
              ┌──────┴──────┐
              │             │
           Plug A         Plug B
        (Adapter for    (Adapter for
         REST API)       CLI)
```

- **Appliance** = Domain Logic (don't change it)
- **Plugs** = Adapters (switch freely)

You can **add or remove adapters** without your domain logic even noticing.

### Real Examples

**Example 1: Same Use Case, Different Triggers**

```
Use Case: PlaceOrder
                 │
                 ↑ called from...
        ┌────────┴────────┐
        │         │        │
   REST API    CLI     Test Case
   (HTTP)    (Bash)    (pytest)
```

All three trigger the **same `PlaceOrder` use case**.

**Example 2: Same Port, Different Implementations**

```
Outbound Port: OrderRepository
                  ↑ implemented by...
        ┌────────┴────────┐
        │         │        │
   Postgres    MongoDB   Fake/Mock
   Adapter     Adapter   Adapter
```

Want to switch from Postgres to MongoDB?
- Just **replace the adapter**
- Domain logic stays **exactly the same**

### Why This Matters for Testing

```python
# Production: real adapters
order_service = PlaceOrder(
    repo=PostgresOrderRepo(),
    payment=StripeAdapter(),
)

# Testing: fake adapters
order_service = PlaceOrder(
    repo=InMemoryOrderRepo(),    # fake!
    payment=MockPaymentService(),  # fake!
)
# Same use case, totally different infrastructure
```

### Visual Plug & Play

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│REST       │  │CLI        │  │Test       │
│Adapter    │  │Adapter    │  │Adapter    │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   ▼
   ┌────────────────────────────┐
   │     Application Core         │
   │                              │
   │   Use Case: CreateOrder      │
   └────────────────────────────┘
```

3 different ways to call same use case → all work.

---

## 4. Comparison with Layered Architecture

### Layered Architecture Refresher

```
🟫 Layered Architecture
   ├── UI Layer
   ├── Business Logic
   └── Data Access
   
   Flow: Top-down (UI → Logic → Data)
   Coupling: Tight (each layer knows next layer)
```

### Key Differences

| Aspect | Layered | Hexagonal |
|---|---|---|
| **Focus** | Internal structure | I/O boundaries |
| **Flow direction** | Top-down | Inward (everything flows to core) |
| **Coupling** | Often tight | Loose (via ports) |
| **Framework dependence** | Often framework-driven (Spring, ASP.NET) | Framework-agnostic core |
| **Testing isolation** | Hard (need mocks of stack) | Easy (swap adapters) |
| **Domain isolation** | Mixed concerns | Pure domain |

### Visual Comparison

```
LAYERED:                       HEXAGONAL:
─────────                      ──────────

┌──────────────┐               ┌─────────────────────┐
│ UI Layer      │              Adapter   Adapter
└──────┬───────┘                ▼          ▼
       ▼                      Port      Port
┌──────────────┐                 ╲      ╱
│ Logic Layer   │                 ╲    ╱
└──────┬───────┘                  ╲  ╱
       ▼                          CORE
┌──────────────┐                  ╱  ╲
│ Data Layer    │                 ╱    ╲
└──────┬───────┘                 ╱      ╲
       ▼                       Port      Port
┌──────────────┐                ▲          ▲
│ Database      │            Adapter   Adapter
└──────────────┘
```

### When To Use What

```
Use LAYERED when:
   ✅ Simple system
   ✅ Small team
   ✅ Early-stage / MVP
   ✅ Single framework + DB

Use HEXAGONAL when:
   ✅ Need long-term maintainability
   ✅ Plan to swap technologies later
   ✅ Heavy testing requirements
   ✅ Complex domain
   ✅ Multiple inbound/outbound channels
```

> **Hexagonal is NOT a replacement** for layered — it's a more **disciplined** form of separation.

---

## 5. Dependency Inversion in Action

This is the **real magic** behind hexagonal.

### Traditional Setup (BAD)

```
Use Case        →    DB / Email / Payment
(business)            (infrastructure)

CORE depends on INFRASTRUCTURE
```

If infrastructure changes → core breaks.

### Hexagonal Setup (GOOD)

```
Use Case        →    Interface (Port)
(business)             ↑ implemented by
                       │
                   Adapter
                  (infrastructure)

INFRASTRUCTURE depends on CORE
```

**Dependency inverted!**

### How It Works (Step by Step)

**Step 1:** Core defines what it needs (interface):
```python
# In core layer
class UserRepository(Protocol):
    """Outbound port — core defines what it needs."""
    def get(self, user_id: int) -> User: ...
    def save(self, user: User) -> None: ...
```

**Step 2:** Core uses interface (doesn't know implementation):
```python
# In core layer
class PlaceOrder:
    def __init__(self, user_repo: UserRepository, payment: PaymentService):
        # Type-hint with abstract interfaces
        self.user_repo = user_repo
        self.payment = payment
```

**Step 3:** Infrastructure implements interface:
```python
# In infrastructure layer
class PostgresUserRepository:
    """Outbound adapter — implements the port."""
    def __init__(self, db_session):
        self.db = db_session
    
    def get(self, user_id: int) -> User:
        return self.db.query(...).first()
```

**Step 4:** Wire them together (at startup):
```python
# In composition root
postgres_repo = PostgresUserRepository(db_session)
stripe_payment = StripePaymentService(api_key)
place_order = PlaceOrder(user_repo=postgres_repo, payment=stripe_payment)
```

### Benefits of Dependency Inversion

```
✅ Domain logic doesn't break if you change DB
✅ You can plug in mocks/stubs for testing
✅ You stay in full control of the contract
✅ Infrastructure can evolve independently
```

---

## 6. Testing Made Easy

This is one of the **biggest practical benefits** of hexagonal architecture.

### Why Testing Is Hard in Tightly Coupled Code

```
❌ To test order creation, you need:
   - Running database
   - Running message broker
   - Running payment service (Stripe API)
   - Network connectivity
   - Test data setup
   - Cleanup after tests
   
   Tests are SLOW + FLAKY + BRITTLE
```

### Why Testing Is Easy in Hexagonal

```
✅ To test order creation:
   - Use in-memory fake adapters
   - No database needed
   - No external services needed
   - No network calls
   
   Tests are FAST + RELIABLE + ISOLATED
```

### Test Levels in Hexagonal

```
┌───────────────────────────────────────┐
│  Unit Tests (fast, isolated)            │
│  - Use FAKE adapters                    │
│  - Test only domain logic               │
│  - Run in milliseconds                  │
├───────────────────────────────────────┤
│  Integration Tests (slower)              │
│  - Use REAL adapters                    │
│  - Verify adapters work correctly        │
│  - Test integration with external sys   │
├───────────────────────────────────────┤
│  End-to-End Tests (slowest)             │
│  - Use REAL adapters + REAL deps        │
│  - Test full system                     │
└───────────────────────────────────────┘
```

### Visual

```
┌──────────────────────────┐
│   Application Core         │
│                            │
│  ┌──────────────────┐     │
│  │ Use Case:         │     │
│  │ PlaceOrder        │─┐  │
│  └──────────────────┘ │  │
│                        ↓  │
│  ┌──────────────────┐    │
│  │ Port:             │    │
│  │ OrderRepository   │    │
│  └─────┬────────┬───┘    │
└────────┼────────┼─────────┘
         │        │
         ▼        ▼
   ┌──────────┐ ┌──────────────┐
   │Fake In-   │ │Real DB        │
   │Memory      │ │Adapter         │
   │Adapter -   │ │Integration     │
   │for Tests   │ │                │
   └──────────┘ └──────────────┘
```

### Example Test

```python
def test_place_order_success():
    # Fake adapters
    fake_repo = InMemoryOrderRepo()
    fake_payment = MockPaymentService(always_succeed=True)
    
    # Real use case with fakes
    use_case = PlaceOrder(repo=fake_repo, payment=fake_payment)
    
    # Test
    order = use_case.execute(user_id=1, amount=100)
    
    # Assertions
    assert order.status == "confirmed"
    assert fake_repo.saved_orders[0] == order
    assert fake_payment.charged_amount == 100
```

> **Goal:** No real database. No real payment gateway. Pure logic test in **< 1 millisecond**.

---

## 7. Example Use Case: Place Order

### Scenario: E-Commerce Checkout

User clicks "Buy Now" → what happens?

### Hexagonal Mapping

```
┌──────────────────────────────────────────┐
│ Adapter: REST Controller                   │ ← Inbound adapter
└────────────────┬─────────────────────────┘
                 ▼ (calls inbound port)
┌──────────────────────────────────────────┐
│             🟪 Core Hexagon                │
│                                            │
│  ┌──────────────┐                          │
│  │  Use Case:    │                          │
│  │  PlaceOrder   │ ← Inbound port           │
│  └──────┬───────┘                          │
│         │ (calls outbound ports)            │
│         ▼                                   │
│  ┌──────────────────┐  ┌──────────────┐  │
│  │ Outbound Port:    │  │ Outbound Port:│  │
│  │ ProductRepository │  │ PaymentService│  │
│  └──────┬─────┬──────┘  └─────┬────────┘  │
└─────────┼─────┼────────────────┼──────────┘
          ▼     ▼                ▼
   ┌──────────┐ ┌─────────┐ ┌────────────┐
   │Postgres   │ │Fake     │ │Stripe       │
   │Adapter    │ │Adapter  │ │Adapter      │
   └──────────┘ │for Testing│ └────────────┘
                └─────────┘
```

### Step-by-Step Flow

1. **User clicks "Buy Now"** in browser
2. **REST Controller** receives `POST /orders`
3. Controller calls **PlaceOrder use case** (inbound port)
4. Use case needs to:
   - Check product stock → calls **ProductRepository** (outbound port)
   - Charge customer → calls **PaymentService** (outbound port)
5. At runtime:
   - `ProductRepository` → fulfilled by **PostgresAdapter**
   - `PaymentService` → fulfilled by **StripeAdapter**
6. Use case returns result → Controller responds to user

### Testing Same Flow

For tests:
- `ProductRepository` → fulfilled by **FakeInMemoryAdapter**
- `PaymentService` → fulfilled by **MockPaymentService**
- **No real DB, no real Stripe call**

### Code Sketch

```python
# Core (no infrastructure dependencies!)
class PlaceOrder:
    """Inbound port — the use case."""
    
    def __init__(
        self,
        product_repo: ProductRepository,  # Outbound port
        payment_service: PaymentService,   # Outbound port
    ):
        self.product_repo = product_repo
        self.payment_service = payment_service
    
    def execute(self, user_id: int, items: list[dict]) -> Order:
        # Pure domain logic — no I/O knowledge
        for item in items:
            product = self.product_repo.get(item["product_id"])
            if product.stock < item["qty"]:
                raise OutOfStock()
        
        total = sum(p.price * i["qty"] for p, i in zip(products, items))
        payment = self.payment_service.charge(user_id, total)
        
        order = Order.create(user_id, items, payment.id)
        return order


# Infrastructure adapters (outside the core)
class PostgresProductRepository:
    """Outbound adapter."""
    def get(self, product_id: int) -> Product:
        # Real PostgreSQL query
        ...

class StripePaymentAdapter:
    """Outbound adapter."""
    def charge(self, user_id: int, amount: float) -> Payment:
        # Real Stripe API call
        ...

class InMemoryProductRepository:
    """Outbound adapter for testing."""
    def __init__(self):
        self.products = {}
    def get(self, product_id: int) -> Product:
        return self.products[product_id]
```

### The Power

- **Production**: Use PostgresAdapter + StripeAdapter
- **Tests**: Use InMemoryAdapter + MockPaymentAdapter
- **Same use case code**!

**Clear boundaries. Clean contracts. Full flexibility.**

---

## 8. Common Misconceptions

### Misconception 1: "Hexagonal = 6 Sides"

❌ The "hexagon" is **just a diagram convention**. Could be 4, 5, or 8 sides.

✅ The point is: domain in middle, ports around, adapters outside.

### Misconception 2: "Use Cases Are Just Service Layer"

❌ Use cases are **inbound ports** — public contracts for what app can do.

✅ They orchestrate domain logic, not just CRUD.

### Misconception 3: "It's Just Repositories"

❌ Repositories are **one type** of outbound port (DB access).

✅ Other outbound ports: email, notifications, message bus, external APIs.

### Misconception 4: "Hexagonal = Microservices"

❌ Hexagonal works in **monoliths, microservices, anything**.

✅ It's an internal architecture pattern, not deployment style.

---

## 9. When to Use Hexagonal Architecture

### ✅ Good Fit

| Scenario | Why |
|---|---|
| Domain is complex | Pure core lets you focus on logic |
| Long-living system | Easier to evolve technology stack |
| High test coverage needed | Fake adapters make unit tests fast |
| Multiple inbound channels (web + CLI + cron) | Use case reusable across all |
| Team values craftsmanship | Encourages disciplined separation |
| Plan to swap infrastructure | Easy database/API/queue changes |

### ❌ Overkill For

| Scenario | Alternative |
|---|---|
| Simple CRUD app | Layered is enough |
| MVP / prototype | Just write it fast |
| Throwaway tools | YAGNI |
| Team < 3 engineers | Add discipline gradually |

---

## 10. Real-World Adoption

### Companies Using Hexagonal

- **Netflix** (parts of their backend services)
- **Uber** (newer services after monolith days)
- **DoorDash** (delivery use cases)
- **Square** (payment processing)
- **Spotify** (some bounded contexts)

### Why They Adopted It

- Domain complexity (financial, logistics, real-time)
- High testing requirements
- Frequent technology evolution
- Multiple integration channels

---

## 11. Summary & Key Takeaways

```
✅ Hexagonal Architecture = decoupled, testable, flexible
✅ Core talks only through PORTS
✅ Adapters are INTERCHANGEABLE
✅ Enables clean separation and better long-term maintainability
```

### The Mental Model

```
                  📡 Web
                     ↓
              Inbound Adapter
                     ↓
              Inbound Port
                     ↓
                  ┌────────┐
                  │  CORE   │  ← pure logic
                  └─┬─────┬┘
                    ↓     ↓
              Outbound Port  Outbound Port
                    ↓     ↓
              Adapter     Adapter
                    ↓     ↓
                Database   Stripe
```

### Memorable Quote

> **"The dependency arrows point INWARD."**

If your core depends on infrastructure → you're doing it wrong.

If infrastructure depends on core (via interfaces) → you're doing it right.

---

## 12. Interview Questions

### Q1: "What is hexagonal architecture?"

**Answer:**
"Hexagonal architecture, also known as Ports and Adapters, is a software design pattern that isolates the core domain logic from external concerns like databases, UIs, and APIs.

The core idea is:
- **Domain logic** sits at the center (the 'hexagon')
- **Ports** are abstract interfaces defining what the core needs and exposes
- **Adapters** are concrete implementations that plug into those ports

The key innovation is **dependency inversion** — infrastructure depends on the core, not the other way around. This makes the system testable (use fake adapters), flexible (swap implementations), and maintainable (core stays clean).

It was introduced by Alistair Cockburn in 2005 and is widely used today in domains where business logic is complex and tech stacks evolve."

### Q2: "What's the difference between hexagonal and layered architecture?"

**Answer:**
"Both promote separation of concerns, but they differ significantly:

**Layered:**
- Focuses on **internal structure** (UI / Logic / Data)
- Flow is **top-down**
- Layers often **call each other directly**
- Coupling can be tight
- Domain often depends on infrastructure

**Hexagonal:**
- Focuses on **I/O boundaries**
- Flow is **inward** (everything goes through ports)
- Core defines abstract **ports**; adapters implement them
- **Dependency inverted** — infrastructure depends on core
- Pure domain logic, framework-agnostic

Hexagonal is more disciplined and better for complex domains. Layered is simpler and OK for early-stage apps. They're not mutually exclusive — you can have layers inside a hexagonal core."

### Q3: "What are inbound and outbound ports?"

**Answer:**
"In hexagonal architecture, ports are abstract interfaces that connect the core to the outside world:

**Inbound Ports (Driving Ports):**
- Define how the outside world can invoke the application
- Examples: `PlaceOrder`, `GetInvoice`, `CancelOrder` use cases
- Multiple adapters can call them (REST, CLI, batch jobs)

**Outbound Ports (Driven Ports):**
- Define what the application needs from external systems
- Examples: `UserRepository`, `PaymentService`, `EmailSender`
- Multiple adapters can fulfill them (PostgreSQL, MongoDB, in-memory)

The core defines both, but doesn't care about implementation. This lets you swap any adapter without touching business logic — which is huge for testing and evolution."

### Q4: "How does hexagonal architecture make testing easier?"

**Answer:**
"It makes testing dramatically easier in three ways:

**1. Unit tests with fake adapters:**
You can test core business logic without a real database, Stripe, or message queue. Just plug in fake/in-memory implementations of outbound ports. Tests run in milliseconds.

**2. True isolation:**
Each use case is tested in pure isolation. No mocking of frameworks, no test database setup, no flaky integration issues.

**3. Same code, different deps:**
The same use case code runs in production (with real adapters) and in tests (with fakes). You're testing what you ship, just with different plug-ins.

For example, to test `PlaceOrder`, you'd inject `InMemoryProductRepo` and `MockPaymentService` instead of real PostgreSQL and Stripe. The use case doesn't know the difference — that's the power."

### Q5: "When should you NOT use hexagonal architecture?"

**Answer:**
"Hexagonal is great for complex domains but **overkill** for:

1. **Simple CRUD apps** — adding ports/adapters just for read/write to a single DB is unnecessary overhead. Layered is fine.

2. **MVPs / prototypes** — you want to ship fast, not architect perfectly.

3. **Throwaway tools** — internal scripts, one-off scripts don't need this discipline.

4. **Small teams (< 3 engineers)** — coordination cost of strict patterns may slow you down.

5. **When the domain is trivial** — if your 'business logic' is just data movement, the patterns add complexity without value.

That said, even simple apps benefit from **some** separation. The judgment call is **how much**. Use hexagonal when:
- Business rules are complex
- System will live > 2 years
- Multiple integration channels likely
- High test coverage is a hard requirement"

---

## 13. Key Slide References (from PDF)

- 📄 **Slide 16**: What is Hexagonal Architecture?
- 📄 **Slide 17**: Anatomy of a Hexagonal App
- 📄 **Slide 18**: Ports & Adapters = Plug & Play
- 📄 **Slide 19**: Comparison with Layered Architecture
- 📄 **Slide 20**: Dependency Inversion in Action
- 📄 **Slide 21**: Testing Made Easy
- 📄 **Slide 22**: Example Use Case — Place Order

---

## 14. What's Next?

**Lecture 3: Clean & Onion Architectures** — Patterns that take hexagonal ideas further with more emphasis on dependencies and boundaries.

➡️ **[Lecture 3: Clean & Onion Architecture](03_Clean_and_Onion_Architecture.md)**

➡️ **For working code:** **[Practical Hands-On](02_Practical_Hands_On.md)**

---

## 🎓 Related Backend_Developer Curriculum

- [Section_01_Foundations/02_Architecture_vs_Design_vs_Code.md](../Section_01_Foundations/02_Architecture_vs_Design_vs_Code.md)
- [Phase2_FastAPI/12_clean_architecture_ddd.md](../../Phase2_FastAPI/12_clean_architecture_ddd.md)
- [PythonBackend_SystemDesign/LLD_Theory/](../../PythonBackend_SystemDesign/LLD_Theory/) — Design patterns
