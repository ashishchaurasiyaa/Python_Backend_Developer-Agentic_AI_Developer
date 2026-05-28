"""
╔══════════════════════════════════════════════════════════════════╗
║              STACK & QUEUE — Complete Theory Guide               ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS A STACK?
─────────────────
A Stack is a linear data structure that follows LIFO (Last In, First Out).
Think of a stack of plates — you add to the top and remove from the top.

Operations:
  push(x)  → add element to top
  pop()    → remove & return top element
  peek()   → view top without removing
  isEmpty()→ check if stack is empty

WHAT IS A QUEUE?
─────────────────
A Queue is a linear data structure that follows FIFO (First In, First Out).
Think of a line at a ticket counter — first person in is first served.

Operations:
  enqueue(x) → add element to rear
  dequeue()  → remove & return front element
  peek()     → view front without removing
  isEmpty()  → check if queue is empty

WHAT IS A DEQUE?
─────────────────
A Deque (Double-Ended Queue) allows insertion and deletion at BOTH ends.
Python's collections.deque is the go-to implementation.

WHY DO WE NEED THEM?
─────────────────────
- Stacks: function call management, undo/redo, expression evaluation,
          backtracking, DFS traversal
- Queues: BFS traversal, task scheduling, producer-consumer problems
- Deques: sliding window algorithms, palindrome check

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Operation         Stack (list)   Queue (deque)  Deque
─────────────────────────────────────────────────────────────────
Push/Enqueue      O(1) amort.    O(1)           O(1)
Pop/Dequeue       O(1)           O(1)           O(1)
Peek              O(1)           O(1)           O(1)
Search            O(n)           O(n)           O(n)
Space             O(n)           O(n)           O(n)
─────────────────────────────────────────────────────────────────

⚠️  list.pop(0) is O(n) — always use collections.deque for queues!
"""

from collections import deque
from typing import List

# ─────────────────────────────────────────────
# 1. STACK — Using Python list
# ─────────────────────────────────────────────
print("=" * 60)
print("STACK IMPLEMENTATION")
print("=" * 60)

class Stack:
    """Stack using Python list (append/pop are O(1))."""
    def __init__(self):
        self._data = []

    def push(self, x):
        self._data.append(x)

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from empty stack")
        return self._data.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty stack")
        return self._data[-1]

    def is_empty(self):
        return len(self._data) == 0

    def size(self):
        return len(self._data)

    def __repr__(self):
        return f"Stack({self._data})"

# Demo
s = Stack()
s.push(1); s.push(2); s.push(3)
print(f"Stack after pushing 1,2,3: {s}")
print(f"Peek: {s.peek()}")
print(f"Pop: {s.pop()}")
print(f"Stack now: {s}")

# ─────────────────────────────────────────────
# 2. QUEUE — Using collections.deque
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUEUE IMPLEMENTATION")
print("=" * 60)

class Queue:
    """Queue using collections.deque (O(1) on both ends)."""
    def __init__(self):
        self._data = deque()

    def enqueue(self, x):
        self._data.append(x)          # add to right (rear)

    def dequeue(self):
        if self.is_empty():
            raise IndexError("dequeue from empty queue")
        return self._data.popleft()   # remove from left (front)

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty queue")
        return self._data[0]

    def is_empty(self):
        return len(self._data) == 0

    def size(self):
        return len(self._data)

    def __repr__(self):
        return f"Queue({list(self._data)})"

# Demo
q = Queue()
q.enqueue("A"); q.enqueue("B"); q.enqueue("C")
print(f"Queue after enqueue A,B,C: {q}")
print(f"Dequeue: {q.dequeue()}")
print(f"Queue now: {q}")

# ─────────────────────────────────────────────
# 3. DEQUE — Double-Ended Queue
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("DEQUE IMPLEMENTATION")
print("=" * 60)

dq = deque()
dq.append(1)        # add right
dq.appendleft(0)    # add left
dq.append(2)
print(f"Deque: {list(dq)}")
print(f"Pop right: {dq.pop()}")
print(f"Pop left: {dq.popleft()}")
print(f"Deque now: {list(dq)}")

