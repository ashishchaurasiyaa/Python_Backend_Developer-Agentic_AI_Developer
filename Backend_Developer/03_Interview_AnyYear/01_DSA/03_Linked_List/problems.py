"""03 — Linked List — Problems | 17 problems | Easy→Hard"""
from typing import Optional
from collections import deque

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val; self.next = next

def build(vals):
    dummy = cur = ListNode(0)
    for v in vals: cur.next = ListNode(v); cur = cur.next
    return dummy.next

def to_list(head):
    r, cur = [], head
    while cur: r.append(cur.val); cur = cur.next
    return r

# P01. Reverse Linked List [Easy][LC 206]
def reverseList(head):
    prev, cur = None, head
    while cur:
        nxt = cur.next; cur.next = prev; prev = cur; cur = nxt
    return prev

print("P01:", to_list(reverseList(build([1,2,3,4,5]))))  # [5,4,3,2,1]

# P02. Merge Two Sorted Lists [Easy][LC 21]
def mergeTwoLists(l1, l2):
    dummy = cur = ListNode(0)
    while l1 and l2:
        if l1.val <= l2.val: cur.next, l1 = l1, l1.next
        else:                cur.next, l2 = l2, l2.next
        cur = cur.next
    cur.next = l1 or l2
    return dummy.next

print("P02:", to_list(mergeTwoLists(build([1,2,4]), build([1,3,4]))))

# P03. Linked List Cycle [Easy][LC 141]
def hasCycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next; fast = fast.next.next
        if slow is fast: return True
    return False

# P04. Remove Nth Node From End [Medium][LC 19]
def removeNthFromEnd(head, n):
    dummy = ListNode(0, head); fast = slow = dummy
    for _ in range(n + 1): fast = fast.next
    while fast: slow = slow.next; fast = fast.next
    slow.next = slow.next.next
    return dummy.next

print("P04:", to_list(removeNthFromEnd(build([1,2,3,4,5]), 2)))  # [1,2,3,5]

# P05. Reorder List [Medium][LC 143]
# L0→L1→…→Ln  →  L0→Ln→L1→Ln-1→…
def reorderList(head):
    if not head: return
    # Find middle
    slow = fast = head
    while fast and fast.next: slow = slow.next; fast = fast.next.next
    # Reverse second half
    prev, cur = None, slow.next; slow.next = None
    while cur: nxt = cur.next; cur.next = prev; prev = cur; cur = nxt
    # Merge
    first, second = head, prev
    while second:
        tmp1, tmp2 = first.next, second.next
        first.next = second; second.next = tmp1
        first, second = tmp1, tmp2

h = build([1,2,3,4,5]); reorderList(h)
print("P05:", to_list(h))  # [1,5,2,4,3]

# P06. Add Two Numbers [Medium][LC 2]
def addTwoNumbers(l1, l2):
    dummy = cur = ListNode(0); carry = 0
    while l1 or l2 or carry:
        val = (l1.val if l1 else 0) + (l2.val if l2 else 0) + carry
        carry, digit = divmod(val, 10)
        cur.next = ListNode(digit); cur = cur.next
        l1 = l1.next if l1 else None
        l2 = l2.next if l2 else None
    return dummy.next

print("P06:", to_list(addTwoNumbers(build([2,4,3]), build([5,6,4]))))  # [7,0,8]

# P07. Find Duplicate Number [Medium][LC 287]
# Array of n+1 integers, each in [1,n]. Find duplicate. O(n) time O(1) space.
def findDuplicate(nums):
    # Floyd's cycle detection on array (treat values as pointers)
    slow = fast = nums[0]
    while True:
        slow = nums[slow]; fast = nums[nums[fast]]
        if slow == fast: break
    slow = nums[0]
    while slow != fast:
        slow = nums[slow]; fast = nums[fast]
    return slow

print("P07:", findDuplicate([1,3,4,2,2]))  # 2

# P08. LRU Cache [Medium][LC 146]
class LRUCache:
    """Doubly linked list + hashmap → O(1) get and put."""
    class Node:
        def __init__(self, k=0, v=0): self.k=k; self.v=v; self.prev=self.next=None

    def __init__(self, capacity: int):
        self.cap = capacity
        self.cache = {}
        self.lru = self.Node()   # least recently used (left)
        self.mru = self.Node()   # most recently used (right)
        self.lru.next = self.mru; self.mru.prev = self.lru

    def _remove(self, node):
        node.prev.next = node.next; node.next.prev = node.prev

    def _insert(self, node):   # insert at MRU end
        node.prev = self.mru.prev; node.next = self.mru
        self.mru.prev.next = self.mru.prev = node

    def get(self, key: int) -> int:
        if key not in self.cache: return -1
        self._remove(self.cache[key]); self._insert(self.cache[key])
        return self.cache[key].v

    def put(self, key: int, value: int) -> None:
        if key in self.cache: self._remove(self.cache[key])
        self.cache[key] = self.Node(key, value); self._insert(self.cache[key])
        if len(self.cache) > self.cap:
            lru = self.lru.next; self._remove(lru); del self.cache[lru.k]

lru = LRUCache(2)
lru.put(1,1); lru.put(2,2); print("P08:", lru.get(1))  # 1

# P09. Palindrome Linked List [Easy][LC 234]
def isPalindrome(head):
    slow = fast = head
    while fast and fast.next: slow = slow.next; fast = fast.next.next
    # Reverse second half
    prev, cur = None, slow
    while cur: nxt=cur.next; cur.next=prev; prev=cur; cur=nxt
    # Compare
    left, right = head, prev
    while right:
        if left.val != right.val: return False
        left=left.next; right=right.next
    return True

