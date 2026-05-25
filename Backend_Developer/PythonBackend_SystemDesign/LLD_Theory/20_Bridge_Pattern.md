# 20 — Bridge Pattern

> Structural pattern. Decouples an abstraction from its implementation so that both can vary independently.

> "Prefer composition over inheritance" — Bridge is one of the best examples of this principle.

---

## The Problem It Solves

You have two orthogonal dimensions of variation:
- Dimension A: shape (Circle, Square, Triangle).
- Dimension B: rendering API (OpenGL, DirectX, Vulkan).

Naive: inherit `Circle` → `OpenGLCircle`, `DirectXCircle`, `VulkanCircle`. Same for Square. Same for Triangle.

```
Shapes:   3
APIs:     3
Classes:  9 (3 × 3)
```

Add a new shape? 3 new classes.
Add a new API? 3 new classes.
**Combinatorial explosion.**

---

## Bridge Solution

Split into two hierarchies:
- **Abstraction**: Shape (has-a Renderer).
- **Implementor**: Renderer interface.

```
Shape -----composes-----> Renderer (interface)
  │                             │
  ├── Circle                    ├── OpenGLRenderer
  ├── Square                    ├── DirectXRenderer
  └── Triangle                  └── VulkanRenderer
```

Now: 3 shapes + 3 renderers = **6 classes** (linear, not multiplicative).

---

## Implementation

```python
from abc import ABC, abstractmethod
import math

# Implementor — varies independently
class Renderer(ABC):
    @abstractmethod
    def render_circle(self, x: float, y: float, radius: float): pass
    @abstractmethod
    def render_square(self, x: float, y: float, side: float):   pass


# Concrete Implementors
class OpenGLRenderer(Renderer):
    def render_circle(self, x, y, radius):
        print(f"OpenGL: circle at ({x}, {y}) r={radius}")

    def render_square(self, x, y, side):
        print(f"OpenGL: square at ({x}, {y}) s={side}")


class DirectXRenderer(Renderer):
    def render_circle(self, x, y, radius):
        print(f"DirectX: circle at ({x}, {y}) r={radius}")

    def render_square(self, x, y, side):
        print(f"DirectX: square at ({x}, {y}) s={side}")


class VulkanRenderer(Renderer):
    def render_circle(self, x, y, radius):
        print(f"Vulkan: circle at ({x}, {y}) r={radius}")

    def render_square(self, x, y, side):
        print(f"Vulkan: square at ({x}, {y}) s={side}")


# Abstraction
class Shape(ABC):
    def __init__(self, renderer: Renderer):
        self.renderer = renderer

    @abstractmethod
    def draw(self): pass


# Refined Abstractions
class Circle(Shape):
    def __init__(self, renderer, x, y, radius):
        super().__init__(renderer)
        self.x, self.y, self.radius = x, y, radius

    def draw(self):
        self.renderer.render_circle(self.x, self.y, self.radius)


class Square(Shape):
    def __init__(self, renderer, x, y, side):
        super().__init__(renderer)
        self.x, self.y, self.side = x, y, side

    def draw(self):
        self.renderer.render_square(self.x, self.y, self.side)


# Usage
shapes = [
    Circle(OpenGLRenderer(), 0, 0, 5),
    Square(DirectXRenderer(), 10, 10, 3),
    Circle(VulkanRenderer(), 5, 5, 2),
]

for s in shapes:
    s.draw()
```

Add new shape (Triangle): 1 new class, works with all renderers.
Add new renderer (Metal): 1 new class, works with all shapes.

---

## Structure

```
┌──────────────┐    ┌────────────────────┐
│  Abstraction │───►│   Implementor      │  (interface)
│              │    │                    │
│ + draw()     │    │ + operation_impl() │
└──────┬───────┘    └────────┬───────────┘
       │                     │
       │                ┌────┴─────┬─────────┐
       │                │          │         │
┌──────▼──────┐    ┌────▼────┐ ┌───▼────┐ ┌──▼─────┐
│   Circle    │    │ OpenGL  │ │DirectX │ │Vulkan  │
│             │    └─────────┘ └────────┘ └────────┘
│ + draw()    │
└─────────────┘
```

---

## When to use

- You have multiple orthogonal dimensions of variation.
- You want to switch implementations at runtime.
- You want both abstraction and implementation to evolve independently.

**Classic use case:** Cross-platform UI frameworks.

---

## Real-World Examples

### GUI Toolkits
- Abstraction: Button, Window, Menu.
- Implementor: WinAPI, Cocoa, GTK, X11.

### Database Drivers (JDBC / SQLAlchemy)
- Abstraction: SQL query interface (`session.execute`).
- Implementor: PostgreSQL driver, MySQL driver, SQLite driver.

### Notification Service
- Abstraction: Notification (Email, SMS, Push).
- Implementor: Provider (SendGrid, Twilio, FCM).

```python
class Notification:
    def __init__(self, sender: NotificationSender):
        self.sender = sender

    def notify(self, user, msg): ...

class EmailNotification(Notification):
    def notify(self, user, msg):
        self.sender.send(user.email, "Subject", msg)

class SMSNotification(Notification):
    def notify(self, user, msg):
        self.sender.send(user.phone, msg)

class SendGridSender(NotificationSender):
    def send(self, to, msg): ...

class TwilioSender(NotificationSender):
    def send(self, to, msg): ...
```

### Logging Framework
- Abstraction: Logger, with levels and formats.
- Implementor: file appender, syslog, kafka sink, stdout.