# ─────────────────────────────────────────────
# 4. KEY PATTERNS
# ─────────────────────────────────────────────

# ── PATTERN 1: Balanced Parentheses ──────────
print("\n" + "=" * 60)
print("PATTERN 1: Balanced Parentheses")
print("=" * 60)

def is_balanced(s: str) -> bool:
    """
    Push opening brackets onto stack.
    On closing bracket, check if it matches the top of stack.
    Time: O(n), Space: O(n)
    """
    stack = []
    mapping = {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in '([{':
            stack.append(ch)
        elif ch in ')]}':
            if not stack or stack[-1] != mapping[ch]:
                return False
            stack.pop()
    return len(stack) == 0

print(is_balanced("()[]{}"))   # True
print(is_balanced("([)]"))     # False
print(is_balanced("{[]}"))     # True

# ── PATTERN 2: Next Greater Element (Monotonic Stack) ──
print("\n" + "=" * 60)
print("PATTERN 2: Next Greater Element — Monotonic Stack")
print("=" * 60)

"""
MONOTONIC STACK:
A stack that is always maintained in monotonically increasing
or decreasing order.

Use case: Next Greater / Previous Greater / Smaller Element problems.

Key insight: When we push a new element that is GREATER than top,
the top's "next greater element" is the new element.
"""

def next_greater_element(nums: List[int]) -> List[int]:
    """
    For each element, find the next element to the right that is greater.
    Returns -1 if none exists.
    Time: O(n), Space: O(n)

    Stack stores INDICES of elements waiting for their NGE.
    Maintain a DECREASING monotonic stack.
    """
    n = len(nums)
    result = [-1] * n
    stack = []  # stores indices

    for i in range(n):
        # While current element is greater than element at stack top
        while stack and nums[i] > nums[stack[-1]]:
            idx = stack.pop()
            result[idx] = nums[i]
        stack.append(i)

    return result

nums = [4, 1, 2, 3]
print(f"nums: {nums}")
print(f"NGE:  {next_greater_element(nums)}")  # [-1, 2, 3, -1]

nums2 = [2, 1, 2, 4, 3]
print(f"nums: {nums2}")
print(f"NGE:  {next_greater_element(nums2)}")  # [4, 2, 4, -1, -1]

# ── PATTERN 3: Sliding Window Maximum (Monotonic Deque) ──
print("\n" + "=" * 60)
print("PATTERN 3: Sliding Window Maximum — Monotonic Deque")
print("=" * 60)

"""
MONOTONIC DEQUE for Sliding Window:
- Maintain a deque of indices
- Front of deque = index of max in current window
- Remove from front if index falls outside window
- Remove from rear if current element >= rear element (maintain decreasing order)

Time: O(n), Space: O(k)
"""

def sliding_window_max(nums: List[int], k: int) -> List[int]:
    dq = deque()   # stores indices, decreasing order of values
    result = []

    for i in range(len(nums)):
        # Remove elements outside the window
        if dq and dq[0] < i - k + 1:
            dq.popleft()

        # Remove smaller elements from rear (they can never be max)
        while dq and nums[i] >= nums[dq[-1]]:
            dq.pop()

        dq.append(i)

        # Window is fully formed
        if i >= k - 1:
            result.append(nums[dq[0]])

    return result

nums = [1, 3, -1, -3, 5, 3, 6, 7]
k = 3
print(f"nums={nums}, k={k}")
print(f"Window max: {sliding_window_max(nums, k)}")  # [3,3,5,5,6,7]

# ── PATTERN 4: Min Stack ──────────────────────
print("\n" + "=" * 60)
print("PATTERN 4: Min Stack — Track minimum at every state")
print("=" * 60)

"""
INSIGHT: Store (value, current_min) pairs in the stack.
Every push records the minimum seen so far.
"""

class MinStack:
    def __init__(self):
        self.stack = []  # (value, min_so_far)

    def push(self, val: int):
        current_min = min(val, self.stack[-1][1]) if self.stack else val
        self.stack.append((val, current_min))

    def pop(self):
        self.stack.pop()

    def top(self):
        return self.stack[-1][0]

    def get_min(self):
        return self.stack[-1][1]

ms = MinStack()
ms.push(5); ms.push(3); ms.push(7); ms.push(1)
print(f"Min: {ms.get_min()}")  # 1
ms.pop()
print(f"Min after pop: {ms.get_min()}")  # 3

# ── PATTERN 5: Expression Evaluation ─────────
print("\n" + "=" * 60)
print("PATTERN 5: Evaluate RPN (Reverse Polish Notation)")
print("=" * 60)

def eval_rpn(tokens: List[str]) -> int:
    """
    Use a stack. On number → push. On operator → pop two, compute, push result.
    Time: O(n), Space: O(n)
    """
    stack = []
    ops = {'+', '-', '*', '/'}
    for tok in tokens:
        if tok not in ops:
            stack.append(int(tok))
        else:
            b, a = stack.pop(), stack.pop()
            if tok == '+': stack.append(a + b)
            elif tok == '-': stack.append(a - b)
            elif tok == '*': stack.append(a * b)
            elif tok == '/': stack.append(int(a / b))  # truncate toward zero
    return stack[0]

print(eval_rpn(["2", "1", "+", "3", "*"]))  # 9
print(eval_rpn(["4", "13", "5", "/", "+"]))  # 6

# ─────────────────────────────────────────────
# 5. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What's the difference between a stack and a queue?
A1: Stack = LIFO (Last In First Out). Queue = FIFO (First In First Out).
    Stack: push/pop from same end. Queue: enqueue at rear, dequeue from front.

Q2: Why use collections.deque instead of list for a queue?
A2: list.pop(0) is O(n) because all elements shift. deque.popleft() is O(1)
    because deque is implemented as a doubly-linked list of fixed-size blocks.

Q3: What is a monotonic stack and when is it used?
A3: A monotonic stack maintains elements in strictly increasing or decreasing order.
    Used for: Next Greater Element, Previous Smaller Element, Largest Rectangle,
    Trapping Rain Water, Daily Temperatures, Car Fleet.

Q4: How do you implement a queue using two stacks?
A4: Use stack_in for push, stack_out for pop. On dequeue, if stack_out is empty,
    pour all of stack_in into stack_out (reverses order). Amortized O(1).

Q5: What is the time complexity of iterating through a stack?
A5: O(n) — you must pop all elements or iterate the underlying list.

Q6: When would you use a deque over a stack or queue?
A6: When you need O(1) operations at BOTH ends — e.g., sliding window maximum,
    palindrome checking, BFS with priority, undo-redo with history limits.

Q7: What's the space complexity of a monotonic stack solution?
A7: O(n) worst case (e.g., strictly decreasing array means all elements stay).
    Average is often much less.

Q8: How does the call stack work in recursion?
A8: Each recursive call pushes a frame onto the call stack. Base case causes
    unwinding (popping frames). Stack overflow = too deep recursion (default
    Python limit is ~1000 frames, adjustable via sys.setrecursionlimit).
"""
print(qa)

# ─────────────────────────────────────────────
# 6. COMMON STACK TEMPLATES
# ─────────────────────────────────────────────
print("=" * 60)
print("TEMPLATES FOR INTERVIEWS")
print("=" * 60)

template = '''
# ── Monotonic Increasing Stack (for next smaller) ──
def next_smaller(nums):
    stack = []
    result = [-1] * len(nums)
    for i, num in enumerate(nums):
        while stack and num < nums[stack[-1]]:
            result[stack.pop()] = num
        stack.append(i)
    return result

# ── Monotonic Decreasing Stack (for next greater) ──
def next_greater(nums):
    stack = []
    result = [-1] * len(nums)
    for i, num in enumerate(nums):
        while stack and num > nums[stack[-1]]:
            result[stack.pop()] = num
        stack.append(i)
    return result

# ── BFS Template using Queue ──
from collections import deque
def bfs(graph, start):
    visited = set([start])
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

# ── DFS Template using Stack ──
def dfs_iterative(graph, start):
    visited = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node not in visited:
            visited.add(node)
            for neighbor in graph[node]:
                stack.append(neighbor)
'''
print(template)