print("P09:", isPalindrome(build([1,2,2,1])))  # True

# P10. Flatten Multilevel Doubly Linked List [Medium][LC 430]
class DNode:
    def __init__(self, val=0): self.val=val; self.prev=self.next=self.child=None

def flatten(head):
    cur = head
    while cur:
        if cur.child:
            child = cur.child; nxt = cur.next
            cur.next = child; child.prev = cur; cur.child = None
            tail = child
            while tail.next: tail = tail.next
            tail.next = nxt
            if nxt: nxt.prev = tail
        cur = cur.next
    return head

# P11. Rotate List [Medium][LC 61]
def rotateRight(head, k):
    if not head or not head.next or k == 0: return head
    length = 1; tail = head
    while tail.next: tail = tail.next; length += 1
    k %= length
    if k == 0: return head
    tail.next = head   # make circular
    steps = length - k
    new_tail = head
    for _ in range(steps - 1): new_tail = new_tail.next
    new_head = new_tail.next; new_tail.next = None
    return new_head

print("P11:", to_list(rotateRight(build([1,2,3,4,5]), 2)))  # [4,5,1,2,3]

# P12. Merge K Sorted Lists [Hard][LC 23]
import heapq
def mergeKLists(lists):
    heap = []
    for i, node in enumerate(lists):
        if node: heapq.heappush(heap, (node.val, i, node))
    dummy = cur = ListNode(0)
    while heap:
        val, i, node = heapq.heappop(heap)
        cur.next = node; cur = cur.next
        if node.next: heapq.heappush(heap, (node.next.val, i, node.next))
    return dummy.next

print("P12:", to_list(mergeKLists([build([1,4,5]),build([1,3,4]),build([2,6])])))

"""
COMPLEXITY SUMMARY:
Reverse List         O(n) O(1)  iterative 3-pointer
Merge Sorted         O(n+m) O(1)  dummy + pointer
Has Cycle            O(n) O(1)  Floyd's 2-pointer
Remove Nth from End  O(n) O(1)  2-pointer gap
Reorder List         O(n) O(1)  middle + reverse + merge
Add Two Numbers      O(n) O(1)  carry simulation
Find Duplicate       O(n) O(1)  Floyd's on array
LRU Cache            O(1) O(n)  DLL + HashMap
Palindrome LL        O(n) O(1)  slow/fast + reverse half
Rotate List          O(n) O(1)  circular trick
Merge K Sorted       O(n log k) O(k) min-heap
"""

# P13. Swap Nodes in Pairs [Medium][LC 24]
def swapPairs(head):
    dummy = ListNode(0, head)
    prev = dummy
    while prev.next and prev.next.next:
        first, second = prev.next, prev.next.next
        first.next = second.next
        second.next = first
        prev.next = second
        prev = first
    return dummy.next

print("P13:", to_list(swapPairs(build([1,2,3,4]))))  # [2,1,4,3]

# P14. Reverse Nodes in k-Group [Hard][LC 25]
def reverseKGroup(head, k):
    # Check there are at least k nodes left to reverse
    node = head; count = 0
    while node and count < k:
        node = node.next; count += 1
    if count < k:
        return head
    # Reverse the first k nodes
    prev, cur = None, head
    for _ in range(k):
        nxt = cur.next; cur.next = prev; prev = cur; cur = nxt
    # `head` is now the tail of this reversed group; connect it to the
    # (recursively reversed) remainder of the list, which starts at `cur`
    head.next = reverseKGroup(cur, k)
    return prev

print("P14:", to_list(reverseKGroup(build([1,2,3,4,5]), 2)))  # [2,1,4,3,5]

# P15. Copy List with Random Pointer [Medium][LC 138]
class RandomNode:
    def __init__(self, val=0, next=None, random=None):
        self.val = val; self.next = next; self.random = random

def copyRandomList(head):
    if not head: return None
    # Pass 1: interleave copies: orig1 -> copy1 -> orig2 -> copy2 -> ...
    cur = head
    while cur:
        copy = RandomNode(cur.val)
        copy.next = cur.next
        cur.next = copy
        cur = copy.next
    # Pass 2: set random pointers on the copies using the interleaving
    cur = head
    while cur:
        if cur.random:
            cur.next.random = cur.random.next
        cur = cur.next.next
    # Pass 3: unweave — split interleaved list back into original + copy
    cur = head
    dummy = copy_cur = RandomNode(0)
    while cur:
        copy_cur.next = cur.next
        cur.next = cur.next.next
        cur = cur.next
        copy_cur = copy_cur.next
    return dummy.next

n1, n2, n3 = RandomNode(1), RandomNode(2), RandomNode(3)
n1.next, n2.next = n2, n3
n1.random, n2.random = n3, n2   # node1.random -> node3, node2.random -> node2
copied = copyRandomList(n1)
vals, c = [], copied
while c: vals.append((c.val, c.random.val if c.random else None)); c = c.next
print("P15:", vals)  # [(1, 3), (2, 2), (3, None)]

# P16. Odd Even Linked List [Medium][LC 328]
def oddEvenList(head):
    if not head or not head.next: return head
    odd, even = head, head.next
    even_head = even
    while even and even.next:
        odd.next = even.next
        odd = odd.next
        even.next = odd.next
        even = even.next
    odd.next = even_head
    return head

print("P16:", to_list(oddEvenList(build([1,2,3,4,5]))))  # [1,3,5,2,4]

# P17. Middle of the Linked List [Easy][LC 876]
def middleNode(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next; fast = fast.next.next
    return slow

print("P17:", to_list(middleNode(build([1,2,3,4,5]))))  # [3,4,5]
