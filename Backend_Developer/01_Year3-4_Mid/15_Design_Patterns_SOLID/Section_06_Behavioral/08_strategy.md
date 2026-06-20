# Strategy

> The single most useful pattern. Most `if/elif` ladders in production code want to become Strategies.

## 1. Intent

Define a family of **interchangeable algorithms**, encapsulate each, and let the caller swap them at runtime.

## 2. Problem

A class needs to do task X using one of several algorithms (sorting, pricing, compression, retry logic), and the choice should be deferred to runtime.

Symptoms:
- `if mode == "fast": … elif mode == "accurate": …`
- A class with 5 variants of the same method.
- Hardcoding the algorithm into the class.

## 3. Solution (UML sketch)

```
┌──────────────┐         ┌──────────────────┐
│  Context     │◇──────> │  <<Strategy>>    │
├──────────────┤         ├──────────────────┤
│ -strategy    │         │ +algorithm(data) │
│ +do(data)    │         └──────────────────┘
└──────────────┘                  △
                         ┌────────┼────────┐
                  ┌─────────┐ ┌─────────┐ ┌─────────┐
                  │ Strat1  │ │ Strat2  │ │ Strat3  │
                  └─────────┘ └─────────┘ └─────────┘
```

## 4. Participants

- **Strategy** — interface for the algorithm.
- **ConcreteStrategy** — one implementation.
- **Context** — uses a Strategy; doesn't know which one.

## 5. Python implementations

### A) Classical — Protocol + classes

```python
from typing import Protocol

class TaxStrategy(Protocol):
    def calc(self, amount: float) -> float: ...

class IndiaGST:
    def calc(self, amount): return amount * 0.18

class USStateTax:
    def __init__(self, rate): self.rate = rate
    def calc(self, amount): return amount * self.rate

class NoTax:
    def calc(self, amount): return 0

class Invoice:
    def __init__(self, tax: TaxStrategy):
        self._tax = tax
    def total(self, subtotal):
        return subtotal + self._tax.calc(subtotal)

inv = Invoice(IndiaGST())
print(inv.total(100))                       # 118
```

### B) Pythonic — strategy as a function

In Python a Strategy is usually just a callable. No class required.

```python
def india_gst(amount):     return amount * 0.18
def us_state_tax(rate):    return lambda amount: amount * rate
def no_tax(_):             return 0

class Invoice:
    def __init__(self, tax_fn):
        self._tax_fn = tax_fn
    def total(self, subtotal):
        return subtotal + self._tax_fn(subtotal)

Invoice(india_gst).total(100)               # 118
Invoice(us_state_tax(0.0825)).total(100)    # 108.25
Invoice(no_tax).total(100)                  # 100
```

### C) Dict-dispatch (Strategy + Factory in one)

```python
STRATEGIES = {
    "gst":  india_gst,
    "us":   us_state_tax(0.0825),
    "none": no_tax,
}

Invoice(STRATEGIES["gst"]).total(100)
```

## 6. Backend examples

- **`sorted(items, key=…)`** — `key` is a Strategy.
- **`json.dumps(obj, default=…)`** — `default` is a Strategy for unknown types.
- **DRF authentication classes / permission classes** — Strategy list per view.
- **Cache backends** (Django: `CACHES = {"default": {"BACKEND": "..."}}`) — Strategy chosen by config.
- **Password hashers** (`PASSWORD_HASHERS` in Django).
- **Logging formatters** — each `Formatter` is a Strategy for `Handler`.
- **Pricing / shipping calculators** in e-commerce.
- **Retry policies** (`tenacity` — `wait`, `stop`, `retry` are all Strategies).

## 7. Pros / Cons

**Pros**
- Replace `if/elif` ladder with polymorphism.
- Algorithms become independently testable.
- New algorithm = new class/function; OCP satisfied.

**Cons**
- More classes/files (in classical form).
- Caller must know the strategy options.
- For only 2 stable variants, the overhead may not pay off.

**Don't use when**
- You have one stable algorithm.
- The strategies share state and a small ladder is clearer.

## 8. Strategy vs other patterns

| | Strategy | State | Template Method |
|---|---|---|---|
| Variation point | Whole algorithm | Behaviour per lifecycle stage | One step inside a fixed skeleton |
| Who picks | Caller | Object internal | Subclass (compile time) |

## 9. Related patterns

- **State** — same UML, different intent.
- **Factory Method** — often used to create the right Strategy.
- **Decorator** — wraps a Strategy with cross-cutting concerns.

## 9. Self-check

1. Why is `key=` on `sorted` a Strategy?
2. Pythonic Strategy needs neither inheritance nor a class. True/false — and how?
3. Difference between Strategy and State.
4. Give a Django/DRF place where Strategy is built in.
5. When is Strategy overkill?
