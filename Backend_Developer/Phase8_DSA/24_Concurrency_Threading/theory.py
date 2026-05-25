
"""
24 — Concurrency & Threading Problems — Theory
================================================
Level: Intermediate
"""
import threading
import time
from collections import deque

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
LeetCode concurrency problems test understanding of:
  - Semaphores (control access to resources)
  - Locks/Mutexes (mutual exclusion)
  - Condition variables (wait/notify)
  - Barriers (synchronize threads at a point)
  - Thread ordering (print in sequence, alternate threads)

Python tools:
  threading.Semaphore(n) — allows n concurrent accessors
  threading.Lock()       — binary semaphore (mutex)
  threading.Event()      — signal between threads
  threading.Condition()  — wait() + notify() + notify_all()
  threading.Barrier(n)   — wait until n threads arrive
"""

# ════════════════════════════════════════════════════════════
# PATTERN 1: Semaphore for Ordering (LC 1114)
# ════════════════════════════════════════════════════════════

class Foo:
    """
    LC 1114: Print in Order.
    first() then second() then third() regardless of thread start order.
    Use semaphores initialized to 0 → block until released.
    """
    def __init__(self):
        self.sem2 = threading.Semaphore(0)   # blocks second until first done
        self.sem3 = threading.Semaphore(0)   # blocks third until second done

    def first(self, printFirst):
        printFirst()
        self.sem2.release()

    def second(self, printSecond):
        self.sem2.acquire()
        printSecond()
        self.sem3.release()

    def third(self, printThird):
        self.sem3.acquire()
        printThird()

# Demo
foo = Foo()
results = []
t1 = threading.Thread(target=foo.first,  args=[lambda: results.append("first")])
t2 = threading.Thread(target=foo.second, args=[lambda: results.append("second")])
t3 = threading.Thread(target=foo.third,  args=[lambda: results.append("third")])
for t in [t3, t1, t2]: t.start()
for t in [t1, t2, t3]: t.join()
print("LC 1114 Foo:", results)   # ['first', 'second', 'third']


# ════════════════════════════════════════════════════════════
# PATTERN 2: Alternating Threads (LC 1115)
# ════════════════════════════════════════════════════════════

class FooBar:
    """
    LC 1115: Alternate between foo() and bar() n times.
    Output: foobarfoobar...
    Two semaphores: one for each turn.
    """
    def __init__(self, n: int):
        self.n = n
        self.foo_sem = threading.Semaphore(1)   # foo goes first
        self.bar_sem = threading.Semaphore(0)

    def foo(self, printFoo):
        for _ in range(self.n):
            self.foo_sem.acquire()
            printFoo()
            self.bar_sem.release()

    def bar(self, printBar):
        for _ in range(self.n):
            self.bar_sem.acquire()
            printBar()
            self.foo_sem.release()

# Demo
fb = FooBar(3)
result = []
t1 = threading.Thread(target=fb.foo, args=[lambda: result.append("foo")])
t2 = threading.Thread(target=fb.bar, args=[lambda: result.append("bar")])
t1.start(); t2.start(); t1.join(); t2.join()
print("LC 1115 FooBar:", "".join(result))   # foobarfoobar foobar


# ════════════════════════════════════════════════════════════
# PATTERN 3: Fizz Buzz with Threads (LC 1195)
# ════════════════════════════════════════════════════════════

class FizzBuzz:
    """
    LC 1195: 4 threads print fizz/buzz/fizzbuzz/number in order.
    Use semaphores to control which thread runs next.
    """
    def __init__(self, n: int):
        self.n = n
        self.num_sem  = threading.Semaphore(1)
        self.fizz_sem = threading.Semaphore(0)
        self.buzz_sem = threading.Semaphore(0)
        self.fb_sem   = threading.Semaphore(0)

    def _dispatch(self, i: int):
        if i % 15 == 0:   self.fb_sem.release()
        elif i % 3 == 0:  self.fizz_sem.release()
        elif i % 5 == 0:  self.buzz_sem.release()
        else:             self.num_sem.release()

    def fizz(self, printFizz):
        for i in range(1, self.n+1):
            if i % 3 == 0 and i % 5 != 0:
                self.fizz_sem.acquire(); printFizz(); self._dispatch(i+1) if i<self.n else None

    def buzz(self, printBuzz):
        for i in range(1, self.n+1):
            if i % 5 == 0 and i % 3 != 0:
                self.buzz_sem.acquire(); printBuzz()

    def fizzbuzz(self, printFizzBuzz):
        for i in range(1, self.n+1):
            if i % 15 == 0:
                self.fb_sem.acquire(); printFizzBuzz()

    def number(self, printNumber):
        for i in range(1, self.n+1):
            if i % 3 != 0 and i % 5 != 0:
                self.num_sem.acquire(); printNumber(i)


# ════════════════════════════════════════════════════════════
# PATTERN 4: Condition Variable (Producer-Consumer)
# ════════════════════════════════════════════════════════════

class BoundedBlockingQueue:
    """
    LC 1188: Thread-safe queue with max capacity.
    enqueue blocks if full, dequeue blocks if empty.
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.queue = deque()
        self.lock = threading.Lock()
        self.not_full  = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)

    def enqueue(self, element: int) -> None:
        with self.not_full:
            while len(self.queue) >= self.capacity:
                self.not_full.wait()       # release lock, wait for signal
            self.queue.append(element)
            self.not_empty.notify()        # signal consumer

    def dequeue(self) -> int:
        with self.not_empty:
            while not self.queue:
                self.not_empty.wait()      # release lock, wait for signal
            val = self.queue.popleft()
            self.not_full.notify()         # signal producer
            return val

    def size(self) -> int:
        with self.lock:
            return len(self.queue)

