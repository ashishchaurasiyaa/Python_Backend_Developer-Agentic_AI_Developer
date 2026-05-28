"""
03 — Linked List — Theory
==========================
Level: Basic → Intermediate
"""
from __future__ import annotations

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
LINKED LIST = sequence of nodes, each pointing to the next.
No contiguous memory needed (unlike array).

TYPES:
  Singly Linked  → each node has (data, next)
  Doubly Linked  → each node has (data, prev, next)
  Circular       → last node points back to head

WHY over array?
  ✅ O(1) insert/delete at head (no shifting)
  ✅ Dynamic size (no pre-allocation)
  ❌ No random access — must traverse O(n)
  ❌ Extra memory for pointers
  ❌ Poor cache locality
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Operation           Singly LL    Array
────────────────────────────────────────
Access by index     O(n)         O(1)
Search              O(n)         O(n)
Insert at head      O(1)         O(n)
Insert at tail      O(n)*        O(1)
Insert at middle    O(n)         O(n)
Delete at head      O(1)         O(n)
Delete at tail      O(n)         O(1)
Delete at middle    O(n)         O(n)
Space               O(n)         O(n)
*O(1) if tail pointer maintained
"""

# ════════════════════════════════════════════════════════════
# NODE & LINKED LIST IMPLEMENTATION
# ════════════════════════════════════════════════════════════

from typing import Optional, Any

class ListNode:
    def __init__(self, val: int = 0, next: Optional[ListNode] = None):
        self.val  = val
        self.next = next

class LinkedList:
    """Singly Linked List with all operations."""

    def __init__(self):
        self.head: Optional[ListNode] = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        nodes, cur = [], self.head
        while cur:
            nodes.append(str(cur.val))
            cur = cur.next
        return " → ".join(nodes) + " → None"

    # ── Insert ──────────────────────────────────────────────
    def prepend(self, val: int) -> None:
        """Insert at head. O(1)."""
        self.head   = ListNode(val, self.head)
        self._size += 1

    def append(self, val: int) -> None:
        """Insert at tail. O(n)."""
        node = ListNode(val)
        if not self.head:
            self.head = node
        else:
            cur = self.head
            while cur.next:
                cur = cur.next
            cur.next = node
        self._size += 1

    def insert_at(self, idx: int, val: int) -> None:
        """Insert at position idx. O(n)."""
        if idx == 0:
            return self.prepend(val)
        cur = self.head
        for _ in range(idx - 1):
            if not cur: raise IndexError("Index out of range")
            cur = cur.next
        new_node      = ListNode(val, cur.next)
        cur.next      = new_node
        self._size   += 1

    # ── Delete ──────────────────────────────────────────────
    def delete_head(self) -> Optional[int]:
        """Remove head. O(1)."""
        if not self.head: return None
        val        = self.head.val
        self.head  = self.head.next
        self._size -= 1
        return val

    def delete_val(self, val: int) -> bool:
        """Remove first occurrence of val. O(n)."""
        if not self.head: return False
        if self.head.val == val:
            self.delete_head()
            return True
        cur = self.head
        while cur.next:
            if cur.next.val == val:
                cur.next    = cur.next.next
                self._size -= 1
                return True
            cur = cur.next
        return False

    # ── Search ──────────────────────────────────────────────
    def search(self, val: int) -> Optional[ListNode]:
        cur = self.head
        while cur:
            if cur.val == val: return cur
            cur = cur.next
        return None

    # ── Reverse ─────────────────────────────────────────────
    def reverse(self) -> None:
        """Reverse in-place. O(n)."""
        prev, cur = None, self.head
        while cur:
            nxt      = cur.next
            cur.next = prev
            prev     = cur
            cur      = nxt
        self.head = prev


# ── Doubly Linked List Node ─────────────────────────────────

class DListNode:
    def __init__(self, val=0):
        self.val  = val
        self.prev: Optional[DListNode] = None
        self.next: Optional[DListNode] = None


# ════════════════════════════════════════════════════════════
# KEY PATTERNS
# ════════════════════════════════════════════════════════════

# PATTERN 1: Dummy Head (simplifies edge cases)
def remove_elements(head: Optional[ListNode], val: int) -> Optional[ListNode]:
    dummy = ListNode(0, head)
    cur   = dummy
    while cur.next:
        if cur.next.val == val:
            cur.next = cur.next.next
        else:
            cur = cur.next
    return dummy.next

# PATTERN 2: Fast & Slow Pointers (Floyd's cycle detection)
def has_cycle(head: Optional[ListNode]) -> bool:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast: return True
    return False

def find_cycle_start(head: Optional[ListNode]) -> Optional[ListNode]:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            # Move one pointer to head, advance both 1 step at a time
            slow = head
            while slow is not fast:
                slow = slow.next
                fast = fast.next
            return slow  # cycle start
    return None

# PATTERN 3: Two Pointers (nth from end, middle)
def find_middle(head: Optional[ListNode]) -> Optional[ListNode]:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    return slow

def remove_nth_from_end(head: Optional[ListNode], n: int) -> Optional[ListNode]:
    dummy = ListNode(0, head)
    fast  = dummy
    for _ in range(n + 1): fast = fast.next
    slow  = dummy
    while fast:
        slow = slow.next
        fast = fast.next
    slow.next = slow.next.next
    return dummy.next

# PATTERN 4: Merge sorted lists
def merge_sorted(l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:
    dummy = cur = ListNode(0)
    while l1 and l2:
        if l1.val <= l2.val:
            cur.next, l1 = l1, l1.next
        else:
            cur.next, l2 = l2, l2.next
        cur = cur.next
    cur.next = l1 or l2
    return dummy.next

# ════════════════════════════════════════════════════════════
# HELPER: Build list from list
# ════════════════════════════════════════════════════════════

def build(vals: list) -> Optional[ListNode]:
    if not vals: return None
    head = ListNode(vals[0])
    cur  = head
    for v in vals[1:]:
        cur.next = ListNode(v)
        cur      = cur.next
    return head

def to_list(head: Optional[ListNode]) -> list:
    result, cur = [], head
    while cur:
        result.append(cur.val)
        cur = cur.next
    return result

# Demo
ll = LinkedList()
for v in [1,2,3,4,5]: ll.append(v)
print("Original:", ll)
ll.reverse()
print("Reversed:", ll)
print("Middle:", find_middle(build([1,2,3,4,5])).val)   # 3

# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q: Why use a dummy node?
A: Simplifies head-deletion edge case. Operations on dummy.next instead of
   handling head separately.

Q: How does Floyd's cycle detection work?
A: Slow moves 1 step, fast moves 2. If cycle exists, they meet inside cycle.
   To find cycle start: reset one pointer to head, advance both 1 step →
   they meet at cycle start (mathematical proof via modular arithmetic).

Q: How to find kth node from end in one pass?
A: Two pointers. Advance fast k steps first. Then advance both until fast
   reaches end. Slow is at kth from end.

Q: Difference between shallow and deep copy of linked list?
A: Shallow: new head, same node objects (mutating one affects both).
   Deep: new head AND new node objects. Use copy.deepcopy() or manual traversal.
"""
