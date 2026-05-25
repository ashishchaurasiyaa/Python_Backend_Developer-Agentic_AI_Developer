"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DSA — Linked Lists: Fundamentals, Classic Problems, LRU Cache
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from collections import deque, defaultdict, OrderedDict
import heapq


# ═══════════════════════════════════════════════════════════════
# SECTION 1: NODE CLASS AND SINGLY LINKED LIST
# ═══════════════════════════════════════════════════════════════

class ListNode:
    """Standard singly linked list node used in all LeetCode problems."""
    def __init__(self, val: int = 0, next: 'ListNode' = None):
        self.val = val
        self.next = next

    def __repr__(self):
        return f"ListNode({self.val})"


class SinglyLinkedList:
    """Full singly linked list implementation for reference."""
    def __init__(self):
        self.head = None
        self.size = 0

    def append(self, val: int) -> None:
        """Add node at tail. O(n)"""
        new_node = ListNode(val)
        if not self.head:
            self.head = new_node
        else:
            curr = self.head
            while curr.next:
                curr = curr.next
            curr.next = new_node
        self.size += 1

    def prepend(self, val: int) -> None:
        """Add node at head. O(1)"""
        new_node = ListNode(val, self.head)
        self.head = new_node
        self.size += 1

    def delete(self, val: int) -> bool:
        """Delete first node with given value. O(n)"""
        if not self.head:
            return False
        if self.head.val == val:
            self.head = self.head.next
            self.size -= 1
            return True
        curr = self.head
        while curr.next:
            if curr.next.val == val:
                curr.next = curr.next.next
                self.size -= 1
                return True
            curr = curr.next
        return False

    def to_list(self) -> list:
        """Convert to Python list. O(n)"""
        result = []
        curr = self.head
        while curr:
            result.append(curr.val)
            curr = curr.next
        return result

    def __len__(self):
        return self.size


# ─── Helper utilities used in tests ───────────────────────────

def list_to_linked(arr: list[int]) -> ListNode:
    """Convert Python list to linked list. Returns head."""
    if not arr:
        return None
    head = ListNode(arr[0])
    curr = head
    for val in arr[1:]:
        curr.next = ListNode(val)
        curr = curr.next
    return head

def linked_to_list(head: ListNode) -> list[int]:
    """Convert linked list to Python list."""
    result = []
    curr = head
    while curr:
        result.append(curr.val)
        curr = curr.next
    return result


# ═══════════════════════════════════════════════════════════════
# SECTION 2: REVERSE LINKED LIST (LeetCode 206)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Given the head of a singly linked list, reverse the list and return the new head.

INTERVIEW NOTE:
  This is one of the most asked linked list questions. Know both iterative and
  recursive. Interviewers often follow up with "reverse in groups of k" (LC 25).
