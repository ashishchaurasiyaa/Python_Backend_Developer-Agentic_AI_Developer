# UML Class Diagrams — LLD Essential

## WHAT

UML (Unified Modeling Language) Class Diagrams visually represent the **structure of classes** — their attributes, methods, and relationships. Used in LLD to communicate design before writing code.

---

## Class Notation

```
┌──────────────────────────┐
│  <<stereotype>>          │  ← optional tag (interface, abstract)
│       ClassName          │  ← class name (bold, uppercase start)
├──────────────────────────┤
│  - private_attr: Type    │  ← attributes
│  + public_attr: Type     │
│  # protected_attr: Type  │
│  __slots__               │
├──────────────────────────┤
│  + method(param: Type)   │  ← methods
│    : ReturnType          │
│  - _helper(): None       │
└──────────────────────────┘

Visibility:
  +  public
  -  private
  #  protected
  ~  package (Python: module-level)
```

---

## Relationships (Most Important!)

### 1. Association — "uses"
A class has a reference to another. Weakest relationship.

```
LLMClient ──────────── Logger
          uses (has a reference)
```

```python
class LLMClient:
    def __init__(self, logger: Logger):
        self.logger = logger   # association
```

### 2. Aggregation — "has-a" (weak ownership)
One class contains others, but they can exist independently.

```
Department ◇──────── Employee
           "has many Employees"
           (Employee can exist without Department)
```

```python
class Department:
    def __init__(self):
        self.employees: list[Employee] = []   # aggregation
    
    def add_employee(self, emp: Employee):
        self.employees.append(emp)
```

### 3. Composition — "owns" (strong ownership)
One class owns others. Contained objects die with the container.

```
ChatSession ◆──────── Message
             "owns Messages"
             (Messages don't exist without ChatSession)
```

```python
class ChatSession:
    def __init__(self):
        self.messages: list[Message] = []   # composition
    
    def add_message(self, role: str, content: str):
        self.messages.append(Message(role, content))  # creates Message
```

### 4. Inheritance — "is-a"
```
        BaseAgent
           △ (hollow triangle = inheritance)
           │
     ┌─────┴──────┐
     │             │
 LLMAgent    ToolAgent
```

```python
class BaseAgent:
    def run(self): ...

class LLMAgent(BaseAgent): ...
class ToolAgent(BaseAgent): ...
```

### 5. Interface / Abstract (Realization)
```
<<interface>>        <<abstract>>
LLMProvider          BaseStorage
     ▲ (dashed)           ▲
     │                    │
OpenAIClient          S3Storage
```

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list) -> str: ...

class OpenAIClient(LLMProvider):
    def complete(self, messages: list) -> str: ...
```

### 6. Dependency — "depends on" (dashed arrow)
```
OrderService ──────> PaymentGateway
             (dashed: uses temporarily)
```

```python
class OrderService:
    def checkout(self, order: Order, gateway: PaymentGateway):
        # gateway is parameter, not stored → dependency
        gateway.charge(order.total)
```

---

## Multiplicity

```
1    → exactly one
0..1 → zero or one (optional)
*    → zero or more
1..* → one or more
n..m → n to m

Examples:
  User 1 ──── 0..* Post    (one user has 0 or more posts)
  Order 1 ──── 1..* Item   (one order has 1+ items)
  User 0..1 ──── 1 Profile (user may have a profile)
```

---

## Full LLD Example: Parking Lot

```
┌─────────────────────────────────────────────────────────────────┐
│  <<abstract>>                                                   │
│  Vehicle                                                        │
├─────────────────────────────────────────────────────────────────┤
│  - license_plate: str                                           │
│  - vehicle_type: VehicleType                                    │
├─────────────────────────────────────────────────────────────────┤
│  + get_type(): VehicleType                                      │
└─────────────────────┬───────────────────────────────────────────┘
                       △
          ┌────────────┼────────────┐
          │            │            │
      ┌───────┐   ┌──────────┐  ┌──────┐
      │  Car  │   │  Truck   │  │ Bike │
      └───────┘   └──────────┘  └──────┘

