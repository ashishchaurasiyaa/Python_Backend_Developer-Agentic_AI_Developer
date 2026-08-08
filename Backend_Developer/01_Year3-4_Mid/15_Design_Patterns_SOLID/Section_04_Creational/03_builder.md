# Builder

> Runnable version of this pattern: [`Design_Patterns_Code/06_builder/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/06_builder/) — `sap_builder` constructs SAP B1 documents step by step.

## 1. Intent

Construct a **complex object** step by step. The same construction process can create different representations.

## 2. Problem

A constructor with **many parameters** — especially optional / order-sensitive ones — becomes unreadable:

```python
# BAD
order = Order(
    customer_id=1, items=[...], shipping="express",
    tax_inclusive=True, gift_wrap=False, promo_code=None,
    notes="", currency="INR", warehouse_id=42,
    insurance=True, payment_token=None, ...
)
```

Symptoms:
- Constructors with 6+ parameters.
- Lots of `None` defaults the caller must remember.
- The object passes through partial states during creation that the type system can't express.

## 3. Solution (UML sketch)

```
┌────────────┐        ┌──────────────┐
│  Director  │───────>│   Builder    │
└────────────┘        ├──────────────┤
                      │ +reset()     │
                      │ +add_part_a()│
                      │ +add_part_b()│
                      │ +get_result()│
                      └──────────────┘
                              △
                              │
                  ┌───────────┴───────────┐
                  │                       │
          ┌──────────────┐         ┌──────────────┐
          │ConcreteBldrA │         │ConcreteBldrB │
          └──────────────┘         └──────────────┘
```

`Director` (optional) orchestrates a recipe. `Builder` exposes step methods and a terminal `build()`.

## 4. Participants

- **Builder** — interface declaring the construction steps.
- **ConcreteBuilder** — implements steps and stores the in-progress product.
- **Product** — the complex object being assembled.
- **Director** *(optional)* — a recipe / sequence of calls.

## 5. Python implementation

### Fluent builder (most common Python flavour)

```python
from dataclasses import dataclass, field

@dataclass
class Order:
    customer_id: int
    items: list[dict] = field(default_factory=list)
    shipping: str = "standard"
    promo_code: str | None = None
    gift_wrap: bool = False
    notes: str = ""

class OrderBuilder:
    def __init__(self, customer_id: int):
        self._order = Order(customer_id=customer_id)

    def add_item(self, sku: str, qty: int):
        self._order.items.append({"sku": sku, "qty": qty})
        return self                              # fluent

    def express(self):
        self._order.shipping = "express"; return self

    def gift_wrap(self):
        self._order.gift_wrap = True; return self

    def promo(self, code: str):
        self._order.promo_code = code; return self

    def note(self, text: str):
        self._order.notes = text; return self

    def build(self) -> Order:
        if not self._order.items:
            raise ValueError("order must have items")
        return self._order

# Usage
order = (OrderBuilder(customer_id=1)
         .add_item("SKU-1", 2)
         .add_item("SKU-2", 1)
         .express()
         .gift_wrap()
         .promo("DIWALI20")
         .build())
```

### Pythonic alternative — kwargs + dataclass

Often a `@dataclass` with defaults *is* the builder Python wants:

```python
@dataclass
class Order:
    customer_id: int
    items: list[dict] = field(default_factory=list)
    shipping: str = "standard"
    gift_wrap: bool = False

order = Order(customer_id=1, shipping="express", gift_wrap=True)
order.items.append({"sku": "X", "qty": 1})
```

Use the explicit Builder when:
- Construction has **rules** between steps (mutually exclusive, ordering, validation at end).
- The same recipe should produce **different products** (the Director angle).
- You want a typed "in-progress" stage where the partially-built object is not exposed.

## 6. Backend examples

- **SQLAlchemy queries** — `session.query(User).filter(...).join(...).order_by(...).limit(10).all()` is a builder; `.all()` is `build()`.
- **Django ORM querysets** — `User.objects.filter(active=True).exclude(...).order_by("name")[:10]` — same idea, lazily evaluated.
- **HTTP clients** — `httpx.Client().build_request(...)`, requests' `PreparedRequest`.
- **Boto3 paginators** — `paginator.paginate(...).build_full_result()`.
- **Pydantic `model_construct`** — bypasses validation and assembles incrementally.

## 7. Pros / Cons

**Pros**
- Readable construction of complex objects.
- Step validation; refuse invalid combinations at `build()`.
- Separates "recipe" (Director) from "ingredients" (Builder).

**Cons**
- Extra class per Builder; boilerplate.
- For simple objects, a constructor or dataclass is shorter.

**Don't use when**
- Object has < 4 params and no inter-step rules.
- A `dict` of kwargs would do.

## 8. Related patterns

- **Abstract Factory** — both create complex objects. AF returns a *family at once*; Builder builds *one* thing step-by-step.
- **Composite** — Builders often build Composites (trees).
- **Fluent interface** — a Pythonic style for Builders (return `self`).

## 9. Self-check

1. Why is "too many constructor params" the canonical Builder smell?
2. What does the Director add over a plain Builder?
3. Why is SQLAlchemy's query API a Builder?
4. When does a `@dataclass` with defaults replace a Builder?
5. Difference between Builder and Abstract Factory in one line.
