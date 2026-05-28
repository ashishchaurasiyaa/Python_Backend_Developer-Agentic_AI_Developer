# Iterator Pattern

> **Category:** Behavioral Design Pattern
> **Intent:** Provide a way to **traverse a collection** without exposing its internal structure.

---

## 1. Problem Statement

Different collections (list, tree, graph, file, DB result set) have **different internal structures**. Clients shouldn't need to know.

Iterator gives a **uniform interface** — `next()` until exhausted. Same client code works for arrays, linked lists, trees, paginated APIs, etc.

---

## 2. Python is Iterator-Native

Python ka **language-level support** hai for iterators — `for` loop ke peeche iterator protocol use hota hai.

### Iterator Protocol
```python
class MyIterator:
    def __iter__(self):
        return self
    def __next__(self):
        if done:
            raise StopIteration
        return next_value
```

### Iterable Protocol
Iterable = anything with `__iter__()` returning an iterator.
```python
class MyCollection:
    def __iter__(self):
        return MyIterator(...)
```

### Built-ins are all iterable
- `list`, `tuple`, `set`, `dict`, `str` — all iterable
- `file objects` — iterate lines
- `generators` — built-in iterator
- `range`, `zip`, `map`, `filter`

---

## 3. Three Ways to Implement Iterator in Python

### Way 1: Custom class with `__iter__` + `__next__`
```python
class CountDown:
    def __init__(self, start):
        self.current = start
    def __iter__(self):
        return self
    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1
```

### Way 2: Generator function (cleanest)
```python
def countdown(start):
    while start > 0:
        yield start
        start -= 1
```

### Way 3: Generator expression
```python
squares = (x*x for x in range(10))
```

**Modern Python: prefer generators.** Less boilerplate.

---

## 4. Iterable vs Iterator (Critical Distinction)

| | Iterable | Iterator |
|---|---|---|
| Has | `__iter__` | `__iter__` + `__next__` |
| Returns | New iterator each call | Itself |
| Multi-pass | ✅ Yes | ❌ Single-use |
| Example | `list`, `set`, `dict` | `iter(list)`, generators |

```python
nums = [1, 2, 3]
print(iter(nums) is iter(nums))   # False — new iterator each time
gen = (x for x in nums)
print(iter(gen) is iter(gen))     # True — generator IS its own iterator
```

---

## 5. Real-World Production Use Cases

### Use Case 1: Streaming large files
```python
def read_large_file(path):
    with open(path) as f:
        for line in f:    # iterator — no full file in memory
            yield line.strip()
```

### Use Case 2: Paginated API client
```python
class APIPaginator:
    def __init__(self, url):
        self.url = url
        self.next_page = url
    def __iter__(self):
        return self
    def __next__(self):
        if not self.next_page:
            raise StopIteration
        resp = http_get(self.next_page)
        self.next_page = resp.get("next")
        return resp["items"]

for batch in APIPaginator("/api/users"):
    process(batch)
```

### Use Case 3: Database cursor (lazy fetch)
```python
import psycopg2
cur = conn.cursor("server_side")  # named cursor = server-side iterator
cur.itersize = 1000
cur.execute("SELECT * FROM users")
for row in cur:    # streams batches
    process(row)
```

### Use Case 4: Tree traversal (DFS/BFS)
```python
def in_order(node):
    if node:
        yield from in_order(node.left)
        yield node.value
        yield from in_order(node.right)
```

### Use Case 5: Infinite sequences
```python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

import itertools
first_10 = list(itertools.islice(fibonacci(), 10))
```

---

## 6. itertools — Iterator Power Tools

```python
import itertools

# Combine
itertools.chain([1,2], [3,4])           # 1,2,3,4
itertools.chain.from_iterable([[1,2],[3,4]])

# Slicing
itertools.islice(iterable, start, stop, step)

# Combinations
itertools.combinations([1,2,3], 2)      # (1,2),(1,3),(2,3)
itertools.permutations([1,2,3], 2)

# Repeating
itertools.repeat("X", 5)
itertools.cycle([1,2,3])                # infinite
itertools.count(start, step)            # infinite counter

# Grouping
itertools.groupby(sorted(data), key=lambda x: x.type)

# Filtering
itertools.takewhile(lambda x: x < 5, [1,2,3,5,1,2])  # 1,2,3
itertools.dropwhile(lambda x: x < 5, [1,2,3,5,1,2])  # 5,1,2

# Compress
itertools.compress(data, selectors)     # like mask
```