"""

# ─── Iterative — O(n) time, O(1) space ────────────────────────
def reverse_list_iterative(head: ListNode) -> ListNode:
    """
    Three-pointer technique: prev, curr, next_node.
    At each step: save next, point curr.next back, advance both pointers.
    """
    prev = None
    curr = head
    while curr:
        next_node = curr.next   # save next
        curr.next = prev        # reverse the link
        prev = curr             # advance prev
        curr = next_node        # advance curr
    return prev  # prev is now the new head
# Time: O(n) | Space: O(1)

# ─── Recursive — O(n) time, O(n) space (call stack) ──────────
def reverse_list_recursive(head: ListNode) -> ListNode:
    """
    Base case: empty list or single node — already reversed.
    Recursive case: reverse rest of list, then point head.next.next back to head.

    Visualization for [1->2->3->None]:
      reverse(3) returns 3 (base)
      At node 2: 2.next.next = 2  =>  3.next = 2
                 2.next = None
      At node 1: 1.next.next = 1  =>  2.next = 1
                 1.next = None
      Result: 3->2->1->None
    """
    if not head or not head.next:
        return head
    new_head = reverse_list_recursive(head.next)
    head.next.next = head   # node after head now points back to head
    head.next = None        # head's next becomes None (it's now the tail)
    return new_head
# Time: O(n) | Space: O(n) — call stack depth

# Interview follow-up: Reverse in groups of K (LeetCode 25)
def reverse_k_group(head: ListNode, k: int) -> ListNode:
    """Reverse nodes in groups of k. Leave remainder as-is."""
    # Check if there are at least k nodes
    count = 0
    curr = head
    while curr and count < k:
        curr = curr.next
        count += 1
    if count < k:
        return head  # not enough nodes, leave as-is

    # Reverse k nodes
    prev, curr = None, head
    for _ in range(k):
        next_node = curr.next
        curr.next = prev
        prev = curr
        curr = next_node

    # head is now the tail of the reversed group
    # Recursively process the rest
    head.next = reverse_k_group(curr, k)
    return prev
# Time: O(n) | Space: O(n/k) for recursion


# ═══════════════════════════════════════════════════════════════
# SECTION 3: DETECT CYCLE — FLOYD'S ALGORITHM (LeetCode 141 / 142)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM 141 (Detect):
  Return True if the linked list has a cycle.

PROBLEM 142 (Find start):
  Return the node where the cycle begins, or None.

APPROACH — Floyd's Tortoise and Hare:
  slow moves 1 step, fast moves 2 steps.
  If they meet → cycle exists.
  To find cycle start: reset slow to head, keep fast at meeting point,
  advance both one step at a time — they meet at cycle start.

WHY IT WORKS (math):
  Let F = distance from head to cycle start.
  Let C = cycle length.
  Let h = distance from cycle start to meeting point.
  At meeting: slow traveled F+h, fast traveled F+h+nC.
  Since fast = 2*slow: F+h+nC = 2(F+h) → F = nC - h.
  So advancing slow from head and fast from meeting point both travel F steps
  to reach the cycle start.
"""

def has_cycle(head: ListNode) -> bool:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False
# Time: O(n) | Space: O(1)

def detect_cycle_start(head: ListNode) -> ListNode:
    """Return the node at which cycle begins, or None."""
    slow = fast = head
    has_cycle_flag = False

    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            has_cycle_flag = True
            break

    if not has_cycle_flag:
        return None

    # Reset slow to head; advance both one step until they meet
    slow = head
    while slow is not fast:
        slow = slow.next
        fast = fast.next

    return slow  # cycle start
# Time: O(n) | Space: O(1)

# Interview note: Hash set approach is O(n) space but simpler to explain.
# Always mention Floyd's as the optimal O(1) space solution.


# ═══════════════════════════════════════════════════════════════
# SECTION 4: FIND MIDDLE NODE (LeetCode 876)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Return the middle node of the linked list.
  If even length, return the second middle node.

APPROACH:
  Slow/fast pointer. Slow advances 1, fast advances 2.
  When fast reaches end, slow is at middle.

  [1,2,3,4,5]: slow stops at 3 (middle)
  [1,2,3,4]:   slow stops at 3 (second middle)

INTERVIEW NOTE:
  Confirm with interviewer: for even-length list, first or second middle?
  This solution returns the second middle (more common in LeetCode).
"""

def find_middle(head: ListNode) -> ListNode:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    return slow
# Time: O(n) | Space: O(1)

# Variation: return first middle for even-length lists
def find_middle_first(head: ListNode) -> ListNode:
    slow, fast = head, head.next  # offset fast by one
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    return slow
# Time: O(n) | Space: O(1)


# ═══════════════════════════════════════════════════════════════
# SECTION 5: MERGE TWO SORTED LISTS (LeetCode 21)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Merge two sorted linked lists and return sorted merged list.
  Reuse existing nodes (do not create new ones).

APPROACH:
  Use a dummy head node to simplify edge cases.
  Compare heads of both lists; attach smaller one to result.
  Append remaining non-empty list.
"""

