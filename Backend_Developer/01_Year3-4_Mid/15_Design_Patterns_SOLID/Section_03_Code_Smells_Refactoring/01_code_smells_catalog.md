# Code Smells — The Symptoms That Call for Patterns

> Pattern without a smell = over-engineering. This section is the **diagnosis** step; sections 04-06 are the treatments.

## 1. Why smells come before patterns

A smell is a *surface indication* of a deeper design problem. It is not a bug — the code works. It's a signal that the next change will be expensive.

The discipline: **name the smell → check the rule of three → then pick a pattern.** Reversing that order is how codebases end up with `AbstractStrategyFactoryProvider` for two if-branches.

---

## 2. Bloaters — code that grew too big

| Smell | Symptom | Cure |
|---|---|---|
| **Long Method** | >30 lines, needs comments to navigate, multiple abstraction levels | Extract Method; if branches vary an algorithm → [Strategy](../Section_06_Behavioral/08_strategy.md) |
| **Large Class** | 500+ lines, 15 attributes, "Manager"/"Service" that does everything | Extract Class, split by [SRP](../Section_02_SOLID_Principles/01_single_responsibility.md) |
| **Long Parameter List** | `def create(a, b, c, d, e, f, g)` | Introduce Parameter Object (dataclass/Pydantic model); [Builder](../Section_04_Creational/) for step-wise construction |
| **Data Clumps** | Same 3-4 params always travel together (`lat, lng, radius`) | Bundle into a value object |
| **Primitive Obsession** | `str` for email/currency/user_id everywhere; validation scattered | Value objects, `NewType`, Pydantic types, `Enum` for magic strings |

```python
# Primitive obsession — validation duplicated at 6 call sites
def send_invoice(email: str, amount: float, currency: str): ...

# Cured — invalid states unrepresentable, validated once
class Email(BaseModel):
    value: EmailStr
class Money(BaseModel):
    amount: Decimal
    currency: Currency          # Enum, not str
def send_invoice(to: Email, total: Money): ...
```

---

## 3. Object-Orientation Abusers — OOP used wrong

| Smell | Symptom | Cure |
|---|---|---|
| **Switch/if-elif Statements** | Type-based branching repeated in several places | [Strategy](../Section_06_Behavioral/08_strategy.md), [State](../Section_06_Behavioral/07_state.md), polymorphism, or a dict of callables |
| **Temporary Field** | Attribute only set/valid during one operation | Extract Class, or pass as a parameter |
| **Refused Bequest** | Subclass inherits methods it doesn't want (`raise NotImplementedError`) | Composition over inheritance; [LSP](../Section_02_SOLID_Principles/03_liskov_substitution.md) violation |
| **Alternative Classes with Different Interfaces** | Two classes do the same thing with different method names | Unify interface, or [Adapter](../Section_05_Structural/) |

```python
# The #1 backend smell — type-branching that repeats
if payment.type == "card":     fee = amt * 0.02
elif payment.type == "upi":    fee = 0
elif payment.type == "wallet": fee = amt * 0.01
# ... and the same ladder again in refund(), in settle(), in report()

# Cured — one dict, or Strategy classes if behavior grows
FEE = {"card": lambda a: a * Decimal("0.02"),
       "upi": lambda a: Decimal(0),
       "wallet": lambda a: a * Decimal("0.01")}
fee = FEE[payment.type](amt)
```

---

## 4. Change Preventers — one change forces many edits

| Smell | Symptom | Cure |
|---|---|---|
| **Divergent Change** | One class changes for many unrelated reasons | Split by reason-to-change (SRP) |
| **Shotgun Surgery** | One logical change → edits in 8 files | Move Method/Field to consolidate; the inverse of divergent change |
| **Parallel Inheritance Hierarchies** | Every new `XHandler` forces a new `XValidator` | Collapse hierarchy, prefer composition |

**Backend example of shotgun surgery:** adding a new order status requires touching the model, serializer, 3 templates, a Celery task, and an admin filter — the status logic wants to be one [State](../Section_06_Behavioral/07_state.md) machine object.

---

## 5. Dispensables — things that shouldn't exist

Duplicate Code (the worst — DRY it *after* the third occurrence), Dead Code, Speculative Generality (abstractions "for the future" that never came — the YAGNI smell), Comments-as-deodorant (a comment explaining *what* the code does = the code should be renamed/extracted), Lazy Class, Data Class (getters/setters only, behavior lives elsewhere → Feature Envy's twin).

---

## 6. Couplers — objects too intimate

| Smell | Symptom | Cure |
|---|---|---|
| **Feature Envy** | Method uses another object's data more than its own | Move Method to where the data lives |
| **Inappropriate Intimacy** | Two classes reach into each other's internals | [Mediator](../Section_06_Behavioral/04_mediator.md), or merge/split them properly |
| **Message Chains** | `order.customer.address.city.name` | Hide Delegate; Law of Demeter |
| **Middle Man** | A class that only forwards calls | Remove it — unless it's a deliberate [Facade](../Section_05_Structural/)/Proxy |

---

## 7. The refactoring workflow (Django/FastAPI reality)

```
1. Pin behavior with tests FIRST (characterization tests if none exist)
2. Name the smell out loud — "this is shotgun surgery"
3. Rule of three — has it hurt 3 times? If not, wait.
4. Smallest refactoring that removes the smell (extract, move, rename)
5. Only NOW consider a pattern, if the smell keeps returning
6. Commit each refactor separately from behavior changes
```

**Fowler's rule that survives every code review:** *"Refactoring changes structure without changing behavior."* If your diff changes both, split the PR — reviewers can't verify a mixed diff, and neither can `git bisect`.

---

## 8. Self-check

1. What's the difference between Divergent Change and Shotgun Surgery? (Same problem, opposite directions.)
2. Why is Speculative Generality a smell when abstraction is "good design"?
3. Your view has a 12-branch `if request.user.role == ...` ladder used in 4 views — which smell, which cure?
4. When is a Middle Man class *not* a smell?
5. Why must characterization tests come before refactoring legacy code?

---

**Related:** [SOLID](../Section_02_SOLID_Principles/) · [Anti-Patterns](../Section_09_Anti_Patterns/) · [Python Idioms vs GoF](../Section_07_Python_Idioms_vs_GoF/)
