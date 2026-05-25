# Facade Pattern

> **Category:** Structural Design Pattern
> **Intent:** Provide a **simplified, unified interface** to a complex subsystem.

---

## 1. Problem Statement

Real systems have **many moving parts**:
- Order checkout → payment + inventory + shipping + email + analytics
- Video transcoding → codec selection + encoding + thumbnail + upload
- User registration → validation + DB + email verification + audit log

Clients shouldn't need to know all these subsystems. **Facade** wraps them and exposes one clean API.

---

## 2. Real-World Analogies

- **Hotel concierge** — handles taxi, restaurant reservation, laundry — guest just calls one person
- **Car ignition** — turning key triggers fuel pump, ignition coil, starter motor
- **REST API** — single endpoint orchestrating multiple microservices

---

## 3. Structure (UML)

```
        ┌──────────┐
Client →│  Facade  │
        └────┬─────┘
             │
   ┌─────────┼─────────┐
   ▼         ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐
│SubA  │ │SubB  │ │SubC  │
└──────┘ └──────┘ └──────┘
```

Client interacts ONLY with Facade. Subsystems can stay complex internally.

---

## 4. Facade vs Other Patterns

| Pattern | Purpose |
|---|---|
| **Facade** | Simplify access to existing complex subsystem |
| Adapter | Make incompatible interface compatible |
| Proxy | Control access (auth, lazy load) — same interface |
| Mediator | Coordinate between peers (bidirectional) |
| Service Layer | Business logic layer in apps |

**Mnemonic:** Facade = "make it easier", Adapter = "make it fit", Proxy = "control access".

---

## 5. Python Implementation

### Basic structure
```python
class PaymentService:
    def charge(self, amount): ...

class InventoryService:
    def reserve(self, items): ...

class ShippingService:
    def schedule(self, address): ...

class OrderFacade:
    """Hides complexity of checkout flow."""
    def __init__(self):
        self.payment = PaymentService()
        self.inventory = InventoryService()
        self.shipping = ShippingService()

    def place_order(self, items, address, card):
        self.inventory.reserve(items)
        self.payment.charge(self._calc_total(items), card)
        self.shipping.schedule(address)
        return "Order placed"
```

---

## 6. When to Use

✅ **Use when:**
- Multiple subsystems need orchestration
- You want to **decouple** clients from subsystem internals
- API surface is too large — need a smaller "user-friendly" subset
- Legacy code with messy structure — wrap with facade

❌ **Don't use when:**
- Only one subsystem — facade is unnecessary indirection
- Need full control — facade hides too much
- Performance-critical hot path — extra layer costs latency

---

## 7. Real Production Examples

### Example 1: AWS SDK (boto3)
```python
import boto3
s3 = boto3.client("s3")
s3.upload_file("local.txt", "bucket", "key.txt")
# Under the hood: auth + retries + multipart + signing + http
```
boto3 client = facade over many low-level operations.

### Example 2: Django ORM
```python
User.objects.create(name="Ashish")
# Internally: connection management + SQL compilation + query execution + caching
```

### Example 3: Auth Facade
```python
class AuthFacade:
    def login(self, email, password):
        user = self.user_repo.get(email)
        if not self.password_hasher.verify(password, user.hash):
            self.audit.log_failed(email)
            raise AuthError
        token = self.token_service.create(user.id)
        self.session_store.save(token, user.id)
        self.audit.log_success(email)
        return token
```

### Example 4: Microservices BFF (Backend for Frontend)
Mobile app hits ONE BFF endpoint. BFF internally fans out to 5 microservices, aggregates, returns one response. BFF is a facade.

### Example 5: Image processing
```python
class ImageFacade:
    def process_upload(self, file):
        validated = self.validator.check(file)
        compressed = self.compressor.compress(validated)
        thumbnail = self.thumbnailer.generate(compressed)
        url = self.storage.upload(compressed)
        thumb_url = self.storage.upload(thumbnail)
        self.db.save(url, thumb_url)
        return {"url": url, "thumb": thumb_url}
```

---

## 8. Pitfalls

### Pitfall 1: Becoming a God Class
Facade grows to do EVERYTHING → unmaintainable. Split into multiple smaller facades.

### Pitfall 2: Hiding too much
Clients need flexibility — facade locks them out. Provide both facade AND direct access.

### Pitfall 3: Tight coupling inside facade
Facade depends on too many concrete classes. Inject dependencies (DI).

### Pitfall 4: Adding business logic
Facade should orchestrate, not contain rules. Put business logic in subsystems.

### Pitfall 5: Anemic facade
Facade just forwards calls 1:1 → useless. Real facade simplifies signatures, combines steps.

---

## 9. Facade vs Service Layer

| Facade | Service Layer |
|---|---|
| Pattern (small scope) | Architecture layer (big scope) |
| Wraps existing complexity | Business logic boundary |
| One class | Multiple classes |
| Read-only by intent | Read + write |

In modern apps, **Service Layer often plays the facade role**.

---

## 10. Interview Questions

**Q1: Facade vs Adapter?**
- Facade: simplify a complex subsystem (one-way wrapping)
- Adapter: convert incompatible interface (translation layer)

**Q2: Facade vs Proxy?**
- Facade: different/simpler interface
- Proxy: same interface, controls access (caching, auth, lazy)

**Q3: Real-world Python facade?**
- `requests.get()` hides urllib3, connection pool, redirects, retries
- `boto3` client hides HTTP signing, multipart uploads

**Q4: Should facade have state?**
Usually yes — holds references to subsystem objects. But avoid request-specific state (use parameters).

**Q5: Facade vs Mediator?**
- Facade: one-way (client → subsystem)
- Mediator: bidirectional coordination between peers

**Q6: How to test facade?**
Mock all subsystem dependencies. Test that facade calls them in correct order with correct args.

**Q7: Facade aur SOLID kaise relate karte?**
- **SRP:** Facade has one responsibility (simplify access)
- **DIP:** Facade depends on abstractions (interfaces)
- **OCP:** Add new subsystems without changing client

---

## 11. Best Practices

1. **Keep facade thin** — orchestrate, don't add logic
2. **Inject subsystems via constructor** — testability + flexibility
3. **Provide multiple facades** if subsystem is huge
4. **Don't force clients through facade** — expose subsystems for advanced use
5. **Document the contract** — clients depend on facade stability
6. **Use facade boundaries for caching/logging** — natural injection points

---

## 12. Key Takeaways

1. **Facade simplifies** a complex subsystem
2. Hides orchestration, exposes a clean API
3. **Not the same as Adapter or Proxy** — different intent
4. Used in SDKs (boto3, requests), BFF, service layer
5. Keep facade thin — beware God Class
6. Inject subsystems for testability

---

## Related
- [[06_Adapter_Pattern]] — interface translation
- [[Command_Composite_Proxy_Flyweight_Patterns]] — Proxy comparison
- [[13_service_layer]] — facade as architectural layer