### Drawing Software (Tkinter, JavaFX)
Same shapes drawn via different backends.

### Cloud Provider Abstractions
- Abstraction: BlobStorage interface.
- Implementor: S3, Azure Blob, GCP Storage.

```python
class BlobStorage(ABC):
    @abstractmethod
    def upload(self, path, data): pass

class S3Backend(BlobStorage):
    def upload(self, path, data): ...

class AzureBackend(BlobStorage):
    def upload(self, path, data): ...

class FileService:
    def __init__(self, backend: BlobStorage):
        self.backend = backend

    def save(self, file, path):
        self.backend.upload(path, file.read())
```

Switching from S3 to Azure = swap the `backend`.

---

## Bridge vs Strategy

Both use composition. Differences:

| Bridge | Strategy |
|---|---|
| Structural | Behavioral |
| Two orthogonal hierarchies | One hierarchy of interchangeable algorithms |
| Often longer-lived (set at construction) | Swapped frequently at runtime |
| About varying impl independently | About varying behavior |

**Bridge:** "I'm a Circle drawn with OpenGL. I won't change my rendering API often."

**Strategy:** "I'm a SortContext. Today I sort with QuickSort, tomorrow with MergeSort."

---

## Bridge vs Adapter

| Bridge | Adapter |
|---|---|
| Designed up-front | Retrofitted |
| Both hierarchies evolve together | Wrapping incompatible interface |
| Composition through abstraction | Composition for compatibility |

**Adapter:** "I have legacy XML API but want to use it as JSON. Wrap it."

**Bridge:** "I'm designing a notification system that supports many providers from day 1."

---

## Trade-offs

### Pros
- ✓ Decouples abstraction from implementation.
- ✓ Both vary independently.
- ✓ Open/Closed Principle.
- ✓ Single Responsibility Principle.

### Cons
- ✗ Increased complexity if only one implementation.
- ✗ More indirection.
- ✗ Over-engineering for simple cases.

---

## Code Smell That Suggests Bridge

```python
class WindowsButton: ...
class MacButton: ...
class LinuxButton: ...

class WindowsCheckbox: ...
class MacCheckbox: ...
class LinuxCheckbox: ...
```

After 3 widgets × 3 OS = 9 classes. Add 4th widget (Slider) = 3 more. Add 4th OS = 4 more.

→ Bridge: split into Widget hierarchy + OS hierarchy.

---

## Python Specifics

Python's duck typing means you don't strictly need ABCs:

```python
class Circle:
    def __init__(self, renderer):
        self.renderer = renderer

    def draw(self):
        self.renderer.render_circle(self.x, self.y, self.radius)
```

Any object with `render_circle` works. Tests easier with mock renderers.

---

## Bridge with Configuration

Often in production, the implementation is chosen at startup via config:

```python
def make_renderer(config) -> Renderer:
    if config.platform == "windows":
        return DirectXRenderer()
    elif config.platform == "mac":
        return MetalRenderer()
    elif config.platform == "linux":
        return OpenGLRenderer()
    raise ValueError("Unsupported platform")

renderer = make_renderer(config)
shapes = [Circle(renderer, ...), Square(renderer, ...)]
```

Factory pattern often pairs with Bridge.

---

## Async Bridge

Modern Python: async implementations.

```python
class AsyncStorage(ABC):
    @abstractmethod
    async def upload(self, path, data): pass

class S3Async(AsyncStorage):
    async def upload(self, path, data):
        async with aioboto3.client("s3") as s3:
            await s3.put_object(Bucket=BUCKET, Key=path, Body=data)
```

Same Bridge pattern, async-flavored.

---

## Testing Benefit

Bridge naturally creates seam for tests:

```python
class MockRenderer(Renderer):
    def __init__(self):
        self.calls = []
    def render_circle(self, x, y, r):
        self.calls.append(("circle", x, y, r))

def test_circle_renders():
    mock = MockRenderer()
    c = Circle(mock, 0, 0, 5)
    c.draw()
    assert mock.calls == [("circle", 0, 0, 5)]
```

No need to actually render — pure unit test.

---

## In Modern Python (Dataclasses + Protocols)

Newer idiomatic version:

```python
from dataclasses import dataclass
from typing import Protocol

class Renderer(Protocol):
    def render_circle(self, x: float, y: float, radius: float) -> None: ...

@dataclass
class Circle:
    renderer: Renderer
    x: float
    y: float
    radius: float

    def draw(self):
        self.renderer.render_circle(self.x, self.y, self.radius)
```

`Protocol` + dataclass = minimal ceremony.

---

## Common Mistakes

### Bridge with only one implementor
If you'll never have a second implementor, it's needless complexity.

**Rule of three:** introduce abstraction when you have at least 3 concrete cases.

### Confused with Adapter
Bridge is up-front design; Adapter wraps legacy. Don't mix them up.

### Forgetting to keep dimensions orthogonal
Bridge works when dimensions don't bleed into each other. If Circle needs to call OpenGL-specific things, your abstraction is leaky.

---

## TL;DR

- Bridge separates abstraction from implementation.
- Avoid combinatorial class explosion.
- Both hierarchies evolve independently.
- Composition > inheritance.
- Common in: GUI toolkits, DB drivers, cloud abstractions, notification systems.
- Differs from Adapter (legacy wrap) and Strategy (swappable algorithm).
- Apply only when there are >= 2 dimensions with multiple variants each.
