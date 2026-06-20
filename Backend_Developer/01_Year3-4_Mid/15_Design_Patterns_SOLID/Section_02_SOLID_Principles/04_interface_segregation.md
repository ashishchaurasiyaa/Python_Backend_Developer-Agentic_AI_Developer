# I — Interface Segregation Principle (ISP)

## Statement

> *No client should be forced to depend on methods it does not use.*

Many small, focused interfaces > one big interface. If a class is forced to implement methods it doesn't need (with `pass` or `raise NotImplementedError`), the interface is too fat.

## The bad version — fat interface

```python
# BAD: Worker forces every implementation to also be edible and sleepy
from abc import ABC, abstractmethod

class Worker(ABC):
    @abstractmethod
    def work(self): ...
    @abstractmethod
    def eat(self): ...
    @abstractmethod
    def sleep(self): ...

class Human(Worker):
    def work(self):  print("typing")
    def eat(self):   print("lunch")
    def sleep(self): print("zzz")

class Robot(Worker):
    def work(self):  print("computing")
    def eat(self):   raise NotImplementedError    # robots don't eat
    def sleep(self): raise NotImplementedError    # robots don't sleep
```

`Robot` is **forced** to know about `eat` and `sleep`. A caller can't trust the interface; every method might raise.

## The fixed version — split interfaces

```python
class Workable(Protocol):
    def work(self): ...

class Eatable(Protocol):
    def eat(self): ...

class Sleepable(Protocol):
    def sleep(self): ...

class Human:
    def work(self):  print("typing")
    def eat(self):   print("lunch")
    def sleep(self): print("zzz")

class Robot:
    def work(self):  print("computing")    # only Workable
```

Each class implements *only what it actually does*. Each caller depends only on the slice it needs.

## ISP in Python via `typing.Protocol`

Python's `Protocol` is structural — there's no inheritance burden. Defining many small protocols is cheap:

```python
class Readable(Protocol):
    def read(self, n: int) -> bytes: ...

class Writable(Protocol):
    def write(self, data: bytes) -> None: ...

class Seekable(Protocol):
    def seek(self, pos: int) -> None: ...

def stream_copy(src: Readable, dst: Writable) -> None:
    while chunk := src.read(8192):
        dst.write(chunk)
```

`stream_copy` doesn't care whether `src` is seekable — it asks for the minimum.

This is straight out of `collections.abc` / `io` — `IOBase`, `RawIOBase`, `BufferedIOBase`, `TextIOBase` are layered by capability for the same reason.

## How ISP shows up in backend code

| Smell | Fix |
|---|---|
| A repository class with `save`, `find`, `bulk_insert`, `archive`, `export_csv`, `import_csv` — and half its consumers only need `find` | Split into `Reader`, `Writer`, `Exporter` protocols |
| A `Notifier` interface with `send_email`, `send_sms`, `send_push` — concrete senders forced to no-op the others | One `Notifier` interface with `send(message)`; sub-types per channel |
| DRF serializers crammed with create + update + bulk + soft-delete | Use mixins per capability |
| A FastAPI dependency that returns a 12-method object but consumers use 2 methods | Return a narrower protocol |

## ISP vs SRP — easy confusion

| | SRP | ISP |
|---|---|---|
| About | The **class** | The **interface** |
| Asks | How many reasons does this class change? | How many methods does each client need? |
| Pain | Class does too many things | Client depends on methods it doesn't use |

A class can satisfy SRP but still violate ISP (one responsibility, fat interface).

## When to *not* split

- Protocols with 2-3 cohesive methods are usually fine. Splitting `Cache` into `Getter` + `Setter` is over-zealous.
- If every implementation needs every method, the interface isn't fat — it's just rich.

## SOLID linkage

- ISP supports **DIP** (you can depend on the narrowest abstraction).
- It supports **OCP** (small interfaces have fewer reasons to change).
- Patterns most affected: **Adapter, Facade, Proxy** (they all advertise focused interfaces).

## Self-check

1. State ISP.
2. Why is `raise NotImplementedError` in a subclass an ISP smell?
3. How does Python's `Protocol` make ISP cheap?
4. Difference between SRP and ISP in one line.
5. When is splitting interfaces *too much*?