def merge_two_sorted_lists(list1: ListNode, list2: ListNode) -> ListNode:
    dummy = ListNode(0)  # sentinel node
    curr = dummy

    while list1 and list2:
        if list1.val <= list2.val:
            curr.next = list1
            list1 = list1.next
        else:
            curr.next = list2
            list2 = list2.next
        curr = curr.next

    # Attach remaining nodes (at most one list has nodes left)
    curr.next = list1 if list1 else list2

    return dummy.next
# Time: O(m + n) | Space: O(1)

# Recursive version (elegant but O(m+n) stack space):
def merge_two_sorted_lists_recursive(l1: ListNode, l2: ListNode) -> ListNode:
    if not l1:
        return l2
    if not l2:
        return l1
    if l1.val <= l2.val:
        l1.next = merge_two_sorted_lists_recursive(l1.next, l2)
        return l1
    else:
        l2.next = merge_two_sorted_lists_recursive(l1, l2.next)
        return l2
# Time: O(m + n) | Space: O(m + n)


# ═══════════════════════════════════════════════════════════════
# SECTION 6: MERGE K SORTED LISTS (LeetCode 23)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Merge k sorted linked lists and return one sorted list.

APPROACH 1 — Min-Heap (optimal):
  Push (val, index, node) for each list's head into a min-heap.
  index used as tiebreaker (ListNode not comparable).
  Pop minimum, attach to result, push that node's next if exists.

APPROACH 2 — Divide and Conquer:
  Repeatedly merge pairs of lists: O(n log k) time, O(log k) stack space.

INTERVIEW NOTE:
  Heap approach is most commonly expected. Know the tiebreaker trick.
"""

def merge_k_sorted_lists(lists: list[ListNode]) -> ListNode:
    heap = []
    # Push (value, list_index, node) — index breaks ties between equal values
    for i, node in enumerate(lists):
        if node:
            heapq.heappush(heap, (node.val, i, node))

    dummy = ListNode(0)
    curr = dummy

    while heap:
        val, i, node = heapq.heappop(heap)
        curr.next = node
        curr = curr.next
        if node.next:
            heapq.heappush(heap, (node.next.val, i, node.next))

    return dummy.next
# Time: O(n log k) where n = total nodes, k = number of lists
# Space: O(k) for the heap

# Divide and conquer approach:
def merge_k_sorted_lists_dc(lists: list[ListNode]) -> ListNode:
    if not lists:
        return None
    if len(lists) == 1:
        return lists[0]
    mid = len(lists) // 2
    left = merge_k_sorted_lists_dc(lists[:mid])
    right = merge_k_sorted_lists_dc(lists[mid:])
    return merge_two_sorted_lists(left, right)
# Time: O(n log k) | Space: O(log k)


# ═══════════════════════════════════════════════════════════════
# SECTION 7: REMOVE NTH NODE FROM END (LeetCode 19)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Remove the nth node from the end of a linked list. Return head.
  1 <= n <= length of list.

APPROACH — Two Pointer (one pass):
  Use fast and slow pointers, both starting at dummy.
  Advance fast by n+1 steps first.
  Then advance both until fast reaches end.
  slow.next is the node to remove.

  WHY n+1? We want slow to stop at the node BEFORE the target,
  so we can re-link slow.next = slow.next.next.
"""

def remove_nth_from_end(head: ListNode, n: int) -> ListNode:
    dummy = ListNode(0)
    dummy.next = head
    fast = slow = dummy

    # Advance fast by n+1 steps
    for _ in range(n + 1):
        fast = fast.next

    # Move both until fast reaches None
    while fast:
        slow = slow.next
        fast = fast.next

    # slow is now just before the target node
    slow.next = slow.next.next

    return dummy.next
# Time: O(n) | Space: O(1)

# Follow-up edge cases:
# - Remove head (n == length): dummy handles this cleanly
# - Single element list, n=1: removes head, returns None
# - n=1: removes last element


