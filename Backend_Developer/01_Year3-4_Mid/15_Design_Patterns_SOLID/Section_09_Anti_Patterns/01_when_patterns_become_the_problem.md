# Anti-Patterns — When Patterns Become the Problem

> Every pattern has a cost: indirection. Paid without a matching pain, it's just tax. This section is the **"when NOT to"** half of pattern knowledge — and the half that separates senior answers from memorized ones.

## 1. Pattern-abuse anti-patterns

### Golden Hammer
Learning Strategy and turning every `if` into a class hierarchy. Symptom: 6 files to change a 2-line rule.
**Cure:** rule of three + "can a function do it?" ([Python idioms](../Section_07_Python_Idioms_vs_GoF/)).

### Singleton Abuse (the most-cited anti-pattern that's *also* a pattern)
```
Problems it creates:
  - Global mutable state — tests leak into each other, order matters
  - Hidden dependency — the signature lies about what the function needs
  - Concurrency hazards — shared state across threads/workers
  - Impossible to substitute in tests without monkeypatching
Legit uses: genuinely-one-per-process resources (connection pool, config,
logger) — and in Python those are just module-level objects or lru_cache
factories, injected via DI so tests can override.
```

### Poltergeist / Middle Man
Classes that exist only to call other classes (`OrderServiceHelperManager`). If removing it changes nothing, remove it.

### Speculative Generality (YAGNI violation)
`AbstractBaseProvider` with exactly one implementation, "for when we add more". The second implementation usually needs a *different* abstraction anyway — you'll rewrite it.

### Anemic Domain Model
Models are pure data bags; all behavior sits in `services.py`. It's procedural code wearing OOP clothes. Not always wrong (fine for CRUD), but if you're doing DDD, this defeats the point — see [`../../05_Microservices/09_domain_driven_design.md`](../../05_Microservices/09_domain_driven_design.md).

---

## 2. Architecture-level anti-patterns

| Anti-pattern | Symptom | Fix |
|---|---|---|
| **Big Ball of Mud** | No boundaries; everything imports everything | Modular monolith first; extract bounded contexts |
| **God Object** | `utils.py` with 4000 lines, `Order` doing payments+email+PDF | Split by reason-to-change |
| **Spaghetti / Lasagna** | Too little structure / too many pointless layers | Layers must earn their existence |
| **Distributed Monolith** | Microservices that must deploy together, sync-call chains | Async events, own the data ([anti-patterns file](../../05_Microservices/11_microservices_anti_patterns.md)) |
| **Vendor Lock-in by abstraction** | Wrapping every AWS SDK "in case we move" | Abstract at seams you'll actually swap |

---

## 3. Python-specific pattern smells

```python
# ❌ Java-style getters/setters — Python has properties
class User:
    def get_name(self): return self._name
    def set_name(self, v): self._name = v

# ✅
class User:
    name: str                       # just an attribute
    @property                       # add behavior LATER without changing callers
    def display_name(self) -> str: return self.name.title()
```

Others: `AbstractFactory` where a dict-of-callables suffices; interface classes with one implementation (`Protocol` if you need typing, else nothing); wrapping every function in a `Command` class when `partial` works; `metaclass` for something a decorator or `__init_subclass__` does more readably.

---

## 4. Observer/signals — the hidden control flow trap

```
Why signals feel great and age badly:
  - Control flow becomes invisible: "who deletes the S3 file when User dies?"
  - Ordering between handlers is implicit and fragile
  - Failures silently swallow or partially apply
  - Tests must remember to disconnect handlers
Use signals for TRUE decoupling (reacting to a 3rd-party app's models).
For your own code, an explicit service call is more readable and debuggable.
```
(See the fuller treatment in [`../../../00_Year0-2_Junior/07_Django_DRF/41_django_middleware_signals_testing_gaps.md`](../../../00_Year0-2_Junior/07_Django_DRF/41_django_middleware_signals_testing_gaps.md).)

---

## 5. The cost ledger — say this in interviews

| Pattern | Buys you | Costs you |
|---|---|---|
| Strategy | Runtime swap, open-closed | Indirection; more files |
| Factory | Decoupled creation | Hidden construction path |
| Observer | Decoupling | Invisible control flow, ordering issues |
| Decorator | Composable behavior | Deep stacks, painful tracebacks |
| Singleton | One instance | Global state, test pain |
| Repository | Swappable persistence, testability | A layer over the ORM that's already a layer |
| Abstract Factory | Family consistency | Rigidity when families diverge |

**Framing that lands:** *"Patterns aren't free — they trade concrete simplicity for flexibility at a specific axis. I add one when the change it anticipates has already hurt me at least twice, and I name the axis: 'this is Strategy because the pricing algorithm changes per market'."*

---

## 6. Refactoring OUT of a pattern

Removing a bad abstraction is normal engineering, not failure:
```
1. Inline the indirection at one call site; keep tests green
2. Repeat until only real variation remains
3. If ONE implementation is left → delete the interface
4. Simplify the caller's vocabulary back to plain code
```

---

## 7. Self-check

1. Why is Singleton both a GoF pattern and a canonical anti-pattern?
2. Your codebase has `AbstractPaymentProvider` with one subclass. Keep or delete? What decides?
3. What makes a "distributed monolith" worse than the monolith it replaced?
4. When are Django signals the right call, and when are they hidden control flow?
5. Name the cost of the last pattern you added to your code. If you can't, that's the finding.

---

**Related:** [Code Smells](../Section_03_Code_Smells_Refactoring/) · [Python Idioms](../Section_07_Python_Idioms_vs_GoF/) · [Microservices anti-patterns](../../05_Microservices/11_microservices_anti_patterns.md)
