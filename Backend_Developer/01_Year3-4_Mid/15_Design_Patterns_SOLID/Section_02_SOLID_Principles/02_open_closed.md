# O — Open/Closed Principle (OCP)

## Statement (Bertrand Meyer)

> *Software entities should be open for extension, but closed for modification.*

Translation: when a new requirement arrives, you should be able to **add new code** rather than **edit existing, tested, deployed code**.

Why? Modifying tested code risks regressions. Adding new code only risks new bugs in the new code.

## The bad version — the `if/elif` ladder

```python
# BAD: every new payment type forces editing this function
class PaymentProcessor:
    def charge(self, method: str, amount: float):
        if method == "credit_card":
            # 30 lines of Stripe calls
            ...
        elif method == "paypal":
            # 40 lines of PayPal calls
            ...
        elif method == "upi":          # ← added 6 months later
            ...
        elif method == "crypto":       # ← added 6 months after that
            ...
        else:
            raise ValueError(f"unknown method {method}")
```

Every new payment type → edit `PaymentProcessor.charge`. The class is **open for modification, closed to extension** — exactly backwards.

## The fixed version — Strategy pattern (OCP made flesh)

```python
from typing import Protocol

class PaymentMethod(Protocol):
    def charge(self, amount: float) -> str: ...   # returns txn id

class StripePayment:
    def charge(self, amount: float) -> str:
        return "stripe-txn-..."

class PayPalPayment:
    def charge(self, amount: float) -> str:
        return "paypal-txn-..."

class UPIPayment:
    def charge(self, amount: float) -> str:
        return "upi-txn-..."

class PaymentProcessor:
    def __init__(self, method: PaymentMethod):
        self.method = method
    def charge(self, amount: float) -> str:
        return self.method.charge(amount)
```

Adding **Crypto** = create `CryptoPayment` class. `PaymentProcessor` and all existing payment classes stay **closed** to modification.

## Pythonic alternative — dict dispatch

For simple cases, you don't need a class hierarchy. A registry is enough:

```python
PAYMENT_METHODS: dict[str, Callable[[float], str]] = {}

def register(name):
    def deco(fn):
        PAYMENT_METHODS[name] = fn
        return fn
    return deco

@register("stripe")
def stripe_charge(amount):  return f"stripe-{amount}"

@register("paypal")
def paypal_charge(amount):  return f"paypal-{amount}"

# Use
PAYMENT_METHODS["stripe"](100)

# Extend without touching the dispatcher:
@register("crypto")
def crypto_charge(amount):  return f"crypto-{amount}"
```

The dict-of-callables is the **Pythonic Strategy** — OCP without the class ceremony.

## How OCP shows up in backend code

| Place | OCP applied |
|---|---|
| DRF serializers | Override `to_representation`, `to_internal_value` — base class never touched |
| Django middleware | Stack new middleware classes; framework's request flow stays closed |
| FastAPI dependency injection | `Depends(new_thing)` adds a dependency without editing the route |
| Celery tasks | New `@app.task` adds work; the worker code is closed |
| SQLAlchemy events | `event.listen(...)` extends behaviour without subclassing |

## Caveats — don't over-apply

1. **YAGNI.** Don't pre-build extension points "in case". Wait until the second variation arrives, then refactor.
2. **OCP is a target, not an absolute.** Some changes *will* require editing existing code. That's fine — OCP minimises it, doesn't ban it.
3. **Abstract too early = harder to read.** A 4-line `if/else` is fine. A 40-line ladder with no end in sight is not.

## SOLID linkage

OCP is enabled by:
- **Polymorphism** (LSP) — substitutable subtypes
- **Abstraction** (DIP) — depend on interfaces, not concretes

Most GoF patterns are OCP machinery: Strategy, Decorator, Factory Method, Template Method, Visitor.

## Self-check

1. State OCP and what "closed" specifically means.
2. Why is the `if/elif` ladder a problem at scale?
3. Give a Pythonic alternative to a Strategy class hierarchy.
4. When is OCP *over-applied*?
5. Name two backend frameworks where OCP is baked in via plugin/registry mechanisms.