---

## 7. Generator Advanced Features

### `send()` — two-way communication
```python
def echo():
    while True:
        msg = yield
        print(f"Got: {msg}")

g = echo()
next(g)               # prime
g.send("hello")
g.send("world")
```

### `yield from` — delegation
```python
def chain_lists(*lists):
    for lst in lists:
        yield from lst    # equivalent to: for x in lst: yield x
```

### `throw()` / `close()`
```python
g = my_gen()
g.throw(ValueError("oops"))    # raise inside generator
g.close()                       # clean up
```

---

## 8. Async Iterators (Python 3.5+)

```python
class AsyncCounter:
    def __init__(self, limit):
        self.i = 0
        self.limit = limit
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self.i >= self.limit:
            raise StopAsyncIteration
        await asyncio.sleep(0.1)
        self.i += 1
        return self.i

async def main():
    async for i in AsyncCounter(5):
        print(i)
```

### Async generator
```python
async def fetch_pages(url):
    while url:
        page = await http_get(url)
        yield page
        url = page.next_url

async for page in fetch_pages(start):
    process(page)
```

---

## 9. Pitfalls

### Pitfall 1: Iterator exhausted, then reused
```python
gen = (x for x in [1,2,3])
list(gen)   # [1,2,3]
list(gen)   # []   — already exhausted!
```

### Pitfall 2: Returning self for non-iterator
`__iter__` on iterable should return a NEW iterator, not self.

### Pitfall 3: Heavy compute in `__next__`
Pre-compute or batch — calling `__next__` for each item is hot path.

### Pitfall 4: Mutating during iteration
```python
d = {"a": 1, "b": 2}
for k in d:
    if k == "a":
        del d[k]   # ❌ RuntimeError: dictionary changed
# Fix: iterate over copy — for k in list(d):
```

### Pitfall 5: Forgetting `StopIteration`
Custom iterators MUST raise StopIteration to signal end.

---

## 10. Iterator vs Other Patterns

| Pattern | Difference |
|---|---|
| **Iterator** | Traverse without exposing internals |
| Observer | Notified on changes (push) |
| Visitor | Define op on different element types |
| Generator | Python's idiomatic iterator |

---

## 11. Interview Questions

**Q1: Iterator vs Iterable?**
Iterable has `__iter__` (returns new iterator each time). Iterator has `__iter__` (returns self) + `__next__`.

**Q2: Generator vs Iterator class?**
Generator = function with `yield`, automatically creates iterator. Iterator class = manual `__iter__`/`__next__`. Generator is preferred.

**Q3: Why use iterators for big data?**
Lazy evaluation → constant memory regardless of dataset size. Process while reading.

**Q4: `yield from` kya karta?**
Delegates iteration to a sub-iterator. Used for nested generators and coroutines.

**Q5: Async iterator kab use?**
Streaming async data — paginated API, WebSocket messages, async DB cursors.

**Q6: Generator se memory savings example?**
```python
sum(x*x for x in range(10**8))   # constant memory
sum([x*x for x in range(10**8)]) # 800MB+ list
```

**Q7: Iterator reset kaise?**
Iterators are one-shot. To reset, get fresh iterator from iterable: `it = iter(iterable)`.

**Q8: `itertools.chain` vs `+`?**
`+` materializes new list. `chain` is lazy — no extra memory.

---

## 12. Best Practices

1. **Prefer generators** over iterator classes
2. **Use `yield from`** for delegation
3. **Stream large data** with generators — don't build full lists
4. **Type hints:** `Iterator[T]`, `Generator[T, S, R]` from `collections.abc`
5. **Use `itertools`** for combinatorics + chaining
6. **Don't mutate during iteration**
7. **Async generators** for streaming I/O

---

## 13. Key Takeaways

1. Iterator pattern is **deeply built into Python** — `for`, `in`, generators
2. **Generators** are the modern Pythonic way
3. **Iterable** != **Iterator** (multi-pass vs single-use)
4. `itertools` provides composable iterator utilities
5. **Lazy evaluation** = constant memory for large data
6. **Async iterators** for streaming I/O

---

## Related
- [[08_Observer_Pattern]] — notification pattern
- [[14_Iterator_Pattern]] — this file
- Built-in: list, dict, set are iterables