# ═══════════════════════════════════════════════════════════════
# SECTION 8: LRU CACHE (LeetCode 146)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Design a data structure that follows the LRU (Least Recently Used) cache policy.
  Implement LRUCache(capacity), get(key), put(key, value).
  Both get and put must run in O(1) average time.

APPROACH 1 — OrderedDict (Python built-in, interview shortcut):
  OrderedDict maintains insertion order.
  On access: move key to end (most recently used).
  On insert: if over capacity, remove first item (least recently used).

APPROACH 2 — Doubly Linked List + HashMap (full implementation):
  HashMap for O(1) key lookup.
  Doubly linked list for O(1) insertion/deletion at any position.
  Most recently used at tail, least recently used at head.
  Dummy head and tail nodes simplify edge cases.

INTERVIEW NOTE:
  Start with OrderedDict to show you know Python's stdlib.
  Then offer to implement with DLL + HashMap to demonstrate DS knowledge.
  Interviewers often ask for the manual DLL implementation.
"""

# ─── Solution A: OrderedDict ───────────────────────────────────
class LRUCacheOrderedDict:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)  # mark as recently used
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # remove LRU (first item)
# Time: O(1) for both get and put | Space: O(capacity)


# ─── Solution B: Doubly Linked List + HashMap ─────────────────
class DLLNode:
    """Node for doubly linked list used in LRU Cache."""
    def __init__(self, key: int = 0, val: int = 0):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class LRUCache:
    """
    Layout: dummy_head <-> LRU node <-> ... <-> MRU node <-> dummy_tail
    Insertions go near tail (MRU side).
    Evictions come from head (LRU side).
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.map = {}  # key -> DLLNode

        # Dummy sentinel nodes — eliminate None checks
        self.head = DLLNode()  # pseudo-head (LRU side)
        self.tail = DLLNode()  # pseudo-tail (MRU side)
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: DLLNode) -> None:
        """Remove a node from the doubly linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_tail(self, node: DLLNode) -> None:
        """Insert node just before tail (MRU position)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def get(self, key: int) -> int:
        if key not in self.map:
            return -1
        node = self.map[key]
        self._remove(node)           # remove from current position
        self._insert_at_tail(node)   # move to MRU position
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self.map:
            self._remove(self.map[key])
        node = DLLNode(key, value)
        self.map[key] = node
        self._insert_at_tail(node)
        if len(self.map) > self.capacity:
            # Remove LRU: node after dummy head
            lru = self.head.next
            self._remove(lru)
            del self.map[lru.key]
# Time: O(1) for both get and put | Space: O(capacity)


# ═══════════════════════════════════════════════════════════════
# QUICK REFERENCE SUMMARY
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM                      | TECHNIQUE                  | TIME    | SPACE
─────────────────────────────┼────────────────────────────┼─────────┼──────
Reverse Linked List          | Three-pointer / Recursion  | O(n)    | O(1)/O(n)
Detect Cycle                 | Floyd's slow/fast          | O(n)    | O(1)
Find Middle                  | Slow/fast pointer          | O(n)    | O(1)
Merge Two Sorted Lists       | Dummy head + two pointers  | O(m+n)  | O(1)
Merge K Sorted Lists         | Min-heap                   | O(n lgk)| O(k)
Remove Nth from End          | Two pointers, gap of n+1   | O(n)    | O(1)
LRU Cache                    | HashMap + DLL              | O(1)    | O(cap)

KEY PATTERNS:
  - Dummy head node: simplifies insert/delete at head edge case
  - Slow/fast pointer: cycles, middle, kth from end
  - Two pointers with gap: nth from end, intersections
  - Heap with (val, idx, node): K-way merge with tiebreaker
