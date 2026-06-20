# Iterator

> In Python, this pattern is **mostly invisible** because `__iter__` / `__next__` and generators are first-class. Still asked in interviews.

## 1. Intent

Provide a way to access elements of a collection **sequentially** without exposing its underlying representation.

## 2. Problem

Collections come in many internal shapes — arrays, linked lists, trees, graphs, streams. Callers want a uniform "next element please" API. Hard-coding traversal couples callers to the structure.

## 3. Solution (UML sketch)

```
┌─────────────────┐           ┌─────────────────┐
│  <<Iterable>>   │ ────────> │  <<Iterator>>   │
├─────────────────┤  __iter__ ├─────────────────┤
│ +iter()         │           │ +next()         │
└─────────────────┘           └─────────────────┘
                                       │
                                       ▼
                          StopIteration when done
```

## 4. Participants

- **Iterable** — produces Iterators.
- **Iterator** — knows the position; `next()` returns the next element or raises `StopIteration`.

## 5. Python implementations

### A) Manual class — `__iter__` + `__next__`

```python
class Counter:
    def __init__(self, start, stop):
        self.cur, self.stop = start, stop
    def __iter__(self):
        return self                          # iterator IS itself
    def __next__(self):
        if self.cur >= self.stop:
            raise StopIteration
        v = self.cur; self.cur += 1
        return v

for x in Counter(0, 3): print(x)             # 0 1 2
```

### B) Separate Iterable and Iterator

For collections that must support multiple simultaneous iterations:

```python
class Range:
    def __init__(self, n): self.n = n
    def __iter__(self):
        return _RangeIter(self.n)            # fresh iterator each time

class _RangeIter:
    def __init__(self, n): self.n, self.i = n, 0
    def __iter__(self): return self
    def __next__(self):
        if self.i >= self.n: raise StopIteration
        v = self.i; self.i += 1
        return v

r = Range(3)
print(list(r), list(r))                      # works twice
```

### C) Generator — the Pythonic way

A generator function *is* an iterator. The GoF Iterator pattern collapses to `yield`:

```python
def counter(start, stop):
    cur = start
    while cur < stop:
        yield cur
        cur += 1

for x in counter(0, 3): print(x)
```

### D) Tree traversal

```python
class Node:
    def __init__(self, value, children=()):
        self.value, self.children = value, list(children)
    def __iter__(self):                       # depth-first
        yield self.value
        for c in self.children:
            yield from c                       # delegate to subtree

t = Node("A", [Node("B", [Node("D")]), Node("C")])
print(list(t))                                # ['A', 'B', 'D', 'C']
```

`yield from` makes recursive iteration trivial.

### E) Infinite iterators

Generators allow lazy infinite sequences:

```python
def naturals():
    i = 1
    while True:
        yield i; i += 1

from itertools import islice
print(list(islice(naturals(), 5)))            # [1,2,3,4,5]
```

## 6. Backend examples

- **Django querysets** — iterated lazily; each iteration fetches rows in chunks.
- **SQLAlchemy `yield_per`** — server-side cursor as Iterator.
- **`os.scandir`** — Iterator over directory entries, frees handles as you go.
- **`csv.reader`** — streaming Iterator over rows.
- **`asyncio` async iterators (`__aiter__`/`__anext__`)** — over async streams (WebSocket frames, Kafka messages).
- **HTTP streaming responses** — `iter_content()`, `iter_lines()`.

## 7. Pros / Cons

**Pros**
- Uniform traversal API.
- Lazy evaluation: don't materialise large collections.
- Supports infinite and streaming sources.

**Cons**
- Single-pass iterators surprise: after the first loop they're exhausted.
- Mixing iteration with mutation is bug-prone (the classic "mutate-while-iterating" error).

**Don't use when**
- You have a list and need random access — just use the list.
- You need to iterate the same data many times — return a fresh iterator each call.

## 8. Related patterns

- **Composite** — Composite trees are usually traversed via Iterators (`yield from`).
- **Visitor** — Visitor walks a structure via Iterator-ish traversal.
- **Generator pattern** (informal) — Python's `yield` is Iterator + Command + Coroutine in one.

## 9. Self-check

1. Difference between an iterable and an iterator.
2. What does `yield from` do that you'd otherwise write recursively?
3. Why is Django's queryset a (lazy) Iterator?
4. How does `__aiter__` differ from `__iter__`?
5. Show a 5-line generator that produces an infinite Fibonacci sequence.
