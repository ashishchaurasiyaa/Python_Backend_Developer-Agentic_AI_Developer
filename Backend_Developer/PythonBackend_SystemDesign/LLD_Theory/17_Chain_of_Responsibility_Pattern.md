# Chain of Responsibility Pattern

> **Category:** Behavioral Design Pattern
> **Intent:** Pass a request along a **chain of handlers**. Each handler either processes the request or passes it to the next.

---

## 1. Problem Statement

A request needs to go through **multiple checks/steps**, but you don't want one giant `if-elif-else` block.

Examples:
- HTTP request → auth → rate-limit → log → handler
- Support ticket → L1 → L2 → L3 escalation
- Expense approval → manager → director → VP → CEO
- Exception handler → try specific → general → log → re-raise

**Solution:** Form a linked chain. Each link decides: handle it, or pass it on.

---

## 2. Real-World Analogies

- **Office hierarchy** — leave request → team lead → manager → HR director
- **Bank loan approval** — loan officer → senior officer → branch manager
- **ATM cash dispenser** — try 1000s → then 500s → then 100s
- **JavaScript event bubbling** — propagates through DOM

---

## 3. Structure (UML)

```
Client ──→ Handler1 ──→ Handler2 ──→ Handler3 ──→ ...
              │             │             │
           handle()      handle()      handle()
              ↓             ↓             ↓
          [done?]       [done?]       [done?]
            │             │             │
           Yes/No        Yes/No        Yes/No
```

---

## 4. Two Variants

### Variant A: "Stop at first match" (validation pipeline)
First handler that can handle returns result; others skipped.
Example: error code → exception handlers.

### Variant B: "Pass through all" (middleware pipeline)
Every handler processes, then passes to next.
Example: HTTP middleware (auth + log + CORS).

---

## 5. Python Implementation

### Approach 1: Classic OOP
```python
from abc import ABC, abstractmethod

class Handler(ABC):
    def __init__(self):
        self._next = None
    def set_next(self, handler):
        self._next = handler
        return handler   # for chaining

    @abstractmethod
    def handle(self, request): ...

    def _next_handle(self, request):
        if self._next:
            return self._next.handle(request)
        return None

class AuthHandler(Handler):
    def handle(self, request):
        if not request.get("token"):
            return {"error": "Unauthorized"}
        return self._next_handle(request)

class RateLimitHandler(Handler):
    def handle(self, request):
        if request.get("ip") in BLACKLIST:
            return {"error": "Too many requests"}
        return self._next_handle(request)
```

### Approach 2: Function pipeline (Pythonic)
```python
def auth(handler):
    def wrapper(req):
        if not req.get("token"):
            return {"error": "Unauthorized"}
        return handler(req)
    return wrapper

def rate_limit(handler):
    def wrapper(req):
        if rate_limited(req["ip"]):
            return {"error": "Too many requests"}
        return handler(req)
    return wrapper

@auth
@rate_limit
def my_handler(req):
    return {"data": "ok"}
```

### Approach 3: List-based chain
```python
def process_chain(request, handlers):
    for handler in handlers:
        result = handler(request)
        if result is not None:
            return result
    return None
```

---

## 6. Use Cases

### ✅ Use when:
- Multiple handlers, each conditional
- Decoupling sender from receiver
- Pipeline of validators / filters
- Order of handlers may change
- New handlers added dynamically

### ❌ Don't use when:
- Simple if-else suffices
- Order doesn't matter
- All handlers must run (use middleware/event pattern instead)

---

## 7. Real Production Examples

### Example 1: HTTP middleware (Django, Flask, FastAPI)
```python
# Django middleware chain
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Each one wraps the next
]
```

### Example 2: Exception handlers
```python
try:
    do_work()
except SpecificError as e:
    handle_specific(e)
except GeneralError as e:
    handle_general(e)
except Exception as e:
    log_and_reraise(e)
```

### Example 3: ATM cash dispenser
```python
class Dispenser:
    def __init__(self, denom, next_=None):
        self.denom = denom
        self.next = next_
    def dispense(self, amount):
        if amount >= self.denom:
            count = amount // self.denom
            print(f"  Dispense {count} x ₹{self.denom}")
            amount %= self.denom
        if amount > 0 and self.next:
            self.next.dispense(amount)
```

### Example 4: Expense approval
Auto-pass <$100 → manager <$1000 → director <$10000 → VP <$100000 → CEO unlimited.

### Example 5: Log filters
Log message → DEBUG filter → INFO filter → ERROR filter → archive.

### Example 6: AI/ML preprocessing pipeline
Raw text → strip whitespace → lowercase → remove stopwords → stem → tokenize.

---

## 8. Pitfalls

### Pitfall 1: No handler matches → request lost
Always have a **default fallback** at end of chain.

### Pitfall 2: Long chain = hard to debug
Add logging at each handler. Use chain visualizer.

### Pitfall 3: Mutable request shared across handlers
Beware accidental mutation. Either deep-copy or use immutable request.

### Pitfall 4: Circular chain
Builder logic mistake → loop. Validate at construction time.

### Pitfall 5: Order matters but isn't documented
Order is implicit and fragile. Use explicit `priority` or named handlers.

---

## 9. Chain vs Other Patterns

| Pattern | Difference |
|---|---|
| **CoR** | Each handler may stop the chain |
| Pipeline | All steps always run (transform) |
| Decorator | Wraps and adds behavior to single object |
| Strategy | Replace single algorithm |
| Middleware | Special CoR for HTTP/RPC |

---

## 10. Interview Questions

**Q1: CoR vs Decorator?**
- CoR: chain of handlers, can short-circuit
- Decorator: stacks layers around single core, all run

**Q2: CoR vs Middleware?**
Middleware is a CoR specialization for request/response, usually with pre + post processing per handler.

**Q3: Real-world CoR?**
- Django middleware
- ASGI/WSGI middleware
- Servlet filters in Java
- Express.js next() chain

**Q4: How to ensure chain ends correctly?**
Add a **terminal handler** that handles the default case (404, log, etc.).

**Q5: Sync vs async chain?**
For I/O, prefer async — handlers can `await`. FastAPI middleware is async.

**Q6: Performance impact?**
Linear: O(N) for N handlers. Each adds overhead. Optimize ordering — cheapest checks first.

---

## 11. Best Practices

1. **Always include a terminal handler** for unhandled cases
2. **Document chain order** — fragile to refactor otherwise
3. **Keep handlers single-purpose** — one check per handler
4. **Use immutable requests** to prevent leaks
5. **Add metrics** — handler-level latency, drops
6. **Make chain configurable** — registry/builder pattern
7. **Combine with Builder** for complex chains

---

## 12. Key Takeaways

1. **CoR = sequential handler chain** with short-circuit option
2. Decouples sender from receiver
3. Two variants: stop-at-first vs pass-through-all (middleware)
4. Used everywhere: middleware, exception handlers, ATM, validation
5. Use **decorator-stack** pattern in Pythonic code
6. Always include fallback / terminal handler

---

## Related
- [[11_Command]] — encapsulate request as object
- [[05_Decorator_Pattern]] — single-object enhancement
- [[Command_Composite_Proxy_Flyweight_Patterns]] — related behavioral