"""


# ═══════════════════════════════════════════════════════════════
# TESTS — run this file to verify all solutions
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ── Reverse Linked List ──
    h = list_to_linked([1, 2, 3, 4, 5])
    assert linked_to_list(reverse_list_iterative(h)) == [5, 4, 3, 2, 1]

    h = list_to_linked([1, 2, 3, 4, 5])
    assert linked_to_list(reverse_list_recursive(h)) == [5, 4, 3, 2, 1]

    h = list_to_linked([1, 2])
    assert linked_to_list(reverse_list_iterative(h)) == [2, 1]
    print("reverse_list: OK")

    # ── Reverse K Group ──
    h = list_to_linked([1, 2, 3, 4, 5])
    assert linked_to_list(reverse_k_group(h, 2)) == [2, 1, 4, 3, 5]
    h = list_to_linked([1, 2, 3, 4, 5])
    assert linked_to_list(reverse_k_group(h, 3)) == [3, 2, 1, 4, 5]
    print("reverse_k_group: OK")

    # ── Cycle Detection ──
    h = list_to_linked([3, 2, 0, -4])
    # Create cycle: tail -> node[1]
    nodes = []
    curr = h
    while curr:
        nodes.append(curr)
        curr = curr.next
    nodes[-1].next = nodes[1]  # tail -> index 1
    assert has_cycle(h) == True
    cycle_start = detect_cycle_start(h)
    assert cycle_start.val == 2
    nodes[-1].next = None  # cleanup
    assert has_cycle(list_to_linked([1, 2])) == False
    print("cycle detection: OK")

    # ── Find Middle ──
    assert find_middle(list_to_linked([1, 2, 3, 4, 5])).val == 3
    assert find_middle(list_to_linked([1, 2, 3, 4])).val == 3
    assert find_middle(list_to_linked([1])).val == 1
    print("find_middle: OK")

    # ── Merge Two Sorted Lists ──
    l1 = list_to_linked([1, 2, 4])
    l2 = list_to_linked([1, 3, 4])
    assert linked_to_list(merge_two_sorted_lists(l1, l2)) == [1, 1, 2, 3, 4, 4]
    assert merge_two_sorted_lists(None, None) is None
    print("merge_two_sorted_lists: OK")

    # ── Merge K Sorted Lists ──
    lists = [list_to_linked([1, 4, 5]), list_to_linked([1, 3, 4]), list_to_linked([2, 6])]
    assert linked_to_list(merge_k_sorted_lists(lists)) == [1, 1, 2, 3, 4, 4, 5, 6]
    assert merge_k_sorted_lists([]) is None
    print("merge_k_sorted_lists: OK")

    # ── Remove Nth from End ──
    h = list_to_linked([1, 2, 3, 4, 5])
    assert linked_to_list(remove_nth_from_end(h, 2)) == [1, 2, 3, 5]
    h = list_to_linked([1])
    assert remove_nth_from_end(h, 1) is None
    h = list_to_linked([1, 2])
    assert linked_to_list(remove_nth_from_end(h, 1)) == [1]
    print("remove_nth_from_end: OK")

    # ── LRU Cache (OrderedDict) ──
    lru = LRUCacheOrderedDict(2)
    lru.put(1, 1)
    lru.put(2, 2)
    assert lru.get(1) == 1
    lru.put(3, 3)        # evicts key 2
    assert lru.get(2) == -1
    lru.put(4, 4)        # evicts key 1
    assert lru.get(1) == -1
    assert lru.get(3) == 3
    assert lru.get(4) == 4
    print("LRUCacheOrderedDict: OK")

    # ── LRU Cache (DLL + HashMap) ──
    lru2 = LRUCache(2)
    lru2.put(1, 1)
    lru2.put(2, 2)
    assert lru2.get(1) == 1
    lru2.put(3, 3)
    assert lru2.get(2) == -1
    lru2.put(4, 4)
    assert lru2.get(1) == -1
    assert lru2.get(3) == 3
    assert lru2.get(4) == 4
    print("LRUCache (DLL): OK")

    print("\nAll tests passed!")
