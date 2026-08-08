# Template Method

> Runnable version of this pattern: [`Design_Patterns_Code/09_template_method/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/09_template_method/) — `reports/generators.py` fixes the report-generation skeleton while subclasses override individual steps.

## 1. Intent

Define the **skeleton** of an algorithm in a base class, letting subclasses override specific steps **without** changing the algorithm's structure.

## 2. Problem

Several algorithms share the same overall flow but differ in a few steps. Inlining the flow in each subclass duplicates the skeleton; pulling out the steps into separate functions loses the structure.

Examples:
- ETL: extract → transform → load. Different sources differ in *how* to extract.
- HTTP requests: validate → authenticate → execute → serialise. Each endpoint customises a step or two.
- Test base classes: setUp → run → tearDown.

## 3. Solution (UML sketch)

```
┌────────────────────────────────┐
│   AbstractClass (template)     │
├────────────────────────────────┤
│ +template_method()             │  ← fixed skeleton
│ +step1()  (abstract)           │
│ +step2()  (hook, default)      │
│ -helper() (final)              │
└────────────────────────────────┘
              △
              │
┌────────────────────────────────┐
│   ConcreteClass                │
├────────────────────────────────┤
│ +step1()  (implemented)        │
│ +step2()  (overridden, optional)│
└────────────────────────────────┘
```

## 4. Participants

- **AbstractClass** — defines `template_method()` (the algorithm) and declares abstract/hook steps.
- **ConcreteClass** — overrides the steps.

## 5. Python implementation

### Beverage example (classic)

```python
from abc import ABC, abstractmethod

class Beverage(ABC):
    def make(self):                          # the Template Method
        self.boil_water()
        self.brew()
        self.pour_in_cup()
        if self.wants_condiments():
            self.add_condiments()

    def boil_water(self):  print("boiling water")
    def pour_in_cup(self): print("pouring into cup")

    @abstractmethod
    def brew(self): ...
    @abstractmethod
    def add_condiments(self): ...

    def wants_condiments(self):              # hook with a default
        return True

class Tea(Beverage):
    def brew(self):           print("steeping tea")
    def add_condiments(self): print("adding lemon")

class Coffee(Beverage):
    def brew(self):           print("dripping coffee")
    def add_condiments(self): print("adding sugar + milk")
    def wants_condiments(self): return False   # opt out

Tea().make()
Coffee().make()
```

### ETL pipeline — backend flavour

```python
class ETLJob(ABC):
    def run(self):                           # template method
        data    = self.extract()
        clean   = self.transform(data)
        self.load(clean)

    @abstractmethod
    def extract(self): ...
    def transform(self, data):               # hook with default
        return data
    @abstractmethod
    def load(self, data): ...

class CSVToWarehouse(ETLJob):
    def __init__(self, path): self.path = path
    def extract(self): return open(self.path).read().splitlines()
    def transform(self, rows): return [r.upper() for r in rows]
    def load(self, rows): print("warehouse <-", rows)
```

## 6. Backend examples

- **Django class-based views** — `View.dispatch()` is the Template Method. You override `get`, `post`, etc.
- **DRF `GenericAPIView`** — `list`, `create`, `retrieve`, `update`, `destroy` are mixin methods plugged into the template.
- **`unittest.TestCase`** — `setUp` / `tearDown` / `runTest` form a Template Method.
- **Django `Form.is_valid` / `clean`** — fixed skeleton calls `clean_<field>` hooks.
- **SQLAlchemy `Mapper.__init_subclass__`** — declarative base hooks into a fixed init flow.
- **Pydantic `BaseModel.__init__`** — fixed validation skeleton; you override `validator` methods.

## 7. Pros / Cons

**Pros**
- Reuses the algorithm structure across many variants.
- New step variants don't break siblings.
- Forces a consistent flow.

**Cons**
- Tight coupling between base and subclasses (inheritance).
- Hard to compose — you can't mix two templates easily.
- LSP risk if subclasses cheat the skeleton.

**Don't use when**
- The "shared skeleton" is 2 lines — a function with callbacks is simpler.
- You'd benefit from composition (Strategy) instead of inheritance.

## 8. Template Method vs Strategy

| | Template Method | Strategy |
|---|---|---|
| Mechanism | Inheritance + overridden hooks | Composition + delegation |
| Variation | Compile-time (subclass) | Runtime (swap object) |
| Skeleton owned by | Base class | Context |
| Multiple variation points | Easy (multiple hooks) | Multiple Strategy objects needed |

Template Method when there's one *family* with shared flow; Strategy when steps are independently swappable.

## 9. Related patterns

- **Factory Method** — Factory Method is often *one* of the hooks in a Template Method.
- **Strategy** — composition-based alternative.
- **Hollywood principle** ("don't call us, we'll call you") — Template Method's essence.

## 9. Self-check

1. Why is Template Method an example of the Hollywood Principle?
2. Where in Django CBVs is Template Method explicit?
3. When does Strategy beat Template Method?
4. What is a "hook" method?
5. Show how `unittest.TestCase` uses Template Method.