# Demo
bbq = BoundedBlockingQueue(3)
def producer():
    for i in range(5):
        bbq.enqueue(i)
def consumer():
    for _ in range(5):
        time.sleep(0.01)
        bbq.dequeue()
pt = threading.Thread(target=producer)
ct = threading.Thread(target=consumer)
pt.start(); ct.start(); pt.join(); ct.join()
print("BoundedQueue final size:", bbq.size())   # 0


# ════════════════════════════════════════════════════════════
# PATTERN 5: Read-Write Lock (Readers-Writers)
# ════════════════════════════════════════════════════════════

class ReadWriteLock:
    """
    Multiple readers can read simultaneously.
    Writer needs exclusive access.
    """
    def __init__(self):
        self.readers = 0
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()

    def acquire_read(self):
        with self.lock:
            self.readers += 1
            if self.readers == 1:
                self.write_lock.acquire()   # first reader blocks writers

    def release_read(self):
        with self.lock:
            self.readers -= 1
            if self.readers == 0:
                self.write_lock.release()   # last reader unblocks writers

    def acquire_write(self):
        self.write_lock.acquire()

    def release_write(self):
        self.write_lock.release()


# ════════════════════════════════════════════════════════════
# PATTERN 6: Barrier (H2O — LC 1117)
# ════════════════════════════════════════════════════════════

class H2O:
    """
    LC 1117: Release H and O molecules to form water.
    Every 2 H molecules + 1 O molecule = H2O.
    Use semaphores to enforce ratio.
    """
    def __init__(self):
        self.h_sem = threading.Semaphore(2)   # allow 2 H
        self.o_sem = threading.Semaphore(0)   # block O until 2 H released
        self.barrier = threading.Barrier(3)   # sync after each water molecule
        self.h_count = 0
        self.lock = threading.Lock()

    def hydrogen(self, releaseHydrogen) -> None:
        self.h_sem.acquire()
        releaseHydrogen()
        with self.lock:
            self.h_count += 1
            if self.h_count == 2:
                self.h_count = 0
                self.o_sem.release()
        self.barrier.wait()
        self.h_sem.release()

    def oxygen(self, releaseOxygen) -> None:
        self.o_sem.acquire()
        releaseOxygen()
        self.barrier.wait()


# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: Semaphore vs Lock — difference?
A: Lock (Mutex) = binary semaphore (0 or 1). Only the acquiring thread can release.
   Semaphore = counter-based. Any thread can release. Semaphore(0) blocks until
   another thread releases it (used for signaling/ordering).

Q2: What is a race condition?
A: Multiple threads access shared data concurrently, and at least one writes.
   Result depends on thread scheduling (non-deterministic).
   Fix: Lock/Mutex around critical section.

Q3: What is deadlock and how to prevent it?
A: Deadlock = two+ threads wait for each other's locks indefinitely.
   Prevention: (1) Always acquire locks in same order. (2) Use timeout.
   (3) tryLock instead of lock. (4) Avoid nested locks.

Q4: What is a condition variable?
A: Mechanism to wait for a condition to become true, releasing the lock while waiting.
   wait() = release lock + sleep until notified.
   notify() = wake one waiting thread.
   notify_all() = wake all waiting threads.
   Always check condition in a WHILE loop (spurious wakeups).

Q5: Python GIL — does threading help with CPU-bound tasks?
A: NO. GIL (Global Interpreter Lock) allows only one thread to execute Python
   bytecode at a time. Use multiprocessing for CPU-bound parallelism.
   Threading helps for I/O-bound tasks (file I/O, network, sleep).

Q6: What is a Semaphore(0) used for?
A: Signaling/ordering between threads. Thread A: sem.acquire() — blocks.
   Thread B: sem.release() — unblocks A. This enforces A runs after B.
   LeetCode ordering problems (LC 1114) use this pattern extensively.

Q7: How does threading.Barrier work?
A: Barrier(n) blocks all threads that call barrier.wait() until n threads
   have called it. Then all are released simultaneously.
   Used in LC 1117 (H2O) to synchronize after each water molecule formed.

Q8: What is monitor pattern?
A: Lock + Condition Variables together. Python's `with condition:` block
   automatically acquires/releases lock. wait() releases lock temporarily.
   BoundedBlockingQueue (LC 1188) uses this pattern.
"""
