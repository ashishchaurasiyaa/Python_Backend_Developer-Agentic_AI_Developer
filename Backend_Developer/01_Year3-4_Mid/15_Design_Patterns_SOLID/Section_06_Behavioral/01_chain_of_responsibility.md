# Chain of Responsibility (CoR)

## 1. Intent

Pass a request along a **chain of handlers**. Each handler decides to process it, pass it on, or stop the chain.

## 2. Problem

You have a sequence of checks/transformations to apply to a request, but:
- The exact sequence changes per route/feature.
- Each handler is independent and should be testable alone.
- The chain should short-circuit when a handler "claims" the request.

Examples: authentication → rate limiting → input validation → logging → business handler.

Symptoms:
- A 200-line `process()` with `if/elif` for each concern.
- Concerns intertwined and impossible to disable individually.

## 3. Solution (UML sketch)

```
┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐
│Handler1│──> │Handler2│──> │Handler3│──> │  End   │
└────────┘    └────────┘    └────────┘    └────────┘
   │              │              │
   ▼              ▼              ▼
 handle or pass on (each owns the decision)
```

## 4. Participants

- **Handler** — interface declaring `handle(request)`; holds a reference to the next handler.
- **ConcreteHandler** — processes the request or forwards it.
- **Client** — builds the chain.

## 5. Python implementation

### Classical CoR

```python
from typing import Optional

class Handler:
    def __init__(self): self._next: Optional["Handler"] = None
    def set_next(self, h: "Handler") -> "Handler":
        self._next = h; return h               # fluent
    def handle(self, request):
        if self._next:
            return self._next.handle(request)
        return None

class AuthHandler(Handler):
    def handle(self, req):
        if not req.get("user"):
            return ("401", "no user")
        return super().handle(req)

class RateLimitHandler(Handler):
    def handle(self, req):
        if req.get("user") == "spammer":
            return ("429", "slow down")
        return super().handle(req)

class BusinessHandler(Handler):
    def handle(self, req):
        return ("200", f"hello {req['user']}")

# Build
chain = AuthHandler()
chain.set_next(RateLimitHandler()).set_next(BusinessHandler())

print(chain.handle({"user": "ash"}))      # ('200', 'hello ash')
print(chain.handle({"user": "spammer"}))  # ('429', 'slow down')
print(chain.handle({}))                   # ('401', 'no user')
```

### Pythonic — list of callables

```python
def auth(req, nxt):
    if not req.get("user"): return ("401", "no user")
    return nxt(req)

def rate_limit(req, nxt):
    if req.get("user") == "spammer": return ("429", "slow down")
    return nxt(req)

def business(req, nxt=None):
    return ("200", f"hello {req['user']}")

def chain(*handlers):
    def call(req, i=0):
        if i == len(handlers) - 1:
            return handlers[i](req)
        return handlers[i](req, lambda r: call(r, i + 1))
    return call

pipeline = chain(auth, rate_limit, business)
pipeline({"user": "ash"})
```

This is exactly **how WSGI / Starlette / Django middleware works**.

## 6. Backend examples

- **Django middleware** — each middleware wraps the next, can short-circuit by returning a `Response`.
- **Starlette / FastAPI middleware stack** — pure CoR.
- **WSGI middleware** — same pattern, older spec.
- **DRF authentication/permission classes** — checked in order, first failure stops the chain.
- **Logging propagation** — each `Logger` passes the record up to its parent unless `propagate=False`.
- **`atexit` / `signal` chains** — registered callbacks run in order; one can suppress the rest.

## 7. Pros / Cons

**Pros**
- Each handler is single-responsibility and unit-testable.
- Chain is configurable without code changes.
- Easy to add/remove/reorder.

**Cons**
- Hard to see the *whole* flow at a glance — debugging means stepping through the chain.
- A handler that forgets to call `next` silently drops requests.
- Hidden order dependencies.

**Don't use when**
- The flow is fixed and short; an inline function is clearer.
- You need all handlers to run regardless — that's a pipeline, not CoR (CoR short-circuits).

## 8. Related patterns

- **Decorator** — also wraps; Decorator typically *always* delegates; CoR can stop.
- **Command** — handlers in CoR may carry Command-like requests.
- **Composite** — trees of handlers (rare).

## 9. Self-check

1. Difference between CoR and Decorator.
2. Why is Django middleware a Chain of Responsibility?
3. What's the most common bug in CoR implementations?
4. State a case where CoR is wrong (a pipeline is better).
5. Write the Pythonic CoR using closures in 6 lines.