┌──────────────────┐  1    ┌──────────────────────────┐
│  ParkingSpot     │ ──── 0..1 │  Vehicle                 │
├──────────────────┤       └──────────────────────────┘
│ - spot_id: str   │
│ - spot_type: Type│
│ - is_available:  │
│   bool           │
├──────────────────┤
│ + park(v): bool  │
│ + leave(): None  │
└──────────────────┘

┌──────────────────┐  1    ┌─────────────────────────┐
│  ParkingFloor    │◆────*  │  ParkingSpot             │
├──────────────────┤ owns  └─────────────────────────┘
│ - floor_id: str  │
│ - spots: list    │
├──────────────────┤
│ + get_free(): [] │
└──────────────────┘

┌────────────────────┐  1   ┌───────────────────────┐
│  ParkingLot        │◆───* │  ParkingFloor          │
├────────────────────┤owns  └───────────────────────┘
│ - name: str        │
│ - floors: list     │
├────────────────────┤ uses ┌───────────────────────┐
│ + park(v): Ticket  │─────►│  Ticket               │
│ + unpark(t): float │      ├───────────────────────┤
└────────────────────┘      │ - ticket_id: str      │
                             │ - entry_time: datetime│
                             │ - spot: ParkingSpot   │
                             └───────────────────────┘
```

---

## Python Code from UML

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto

class VehicleType(StrEnum):
    CAR   = auto()
    TRUCK = auto()
    BIKE  = auto()

class SpotType(StrEnum):
    COMPACT  = auto()
    REGULAR  = auto()
    LARGE    = auto()

class Vehicle(ABC):
    def __init__(self, license_plate: str):
        self.license_plate = license_plate
    
    @abstractmethod
    def get_type(self) -> VehicleType: ...

class Car(Vehicle):
    def get_type(self) -> VehicleType: return VehicleType.CAR

class Truck(Vehicle):
    def get_type(self) -> VehicleType: return VehicleType.TRUCK

@dataclass
class ParkingSpot:
    spot_id:       str
    spot_type:     SpotType
    _vehicle:      Vehicle | None = field(default=None, init=False)
    
    @property
    def is_available(self) -> bool:
        return self._vehicle is None
    
    def park(self, vehicle: Vehicle) -> bool:
        if not self.is_available:
            return False
        self._vehicle = vehicle
        return True
    
    def leave(self) -> Vehicle | None:
        v, self._vehicle = self._vehicle, None
        return v

@dataclass
class Ticket:
    ticket_id:  str
    spot:       ParkingSpot
    entry_time: datetime = field(default_factory=datetime.now)

class ParkingFloor:
    def __init__(self, floor_id: str, spot_counts: dict[SpotType, int]):
        self.floor_id = floor_id
        self.spots: list[ParkingSpot] = [
            ParkingSpot(f"{floor_id}-{t}-{i}", t)
            for t, count in spot_counts.items()
            for i in range(count)
        ]
    
    def get_free_spot(self, spot_type: SpotType) -> ParkingSpot | None:
        return next(
            (s for s in self.spots
             if s.spot_type == spot_type and s.is_available),
            None
        )
```

---

## Reading UML: Quick Reference Card

```
Arrow types:
  ─────────►   association / dependency (dashed = dependency)
  ──────────◇  aggregation (hollow diamond at owner end)
  ──────────◆  composition (filled diamond at owner end)
       △         inheritance (hollow triangle, points to parent)
  - - - - △   realization/interface (dashed + hollow triangle)
  - - - - ►   dependency (dashed arrow)

Multiplicity (near arrow ends):
  1      0..1    *    1..*    2..5
```

---

## Interview Q&A

**Q: What is the difference between aggregation and composition?**
A: Composition = strong ownership. The child CANNOT exist without the parent (Chat → Messages: messages are deleted when chat is deleted). Aggregation = weak ownership. The child CAN exist independently (Department → Employees: employee exists even if department is dissolved).

**Q: When should you draw a UML diagram in an interview?**
A: After gathering requirements and before coding. Sketch the main classes, their relationships, and key methods. Shows you think at design level, not just code level. Keep it simple — 5-8 classes max.

**Q: What does "Favor composition over inheritance" mean?**
A: Instead of subclassing to add behavior, hold a reference to an object that provides the behavior. More flexible: you can swap implementations at runtime. Example: instead of LoggingLLMClient(LLMClient), use LLMClient with a Logger instance.
